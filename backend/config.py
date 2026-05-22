"""
설정 관리 - 환경 변수 로드
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# API 키
SOLAR_API_KEY = os.getenv("SOLAR_API_KEY", "")
SOLAR_MODEL = os.getenv("SOLAR_MODEL", "solar-pro3")
UPSTAGE_API_KEY = os.getenv("UPSTAGE_API_KEY", "")
UPSTAGE_EFFECTIVE_API_KEY = UPSTAGE_API_KEY or SOLAR_API_KEY
UPSTAGE_DOCUMENT_PARSE_URL = os.getenv(
    "UPSTAGE_DOCUMENT_PARSE_URL",
    "https://api.upstage.ai/v1/document-digitization"
)
UPSTAGE_DOCUMENT_PARSE_MODEL = os.getenv("UPSTAGE_DOCUMENT_PARSE_MODEL", "document-parse")
UPSTAGE_DOCUMENT_PARSE_OCR = os.getenv("UPSTAGE_DOCUMENT_PARSE_OCR", "force")
UPSTAGE_DOCUMENT_PARSE_BASE64_ENCODING = os.getenv(
    "UPSTAGE_DOCUMENT_PARSE_BASE64_ENCODING",
    "['table']"
)
NARAJANGTEO_SERVICE_KEY = os.getenv("NARAJANGTEO_SERVICE_KEY", "")

# 서버 설정
SERVER_PORT = int(os.getenv("SERVER_PORT", 8000))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# CORS 허용 도메인 (콤마로 구분). 비어 있으면 데모용으로 모든 도메인 허용.
_cors_raw = os.getenv("CORS_ORIGINS", "").strip()
if _cors_raw:
    CORS_ORIGINS = [origin.strip() for origin in _cors_raw.split(",") if origin.strip()]
else:
    CORS_ORIGINS = ["*"]

# Solar Pro3 API 설정 (OpenAI 호환)
SOLAR_API_BASE_URL = os.getenv("SOLAR_API_BASE_URL", "https://api.upstage.ai/v1")

if __name__ != "__main__":
    print(f"[Config] SOLAR_MODEL: {SOLAR_MODEL}")
    print(f"[Config] SOLAR_API_BASE_URL: {SOLAR_API_BASE_URL}")
    print(
        f"[Config] API keys loaded: SOLAR={bool(SOLAR_API_KEY)}, "
        f"UPSTAGE={bool(UPSTAGE_API_KEY)}, "
        f"UPSTAGE_EFFECTIVE={bool(UPSTAGE_EFFECTIVE_API_KEY)}"
    )
