"""
ProfileAgent
- 회사 정보 조회 (RAG 기반 search_company_profile 툴 호출)
"""
from typing import Dict, Any, Optional, Callable
from backend.tools.company_rag import search_company_profile


class ProfileAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(
        self,
        company_id: Optional[str],
        company_profile_override: Optional[Dict[str, Any]] = None,
        retry: bool = False,
    ) -> Dict[str, Any]:
        """회사 프로필을 반환한다. retry=True 면 재시도 로그를 남긴다."""
        self.record_tool("search_company_profile")
        if retry:
            self.log("추가 회사 정보 조회 시도")
        else:
            self.log("회사 정보 조회 호출 (search_company_profile)")
        profile = search_company_profile(
            company_id=company_id,
            company_profile_override=company_profile_override,
        )
        if not retry:
            self.log(
                f"회사: {profile.get('name')} (스킬: {', '.join(profile.get('skills', []))})"
            )
        return profile
