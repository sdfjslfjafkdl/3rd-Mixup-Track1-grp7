"""
ProposalAgent
- 제안서 초안 생성 (generate_proposal) 및 피드백 기반 수정 (revise_proposal)
"""
from typing import Dict, Any, Callable
from backend.tools.proposal_generator import generate_proposal, revise_proposal


class ProposalAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def generate(self, candidate: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
        """제안서 초안 생성"""
        self.record_tool("generate_proposal")
        self.log("제안서 생성 호출 (generate_proposal)")
        proposal = generate_proposal(candidate, profile)
        self.log("제안서 초안 생성 완료")
        return proposal

    def revise(
        self,
        base_draft: str,
        feedback: str,
        candidate: Dict[str, Any],
        profile: Dict[str, Any],
        assessment: Dict[str, Any],
        evaluation: Dict[str, Any],
        match_result: Dict[str, Any],
    ) -> str:
        """PM 피드백을 반영해 제안서 본문을 재작성한 텍스트 반환"""
        self.record_tool("revise_proposal")
        self.log("Revision Agent 호출 (revise_proposal)")
        return revise_proposal(
            base_draft,
            feedback,
            bid=candidate,
            profile=profile,
            assessment=assessment,
            evaluation=evaluation,
            match_result=match_result,
        )
