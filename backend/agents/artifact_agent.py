"""
ArtifactAgent
- 제안서(docx) / 평가표(xlsx) 산출물 생성
"""
from typing import Dict, Any, Optional, Tuple, Callable
from backend.services.file_generator import generate_docx, generate_xlsx


class ArtifactAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(
        self,
        proposal: Dict[str, Any],
        candidate: Dict[str, Any],
        profile: Dict[str, Any],
        match_result: Dict[str, Any],
        assessment: Dict[str, Any],
        log_label: str = "문서 파일 생성 (docx/xlsx)",
        error_label: str = "문서 생성 실패",
        log_success: bool = True,
    ) -> Tuple[Optional[str], Optional[str]]:
        """(docx_path, xlsx_path) 튜플 반환. 실패 시 None 으로 채워서 반환."""
        docx_path: Optional[str] = None
        xlsx_path: Optional[str] = None
        try:
            self.record_tool("generate_files")
            self.log(log_label)
            docx_path = generate_docx(proposal, candidate, profile)
            xlsx_path = generate_xlsx(proposal, match_result, assessment, candidate)
            if log_success:
                self.log(f"문서 생성 완료: {docx_path}")
                self.log(f"평가표 생성 완료: {xlsx_path}")
        except Exception as e:
            self.log(f"{error_label}: {e}")
        return docx_path, xlsx_path
