"""
나라장터 입찰공고 검색
"""
from __future__ import annotations

import re
import time
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
# 다중 키워드 검색 시 후보 개수 / 병합 결과 상한
_KEYWORD_CANDIDATES_LIMIT = 5
_MAX_MERGED_RESULTS = 20
# 키워드별 API 호출 재시도 (일시적 실패 대비)
_PER_KEYWORD_RETRY_ATTEMPTS = 2  # 총 시도 횟수 (= 1회 재시도)
_PER_KEYWORD_RETRY_DELAY_SEC = 0.5

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


# 긴 업종 설명/복합어를 분리할 때 쓰는 구분자: 쉼표, 가운뎃점, 슬래시
_KEYWORD_SEPARATORS = re.compile(r"[,/·]")


def _keyword_candidates(keyword: Optional[str]) -> List[str]:
    """긴/복합 키워드를 다중 검색용 후보 리스트로 분해한다.

    - None/빈 문자열 → []  (호출 측에서 키워드 없이 전체 조회 1회로 처리)
    - 구분자(쉼표/가운뎃점/슬래시) 없고 공백 1개 이하 → [원본]
      (예: "플랫폼 노동" → ["플랫폼 노동"])
    - 그 외에는 구분자로 조각낸 뒤 각 조각을 후보로 추가하고,
      여러 어절 조각은 앞쪽 1~2어절 후보도 함께 추가한다.
      1글자/빈 토큰은 제외, 중복 제거, 원본 순서 유지, 최대 _KEYWORD_CANDIDATES_LIMIT 개.
    """
    if not keyword:
        return []
    raw = keyword.strip()
    if not raw:
        return []

    has_sep = bool(_KEYWORD_SEPARATORS.search(raw))
    space_count = raw.count(" ")
    if not has_sep and space_count <= 1:
        # 이미 짧고 단순한 키워드 — 후보 1개로 기존과 동일하게 1회 검색
        return [raw]

    candidates: List[str] = []
    seen: set = set()

    def _add(token: Optional[str]) -> None:
        if not token:
            return
        t = token.strip()
        if len(t) < 2:  # 1글자 토큰/빈문자 제외
            return
        if t in seen:
            return
        seen.add(t)
        candidates.append(t)

    # 1) 구분자로 분리한 각 조각(원본 순서 유지)
    chunks = [c.strip() for c in _KEYWORD_SEPARATORS.split(raw) if c.strip()]
    for chunk in chunks:
        _add(chunk)

    # 2) 여러 어절 조각은 앞쪽 2어절, 그리고 1어절도 추가 후보로
    for chunk in chunks:
        words = chunk.split()
        if len(words) >= 2:
            _add(" ".join(words[:2]))
            _add(words[0])

    return candidates[:_KEYWORD_CANDIDATES_LIMIT]


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


def _search_single_keyword(
    operation: str,
    keyword: Optional[str],
    business_type: str,
) -> List[Dict[str, Any]]:
    """단일 키워드에 대해 기존 lookback 루프(7→14→30일) 로 한 번 검색.

    - 조회 기간 로직(min(days, 30) 상한 포함)은 변경 없음
    - 첫 lookback 기간에서 결과가 나오면 즉시 반환
    """
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
            return [_to_internal_bid(item, business_type) for item in items]
    return []


def _search_keyword_with_retry(
    operation: str,
    keyword: Optional[str],
    business_type: str,
) -> List[Dict[str, Any]]:
    """_search_single_keyword 를 짧은 재시도와 함께 감싼다.

    - 일시적 실패(NaraJangteoAPIError, 네트워크/타임아웃 등)는 _PER_KEYWORD_RETRY_DELAY_SEC 간격으로
      _PER_KEYWORD_RETRY_ATTEMPTS 회까지 재시도한다.
    - 모든 시도가 실패하면 마지막 에러를 NaraJangteoAPIError 로 정규화해 raise.
      (호출 측의 try/except NaraJangteoAPIError 가 그대로 동작하도록)
    """
    last_err: Optional[Exception] = None
    for attempt in range(1, _PER_KEYWORD_RETRY_ATTEMPTS + 1):
        try:
            return _search_single_keyword(operation, keyword, business_type)
        except Exception as e:  # 네트워크 타임아웃·NaraJangteoAPIError 모두 흡수
            last_err = e
            if attempt < _PER_KEYWORD_RETRY_ATTEMPTS:
                print(
                    f"[search_bids] keyword={keyword!r} 일시 실패 "
                    f"(시도 {attempt}/{_PER_KEYWORD_RETRY_ATTEMPTS}): {e} "
                    f"— {_PER_KEYWORD_RETRY_DELAY_SEC}s 후 재시도"
                )
                time.sleep(_PER_KEYWORD_RETRY_DELAY_SEC)
    if isinstance(last_err, NaraJangteoAPIError):
        raise last_err
    raise NaraJangteoAPIError(
        f"keyword={keyword!r} 검색 실패 ({_PER_KEYWORD_RETRY_ATTEMPTS}회 시도): {last_err}"
    ) from last_err


def search_bids(keyword: str = None, business_type: str = None) -> List[Dict[str, Any]]:
    """나라장터 입찰공고를 검색하고 내부 형식으로 변환해 반환한다.

    긴/복합 키워드는 _keyword_candidates 로 여러 후보로 분해하고,
    후보별로 단일 키워드 검색을 돌린 뒤 id 기준으로 dedup 해 병합한다.
    """
    resolved_business_type = _resolve_business_type(business_type)
    operation = BUSINESS_TYPE_TO_OPERATION[resolved_business_type]

    candidates = _keyword_candidates(keyword)

    # None/빈 → 키워드 없이 전체 조회 1회 (기존 동작)
    if not candidates:
        print("[search_bids] 키워드 없이 전체 조회")
        return _search_keyword_with_retry(operation, None, resolved_business_type)

    # 짧고 단순한 키워드 → 후보 1개. 기존과 동일하게 1회 검색
    if len(candidates) == 1:
        only = candidates[0]
        print(f"[search_bids] 단일 키워드 검색: {only!r}")
        return _search_keyword_with_retry(operation, only, resolved_business_type)

    # 다중 키워드: 후보별 검색 → id 기준 dedup 병합
    print(f"[search_bids] 다중 키워드 후보 ({len(candidates)}건): {candidates}")
    merged: List[Dict[str, Any]] = []
    seen_ids: set = set()
    last_error: Optional[NaraJangteoAPIError] = None
    any_success = False

    for cand in candidates:
        try:
            results = _search_keyword_with_retry(operation, cand, resolved_business_type)
        except NaraJangteoAPIError as e:
            # 한 키워드가 실패해도 나머지 후보로 계속 진행
            last_error = e
            print(f"[search_bids]   '{cand}' 실패: {e}")
            continue

        any_success = True
        print(f"[search_bids]   '{cand}' -> {len(results)}건")
        for bid in results:
            bid_id = bid.get("id")
            if bid_id and bid_id in seen_ids:
                continue
            if bid_id:
                seen_ids.add(bid_id)
            merged.append(bid)

    # 모든 후보가 실패했으면 마지막 에러 raise
    if not any_success and last_error is not None:
        raise last_error

    print(f"[search_bids] 병합 결과: {len(merged)}건 (dedup 후, 상한 {_MAX_MERGED_RESULTS})")
    return merged[:_MAX_MERGED_RESULTS]
