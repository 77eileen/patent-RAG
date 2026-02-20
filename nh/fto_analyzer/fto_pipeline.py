"""
FTO 분석 3단계 파이프라인

Step A: 특허 청구항에서 구성요소 추출
Step B: 구성 대비 (사용자 제품 vs 특허)
Step C: 판단 및 결론

미등록 특허는 LLM 분석 없이 고정 템플릿 사용
"""

import json
import google.generativeai as genai
from .config import get_model
from .prompts import STEP_A_PROMPT, STEP_B_PROMPT, STEP_C_PROMPT


# ============================================
# 등록 여부 판정
# ============================================

def is_patent_registered(patent: dict) -> bool:
    """
    특허의 등록 여부를 판정

    미등록 판정 기준:
    - register_number가 없거나 빈 문자열
    - register_status가 "등록"이 아닌 경우 (공개, 출원, 거절, 취하 등)

    Returns:
        True: 등록 특허, False: 미등록
    """
    reg_num = patent.get('register_number', '')
    reg_status = patent.get('register_status', '')

    if not reg_num or str(reg_num).strip() == '':
        return False

    if reg_status != '등록':
        return False

    return True


# ============================================
# 청구항 텍스트 관련 유틸리티
# ============================================

def extract_independent_claim(all_claims):
    """
    특허의 all_claims에서 첫 번째 독립항 텍스트를 추출

    - 등록 청구항 우선
    - 청구항 1이 (삭제)이면 다음 독립항 탐색
    - dict 형식과 string 형식 모두 지원
    """
    if not all_claims:
        return None

    # dict 형식
    if isinstance(all_claims[0], dict):
        registered = [c for c in all_claims if c.get('source_type') in ('registered', '등록')]
        pool = registered if registered else all_claims

        sorted_claims = sorted(pool, key=lambda c: int(c.get('claim_number', 999)))

        for claim in sorted_claims:
            if claim.get('claim_type') == 'independent':
                text = claim.get('text', '').strip()
                if text and '(삭제)' not in text:
                    return text

        for claim in sorted_claims:
            text = claim.get('text', '').strip()
            if text and '(삭제)' not in text:
                return text

    # string 형식
    elif isinstance(all_claims[0], str):
        for claim_str in all_claims:
            if '(삭제)' not in claim_str:
                return claim_str

    return None


def format_claims_text(all_claims) -> str:
    """
    all_claims를 읽기 좋은 텍스트로 변환 (미등록 특허 템플릿용)
    마지막 버전(최신) 청구항을 반환
    """
    if not all_claims:
        return "(청구항 없음)"

    # dict 형식
    if isinstance(all_claims[0], dict):
        lines = []
        seen = set()
        for claim in sorted(all_claims, key=lambda c: int(c.get('claim_number', 999))):
            num = claim.get('claim_number', '')
            text = claim.get('text', '').strip()
            if text and num not in seen and '(삭제)' not in text:
                seen.add(num)
                lines.append(f"[청구항 {num}] {text}")
        return "\n\n".join(lines) if lines else "(청구항 없음)"

    # string 형식
    elif isinstance(all_claims[0], str):
        valid = [c for c in all_claims if '(삭제)' not in c]
        return "\n\n".join(valid) if valid else "(청구항 없음)"

    return "(청구항 없음)"


def get_unregistered_template(patent: dict) -> str:
    """미등록(공개) 특허용 고정 템플릿 메시지 생성"""
    return (
        "검색 결과, 사용자의 제품 구성과 유사한 내용을 포함하는 공개특허가 "
        "확인되었습니다. 해당 문헌은 현재 출원 공개 단계로, 아직 권리가 "
        "확정된 상태는 아닙니다. 다만 향후 심사 과정에서 등록될 경우 "
        "권리가 발생할 수 있으므로, 심사 진행 및 등록 여부를 지속적으로 "
        "모니터링하시길 권장드립니다."
    )


# ============================================
# Step A: 구성요소 추출
# ============================================

def step_a_extract_components(claim_text: str) -> list:
    """
    Step A: 청구항에서 구성요소 추출

    Returns:
        list: 구성요소 리스트 (JSON 배열)
    """
    model = get_model()
    prompt = f"{STEP_A_PROMPT}\n\n## 분석할 청구항\n{claim_text}"

    response = model.generate_content(
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json"
        )
    )

    result = json.loads(response.text)

    if isinstance(result, dict) and 'components' in result:
        return result['components']
    if isinstance(result, list):
        return result

    return []


# ============================================
# Step B: 구성 대비
# ============================================

def step_b_compare(patent_components: list, user_query: str, user_components: str) -> dict:
    """
    Step B: 구성 대비

    Returns:
        dict: 구성대비 결과 (comparison 키 포함)
    """
    model = get_model()
    user_input = f"""## 특허 구성요소
{json.dumps(patent_components, ensure_ascii=False)}

## 사용자 질문
{user_query}

## 사용자 제품 구성요소
{user_components}"""

    prompt = f"{STEP_B_PROMPT}\n\n{user_input}"

    response = model.generate_content(
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json"
        )
    )

    result = json.loads(response.text)

    if isinstance(result, dict) and 'comparison' in result:
        return result
    if isinstance(result, list):
        return {"comparison": result}

    return {"comparison": []}


# ============================================
# Step C: 판단 및 결론
# ============================================

def step_c_judge(comparison_result: dict) -> dict:
    """
    Step C: 판단 및 결론

    Returns:
        dict: {"judgment": "...", "conclusion": "..."}
    """
    model = get_model()
    user_input = f"""## 구성 대비 결과
{json.dumps(comparison_result, ensure_ascii=False)}"""

    prompt = f"{STEP_C_PROMPT}\n\n{user_input}"

    response = model.generate_content(
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        generation_config=genai.GenerationConfig(
            temperature=0,
            response_mime_type="application/json"
        )
    )

    result = json.loads(response.text)

    if 'judgment' not in result:
        result['judgment'] = '분석 결과를 생성할 수 없습니다.'
    if 'conclusion' not in result:
        result['conclusion'] = '침해 여부 분석을 위해 보다 구체적인 실시 정보가 필요합니다.'

    return result


# ============================================
# 단일 특허 분석 (등록/미등록 분기)
# ============================================

def analyze_single_patent(patent: dict, user_query: str, user_components: str) -> dict:
    """
    단일 특허에 대해 분석 수행

    - 등록 특허: Step A → B → C 순차 실행
    - 미등록 특허: LLM 호출 없이 고정 템플릿 반환

    Returns:
        dict: analysis_results 항목
    """

    base_info = {
        'rank': patent.get('rank', 0),
        'application_number': patent.get('application_number', ''),
        'register_number': patent.get('register_number', ''),
        'open_number': patent.get('open_number', ''),
        'register_status': patent.get('register_status', ''),
        'title': patent.get('title', ''),
    }

    # ── 미등록 특허: LLM 스킵 ──
    if not is_patent_registered(patent):
        claims_text = format_claims_text(patent.get('all_claims', []))
        return {
            **base_info,
            'is_registered': False,
            'pub_number': patent.get('open_number', patent.get('application_number', '')),
            'claims_text': claims_text,
            'template_message': get_unregistered_template(patent),
            'success': True,
            'error': None,
        }

    # ── 등록 특허: Step A → B → C ──
    result = {
        **base_info,
        'is_registered': True,
        'success': False,
        'error': None,
        'claim_text': None,
        'components': None,
        'comparison': None,
        'judgment': None,
        'conclusion': None,
    }

    try:
        # 독립항 추출
        claim_text = extract_independent_claim(patent.get('all_claims', []))
        if not claim_text:
            result['error'] = '독립항을 찾을 수 없습니다.'
            return result

        result['claim_text'] = claim_text

        # Step A: 구성요소 추출
        patent_components = step_a_extract_components(claim_text)
        result['components'] = patent_components

        # Step B: 구성 대비
        comparison = step_b_compare(patent_components, user_query, user_components)
        result['comparison'] = comparison

        # Step C: 판단 및 결론
        judgment_result = step_c_judge(comparison)
        result['judgment'] = judgment_result.get('judgment', '')
        result['conclusion'] = judgment_result.get('conclusion', '')

        result['success'] = True

    except Exception as e:
        result['error'] = str(e)

    return result
