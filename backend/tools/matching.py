"""
Requirement Matching & Scoring (mock)
요구사항 리스트와 회사 프로필을 받아 항목별 적합도와 전체 Win Probability를 계산한다.
"""
import re


def _tokenize(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^0-9a-zA-Z가-힣]+", (text or "").lower())
        if len(token) >= 2
    ]


def _token_overlap_score(requirement_text: str, candidate_texts: list[str]) -> int:
    req_tokens = set(_tokenize(requirement_text))
    if not req_tokens:
        return 0

    best_score = 0
    for candidate_text in candidate_texts:
        candidate_tokens = set(_tokenize(candidate_text))
        if not candidate_tokens:
            continue
        overlap = req_tokens & candidate_tokens
        if not overlap:
            continue
        ratio = len(overlap) / max(len(req_tokens), 1)
        if ratio >= 0.5:
            best_score = max(best_score, 90)
        elif ratio >= 0.3:
            best_score = max(best_score, 75)
        else:
            best_score = max(best_score, 60)
    return best_score


def _is_procedural_requirement(requirement_type: str, requirement_text: str) -> bool:
    return requirement_type in {"제출서류", "평가"} or any(
        keyword in requirement_text for keyword in ("제출", "서류", "평가", "심사", "계획서")
    )


def _base_score_for_requirement(requirement_type: str, requirement_text: str) -> int:
    if _is_procedural_requirement(requirement_type, requirement_text):
        return 45
    if any(keyword in requirement_text for keyword in ("실적", "경험")):
        return 35
    return 20

def match_requirements(requirements: list, profile: dict, proposal_text: str = None):
    """매칭 알고리즘(간단한 룰 기반)
    - 각 요구사항에 대해 회사 skills/certifications/projects에서 키워드 매칭
    - 항목별 점수: 0~100
    - 전체 Win Probability: 가중평균과 일부 휴리스틱 반영
    - proposal_text 가 주어지면 회사 프로필 외에 제안서 본문도 토큰 유사도 매칭 근거에 포함한다.
    """
    skills = [s.lower() for s in profile.get("skills", [])]
    certs = [c.lower() for c in profile.get("certifications", [])]
    projects = [p.get("title", "").lower() for p in profile.get("projects", [])]
    summary = (profile.get("summary") or "").lower()
    company_name = (profile.get("name") or "").lower()
    evidence_pool = skills + certs + projects + [summary, company_name]
    # 제안서 본문이 들어오면 토큰 매칭 근거 풀에 포함 (skill/cert 단어 매칭 규칙은 그대로 유지)
    if proposal_text:
        evidence_pool = evidence_pool + [proposal_text.lower()]

    total_weight = 0
    weighted_score_sum = 0
    details = []

    for r in requirements:
        weight = r.get("weight", 0)
        total_weight += weight
        text = r.get("text", "").lower()
        req_type = r.get("type", "")
        score = 0

        # 스킬 매칭
        for s in skills:
            if s in text:
                score = max(score, 80)
        # 인증 매칭
        for c in certs:
            if c in text:
                score = max(score, 90)
        # 프로젝트 매칭(유사 프로젝트)
        for p in projects:
            if p in text:
                score = max(score, 85)
        # 토큰 수준 유사도 기반 보완
        score = max(score, _token_overlap_score(text, evidence_pool))
        # 직접 매칭이 약해도 문서성/절차성 항목은 최소 준비 점수를 부여
        if score == 0:
            score = _base_score_for_requirement(req_type, text)
        # 요구사항이 가볍다면 최소 점수
        if weight == 0 and score == 0:
            score = 60

        weighted_score_sum += score * weight
        details.append({"req_id": r.get("id"), "text": r.get("text"), "score": score, "weight": weight})

    overall = int((weighted_score_sum / total_weight) if total_weight > 0 else 0)

    # 단순 Win Probability 휴리스틱
    win_prob = overall
    # 보정: 인증/프로젝트가 충분하면 +10
    if len(certs) > 0 and len(projects) > 0:
        win_prob = min(100, win_prob + 10)

    return {"overall_score": overall, "win_probability": win_prob, "details": details}
