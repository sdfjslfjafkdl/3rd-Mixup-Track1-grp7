"""
SearchAgent
- 공고 검색 (search_bids 툴 호출)
"""
from typing import List, Dict, Any, Callable
from backend.tools.search_bids import search_bids


class SearchAgent:
    def __init__(self, log: Callable[[str], None], record_tool: Callable[[str], None]):
        self.log = log
        self.record_tool = record_tool

    def run(self, keyword: str = None, business_type: str = None) -> List[Dict[str, Any]]:
        """검색 조건으로 공고 목록을 반환한다."""
        self.record_tool("search_bids")
        self.log("Phase 1: 공고 검색 호출 (search_bids)")
        bids = search_bids(keyword=keyword, business_type=business_type)
        self.log(f"수집된 공고 수: {len(bids)}")
        return bids
