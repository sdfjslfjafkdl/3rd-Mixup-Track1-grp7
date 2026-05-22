"""
DocumentAgent
- 공고 첨부 PDF 파싱 / 메타데이터 fallback / 파싱 결과 캐시
"""
from typing import Dict, Any, Optional, Callable
from backend.tools.document_parser import parse_document


class DocumentAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool
        # 같은 문서를 반복 파싱하지 않도록 간단 캐시 유지
        self.cache: Dict[str, Dict[str, Any]] = {}

    def reset_cache(self) -> None:
        """orchestrator 가 새 run을 시작할 때 캐시 초기화"""
        self.cache = {}

    def _build_metadata_only_doc(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """PDF 미업로드 시 공고 메타데이터만으로 최소 문서 컨텍스트를 만든다."""
        text = (
            f"공고명: {candidate.get('title', '')}\n"
            f"발주기관: {candidate.get('agency', '')}\n"
            f"사업구분: {candidate.get('businessType', '')}\n"
            f"마감일: {candidate.get('deadline', '')}\n"
            f"예산: {candidate.get('estimatedAmount') or candidate.get('budget') or ''}\n"
            f"공고번호: {candidate.get('bidNoticeNo', '')}\n"
        )
        return {
            "text": text,
            "sections": [{"title": "bid_metadata", "content": text, "page": 1}],
            "raw": {"metadata_only": True},
            "source": "metadata_only",
            "filename": None,
            "parse_method": "metadata_only",
        }

    def parse_initial(
        self,
        candidate: Dict[str, Any],
        uploaded_doc_path: Optional[str],
        use_metadata_only: bool,
    ) -> Dict[str, Any]:
        """루프 첫 진입 시 문서 컨텍스트 확보"""
        if uploaded_doc_path:
            self.record_tool("parse_document")
            self.log(f"PDF 기반 작성: 업로드 문서 파싱 호출 - {uploaded_doc_path}")
            if uploaded_doc_path in self.cache:
                doc = self.cache[uploaded_doc_path]
                self.log("업로드 PDF 캐시 적중: 기존 파싱 결과 재사용")
            else:
                doc = parse_document(uploaded_doc_path)
                self.cache[uploaded_doc_path] = doc
            self.log(f"문서 파서 모드: {doc.get('parse_method')}")
            return doc

        if use_metadata_only:
            self.record_tool("metadata_mode")
            self.log("메타데이터 기반 자동 작성: 업로드 PDF 없이 공고 메타데이터만 사용")
            return self._build_metadata_only_doc(candidate)

        # 기본 호환 경로. 현재 프론트에서는 PDF 미업로드 시 metadata_only를 사용한다.
        self.record_tool("parse_document")
        self.log(f"문서 파싱 호출 (parse_document) - {candidate.get('doc')}")
        doc_source = candidate.get("doc")
        if doc_source in self.cache:
            doc = self.cache[doc_source]
            self.log("문서 캐시 적중: 기존 파싱 결과 재사용")
        else:
            doc = parse_document(doc_source)
            if doc_source:
                self.cache[doc_source] = doc
        return doc

    def parse_retry(
        self,
        candidate: Dict[str, Any],
        uploaded_doc_path: Optional[str],
        use_metadata_only: bool,
    ) -> Dict[str, Any]:
        """루프 재시도 시 추가 문서 수집"""
        if uploaded_doc_path:
            if uploaded_doc_path in self.cache:
                self.log("추가 업로드 PDF 파싱 생략: 캐시된 결과 재사용")
                return self.cache[uploaded_doc_path]
            self.record_tool("parse_document")
            self.log("추가 업로드 PDF 파싱 시도")
            doc = parse_document(uploaded_doc_path)
            self.cache[uploaded_doc_path] = doc
            return doc

        if use_metadata_only:
            self.log("추가 문서 파싱 생략: 메타데이터 기반 자동 작성 유지")
            return self._build_metadata_only_doc(candidate)

        doc_source = candidate.get("doc")
        if doc_source in self.cache:
            self.log("추가 문서 파싱 생략: 캐시된 결과 재사용")
            return self.cache[doc_source]
        self.record_tool("parse_document")
        self.log("추가 문서 파싱 시도")
        doc = parse_document(doc_source)
        if doc_source:
            self.cache[doc_source] = doc
        return doc
