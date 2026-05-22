"""
제안서 초안 생성
generate_proposal(bid, profile) -> {draft_text, matrix}
revise_proposal(draft, feedback) -> new_draft
summarize_revision_changes(old_draft, new_draft, feedback) -> [수정 이유 불릿, ...]
"""
import json
import re
from typing import Any, Dict, List

from backend.agents.solar_client import SolarClient


PROPOSAL_SECTIONS = [
    "사업 개요 / 제안 배경",
    "사업 이해 및 추진 방향",
    "회사 역량 및 수행 실적",
    "과업별 수행 방안 / 추진 일정",
    "차별화 포인트 (Win Theme)",
    "리스크 및 대응 방안",
    "기대 효과",
]
DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{4}\.\d{1,2}\.\d{1,2}\b|\b\d{4}년\s*\d{1,2}월\s*\d{1,2}일\b")
TEXT_REPLACEMENTS = {
    "TensorFlow/Keras": "검증된 AI 개발 도구",
    "Python 기반 TensorFlow/Keras": "검증된 AI 개발 도구",
    "Apache Kafka와 AWS Kinesis": "확장 가능한 데이터 처리 구성",
    "Airflow": "운영 가능한 배치 처리 구성",
    "AWS KMS와 TLS/SSL": "암호화 체계",
    "IAM 정책": "접근 통제 정책",
    "A/B 테스트": "비교 검증",
    "교차 검증": "성능 검증",
    "침투 테스트": "보안 점검",
    "보안 감사": "보안 점검",
    "주간 스프린트 회의": "정기 점검",
    "주간 회의": "정기 점검",
}


def _build_matrix(bid: Dict[str, Any], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    matrix = []
    for r in bid.get("requirements", []):
        matrix.append({
            "requirement_id": r.get("id"),
            "requirement_text": r.get("text"),
            "response": "회사 역량으로 대응 가능" if any(k.lower() in r.get("text","\n").lower() for k in profile.get("skills", [])) else "추가 자료 필요",
            "weight": r.get("weight")
        })
    return matrix


def _build_evidence_payload(bid: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bid": {
            "id": bid.get("id"),
            "title": bid.get("title"),
            "businessType": bid.get("businessType"),
            "agency": bid.get("agency"),
            "deadline": bid.get("deadline"),
            "budget": bid.get("budget"),
            "estimatedAmount": bid.get("estimatedAmount"),
            "document_summary": bid.get("document_summary"),
            "requirements": bid.get("requirements", [])[:15],
        },
        "profile": {
            "company_id": profile.get("company_id"),
            "name": profile.get("name"),
            "summary": profile.get("summary"),
            "skills": profile.get("skills", []),
            "certifications": profile.get("certifications", []),
            "projects": profile.get("projects", []),
            "headcount": profile.get("headcount"),
        },
    }


def _fallback_proposal_text(bid: Dict[str, Any], profile: Dict[str, Any]) -> str:
    title = bid.get("title") or "공고명 미상"
    company = profile.get("name") or "제안사 미상"
    agency = bid.get("agency") or "발주기관 정보 미상"
    budget = bid.get("budget") or bid.get("estimatedAmount") or "예산 정보 미상"
    requirements = bid.get("requirements", [])
    req_summary = ", ".join(
        r.get("text", "").strip() for r in requirements[:5] if r.get("text")
    ) or "세부 요구사항은 원문 기준으로 재확인이 필요합니다."
    projects = profile.get("projects", [])
    project_summary = "\n".join(
        f"- {p.get('year', '')} {p.get('title', '')} ({p.get('role', '')})"
        for p in projects[:3]
    ) or "- 회사 프로필 기반 수행 실적 추가 확보 필요"

    return f"""# {title}

## 사업 개요 / 제안 배경
본 제안서는 {agency}에서 추진하는 {title}에 대응하기 위해 작성되었습니다. 확인 가능한 공고 정보 기준으로 예산은 {budget}이며, 주요 요구사항은 {req_summary}입니다. 제안사 {company}는 해당 요구사항을 충족할 수 있도록 프로젝트 범위와 산출물 기준을 우선 정리해 제안 전략을 수립합니다.

## 사업 이해 및 추진 방향
본 사업은 요구사항 충족뿐 아니라 실제 운영 관점의 안정성, 일정 준수, 협업 체계를 함께 제시하는 것이 중요합니다. 이에 따라 공고문에 명시된 우선순위를 중심으로 범위를 재구성하고, 착수 초기에는 요구사항 상세화와 위험요소 점검을 병행하는 방향으로 추진합니다.

## 회사 역량 및 수행 실적
{company}는 {profile.get('summary') or '관련 분야 수행 경험을 보유한 기업'}입니다. 보유 역량은 {", ".join(profile.get('skills', [])) or '추가 확인 필요'} 수준으로 확인되며, 관련 수행 실적은 아래와 같습니다.
{project_summary}

## 과업별 수행 방안 / 추진 일정
착수 단계에서는 공고 요구사항과 발주기관 기대사항을 상세 분석하고, 이후 설계 및 실행 단계에서는 핵심 과업별 산출물과 검토 일정을 구체화합니다. 종료 단계에서는 결과물 검수와 이행계획 정리를 통해 실제 사업 수행 가능성을 높이는 방식으로 일정을 운영합니다.

## 차별화 포인트 (Win Theme)
제안 차별화의 핵심은 요구사항을 단순 나열하지 않고, 회사가 보유한 경험과 연결해 실행 가능성 중심으로 설명하는 것입니다. 특히 유사 프로젝트 경험과 기술 역량을 공고 요구와 직접 매핑해 발주기관이 판단하기 쉬운 구조로 제시합니다.

## 리스크 및 대응 방안
현재 확보된 근거만으로 단정하기 어려운 자격, 세부 일정, 추가 인력 요구는 착수 전 점검 항목으로 명시하고 증빙 준비 계획과 함께 관리합니다. 또한 요구사항 해석 차이, 일정 변동, 자료 부족과 같은 리스크는 초기 협의체계를 통해 조기에 완화합니다.

## 기대 효과
본 제안서는 공고 정보와 회사 프로필에 근거해 실현 가능한 수행 방향을 제시하는 데 목적이 있습니다. 이를 통해 발주기관 관점에서는 요구 대응의 명확성을 높이고, 제안사 관점에서는 실제 수행 단계로 이어질 수 있는 실행 중심 계획을 확보할 수 있습니다.
""".strip()


def _sanitize_generated_proposal(draft: str, bid: Dict[str, Any]) -> str:
    if not draft:
        return draft

    allowed_exact_dates = {str(bid.get("deadline")).strip()} if bid.get("deadline") else set()
    lines = draft.splitlines()
    sanitized_lines: List[str] = []
    inside_schedule_section = False

    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## "):
            inside_schedule_section = line == "## 과업별 수행 방안 / 추진 일정"
            sanitized_lines.append(raw_line)
            continue

        if inside_schedule_section:
            found_dates = [match.group(0) for match in DATE_PATTERN.finditer(line)]
            unsupported_dates = [value for value in found_dates if value not in allowed_exact_dates]
            if unsupported_dates:
                sanitized_lines.append(
                    "추진 일정은 착수, 분석·설계, 구현, 검증 및 최종 정리 단계로 운영하며, 세부 마일스톤과 확정 일정은 발주기관 협의 및 착수 후 계획에 맞춰 구체화합니다."
                )
                continue

        sanitized_lines.append(raw_line)

    sanitized = "\n".join(sanitized_lines).strip()
    for source, target in TEXT_REPLACEMENTS.items():
        sanitized = sanitized.replace(source, target)
    sanitized = sanitized.replace("95% 이상", "목표 수준")
    sanitized = sanitized.replace("( headcount )", "")
    return sanitized


def generate_proposal(bid: dict, profile: dict):
    evidence_payload = _build_evidence_payload(bid, profile)
    matrix = _build_matrix(bid, profile)

    system_prompt = """
너는 공공입찰 제안서 작성 에이전트다.
- 반드시 아래 7개 섹션을 모두 포함해 Markdown 본문만 출력한다.
- 각 섹션은 `## 섹션명` 형식의 제목과 최소 한 단락 이상의 실질 내용을 포함한다.
- 공고 정보와 회사 프로필에 근거해 작성하고, 근거에 없는 회사 실적, 수치, 고객명, 인증, 인력, 일정, 성과를 새로 만들지 않는다.
- 공고명, 발주기관, 예산/금액 등 확인 가능한 항목은 본문에 자연스럽게 반영한다.
- 공고문에 없는 세부 일정, 마일스톤 날짜, 사업기간, 착수일, 완료일은 절대 새로 만들지 않는다.
- 일정 정보 근거가 없으면 `착수 단계`, `분석·설계 단계`, `구현 단계`, `검증 단계`처럼 단계 중심으로만 작성한다.
- 요구사항이 비어 있거나 근거가 부족한 부분은 추정하지 말고, 점검/준비/대응 계획 중심으로 서술한다.
- 회사 수행 실적은 profile.projects에 있는 항목만 활용한다.
- profile.headcount는 총인원 수만 언급할 수 있으며, 인력 역할 구성이나 조직 체계는 근거가 없으면 새로 만들지 않는다.
- 외부 파트너, 추가 인증, 감사 체계, 특정 방법론/도구/회의체는 근거가 있을 때만 언급한다.
- 회사 프로필에 없는 자격/등록/소재지/장비/보유 여부는 단정하지 않는다.
- 문체는 간결하지만 제안서답게 설득력 있게 작성한다.
- 서론/메모/주석/면책문 없이 최종 본문만 출력한다.
""".strip()

    user_prompt = f"""
[근거 데이터]
{json.dumps(evidence_payload, ensure_ascii=False, indent=2)}

[작성 지시]
아래 7개 섹션을 모두 포함한 제안서 본문을 작성하라.
1. 사업 개요 / 제안 배경
2. 사업 이해 및 추진 방향
3. 회사 역량 및 수행 실적
4. 과업별 수행 방안 / 추진 일정
5. 차별화 포인트 (Win Theme)
6. 리스크 및 대응 방안
7. 기대 효과

각 섹션은 최소 한 단락 이상의 실질 내용을 포함해야 하며, 공고 요구사항 요약과 회사 프로필 근거를 반영하라.
""".strip()

    draft = ""
    try:
        client = SolarClient()
        draft = client.chat(
            user_prompt,
            system_prompt=system_prompt,
            max_tokens=2800,
        ).strip()
        draft = _sanitize_generated_proposal(draft, bid)
        print("\n" + "=" * 80)
        print("[generate_proposal] Solar Pro3 raw output start")
        print(draft)
        print("[generate_proposal] Solar Pro3 raw output end")
        print(f"[generate_proposal] output_length={len(draft)}")
        print("=" * 80 + "\n")
    except Exception as e:
        print(f"⚠️ [generate_proposal] Solar 생성 실패, 폴백 사용: {e}")

    if not draft:
        draft = _fallback_proposal_text(bid, profile)
        print("\n" + "=" * 80)
        print("[generate_proposal] fallback output start")
        print(draft)
        print("[generate_proposal] fallback output end")
        print(f"[generate_proposal] output_length={len(draft)}")
        print("=" * 80 + "\n")

    return {"draft_text": draft, "matrix": matrix}


def revise_proposal(
    draft: str,
    feedback: str,
    bid: dict | None = None,
    profile: dict | None = None,
    assessment: dict | None = None,
    evaluation: dict | None = None,
    match_result: dict | None = None
):
    """PM 피드백을 바탕으로 Solar Pro3에게 수정본 작성을 요청한다.

    해커톤 MVP 안정성을 위해 Solar 호출 실패 시에는 기존 draft에
    피드백을 덧붙이는 폴백을 사용한다.
    """
    bid = bid or {}
    profile = profile or {}
    assessment = assessment or {}
    evaluation = evaluation or {}
    match_result = match_result or {}

    evidence_payload = {
        "bid": {
            "title": bid.get("title"),
            "businessType": bid.get("businessType"),
            "agency": bid.get("agency"),
            "deadline": bid.get("deadline"),
            "budget": bid.get("budget"),
            "estimatedAmount": bid.get("estimatedAmount"),
            "document_summary": bid.get("document_summary"),
            "requirements": bid.get("requirements", [])[:12],
        },
        "profile": {
            "name": profile.get("name"),
            "summary": profile.get("summary"),
            "skills": profile.get("skills", []),
            "certifications": profile.get("certifications", []),
            "projects": profile.get("projects", []),
            "headcount": profile.get("headcount"),
        },
        "assessment": assessment,
        "evaluation": evaluation,
        "match_result": match_result,
    }

    system_prompt = """
너는 공공입찰 제안서 수정 에이전트다.
- 기존 초안의 구조를 최대한 유지한다.
- PM 피드백을 반영해 문장을 더 구체적이고 설득력 있게 다듬는다.
- 아래 7개 섹션이 빠지지 않도록 유지한다.
- 각 섹션은 `## 섹션명` 형식을 유지하고, 피드백을 반영해 본문 자체를 다시 쓴다.
- 아래 [근거 데이터]에 없는 회사 실적, 수치, 고객명, 인증, 인력, 일정, 장비, 성과를 새로 만들지 않는다.
- 공고문에 없는 세부 일정, 마일스톤 날짜, 사업기간, 착수일, 완료일은 절대 새로 만들지 않는다.
- 근거가 없는 항목은 일반적 표현으로만 완화해서 작성하고, 구체값을 지어내지 않는다.
- profile.headcount는 총인원 수만 언급할 수 있으며, 인력 역할 구성이나 조직 체계는 근거가 없으면 새로 만들지 않는다.
- 외부 파트너, 추가 인증, 감사 체계, 특정 방법론/도구/회의체는 근거가 있을 때만 언급한다.
- 기존 초안에 있더라도 [근거 데이터]에 없는 구체 사실은 삭제하거나 보수적 표현으로 바꾼다.
- 입찰 자격요건 문장은, 회사 프로필에 명시적 근거가 없으면 "이미 보유/완료/충족"처럼 단정하지 말고
  "충족 여부를 점검하고 증빙을 준비한다", "관련 요건에 맞춰 대응한다"처럼 써라.
- 회사 개요 섹션에서도 profile에 없는 항목(설립연도, 본사 소재지, 법인 형태 등)은 새로 만들지 말고 아예 생략하라.
- 과장 표현(완벽, 100%, 절대 보장)은 피한다.
- Markdown 본문만 출력하고, 설명/주석/면책문은 붙이지 않는다.
""".strip()

    user_prompt = f"""
[근거 데이터]
{json.dumps(evidence_payload, ensure_ascii=False, indent=2)}

[기존 초안]
{draft}

[PM 피드백]
{feedback}

[수정 지시]
1. 피드백을 반영해 제안서 초안을 다시 작성하라.
2. 기존 초안보다 더 명확한 구조와 문장으로 정리하라.
3. [근거 데이터]에 없는 고유명사/수치/실적/인증/성과는 추가하지 마라.
4. 특히 회사 수행실적은 profile.projects에 있는 내용만 활용하라.
5. 요구사항 대응과 리스크 완화는 bid.requirements, assessment, evaluation 범위 안에서만 서술하라.
6. 회사 프로필에 없는 자격/등록/소재지/장비 보유는 충족 사실처럼 단정하지 말고 준비/점검/대응 계획으로 써라.
7. profile에 없는 회사 일반정보(설립연도, 주소, 법인형태 등)는 쓰지 말고, 해당 항목이 필요하면 생략하라.
8. 결과는 설명 없이 수정된 본문만 출력하라.
9. 아래 섹션을 모두 유지하라: {", ".join(PROPOSAL_SECTIONS)}.
10. 일정 정보 근거가 없으면 단계 중심 일정으로만 작성하라.
""".strip()

    try:
        client = SolarClient()
        revised = client.chat(
            user_prompt,
            system_prompt=system_prompt,
            max_tokens=3200,
        ).strip()
        revised = _sanitize_generated_proposal(revised, bid)
        print("\n" + "=" * 80)
        print("[revise_proposal] Solar Pro3 raw output start")
        print(revised)
        print("[revise_proposal] Solar Pro3 raw output end")
        print(f"[revise_proposal] output_length={len(revised)}")
        print("=" * 80 + "\n")
        if revised:
            return revised
    except Exception as e:
        print(f"⚠️ [revise_proposal] Solar 재작성 실패, 폴백 사용: {e}")

    return draft + "\n\n[PM 피드백 반영 - 폴백]\n" + feedback


def _parse_revision_bullets(text: str) -> List[str]:
    """모델 출력에서 불릿 줄을 뽑아 문자열 리스트로 정리한다."""
    if not text:
        return []
    bullets: List[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # `- `, `* `, `• `, `1.`, `1)` 등 흔한 불릿 prefix 제거
        cleaned = re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", line).strip()
        # 마크다운 강조 기호 제거 (본문 형식과 일관)
        cleaned = cleaned.replace("**", "").strip()
        if cleaned:
            bullets.append(cleaned)
    return bullets


def summarize_revision_changes(
    old_draft: str,
    new_draft: str,
    feedback: str,
    bid: dict | None = None,
    profile: dict | None = None,
) -> List[str]:
    """기존 초안 → 수정본 변화와 PM 피드백을 바탕으로 "무엇을 왜 바꿨는지"를
    3~5개의 짧은 한국어 불릿으로 요약해 문자열 리스트로 반환한다.

    - 본문 작성 동작과 분리되어 있어 revise_proposal 의 출력은 그대로 둔다.
    - Solar 호출 실패 시 안전한 폴백 메시지 1건을 담은 리스트를 반환한다.
    """
    bid = bid or {}
    profile = profile or {}

    evidence_payload = {
        "bid": {
            "title": bid.get("title"),
            "agency": bid.get("agency"),
            "deadline": bid.get("deadline"),
            "requirements": bid.get("requirements", [])[:8],
        },
        "profile": {
            "name": profile.get("name"),
            "skills": profile.get("skills", []),
            "projects": profile.get("projects", []),
        },
    }

    system_prompt = """
너는 공공입찰 제안서 수정 사유 요약 에이전트다.
- 기존 초안과 수정본을 비교해서 "무엇을 왜 바꿨는지"를 한국어로 3~5개의 짧은 불릿으로만 요약한다.
- 각 불릿은 한 문장으로 작성하고, "변경 내용 — 변경 이유" 형태가 자연스럽다.
- PM 피드백이 반영된 부분은 1개 이상 반드시 포함한다.
- [근거 데이터]에 없는 회사 실적, 수치, 일정, 인증 등은 추가하지 마라. 본문에 실제로 나타난 변화만 근거로 한다.
- 출력은 오직 불릿 목록만. 머리말/꼬리말/번호 매기기/설명/마크다운 표는 붙이지 마라.
- 각 불릿은 `- ` 로 시작한다.
""".strip()

    user_prompt = f"""
[근거 데이터]
{json.dumps(evidence_payload, ensure_ascii=False, indent=2)}

[PM 피드백]
{feedback}

[기존 초안]
{old_draft}

[수정본]
{new_draft}

[지시]
위 변경에서 PM 피드백 반영을 중심으로 무엇을 왜 바꿨는지 3~5개의 짧은 한국어 불릿으로만 요약하라.
""".strip()

    fallback: List[str] = ["PM 피드백을 반영해 본문을 다시 작성함"]

    try:
        client = SolarClient()
        raw = client.chat(
            user_prompt,
            system_prompt=system_prompt,
            max_tokens=600,
        ).strip()
        print("\n" + "=" * 80)
        print("[summarize_revision_changes] Solar Pro3 raw output start")
        print(raw)
        print("[summarize_revision_changes] Solar Pro3 raw output end")
        print("=" * 80 + "\n")
        bullets = _parse_revision_bullets(raw)
        if bullets:
            # 너무 많이 오면 5개까지만 사용
            return bullets[:5]
    except Exception as e:
        print(f"⚠️ [summarize_revision_changes] Solar 호출 실패, 폴백 사용: {e}")

    return fallback
