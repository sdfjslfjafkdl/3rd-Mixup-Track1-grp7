"""
MatchingAgent
- 요구사항-회사 매칭 + 자격 평가 (match_requirements, assess_eligibility)
"""
from typing import Dict, Any, List, Tuple, Callable
from backend.tools.matching import match_requirements
from backend.tools.assess_eligibility import assess_eligibility


class MatchingAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(
        self,
        requirements: List[Dict[str, Any]],
        profile: Dict[str, Any],
        candidate: Dict[str, Any],
        proposal_text: str = None,
        label_suffix: str = "",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """(match_result, assessment) 튜플 반환.

        proposal_text 가 주어지면 매칭/자격 평가 모두 본문을 함께 근거로 사용한다.
        label_suffix 는 로그 라벨에 붙이는 보조 텍스트 (예: " (본문 반영)").
        """
        # 매칭 및 스코어링
        self.record_tool("match_requirements")
        self.log(f"요구사항 매칭 호출 (match_requirements){label_suffix}")
        match_result = match_requirements(requirements, profile, proposal_text=proposal_text)
        self.log(
            f"전체 적합도: {match_result.get('overall_score')} - "
            f"WinProb: {match_result.get('win_probability')}%"
        )

        # 자격 판단 (기존 규칙 기반) - 보완적으로 사용
        self.record_tool("assess_eligibility")
        self.log(f"자격 판단 호출 (assess_eligibility){label_suffix}")
        assessment = assess_eligibility(candidate, profile, proposal_text=proposal_text)
        self.log(
            f"자격 매칭점수: {assessment.get('match_score')}% - "
            f"충족: {assessment.get('eligible')}"
        )
        return match_result, assessment
