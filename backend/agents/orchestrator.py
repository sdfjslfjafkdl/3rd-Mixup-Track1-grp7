"""
Orchestrator Agent (간단 구현)
- 목표: 공고 선택→요건추출→회사매칭→자격판단→제안서 생성→RedTeam 평가
- 로그를 단계별로 쌓아 반환
"""
from typing import List, Dict, Any, Callable, Optional
import time
from pathlib import Path

# 로컬 툴 임포트
from backend.tools.search_bids import search_bids
from backend.tools.document_parser import parse_document
from backend.tools.company_rag import search_company_profile
from backend.tools.requirement_extractor import extract_requirements_from_doc
from backend.tools.matching import match_requirements
from backend.tools.assess_eligibility import assess_eligibility
from backend.tools.proposal_generator import generate_proposal, revise_proposal
from backend.tools.evaluator import evaluate_proposal
from backend.services.file_generator import generate_docx, generate_xlsx


class Orchestrator:
    def __init__(self, on_log: Callable[[str], None] = None):
        self.logs: List[str] = []
        self.on_log = on_log
        # 호출된 툴 이력
        self.tool_calls: List[Dict[str, Any]] = []
        # 같은 문서를 반복 파싱하지 않도록 간단 캐시 유지
        self.document_cache: Dict[str, Dict[str, Any]] = {}

    def log(self, message: str):
        ts = time.strftime('%H:%M:%S')
        entry = f"[{ts}] {message}"
        self.logs.append(entry)
        if self.on_log:
            self.on_log(entry)
        print(entry)

    def _record_tool_call(self, tool_name: str):
        """툴 호출 이력 기록"""
        self.tool_calls.append({"tool": tool_name, "ts": time.time()})

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

    def run_by_search(
        self,
        keyword: str = None,
        business_type: str = None,
        company_id: str = None,
        uploaded_doc_path: Optional[str] = None,
        use_metadata_only: bool = False,
        company_profile_override: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """검색 조건으로 Orchestrator 흐름 실행 (정보 충분성 체크 및 재시도 루프 포함)

        Returns:
            dict: {logs, candidate, assessment, proposal, evaluation, tool_calls}
        """
        # 초기화
        self.logs = []
        self.tool_calls = []
        self.document_cache = {}
        self.log("Orchestrator 시작: 검색 기준 수집")

        # Phase 1: search bids
        self._record_tool_call("search_bids")
        self.log("Phase 1: 공고 검색 호출 (search_bids)")
        bids = search_bids(keyword=keyword, business_type=business_type)
        self.log(f"수집된 공고 수: {len(bids)}")

        if len(bids) == 0:
            self.log("공고가 없습니다. 종료")
            return {"logs": self.logs, "tool_calls": self.tool_calls}

        candidate = bids[0]
        self.log(f"선택된 공고: {candidate.get('id')} - {candidate.get('title')}")

        # 루프: 정보 충분성 판단 후 필요 시 재호출 (최대 재시도)
        max_retries = 2
        attempt = 0
        assessment = None
        profile = None
        doc = None

        while attempt <= max_retries:
            attempt += 1
            self.log(f"루프 시도 {attempt}/{max_retries + 1}")

            if uploaded_doc_path:
                self._record_tool_call("parse_document")
                self.log(f"PDF 기반 작성: 업로드 문서 파싱 호출 - {uploaded_doc_path}")
                doc_source = uploaded_doc_path
                if doc_source in self.document_cache:
                    doc = self.document_cache[doc_source]
                    self.log("업로드 PDF 캐시 적중: 기존 파싱 결과 재사용")
                else:
                    doc = parse_document(doc_source)
                    self.document_cache[doc_source] = doc
                self.log(f"문서 파서 모드: {doc.get('parse_method')}")
            elif use_metadata_only:
                self._record_tool_call("metadata_mode")
                self.log("메타데이터 기반 자동 작성: 업로드 PDF 없이 공고 메타데이터만 사용")
                doc = self._build_metadata_only_doc(candidate)
                doc_source = "metadata_only"
            else:
                # 기본 호환 경로. 현재 프론트에서는 PDF 미업로드 시 metadata_only를 사용한다.
                self._record_tool_call("parse_document")
                self.log(f"문서 파싱 호출 (parse_document) - {candidate.get('doc')}")
                doc_source = candidate.get("doc")
                if doc_source in self.document_cache:
                    doc = self.document_cache[doc_source]
                    self.log("문서 캐시 적중: 기존 파싱 결과 재사용")
                else:
                    doc = parse_document(doc_source)
                    if doc_source:
                        self.document_cache[doc_source] = doc
            self.log(f"문서 요약: {doc.get('text')}")

            # 회사 정보 조회
            self._record_tool_call("search_company_profile")
            self.log("회사 정보 조회 호출 (search_company_profile)")
            profile = search_company_profile(
                company_id=company_id,
                company_profile_override=company_profile_override
            )
            self.log(f"회사: {profile.get('name')} (스킬: {', '.join(profile.get('skills', []))})")

            # 요건 추출
            self._record_tool_call("extract_requirements")
            self.log("요구사항 추출 호출 (extract_requirements)")
            requirements = extract_requirements_from_doc(candidate, doc)
            candidate["requirements"] = requirements
            self.log(f"추출된 요구사항 수: {len(requirements)}")
            if candidate.get("document_summary"):
                summary = candidate["document_summary"]
                self.log(
                    "문서 추출 요약: "
                    f"예산={summary.get('estimated_amount') or '-'}, "
                    f"제출서류={len(summary.get('submission_docs', []))}건"
                )

            # 매칭 및 스코어링
            self._record_tool_call("match_requirements")
            self.log("요구사항 매칭 호출 (match_requirements)")
            match_result = match_requirements(requirements, profile)
            self.log(f"전체 적합도: {match_result.get('overall_score')} - WinProb: {match_result.get('win_probability')}%")

            # 자격 판단 (기존 규칙 기반) - 보완적으로 사용
            self._record_tool_call("assess_eligibility")
            self.log("자격 판단 호출 (assess_eligibility)")
            assessment = assess_eligibility(candidate, profile)
            self.log(f"자격 매칭점수: {assessment.get('match_score')}% - 충족: {assessment.get('eligible')}")

            # 충분성 판단: eligible 이거나 매칭 세부 정보가 충분하면 종료
            missing_reqs = [d for d in assessment.get('details', []) if d.get('status') == 'missing']
            if assessment.get('eligible') and len(missing_reqs) == 0:
                self.log("정보 충분: 자격 충족 판단 완료")
                break

            # 아니라면 재시도 전략: 문서/프로필 재수집 혹은 추가 툴 호출
            if attempt <= max_retries:
                self.log("정보 부족: 추가 데이터 수집 시도")
                if uploaded_doc_path:
                    if uploaded_doc_path in self.document_cache:
                        self.log("추가 업로드 PDF 파싱 생략: 캐시된 결과 재사용")
                        doc = self.document_cache[uploaded_doc_path]
                    else:
                        self._record_tool_call("parse_document")
                        self.log("추가 업로드 PDF 파싱 시도")
                        doc = parse_document(uploaded_doc_path)
                        self.document_cache[uploaded_doc_path] = doc
                elif use_metadata_only:
                    self.log("추가 문서 파싱 생략: 메타데이터 기반 자동 작성 유지")
                    doc = self._build_metadata_only_doc(candidate)
                elif candidate.get("doc") in self.document_cache:
                    self.log("추가 문서 파싱 생략: 캐시된 결과 재사용")
                    doc = self.document_cache[candidate.get("doc")]
                else:
                    self._record_tool_call("parse_document")
                    self.log("추가 문서 파싱 시도")
                    doc = parse_document(candidate.get('doc'))
                    if candidate.get("doc"):
                        self.document_cache[candidate.get("doc")] = doc

                self._record_tool_call("search_company_profile")
                self.log("추가 회사 정보 조회 시도")
                profile = search_company_profile(
                    company_id=company_id,
                    company_profile_override=company_profile_override
                )
                # 루프가 다시 돌아가면서 reassess
            else:
                self.log("최대 재시도 도달: 루프 종료")
                break

        # 제안서 생성
        self._record_tool_call("generate_proposal")
        self.log("제안서 생성 호출 (generate_proposal)")
        proposal = generate_proposal(candidate, profile)
        self.log("제안서 초안 생성 완료")

        # Red Team 평가
        self._record_tool_call("evaluate_proposal")
        self.log("Red Team 평가 호출 (evaluate_proposal)")
        evaluation = evaluate_proposal(proposal.get('draft_text'), candidate, profile, match_result=match_result, assessment=assessment)
        self.log(f"리스크 스코어: {evaluation.get('risk_score')}")

        # 파일 생성: docx, xlsx
        docx_path = None
        xlsx_path = None
        try:
            self._record_tool_call("generate_files")
            self.log("문서 파일 생성 (docx/xlsx)")
            docx_path = generate_docx(proposal, candidate, profile)
            xlsx_path = generate_xlsx(proposal, match_result, assessment, candidate)
            self.log(f"문서 생성 완료: {docx_path}")
            self.log(f"평가표 생성 완료: {xlsx_path}")
        except Exception as e:
            self.log(f"문서 생성 실패: {e}")

        docx_url = f"/files/{Path(docx_path).name}" if docx_path else None
        xlsx_url = f"/files/{Path(xlsx_path).name}" if xlsx_path else None

        result = {
            "logs": self.logs,
            "candidate": candidate,
            "profile": profile,
            "assessment": assessment,
            "proposal": proposal,
            "evaluation": evaluation,
            "match_result": match_result,
            "memory": {
                "keyword": keyword,
                "business_type": business_type,
                "company_id": company_id,
                "company_profile_override": company_profile_override,
                "source_mode": "pdf_upload" if uploaded_doc_path else ("metadata_only" if use_metadata_only else "bid_document"),
                "uploaded_doc_path": uploaded_doc_path,
                "document_parse": {
                    "source": doc.get("source"),
                    "filename": doc.get("filename"),
                    "parse_method": doc.get("parse_method"),
                    "section_count": len(doc.get("sections", [])),
                    "text_preview": (doc.get("text") or "")[:1200],
                },
                "tool_calls": self.tool_calls,
                "revision_history": [],
            },
            "files": {
                "docx": docx_url,
                "xlsx": xlsx_url,
                "docx_path": docx_path,
                "xlsx_path": xlsx_path
            },
            "tool_calls": self.tool_calls
        }
        return result

    def revise_with_feedback(
        self,
        base_result: Dict[str, Any],
        feedback: str,
        revision_meta: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        """PM 피드백을 반영해 제안서를 재작성하고 재평가한다."""
        self.logs = []
        self.tool_calls = []
        self.log("Human-in-the-Loop 시작: PM 피드백 반영")

        candidate = base_result.get("candidate", {})
        profile = base_result.get("profile", {})
        proposal = base_result.get("proposal", {})
        match_result = base_result.get("match_result", {})
        assessment = base_result.get("assessment", {})
        previous_evaluation = base_result.get("evaluation", {})
        memory = base_result.get("memory", {}) or {}
        revision_history = list(memory.get("revision_history", []))

        self._record_tool_call("revise_proposal")
        self.log("Revision Agent 호출 (revise_proposal)")
        revised_draft = revise_proposal(
            proposal.get("draft_text", ""),
            feedback,
            bid=candidate,
            profile=profile,
            assessment=assessment,
            evaluation=previous_evaluation,
            match_result=match_result,
        )
        revised_proposal = {
            **proposal,
            "draft_text": revised_draft,
        }

        self._record_tool_call("evaluate_proposal")
        self.log("Evaluator 재호출 (evaluate_proposal)")
        revised_evaluation = evaluate_proposal(
            revised_draft,
            candidate,
            profile,
            match_result=match_result,
            assessment=assessment
        )

        docx_path = None
        xlsx_path = None
        try:
            self._record_tool_call("generate_files")
            self.log("수정본 산출물 재생성 (docx/xlsx)")
            docx_path = generate_docx(revised_proposal, candidate, profile)
            xlsx_path = generate_xlsx(revised_proposal, match_result, assessment, candidate)
        except Exception as e:
            self.log(f"수정본 파일 생성 실패: {e}")

        revision_entry = {
            "feedback": feedback,
            "meta": revision_meta or {},
            "previous_risk_score": previous_evaluation.get("risk_score"),
            "new_risk_score": revised_evaluation.get("risk_score"),
            "ts": time.time(),
        }
        revision_history.append(revision_entry)

        docx_url = f"/files/{Path(docx_path).name}" if docx_path else None
        xlsx_url = f"/files/{Path(xlsx_path).name}" if xlsx_path else None

        result = {
            "logs": self.logs,
            "candidate": candidate,
            "profile": profile,
            "assessment": assessment,
            "proposal": revised_proposal,
            "evaluation": revised_evaluation,
            "match_result": match_result,
            "memory": {
                **memory,
                "revision_history": revision_history,
            },
            "files": {
                "docx": docx_url,
                "xlsx": xlsx_url,
                "docx_path": docx_path,
                "xlsx_path": xlsx_path
            },
            "tool_calls": self.tool_calls
        }
        self.log(f"피드백 반영 완료: revision #{len(revision_history)}")
        return result


if __name__ == "__main__":
    orch = Orchestrator()
    res = orch.run_by_search(keyword="데이터", business_type="용역", company_id="COMPANY_A")
    print('\n=== 결과 요약 ===')
    print(f"공고: {res.get('candidate', {}).get('title')}")
    print(f"매칭점수: {res.get('assessment', {}).get('match_score')}")
    print(f"제안서 초안(요약): {res.get('proposal', {}).get('draft_text')[:120]}...")
