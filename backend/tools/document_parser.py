"""
Upstage Document Parse 연동
parse_document(file_or_url) -> {text, sections, raw}
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import mimetypes
import os
import subprocess

import requests

from backend.config import (
    UPSTAGE_API_KEY,
    UPSTAGE_EFFECTIVE_API_KEY,
    UPSTAGE_DOCUMENT_PARSE_BASE64_ENCODING,
    UPSTAGE_DOCUMENT_PARSE_MODEL,
    UPSTAGE_DOCUMENT_PARSE_OCR,
    UPSTAGE_DOCUMENT_PARSE_URL,
)

DEFAULT_TIMEOUT = 60


class UpstageDocumentParseError(RuntimeError):
    """Upstage Document Parse 호출 오류"""


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _guess_filename(file_or_url: str, content_type: str = "") -> str:
    path_name = Path(urlparse(file_or_url).path).name if _is_url(file_or_url) else Path(file_or_url).name
    if path_name:
        return path_name

    if content_type:
        guessed_ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
        return f"document{guessed_ext}"

    return "document.bin"


def _download_document(url: str) -> tuple[bytes, str, str]:
    response = requests.get(url, timeout=DEFAULT_TIMEOUT)
    if response.status_code != 200:
        raise UpstageDocumentParseError(
            f"문서 다운로드 실패(status={response.status_code}): {url}"
        )

    content_type = response.headers.get("Content-Type", "")
    filename = _guess_filename(url, content_type)
    return response.content, filename, content_type


def _read_local_document(file_path: str) -> tuple[bytes, str, str]:
    path = Path(file_path)
    if not path.exists():
        raise UpstageDocumentParseError(f"문서 파일을 찾을 수 없습니다: {file_path}")
    if not path.is_file():
        raise UpstageDocumentParseError(f"문서 경로가 파일이 아닙니다: {file_path}")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return path.read_bytes(), path.name, content_type


def _load_document_bytes(file_or_url: str) -> tuple[bytes, str, str]:
    if _is_url(file_or_url):
        return _download_document(file_or_url)
    return _read_local_document(file_or_url)


def _extract_pdf_text_fallback(file_path: str) -> str:
    """UPSTAGE_API_KEY가 없을 때 쓰는 매우 단순한 PDF 텍스트 추출 폴백."""
    try:
        completed = subprocess.run(
            ["/usr/bin/strings", "-n", "6", file_path],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = []
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            if len(stripped) < 6:
                continue
            lines.append(stripped)
        return "\n".join(lines[:5000])
    except Exception as exc:
        raise UpstageDocumentParseError(f"PDF 폴백 텍스트 추출 실패: {exc}") from exc


def _call_upstage_document_parse(document_bytes: bytes, filename: str, content_type: str) -> Dict[str, Any]:
    if not UPSTAGE_EFFECTIVE_API_KEY:
        raise UpstageDocumentParseError("Document Parse용 API 키가 설정되지 않았습니다.")

    headers = {"Authorization": f"Bearer {UPSTAGE_EFFECTIVE_API_KEY}"}
    files = {
        "document": (
            filename,
            document_bytes,
            content_type or "application/octet-stream",
        )
    }
    data = {
        "model": UPSTAGE_DOCUMENT_PARSE_MODEL,
        "ocr": UPSTAGE_DOCUMENT_PARSE_OCR,
        "base64_encoding": UPSTAGE_DOCUMENT_PARSE_BASE64_ENCODING,
    }

    response = requests.post(
        UPSTAGE_DOCUMENT_PARSE_URL,
        headers=headers,
        files=files,
        data=data,
        timeout=DEFAULT_TIMEOUT,
    )

    try:
        payload = response.json()
    except ValueError as exc:
        raise UpstageDocumentParseError(
            f"Document Parse 응답 파싱 실패(status={response.status_code}): {response.text[:500]}"
        ) from exc

    if response.status_code != 200:
        raise UpstageDocumentParseError(
            f"Document Parse 오류(status={response.status_code}): {payload}"
        )

    return payload


def _extract_text(payload: Dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, dict):
        markdown = content.get("markdown")
        if isinstance(markdown, str) and markdown.strip():
            return markdown

        html = content.get("html")
        if isinstance(html, str) and html.strip():
            return html

        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text

    if isinstance(payload.get("text"), str):
        return payload["text"]

    pages = payload.get("pages")
    if isinstance(pages, list):
        texts: List[str] = []
        for page in pages:
            if isinstance(page, dict):
                page_text = page.get("markdown") or page.get("text") or page.get("html")
                if isinstance(page_text, str) and page_text.strip():
                    texts.append(page_text)
        if texts:
            return "\n\n".join(texts)

    return ""


def _extract_sections(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    elements = payload.get("elements")
    if isinstance(elements, list):
        for index, element in enumerate(elements, start=1):
            if not isinstance(element, dict):
                continue
            text = element.get("content") or element.get("text") or element.get("markdown") or ""
            if not isinstance(text, str) or not text.strip():
                continue
            sections.append(
                {
                    "title": element.get("category") or f"element_{index}",
                    "content": text.strip(),
                    "page": element.get("page"),
                }
            )

    if sections:
        return sections

    pages = payload.get("pages")
    if isinstance(pages, list):
        for index, page in enumerate(pages, start=1):
            if not isinstance(page, dict):
                continue
            page_text = page.get("markdown") or page.get("text") or page.get("html") or ""
            if isinstance(page_text, str) and page_text.strip():
                sections.append(
                    {
                        "title": f"page_{index}",
                        "content": page_text.strip(),
                        "page": page.get("id") or index,
                    }
                )

    return sections


def parse_document(file_path: str) -> Dict[str, Any]:
    """주어진 파일 경로 또는 URL 문서를 Upstage Document Parse로 파싱한다."""
    local_path = Path(file_path) if not _is_url(file_path) else None
    # SOLAR_API_KEY만 있어도 Document Parse를 호출할 수 있으므로
    # 실제 유효 키(UPSTAGE_EFFECTIVE_API_KEY) 기준으로 폴백 여부를 판단한다.
    if local_path and local_path.suffix.lower() == ".pdf" and not UPSTAGE_EFFECTIVE_API_KEY:
        text = _extract_pdf_text_fallback(file_path)
        sections = [{"title": "document_body", "content": text.strip(), "page": 1}] if text.strip() else []
        return {
            "text": text,
            "sections": sections,
            "raw": {"fallback": True},
            "source": file_path,
            "filename": local_path.name,
            "parse_method": "fallback_strings_extract",
        }

    document_bytes, filename, content_type = _load_document_bytes(file_path)
    payload = _call_upstage_document_parse(document_bytes, filename, content_type)
    text = _extract_text(payload)
    sections = _extract_sections(payload)
    if not sections and text.strip():
        sections = [{"title": "document_body", "content": text.strip(), "page": 1}]

    return {
        "text": text,
        "sections": sections,
        "raw": payload,
        "source": file_path,
        "filename": filename,
        "parse_method": "upstage_document_parse",
    }


def test_parse_document(file_or_url: str) -> Dict[str, Any]:
    """실제 Document Parse 연결 확인용 작은 테스트 함수."""
    result = parse_document(file_or_url)
    return {
        "source": result["source"],
        "filename": result["filename"],
        "text_preview": result["text"][:1000],
        "section_count": len(result["sections"]),
        "first_section": result["sections"][0] if result["sections"] else None,
        "raw_keys": sorted(result["raw"].keys()),
    }
