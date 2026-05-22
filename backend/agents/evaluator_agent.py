"""
EvaluatorAgent
- Red Team 관점에서 제안서를 평가 (evaluate_proposal 툴 호출)
"""
from typing import Dict, Any, Callable
from backend.tools.evaluator import evaluate_proposal


class EvaluatorAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(
        self,
        draft_text: str,
        candidate: Dict[str, Any],
        profile: Dict[str, Any],
        match_result: Dict[str, Any],
        assessment: Dict[str, Any],
        log_label: str = "Red Team 평가 호출 (evaluate_proposal)",
    ) -> Dict[str, Any]:
        """평가 결과 dict 반환. 호출 컨텍스트(최초/재평가)에 따라 로그 라벨만 다르게 받음."""
        self.record_tool("evaluate_proposal")
        self.log(log_label)
        return evaluate_proposal(
            draft_text,
            candidate,
            profile,
            match_result=match_result,
            assessment=assessment,
        )
