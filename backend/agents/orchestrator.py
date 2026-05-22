"""
Orchestrator (얇은 코디네이터)
- 각 단계(검색/문서/프로필/요건/매칭/제안서/평가/산출물) 를 전용 Agent 에 위임한다.
- 정보 충분성 판단 + 재시도 루프 + 제안서 버전 관리(memory.versions) 는 여기서 담당.
"""
from typing import List, Dict, Any, Callable, Optional
import time
from pathlib import Path

from backend.agents.search_agent import SearchAgent
from backend.agents.document_agent import DocumentAgent
from backend.agents.profile_agent import ProfileAgent
from backend.agents.requirement_agent import RequirementAgent
from backend.agents.matching_agent import MatchingAgent
from backend.agents.proposal_agent import ProposalAgent
from backend.agents.evaluator_agent import EvaluatorAgent
from backend.agents.artifact_agent import ArtifactAgent


class Orchestrator:
    def __init__(self, on_log: Callable[[str], None] = None):
        self.logs: List[str] = []
        self.on_log = on_log
        # 호출된 툴 이력
        self.tool_calls: List[Dict[str, Any]] = []
        # 하위 agent 들에 log/record_tool 콜백을 주입해서 동일한 로그/툴 이력에 누적
        self.search = SearchAgent(self.log, self._record_tool_call)
        self.document = DocumentAgent(self.log, self._record_tool_call)
        self.profile = ProfileAgent(self.log, self._record_tool_call)
        self.requirement = RequirementAgent(self.log, self._record_tool_call)
        self.matching = MatchingAgent(self.log, self._record_tool_call)
        self.proposal = ProposalAgent(self.log, self._record_tool_call)
        self.evaluator = EvaluatorAgent(self.log, self._record_tool_call)
        self.artifact = ArtifactAgent(self.log, self._record_tool_call)

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
            dict: {logs, candidate, assessment, proposal, evaluation, tool_calls, ...}
        """
        # 초기화
        self.logs = []
        self.tool_calls = []
        self.document.reset_cache()
        self.log("Orchestrator 시작: 검색 기준 수집")

        # Phase 1: 공고 검색
        bids = self.search.run(keyword=keyword, business_type=business_type)
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
        match_result = None

        while attempt <= max_retries:
            attempt += 1
            self.log(f"루프 시도 {attempt}/{max_retries + 1}")

            # 문서 파싱
            doc = self.document.parse_initial(candidate, uploaded_doc_path, use_metadata_only)
            self.log(f"문서 요약: {doc.get('text')}")

            # 회사 정보 조회
            profile = self.profile.run(company_id, company_profile_override)

            # 요건 추출
            requirements = self.requirement.run(candidate, doc)

            # 매칭 + 자격 판단
            match_result, assessment = self.matching.run(requirements, profile, candidate)

            # 충분성 판단: eligible 이거나 매칭 세부 정보가 충분하면 종료
            missing_reqs = [d for d in assessment.get('details', []) if d.get('status') == 'missing']
            if assessment.get('eligible') and len(missing_reqs) == 0:
                self.log("정보 충분: 자격 충족 판단 완료")
                break

            # 아니라면 재시도 전략: 문서/프로필 재수집
            if attempt <= max_retries:
                self.log("정보 부족: 추가 데이터 수집 시도")
                doc = self.document.parse_retry(candidate, uploaded_doc_path, use_metadata_only)
                profile = self.profile.run(company_id, company_profile_override, retry=True)
                # 루프가 다시 돌아가면서 reassess
            else:
                self.log("최대 재시도 도달: 루프 종료")
                break

        # 제안서 생성
        proposal = self.proposal.generate(candidate, profile)

        # 자격/매칭 재계산: 생성된 본문을 근거 텍스트에 포함시켜 점수가 본문을 반영하게 함
        # (루프 단계의 assessment/match_result 는 사전 충분성 판단용으로 이미 끝났음)
        match_result, assessment = self.matching.run(
            candidate.get("requirements", []),
            profile,
            candidate,
            proposal_text=proposal.get("draft_text", ""),
            label_suffix=" (본문 반영)",
        )

        # Red Team 평가 (본문 반영된 assessment/match_result 사용)
        evaluation = self.evaluator.run(
            proposal.get('draft_text'),
            candidate,
            profile,
            match_result,
            assessment,
            log_label="Red Team 평가 호출 (evaluate_proposal)",
        )
        self.log(f"리스크 스코어: {evaluation.get('risk_score')}")

        # 파일 생성: docx, xlsx
        docx_path, xlsx_path = self.artifact.run(
            proposal, candidate, profile, match_result, assessment,
            log_label="문서 파일 생성 (docx/xlsx)",
            error_label="문서 생성 실패",
            log_success=True,
        )

        docx_url = f"/files/{Path(docx_path).name}" if docx_path else None
        xlsx_url = f"/files/{Path(xlsx_path).name}" if xlsx_path else None

        # 원본 제안서를 versions[0] 으로 기록 (프론트가 버전 간 비교 가능하도록 본문 전체 보존)
        # 원본은 수정 이력이 없으므로 change_reasons 는 None
        initial_version = {
            "version": 1,
            "label": "원본",
            "draft_text": proposal.get("draft_text", ""),
            "risk_score": evaluation.get("risk_score"),
            "match_score": assessment.get("match_score") if assessment else None,
            "win_probability": match_result.get("win_probability") if match_result else None,
            "files": {"docx": docx_url, "xlsx": xlsx_url},
            "feedback": None,
            "change_reasons": None,
            "ts": time.time(),
        }

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
                "versions": [initial_version],
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
        # 누적 버전 배열 로드 (없으면 base 의 원본 제안서로 시드)
        versions = list(memory.get("versions", []))
        if not versions:
            base_files = base_result.get("files", {}) or {}
            versions = [{
                "version": 1,
                "label": "원본",
                "draft_text": proposal.get("draft_text", ""),
                "risk_score": previous_evaluation.get("risk_score"),
                "match_score": assessment.get("match_score") if assessment else None,
                "win_probability": match_result.get("win_probability") if match_result else None,
                "files": {"docx": base_files.get("docx"), "xlsx": base_files.get("xlsx")},
                "feedback": None,
                "change_reasons": None,
                "ts": time.time(),
            }]

        # 1) 본문 재작성
        old_draft = proposal.get("draft_text", "")
        revised_draft = self.proposal.revise(
            old_draft,
            feedback,
            candidate, profile, assessment, previous_evaluation, match_result,
        )
        revised_proposal = {
            **proposal,
            "draft_text": revised_draft,
        }

        # 1-b) 수정 이유 요약 (실패해도 폴백 메시지가 들어와 에러 없이 진행)
        change_reasons = self.proposal.summarize_changes(
            old_draft, revised_draft, feedback, candidate, profile,
        )

        # 1-c) 본문 변경 반영해 자격/매칭 재계산 — 점수가 다듬은 본문을 진짜로 반영하도록
        match_result, assessment = self.matching.run(
            candidate.get("requirements", []),
            profile,
            candidate,
            proposal_text=revised_draft,
            label_suffix=" (수정본 반영)",
        )

        # 2) 재평가 (재계산된 assessment/match_result 로 risk_score 가 자연히 갱신됨)
        revised_evaluation = self.evaluator.run(
            revised_draft, candidate, profile, match_result, assessment,
            log_label="Evaluator 재호출 (evaluate_proposal)",
        )

        # 3) 산출물 재생성
        docx_path, xlsx_path = self.artifact.run(
            revised_proposal, candidate, profile, match_result, assessment,
            log_label="수정본 산출물 재생성 (docx/xlsx)",
            error_label="수정본 파일 생성 실패",
            log_success=False,
        )

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

        # 이번 수정본을 versions 에 누적 (본문 전체 + 별도 파일 경로 보존)
        new_version_num = len(versions) + 1
        new_version = {
            "version": new_version_num,
            "label": f"수정본 {new_version_num - 1}",
            "draft_text": revised_draft,
            "risk_score": revised_evaluation.get("risk_score"),
            "match_score": assessment.get("match_score") if assessment else None,
            "win_probability": match_result.get("win_probability") if match_result else None,
            "files": {"docx": docx_url, "xlsx": xlsx_url},
            "feedback": feedback,
            "change_reasons": change_reasons,
            "ts": time.time(),
        }
        versions.append(new_version)

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
                "versions": versions,
            },
            "files": {
                "docx": docx_url,
                "xlsx": xlsx_url,
                "docx_path": docx_path,
                "xlsx_path": xlsx_path
            },
            "tool_calls": self.tool_calls
        }
        self.log(f"피드백 반영 완료: revision #{len(revision_history)} (총 버전 {len(versions)}개)")
        return result


if __name__ == "__main__":
    orch = Orchestrator()
    res = orch.run_by_search(keyword="데이터", business_type="용역", company_id="COMPANY_A")
    print('\n=== 결과 요약 ===')
    print(f"공고: {res.get('candidate', {}).get('title')}")
    print(f"매칭점수: {res.get('assessment', {}).get('match_score')}")
    print(f"제안서 초안(요약): {res.get('proposal', {}).get('draft_text')[:120]}...")
