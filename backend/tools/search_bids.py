"""
나라장터 입찰공고 검색
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import quote

import requests

from backend.config import NARAJANGTEO_SERVICE_KEY

BASE_URL = "https://apis.data.go.kr/1230000/ad/BidPublicInfoService"
DEFAULT_TIMEOUT = 20
DEFAULT_LOOKBACK_DAYS = 7
LOOKBACK_DAY_STEPS = (7, 14, 30)
DEFAULT_PAGE_NO = 1
DEFAULT_NUM_OF_ROWS = 10

BUSINESS_TYPE_TO_OPERATION = {
    "용역": "getBidPblancListInfoServcPPSSrch",
    "공사": "getBidPblancListInfoCnstwkPPSSrch",
    "물품": "getBidPblancListInfoThngPPSSrch",
    "외자": "getBidPblancListInfoFrgcptPPSSrch",
}

KEY_ERROR_TOKENS = (
    "SERVICE KEY IS NOT REGISTERED ERROR",
    "SERVICE_KEY_IS_NOT_REGISTERED_ERROR",
    "등록되지 않은",
    "인증키",
    "SERVICE ACCESS DENIED",
    "INVALID_REQUEST_PARAMETER_ERROR",
)


class NaraJangteoAPIError(RuntimeError):
    """나라장터 API 호출 오류"""


def _resolve_business_type(business_type: Optional[str]) -> str:
    if business_type in BUSINESS_TYPE_TO_OPERATION:
        return business_type
    return "용역"


def _format_query_datetime(value: datetime, end_of_day: bool = False) -> str:
    if end_of_day:
        return value.strftime("%Y%m%d2359")
    return value.strftime("%Y%m%d0000")


def _default_date_range(days: int = DEFAULT_LOOKBACK_DAYS) -> tuple[str, str]:
    end_at = datetime.now()
    start_at = end_at - timedelta(days=days)
    return _format_query_datetime(start_at), _format_query_datetime(end_at, end_of_day=True)


def _candidate_lookback_days(initial_days: int = DEFAULT_LOOKBACK_DAYS) -> List[int]:
    candidates: List[int] = []
    for days in (initial_days, *LOOKBACK_DAY_STEPS):
        normalized = min(days, 30)
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _build_params(
    service_key: str,
    keyword: Optional[str],
    page_no: int,
    num_of_rows: int,
    inqry_bgn_dt: str,
    inqry_end_dt: str,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "serviceKey": service_key,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "inqryDiv": "1",
        "inqryBgnDt": inqry_bgn_dt,
        "inqryEndDt": inqry_end_dt,
        "type": "json",
    }
    if keyword:
        params["bidNtceNm"] = keyword
    return params


def _extract_response_payload(data: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], List[Dict[str, Any]]]:
    response = data.get("response")
    if not isinstance(response, dict):
        raise NaraJangteoAPIError(f"예상과 다른 응답 형식입니다: {data}")

    header = response.get("header") or {}
    body = response.get("body") or {}
    items = body.get("items", [])

    if isinstance(items, dict):
        if "item" in items:
            items = items["item"]
        else:
            items = [items]
    elif items is None:
        items = []

    if isinstance(items, list):
        normalized_items = [item for item in items if isinstance(item, dict)]
    else:
        normalized_items = []

    return header, body, normalized_items


def _is_service_key_error(response: requests.Response, data: Optional[Dict[str, Any]]) -> bool:
    if response.status_code == 401:
        return True

    response_text = response.text or ""
    if any(token in response_text for token in KEY_ERROR_TOKENS):
        return True

    if data:
        header = data.get("response", {}).get("header", {})
        result_msg = str(header.get("resultMsg", ""))
        if any(token in result_msg for token in KEY_ERROR_TOKENS):
            return True

    return False


def _call_bid_api(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}/{operation}"
    response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)

    try:
        data = response.json()
    except ValueError as exc:
        raise NaraJangteoAPIError(
            f"JSON 응답 파싱 실패(status={response.status_code}): {response.text[:500]}"
        ) from exc

    return {"response": response, "data": data}


def _request_with_key_fallback(
    operation: str,
    keyword: Optional[str],
    page_no: int,
    num_of_rows: int,
    inqry_bgn_dt: str,
    inqry_end_dt: str,
) -> Dict[str, Any]:
    if not NARAJANGTEO_SERVICE_KEY:
        raise NaraJangteoAPIError("NARAJANGTEO_SERVICE_KEY가 설정되지 않았습니다.")

    decoded_key = NARAJANGTEO_SERVICE_KEY
    encoded_key = quote(NARAJANGTEO_SERVICE_KEY, safe="")
    keys_to_try = [decoded_key]
    if encoded_key != decoded_key:
        keys_to_try.append(encoded_key)

    last_error: Optional[NaraJangteoAPIError] = None

    for service_key in keys_to_try:
        params = _build_params(
            service_key=service_key,
            keyword=keyword,
            page_no=page_no,
            num_of_rows=num_of_rows,
            inqry_bgn_dt=inqry_bgn_dt,
            inqry_end_dt=inqry_end_dt,
        )
        result = _call_bid_api(operation, params)
        response = result["response"]
        data = result["data"]

        if _is_service_key_error(response, data) and service_key != keys_to_try[-1]:
            continue

        header, _, _ = _extract_response_payload(data)
        result_code = str(header.get("resultCode", ""))
        result_msg = str(header.get("resultMsg", ""))

        if response.status_code != 200 or result_code not in {"00", "03"}:
            last_error = NaraJangteoAPIError(
                f"나라장터 API 오류(status={response.status_code}, resultCode={result_code}, resultMsg={result_msg})"
            )
            if _is_service_key_error(response, data) and service_key != keys_to_try[-1]:
                continue
            raise last_error

        return data

    if last_error:
        raise last_error

    raise NaraJangteoAPIError("나라장터 API 호출에 실패했습니다.")


def _to_internal_bid(item: Dict[str, Any], business_type: str) -> Dict[str, Any]:
    bid_notice_no = str(item.get("bidNtceNo") or "").strip()
    bid_notice_ord = str(item.get("bidNtceOrd") or "").strip()
    internal_id = f"{bid_notice_no}-{bid_notice_ord}" if bid_notice_ord else bid_notice_no

    deadline = item.get("bidClseDt") or item.get("opengDt") or ""
    budget = item.get("asignBdgtAmt")
    if budget in (None, "", "0", 0):
        budget = item.get("presmptPrce")

    notice_url = (
        item.get("stdNtceDocUrl")
        or item.get("ntceSpecDocUrl1")
        or item.get("ntceSpecDocUrl2")
        or item.get("ntceSpecDocUrl3")
        or item.get("bidNtceDtlUrl")
        or internal_id
    )

    return {
        "id": internal_id or item.get("bidNtceNm", "UNKNOWN"),
        "title": item.get("bidNtceNm", ""),
        "businessType": business_type,
        "agency": item.get("dminsttNm") or item.get("ntceInsttNm") or "",
        "deadline": deadline,
        "budget": budget,
        "bidNoticeNo": bid_notice_no,
        "estimatedAmount": budget,
        "doc": notice_url,
        "requirements": [],
        "raw": item,
    }


def test_search_bids_api(
    keyword: Optional[str] = None,
    business_type: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Dict[str, Any]:
    """실제 나라장터 API 연결을 1건으로 테스트한다."""
    resolved_business_type = _resolve_business_type(business_type)
    operation = BUSINESS_TYPE_TO_OPERATION[resolved_business_type]
    attempts: List[Dict[str, Any]] = []

    for days in _candidate_lookback_days(lookback_days):
        inqry_bgn_dt, inqry_end_dt = _default_date_range(days)
        data = _request_with_key_fallback(
            operation=operation,
            keyword=keyword,
            page_no=DEFAULT_PAGE_NO,
            num_of_rows=1,
            inqry_bgn_dt=inqry_bgn_dt,
            inqry_end_dt=inqry_end_dt,
        )

        header, body, items = _extract_response_payload(data)
        attempts.append(
            {
                "lookback_days": days,
                "inqryBgnDt": inqry_bgn_dt,
                "inqryEndDt": inqry_end_dt,
                "total_count": body.get("totalCount"),
                "resultCode": header.get("resultCode"),
                "resultMsg": header.get("resultMsg"),
            }
        )

        if items:
            mapped_items = [_to_internal_bid(item, resolved_business_type) for item in items]
            return {
                "operation": operation,
                "business_type": resolved_business_type,
                "query": {
                    "keyword": keyword,
                    "inqryBgnDt": inqry_bgn_dt,
                    "inqryEndDt": inqry_end_dt,
                    "numOfRows": 1,
                    "pageNo": DEFAULT_PAGE_NO,
                    "lookbackDays": days,
                },
                "header": header,
                "total_count": body.get("totalCount"),
                "attempts": attempts,
                "raw_item": items[0],
                "mapped_item": mapped_items[0],
            }

    return {
        "operation": operation,
        "business_type": resolved_business_type,
        "query": {
            "keyword": keyword,
            "numOfRows": 1,
            "pageNo": DEFAULT_PAGE_NO,
        },
        "attempts": attempts,
        "raw_item": None,
        "mapped_item": None,
    }


def search_bids(keyword: str = None, business_type: str = None) -> List[Dict[str, Any]]:
    """나라장터 입찰공고를 검색하고 내부 형식으로 변환해 반환한다."""
    resolved_business_type = _resolve_business_type(business_type)
    operation = BUSINESS_TYPE_TO_OPERATION[resolved_business_type]
    for days in _candidate_lookback_days():
        inqry_bgn_dt, inqry_end_dt = _default_date_range(days)
        data = _request_with_key_fallback(
            operation=operation,
            keyword=keyword,
            page_no=DEFAULT_PAGE_NO,
            num_of_rows=DEFAULT_NUM_OF_ROWS,
            inqry_bgn_dt=inqry_bgn_dt,
            inqry_end_dt=inqry_end_dt,
        )

        _, _, items = _extract_response_payload(data)
        if items:
            return [_to_internal_bid(item, resolved_business_type) for item in items]

    return []
