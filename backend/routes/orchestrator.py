from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from ..agents.orchestrator import Orchestrator
from ..tools.search_bids import search_bids, NaraJangteoAPIError
from queue import Queue
from threading import Thread
import json
import os
import shutil
import tempfile

router = APIRouter()

class OrchestratorRequest(BaseModel):
    keyword: Optional[str] = None
    business_type: Optional[str] = None
    company_id: Optional[str] = None


class RevisionRequest(BaseModel):
    base_result: dict
    feedback_text: str
    feedback_mode: str = "내용 수정"
    section_request: Optional[str] = None
    tone_strength: Optional[str] = None


class BidSearchRequest(BaseModel):
    keyword: Optional[str] = None
    business_type: str = "용역"


@router.post("/bids/search")
async def search_bid_notices(req: BidSearchRequest):
    """실제 나라장터 공고를 검색해 프론트에 반환한다.

    데모 안정성을 위해 외부 API 일시 실패(NaraJangteoAPIError, 네트워크 등) 시에는
    500/502 대신 빈 목록 + 안내 메시지를 200으로 반환한다.
    """
    try:
        bids = search_bids(keyword=req.keyword, business_type=req.business_type)
        return {
            "count": len(bids),
            "items": bids,
        }
    except NaraJangteoAPIError as e:
        print(f"[search_bid_notices] 나라장터 API 실패 (모든 키워드 후보 실패): {e}")
        return {
            "count": 0,
            "items": [],
            "message": "일시적으로 공고를 불러오지 못했습니다. 다시 시도해 주세요.",
        }
    except Exception as e:
        # 외부 API와 무관한 예외(코드 버그 등)는 디버깅을 위해 500으로 남겨둠
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orchestrator/start")
async def start_orchestrator(req: OrchestratorRequest):
    """Orchestrator를 실행하고 로그/결과를 반환한다"""
    orch = Orchestrator()
    try:
        result = orch.run_by_search(keyword=req.keyword, business_type=req.business_type, company_id=req.company_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/orchestrator/stream")
def start_orchestrator_stream(req: OrchestratorRequest):
    """Orchestrator를 실행하면서 로그를 스트리밍한다"""
    queue = Queue()
    result_holder = {}

    def on_log(message: str):
        queue.put({"type": "log", "message": message})

    def worker():
        nonlocal result_holder
        orch = Orchestrator(on_log=on_log)
        try:
            result_holder["result"] = orch.run_by_search(
                keyword=req.keyword,
                business_type=req.business_type,
                company_id=req.company_id
            )
        except Exception as e:
            result_holder["error"] = str(e)
        finally:
            queue.put({"type": "done"})

    thread = Thread(target=worker, daemon=True)
    thread.start()

    def event_generator():
        while True:
            item = queue.get()
            if item["type"] == "done":
                break
            yield json.dumps(item) + "\n"

        if "error" in result_holder:
            yield json.dumps({"type": "error", "message": result_holder["error"]}) + "\n"
        else:
            yield json.dumps({"type": "result", "payload": result_holder.get("result")}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/orchestrator/stream-upload")
def start_orchestrator_stream_with_upload(
    keyword: Optional[str] = Form(default=None),
    business_type: Optional[str] = Form(default=None),
    company_id: Optional[str] = Form(default=None),
    company_profile: Optional[str] = Form(default=None),
    pdf_file: UploadFile | None = File(default=None),
):
    """선택적 PDF 업로드를 받아 Orchestrator를 실행하면서 로그를 스트리밍한다."""
    queue = Queue()
    result_holder = {}
    saved_pdf_path = None
    company_profile_payload = None

    if company_profile:
        try:
            company_profile_payload = json.loads(company_profile)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="company_profile JSON 형식이 올바르지 않습니다.")

    if pdf_file and pdf_file.filename:
        suffix = os.path.splitext(pdf_file.filename)[1] or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=tempfile.gettempdir()) as temp_file:
            shutil.copyfileobj(pdf_file.file, temp_file)
            saved_pdf_path = temp_file.name

    def on_log(message: str):
        queue.put({"type": "log", "message": message})

    def worker():
        nonlocal result_holder, saved_pdf_path
        orch = Orchestrator(on_log=on_log)
        try:
            result_holder["result"] = orch.run_by_search(
                keyword=keyword,
                business_type=business_type,
                company_id=company_id,
                uploaded_doc_path=saved_pdf_path,
                use_metadata_only=(saved_pdf_path is None),
                company_profile_override=company_profile_payload,
            )
        except Exception as e:
            result_holder["error"] = str(e)
        finally:
            if saved_pdf_path and os.path.exists(saved_pdf_path):
                try:
                    os.remove(saved_pdf_path)
                except OSError:
                    pass
            queue.put({"type": "done"})

    thread = Thread(target=worker, daemon=True)
    thread.start()

    def event_generator():
        while True:
            item = queue.get()
            if item["type"] == "done":
                break
            yield json.dumps(item) + "\n"

        if "error" in result_holder:
            yield json.dumps({"type": "error", "message": result_holder["error"]}) + "\n"
        else:
            yield json.dumps({"type": "result", "payload": result_holder.get("result")}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@router.post("/orchestrator/revise")
async def revise_orchestrator_result(req: RevisionRequest):
    """PM 피드백을 반영해 제안서를 재작성하고 재평가한다."""
    orch = Orchestrator()
    try:
        feedback_parts = [f"[피드백 유형] {req.feedback_mode}", req.feedback_text.strip()]
        if req.section_request:
            feedback_parts.append(f"[추가 섹션 요청] {req.section_request.strip()}")
        if req.tone_strength:
            feedback_parts.append(f"[강도 조절] {req.tone_strength.strip()}")

        merged_feedback = "\n".join(part for part in feedback_parts if part)
        result = orch.revise_with_feedback(
            base_result=req.base_result,
            feedback=merged_feedback,
            revision_meta={
                "feedback_mode": req.feedback_mode,
                "section_request": req.section_request,
                "tone_strength": req.tone_strength,
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
