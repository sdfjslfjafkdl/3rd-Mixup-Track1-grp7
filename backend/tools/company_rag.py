"""
회사 RAG mock - 회사 정보 검색
"""
from backend.services.mock_data import SAMPLE_COMPANY_PROFILE


def search_company_profile(query: str = None, company_id: str = None, company_profile_override: dict = None):
    """회사 프로필을 반환 (mock 또는 사용자 입력 기반 override)
    Args:
        query: 검색 쿼리 (미사용)
        company_id: 회사 식별자 (없으면 SAMPLE_COMPANY_PROFILE 반환)
        company_profile_override: 프론트에서 전달한 사용자 입력 프로필
    """
    if isinstance(company_profile_override, dict) and company_profile_override:
        return {
            **SAMPLE_COMPANY_PROFILE,
            **company_profile_override,
        }

    # 단순 mock: override가 없으면 기본 샘플 프로필 반환
    return SAMPLE_COMPANY_PROFILE
