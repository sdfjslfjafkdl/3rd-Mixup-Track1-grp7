"""
Requirement Extractor
공고 원문과 파싱된 문서에서 일정/예산/제출서류/핵심 요구사항을 추출한다.
"""
from __future__ import annotations

from html import unescape
import re
from typing import Any, Dict, List


# 요구사항으로 볼 가능성이 높은 키워드들.
# 해커톤 MVP 기준이라 규칙을 단순하게 유지한다.
REQUIREMENT_KEYWORDS = (
    "자격",
    "경험",
    "실적",
    "인증",
    "보유",
    "가능",
    "참가",
    "제출",
    "평가",
    "심사",
    "면허",
    "등록",
)

SECTION_HINTS = (
    "입찰참가자격",
    "참가자격",
    "제출서류",
    "평가기준",
    "낙찰자 결정",
    "낙찰자결정",
    "유의사항",
)

MAJOR_SECTION_PATTERN = re.compile(r"^\d+([.-]\d+)?\.")
ITEM_START_PATTERN = re.compile(r"^([0-9]+[)\.]|[①-⑨]|[-*])")
CIRCLED_ITEM_PATTERN = re.compile(r"(?=[①②③④⑤⑥⑦⑧⑨])")
LONG_SENTENCE_SPLIT_PATTERN = re.compile(r"\s(?=(가\.|나\.|다\.|라\.|마\.|바\.|사\.|아\.|자\.|차\.))")
NOISE_MARKERS = (
    "제안서 작성 요령",
    "작성지침",
    "작성서식",
    "주의사항",
    "문의처",
    "표지 및 본문 작성요령",
    "제안서(예시)",
    "입찰참가신청서",
    "입찰서",
    "청렴계약이행 서약서",
    "서 약 서",
)


def _html_to_text(value: str) -> str:
    """Document Parse markdown/html을 줄 단위 텍스트로 단순 정리한다."""
    normalized = value.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    normalized = re.sub(r"</(p|div|h1|h2|h3|li|tr|table|section|footer)>", "\n", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = unescape(normalized)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    return normalized.strip()


def _normalize_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"\s+", " ", line)
    return line


def _condense_requirement_text(text: str, max_length: int = 120) -> str:
    normalized = _normalize_line(text)
    if not normalized:
        return ""

    for marker in NOISE_MARKERS:
        marker_index = normalized.find(marker)
        if marker_index > 0:
            normalized = normalized[:marker_index].strip()
            break

    normalized = LONG_SENTENCE_SPLIT_PATTERN.split(normalized, maxsplit=1)[0].strip()
    normalized = re.split(r"\s(?=※|\(|- \d+ -|[IVX]+\.)", normalized, maxsplit=1)[0].strip()
    normalized = re.sub(r"\s{2,}", " ", normalized).strip(" -,:;")

    if len(normalized) > max_length:
        normalized = normalized[:max_length].rstrip(" ,.;:") + "..."
    return normalized


def _is_noisy_requirement(text: str) -> bool:
    normalized = _normalize_line(text)
    if len(normalized) > 220:
        return True
    if sum(1 for marker in NOISE_MARKERS if marker in normalized) >= 1:
        return True
    return False


def _merge_wrapped_lines(lines: List[str]) -> List[str]:
    """PDF 줄바꿈으로 잘린 문장을 하나의 항목으로 최대한 합친다."""
    merged: List[str] = []

    for raw_line in lines:
        line = _normalize_line(raw_line)
        if not line:
            continue

        if not merged:
            merged.append(line)
            continue

        if ITEM_START_PATTERN.match(line) or MAJOR_SECTION_PATTERN.match(line):
            merged.append(line)
            continue

        merged[-1] = f"{merged[-1]} {line}"

    return merged


def _extract_text_block(text: str, start_markers: tuple[str, ...], end_markers: tuple[str, ...]) -> str:
    """본문에서 특정 섹션 구간만 잘라낸다."""
    for marker in start_markers:
        idx = text.find(marker)
        if idx == -1:
            continue

        block = text[idx:]
        end_index = len(block)
        for end_marker in end_markers:
            end_idx = block.find(end_marker)
            if end_idx > 0:
                end_index = min(end_index, end_idx)

        return block[:end_index].strip()

    return ""


def _split_circled_items(block_text: str) -> List[str]:
    """① ② ③ 형태 항목을 개별 문장으로 분리한다."""
    if not block_text:
        return []

    pieces = []
    for chunk in CIRCLED_ITEM_PATTERN.split(block_text):
        normalized = _normalize_line(chunk)
        if not normalized:
            continue
        if normalized[0] not in "①②③④⑤⑥⑦⑧⑨":
            continue
        # 다음 숫자 소항목이 이어지면 너무 긴 문장이 되므로 앞부분만 우선 사용한다.
        trimmed = re.split(r"\s(?=1\)|2\)|3\)|4\))", normalized, maxsplit=1)[0]
        pieces.append(trimmed)
    return pieces


def _extract_money(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    return re.sub(r"[^\d]", "", match.group(1))


def _extract_schedule(text: str, bid: Dict[str, Any]) -> Dict[str, str]:
    schedule: Dict[str, str] = {}

    raw = bid.get("raw") or {}
    if raw.get("bidBeginDt"):
        schedule["bid_begin"] = raw["bidBeginDt"]
    if raw.get("bidClseDt"):
        schedule["bid_close"] = raw["bidClseDt"]
    if raw.get("opengDt"):
        schedule["bid_open"] = raw["opengDt"]

    start_match = re.search(
        r"(입찰개시일시|개찰일시|전자입찰서 제출 시작일시)\s*[:：]?\s*([0-9]{4}[.\-]\s*[0-9]{1,2}[.\-]\s*[0-9]{1,2}\.?\s*[0-9]{0,2}[:시]\s*[0-9]{0,2})",
        text,
        flags=re.IGNORECASE,
    )
    end_match = re.search(
        r"(입찰마감일시|전자입찰서 제출 마감일시|마감일시)\s*[:：]?\s*([0-9]{4}[.\-]\s*[0-9]{1,2}[.\-]\s*[0-9]{1,2}\.?\s*[0-9]{0,2}[:시]\s*[0-9]{0,2})",
        text,
        flags=re.IGNORECASE,
    )

    if start_match and "bid_begin" not in schedule:
        schedule["bid_begin"] = _normalize_line(start_match.group(2))
    if end_match and "bid_close" not in schedule:
        schedule["bid_close"] = _normalize_line(end_match.group(2))

    return schedule


def _collect_section_lines(lines: List[str], heading_keywords: tuple[str, ...], max_lines: int = 8) -> List[str]:
    """지정한 제목 주변의 줄만 잘라서 추출한다."""
    for index, line in enumerate(lines):
        normalized = _normalize_line(line)
        if any(keyword in normalized for keyword in heading_keywords):
            collected: List[str] = []
            for candidate in lines[index + 1:index + 1 + max_lines]:
                candidate = _normalize_line(candidate)
                if not candidate:
                    continue
                if MAJOR_SECTION_PATTERN.match(candidate):
                    break
                collected.append(candidate)
            return _merge_wrapped_lines(collected)
    return []


def _extract_submission_docs(lines: List[str]) -> List[str]:
    results: List[str] = []
    targeted_lines = _collect_section_lines(lines, ("제출서류", "적격심사 서류", "증빙자료"), max_lines=10)
    if targeted_lines:
        for item in targeted_lines:
            if any(keyword in item for keyword in ("제출", "서류", "증빙", "계획서", "확약서")):
                results.append(item)

    unique_results: List[str] = []
    seen = set()
    for item in results:
        if item not in seen:
            seen.add(item)
            unique_results.append(item)
    return unique_results[:8]


def _infer_requirement_type(text: str) -> str:
    if any(keyword in text for keyword in ("인증", "면허", "등록")):
        return "인증"
    if any(keyword in text for keyword in ("실적", "경험")):
        return "실적"
    if any(keyword in text for keyword in ("제출", "서류")):
        return "제출서류"
    if any(keyword in text for keyword in ("평가", "심사")):
        return "평가"
    return "기술"


def _infer_weight(text: str) -> int:
    if any(keyword in text for keyword in ("필수", "반드시", "자격", "면허", "등록")):
        return 25
    if any(keyword in text for keyword in ("평가", "심사", "실적", "경험")):
        return 20
    if any(keyword in text for keyword in ("제출", "서류")):
        return 10
    return 15


def _extract_requirement_lines(lines: List[str]) -> List[Dict[str, Any]]:
    requirements: List[Dict[str, Any]] = []
    seen_texts = set()
    focused_lines: List[str] = []

    for section_lines in (
        _collect_section_lines(lines, ("입찰참가자격", "참가자격"), max_lines=14),
        _collect_section_lines(lines, ("평가기준", "적격심사", "안전보건수준평가"), max_lines=14),
    ):
        focused_lines.extend(section_lines)

    # 관련 제목 주변에서 먼저 찾고, 그래도 부족하면 전체 문서로 확장한다.
    source_lines = focused_lines or lines

    for index, line in enumerate(source_lines, start=1):
        normalized = _normalize_line(line)
        if len(normalized) < 6:
            continue
        if not any(keyword in normalized for keyword in REQUIREMENT_KEYWORDS):
            continue
        if any(noise in normalized for noise in ("콜센터", "연락처", "홈페이지", "방문 또는 우편")):
            continue
        if _is_noisy_requirement(normalized):
            continue
        if normalized in seen_texts:
            continue

        seen_texts.add(normalized)
        requirements.append(
            {
                "id": f"doc_req_{index}",
                "text": _condense_requirement_text(normalized),
                "type": _infer_requirement_type(normalized),
                "weight": _infer_weight(normalized),
                "source": "document",
            }
        )

    return requirements[:12]


def _build_requirement(requirement_id: str, text: str) -> Dict[str, Any]:
    normalized = _condense_requirement_text(text)
    return {
        "id": requirement_id,
        "text": normalized,
        "type": _infer_requirement_type(normalized),
        "weight": _infer_weight(normalized),
        "source": "document",
    }


def _extract_structured_requirements(plain_text: str) -> List[Dict[str, Any]]:
    """입찰참가자격/평가기준 구간에서 핵심 항목을 우선 추출한다."""
    requirements: List[Dict[str, Any]] = []

    qualification_block = _extract_text_block(
        plain_text,
        start_markers=("2. 입찰참가자격", "입찰참가자격"),
        end_markers=("3. 공동계약", "4. 낙찰자 결정방법", "4. 낙찰자 결정"),
    )
    evaluation_block = _extract_text_block(
        plain_text,
        start_markers=("4. 낙찰자 결정방법", "낙찰자 결정방법"),
        end_markers=("5. 입찰보증금", "5. 입찰의 무효", "4-1. 안전보건수준평가"),
    )
    safety_block = _extract_text_block(
        plain_text,
        start_markers=("4-1. 안전보건수준평가", "안전보건수준평가"),
        end_markers=("5. 입찰보증금", "5. 입찰의 무효"),
    )

    seen = set()

    for index, item in enumerate(_split_circled_items(qualification_block), start=1):
        if any(noise in item for noise in ("콜센터", "연락처", "문의사항", "입찰 및 계약에 관한 사항", "설계서 열람 등 용역에 관한 사항")):
            continue
        if len(item) < 12:
            continue
        if _is_noisy_requirement(item):
            continue
        if item in seen:
            continue
        seen.add(item)
        requirements.append(_build_requirement(f"qualification_{index}", item))

    evaluation_lines = _merge_wrapped_lines(evaluation_block.splitlines())
    for index, line in enumerate(evaluation_lines, start=1):
        normalized = _normalize_line(line)
        if not normalized:
            continue
        if not any(keyword in normalized for keyword in ("평가기준", "적격심사", "95점", "낙찰하한율", "실적", "제출")):
            continue
        if _is_noisy_requirement(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        requirements.append(_build_requirement(f"evaluation_{index}", normalized))

    safety_lines = _merge_wrapped_lines(safety_block.splitlines())
    for index, line in enumerate(safety_lines, start=1):
        normalized = _normalize_line(line)
        if not normalized:
            continue
        if not any(keyword in normalized for keyword in ("안전보건", "계획서", "증빙자료", "60점", "제출")):
            continue
        if _is_noisy_requirement(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        requirements.append(_build_requirement(f"safety_{index}", normalized))

    return requirements[:12]


def _extract_summary(text: str, lines: List[str]) -> Dict[str, Any]:
    summary = {
        "estimated_amount": _extract_money(r"추\s*정\s*금\s*액\s*[:：]?\s*금?\s*([0-9,]+)원", text),
        "estimated_price": _extract_money(r"추\s*정\s*가\s*격\s*[:：]?\s*금?\s*([0-9,]+)원", text),
        "vat": _extract_money(r"부가가치세\s*[:：]?\s*금?\s*([0-9,]+)원", text),
        "schedule": {},
        "submission_docs": _extract_submission_docs(lines),
    }
    return summary


def extract_requirements_from_doc(bid: dict, doc: dict) -> List[Dict[str, Any]]:
    """문서 본문에서 요구사항과 핵심 메타데이터를 추출한다.

    반환값은 기존 파이프라인 호환을 위해 requirements 리스트를 유지한다.
    또한 downstream이 바로 사용할 수 있도록 bid 딕셔너리에 추출 메타데이터를 보강한다.
    """
    doc_text = doc.get("text", "") or ""
    plain_text = _html_to_text(doc_text)
    lines = [line for line in plain_text.splitlines() if _normalize_line(line)]

    extracted_requirements = _extract_structured_requirements(plain_text)
    if not extracted_requirements:
        extracted_requirements = _extract_requirement_lines(lines)
    extracted_summary = _extract_summary(plain_text, lines)
    extracted_summary["schedule"] = _extract_schedule(plain_text, bid)

    # 실문서에서 아무것도 못 찾은 경우에만 기존 mock requirements를 폴백으로 사용한다.
    if not extracted_requirements:
        for item in bid.get("requirements", []):
            fallback = item.copy()
            fallback["source"] = fallback.get("source", "mock")
            extracted_requirements.append(fallback)

    if extracted_summary["submission_docs"]:
        extracted_requirements.append(
            {
                "id": "doc_submission_docs",
                "text": _condense_requirement_text(" / ".join(extracted_summary["submission_docs"]), max_length=140),
                "type": "제출서류",
                "weight": 10,
                "source": "document",
            }
        )

    # 후속 단계에서 바로 사용할 수 있게 bid에 추출 메타데이터를 주입한다.
    bid["requirements"] = extracted_requirements
    bid["document_summary"] = extracted_summary
    if extracted_summary.get("estimated_amount"):
        bid["estimatedAmount"] = extracted_summary["estimated_amount"]
        bid["budget"] = extracted_summary["estimated_amount"]
    schedule = extracted_summary.get("schedule", {})
    if schedule.get("bid_close"):
        bid["deadline"] = schedule["bid_close"]

    return extracted_requirements
