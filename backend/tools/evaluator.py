"""
Red Team 간단 평가 (리스크 탐지)
"""

def evaluate_proposal(draft: str, bid: dict, profile: dict, match_result: dict = None, assessment: dict = None):
    """Evaluator 강화:
    - 과다 약속(overpromise) 문구 탐지
    - 요구사항 미충족 항목을 리스크로 표기
    - 권고사항 생성(증빙 요청, 문구 완화 등)
    """
    risks = []
    recommendations = []

    # 1) 과다 약속 표현 체크
    risk_phrases = ["완벽", "100%", "절대", "보장"]
    for p in risk_phrases:
        if p in draft:
            risks.append({"type": "overpromise", "text": f"위험 표현 발견: '{p}'"})
            recommendations.append("약속 표현을 완화하고 구체적 근거(수치/실적)를 추가하세요.")

    # 2) 요구사항 미충족 기반 리스크
    missing = []
    if assessment:
        for d in assessment.get('details', []):
            if d.get('status') == 'missing':
                missing.append(d)
                risks.append({"type": "missing_requirement", "text": f"요구사항 미충족: {d.get('req')}"})
                recommendations.append(f"요구사항 {d.get('req')} 관련 증빙(실적/인증)을 제출하세요.")
            if d.get('status') == 'review_needed':
                recommendations.append(f"요구사항 {d.get('req')} 항목은 증빙 서류와 대응 계획을 명확히 제시하세요.")

    # 3) 매칭 결과 기반 권고 (약한 항목에 대해 보완 제안)
    if match_result:
        low_items = [d for d in match_result.get('details', []) if d.get('score', 0) < 60]
        for li in low_items:
            recommendations.append(f"'{li.get('text')}' 항목은 점수({li.get('score')})가 낮습니다. 구체적 증빙/방법론을 추가하세요.")

        overall_score = match_result.get("overall_score", 0) or 0
        if overall_score < 50:
            risks.append({"type": "low_match_score", "text": f"전체 적합도가 낮습니다: {overall_score}"})
            recommendations.append("공고 핵심 자격요건과 직접 연결되는 실적, 인증, 수행 범위를 더 명확히 보강하세요.")
        elif overall_score < 70:
            recommendations.append("중간 수준 적합도로 판단됩니다. 핵심 요구사항별 대응 근거를 표 형식으로 더 명확히 제시하세요.")

    if assessment:
        match_score = assessment.get("match_score", 0) or 0
        if match_score < 50:
            risks.append({"type": "low_eligibility_score", "text": f"자격 매칭 점수가 낮습니다: {match_score}"})
        elif match_score < 70:
            recommendations.append("자격 매칭 점수가 경계 수준입니다. 필수 등록·허가·제출서류 준비 상태를 분명히 표시하세요.")

    # Risk scoring: 기본 0, 항목당 가중치
    risk_score = 0
    risk_score += sum(10 for _ in risks)
    # 매칭 낮은 항목이 많으면 추가
    if match_result:
        low_count = len([d for d in match_result.get('details', []) if d.get('score', 0) < 60])
        risk_score += low_count * 5
        overall_score = match_result.get("overall_score", 0) or 0
        risk_score += max(0, 60 - overall_score) // 3
    if assessment:
        match_score = assessment.get("match_score", 0) or 0
        risk_score += max(0, 50 - match_score) // 4

    unique_recommendations = []
    seen = set()
    for item in recommendations:
        if item in seen:
            continue
        seen.add(item)
        unique_recommendations.append(item)

    return {
        "risks": risks,
        "recommendations": unique_recommendations,
        "risk_score": risk_score
    }
