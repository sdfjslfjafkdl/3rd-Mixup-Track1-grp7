"""
RequirementAgent
- 공고/문서에서 요구사항 추출 (extract_requirements_from_doc 툴 호출)
"""
from typing import Dict, Any, List, Callable
from backend.tools.requirement_extractor import extract_requirements_from_doc


class RequirementAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(self, candidate: Dict[str, Any], doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """추출된 요구사항 목록을 반환하고 candidate['requirements'] 에도 기록"""
        self.record_tool("extract_requirements")
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
        return requirements
