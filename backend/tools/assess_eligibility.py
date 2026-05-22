"""
자격 판단 규칙
assess_eligibility(bid, profile) -> {eligible: bool, reasons: [], details: []}
"""
import re


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^0-9a-zA-Z가-힣]+", (text or "").lower())
        if len(token) >= 2
    ]


def _requirement_match_ratio(text: str, profile_texts: list[str]) -> float:
    req_tokens = set(_tokenize(text))
    if not req_tokens:
        return 0.0

    best_ratio = 0.0
    for profile_text in profile_texts:
        profile_tokens = set(_tokenize(profile_text))
        if not profile_tokens:
            continue
        overlap = req_tokens & profile_tokens
        if not overlap:
            continue
        ratio = len(overlap) / max(len(req_tokens), 1)
        if ratio > best_ratio:
            best_ratio = ratio
    return best_ratio


def _is_procedural_requirement(requirement: dict) -> bool:
    req_type = requirement.get("type", "")
    text = requirement.get("text", "")
    return req_type in {"제출서류", "평가"} or any(
        keyword in text for keyword in ("제출", "서류", "평가", "심사", "계획서")
    )


def _is_critical_requirement(requirement: dict) -> bool:
    req_type = requirement.get("type", "")
    text = requirement.get("text", "")
    return req_type == "인증" or any(keyword in text for keyword in ("면허", "등록", "자격", "허가"))


def assess_eligibility(bid: dict, profile: dict):
    """간단 규칙 기반 자격 판단
    - 완전 매칭만 보지 않고 토큰 유사도와 절차성 항목을 함께 반영한다.
    - 자격/허가/등록 같은 치명 요건은 별도로 추적한다.
    """
    reasons = []
    total_weight = 0
    matched_weight = 0
    details = []

    reqs = bid.get("requirements", [])
    skills = [s.lower() for s in profile.get("skills", [])]
    certs = [c.lower() for c in profile.get("certifications", [])]
    projects = [p.get("title", "").lower() for p in profile.get("projects", [])]
    summary = (profile.get("summary") or "").lower()
    profile_texts = skills + certs + projects + [summary]
    critical_missing = False

    for r in reqs:
        total_weight += r.get("weight", 0)
        text = r.get("text", "").lower()
        weight = r.get("weight", 0)
        ratio = _requirement_match_ratio(text, profile_texts)
        matched = any(skill in text for skill in skills) or any(cert in text for cert in certs)

        if matched or ratio >= 0.45:
            matched_weight += weight
            details.append({"req": r.get("id"), "status": "matched", "weight": weight, "ratio": round(ratio, 2)})
        elif _is_procedural_requirement(r):
            matched_weight += weight * 0.5
            details.append({"req": r.get("id"), "status": "review_needed", "weight": weight, "ratio": round(ratio, 2)})
        else:
            reasons.append(f"요구사항 미충족: {r.get('text')}")
            details.append({"req": r.get("id"), "status": "missing", "weight": weight, "ratio": round(ratio, 2)})
            if _is_critical_requirement(r):
                critical_missing = True

    match_score = int((matched_weight / total_weight) * 100) if total_weight > 0 else 0
    eligible = match_score >= 60 and not critical_missing

    return {
        "eligible": eligible,
        "match_score": match_score,
        "details": details,
        "reasons": reasons
    }
