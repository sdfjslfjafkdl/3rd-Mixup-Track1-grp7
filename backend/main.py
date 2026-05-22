"""
BizScope - 입찰공고 자동 수집 & 제안서 작성 Agent
FastAPI 메인 서버
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from backend.config import SERVER_PORT, LOG_LEVEL
# 라우터 등록
from backend.routes.orchestrator import router as orchestrator_router

# FastAPI 앱 생성
app = FastAPI(
    title="BizScope",
    description="Solar Pro3 기반 입찰공고 제안서 자동화",
    version="0.1.0"
)

# 정적 파일 서빙 (프론트엔드)
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# 파일 다운로드용 정적 서빙 (생성된 문서)
# file_generator.py와 동일하게 프로젝트 루트의 output 폴더를 바라봐야 한다.
output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "output"))
os.makedirs(output_path, exist_ok=True)
app.mount("/files", StaticFiles(directory=output_path), name="files")

# 헬스 체크
@app.get("/")
async def root():
    """서버 상태 확인"""
    return {
        "status": "running",
        "message": "BizScope Server is ready",
        "version": "0.1.0",
        "note": "프론트엔드: http://localhost:8000/static/"
    }

@app.get("/health")
async def health():
    """헬스 체크"""
    return {"status": "healthy"}

app.include_router(orchestrator_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 BizScope Server starting on http://localhost:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level=LOG_LEVEL.lower())
