"""
Mock 데이터: 샘플 입찰공고와 회사 프로필
"""
from datetime import date

SAMPLE_BIDS = [
    {
        "id": "BID001",
        "title": "AI 기반 데이터 분석 시스템 개발",
        "businessType": "용역",
        "budget": 50000000,
        "deadline": "2026-06-30",
        "requirements": [
            {"id": "r1", "text": "AI 모델 개발 경험", "type": "기술", "weight": 30},
            {"id": "r2", "text": "데이터 파이프라인 구축 경험", "type": "기술", "weight": 20},
            {"id": "r3", "text": "ISO27001 수준의 보안 체계", "type": "보안", "weight": 20},
            {"id": "r4", "text": "유사 프로젝트 수행 실적 2건 이상", "type": "실적", "weight": 30}
        ],
        "doc": "bid_001.pdf"
    },
    {
        "id": "BID002",
        "title": "클라우드 마이그레이션 컨설팅",
        "businessType": "용역",
        "budget": 30000000,
        "deadline": "2026-06-15",
        "requirements": [
            {"id": "r1", "text": "클라우드 마이그레이션 경험", "type": "기술", "weight": 40},
            {"id": "r2", "text": "MS Azure/MSP 파트너 자격", "type": "인증", "weight": 30},
            {"id": "r3", "text": "프로젝트 관리 능력", "type": "관리", "weight": 30}
        ],
        "doc": "bid_002.pdf"
    },
    {
        "id": "BID003",
        "title": "보안 솔루션 구축",
        "businessType": "물품",
        "budget": 20000000,
        "deadline": "2026-07-10",
        "requirements": [
            {"id": "r1", "text": "보안장비 공급 경험", "type": "기술", "weight": 50},
            {"id": "r2", "text": "국가 정보보호 인증 보유", "type": "인증", "weight": 50}
        ],
        "doc": "bid_003.pdf"
    }
]

SAMPLE_COMPANY_PROFILE = {
    "company_id": "COMPANY_A",
    "name": "에이아이솔루션즈",
    "summary": "AI/데이터 분석 전문 기업으로 공공·금융 영역 수행 경험 보유",
    "skills": ["AI 모델 개발", "데이터 파이프라인", "클라우드 아키텍처", "보안"],
    "certifications": ["ISO27001"],
    "projects": [
        {"title": "금융권 위험탐지 모델 개발", "year": 2024, "role": "개발", "value": 20000000},
        {"title": "공공기관 데이터 통합 플랫폼", "year": 2023, "role": "시스템통합", "value": 35000000}
    ],
    "headcount": 45
}
