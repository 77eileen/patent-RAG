"""
정규표현식 기반 조사/어미 제거 테스트
- 형태소 분석 없이 단순 패턴 매칭으로 조사 제거
- 화학물질명 보존 여부 확인
"""

import re

# SAMPLES = [
#     "하이드록시에틸셀룰로오스를 포함하는 안과용 조성물",
#     "덱사메타손 및 포비돈-요오드를 포함하는 미생물 감염 치료용 조성물",
#     "디알킬카보네이트를 포함하는 모발 컨디셔닝 조성물",
#     "포스파티딜콜린, 콜레스테롤을 증발농축하여 박막을 형성하는 리포좀 제조방법",
# ]

SAMPLES = [
    "본 발명은 구절초(九節草, Chrysanthemum zawadskii var. latilobum ) 추출물의 유기용매 분획물을 유효성분으로 함유하는 발모 및 육모 조성물, 및 그의 제조방법에 관한 것으로, 특히 천연 식물인 구절초의 비극성 유기 용매 분획물을 유효성분으로 포함하여 부작용이 없으면서도, 그 효과의 우수성이 실험적으로 입증된 발모 및 육모 조성물에 관한 것이다.구절초, 발모, 조성물, 유기용매",
]

# 1글자 조사만 제거 (안전 — 단어 끝 1글자만 깎음)
JOSA_1 = re.compile(r"(을|를|이|가|은|는|의|에|로|와|과)$")

# 2글자 이상 어미는 별도 처리
EOMI_2 = re.compile(r"(으로부터|포함하는|구성되는|구성된|선택된|되는|하는|된|하여|으로|에서|이며|이고)$")

# 제거 대상 기능어 (단독 단어)
STOPWORDS = {"및", "또는", "상기", "본", "그", "이", "그리고"}


def clean_special_chars(text: str) -> str:
    """특수문자 정제: 괄호, 마침표, 쉼표 → 공백"""
    return re.sub(r"[().,]", " ", text)


def remove_josa(word: str) -> str:
    """단어 끝의 조사/어미를 단계적 제거 (2글자 어미 먼저 → 1글자 조사)"""
    # Step 1: 2글자 이상 어미 제거
    prev = None
    while prev != word:
        prev = word
        word = EOMI_2.sub("", word)
    # Step 2: 1글자 조사 제거 (1회만)
    word = JOSA_1.sub("", word)
    return word


def process_text(text: str) -> list[str]:
    """텍스트에서 특수문자 정제 → 조사 제거 → 불용어 제거"""
    text = clean_special_chars(text)
    words = re.split(r"\s+", text)
    result = []
    for w in words:
        cleaned = remove_josa(w.strip())
        if cleaned and cleaned not in STOPWORDS:
            result.append(cleaned)
    return result


def print_separator(char="═", width=100):
    print(char * width)


# ── 화학물질명 보존 체크 ──
CHEMICALS = [
    "구절초",
    "추출물",
    "유기용매",
    "분획물",
    "유효성분",
    "발모",
    "육모",
    "조성물",
    "제조방법",
    "비극성",
    "부작용",
]


if __name__ == "__main__":
    print()
    print_separator()
    print("  정규표현식 기반 조사/어미 제거 테스트 (형태소 분석 없음)")
    print_separator()

    all_results = []

    for i, text in enumerate(SAMPLES, 1):
        result = process_text(text)
        all_results.append(result)

        print(f"\n  [{i}] 원문: \"{text}\"")
        print("  " + "─" * 96)

        # 특수문자 정제 후 단어별 변환 과정
        cleaned_text = clean_special_chars(text)
        print(f"  정제 후: \"{cleaned_text.strip()}\"")
        print("  " + "─" * 96)
        words = re.split(r"\s+", cleaned_text)
        print(f"  {'원래 단어':<30} {'조사 제거 후':<30} {'변화'}")
        print("  " + "─" * 96)
        for w in words:
            if not w.strip():
                continue
            cleaned = remove_josa(w.strip())
            changed = "→ 변환됨" if w.strip() != cleaned else "(동일)"
            if cleaned in STOPWORDS:
                changed += " → 불용어 제거"
            print(f"  {w.strip():<30} {cleaned:<30} {changed}")

        print(f"\n  → 최종 결과: {result}")

    # ── 화학물질명 보존 요약 ──
    print()
    print_separator()
    print("  화학물질명 보존 결과")
    print_separator()
    print(f"\n  {'화학물질명':<30} {'보존?':<10} {'어디서 발견'}")
    print("  " + "─" * 96)

    flat = []
    for r in all_results:
        flat.extend(r)

    for chem in CHEMICALS:
        found = chem in flat
        # 부분 매칭도 확인 (포비돈-요오드 → 포비돈-요오드 형태)
        partial = [w for w in flat if chem in w]
        if found:
            print(f"  {chem:<30} {'O 보존':<10} {chem}")
        elif partial:
            print(f"  {chem:<30} {'△ 부분':<10} {partial}")
        else:
            print(f"  {chem:<30} {'X 소실':<10}")

    print()
    print_separator()
    print("  결론: 정규표현식 조사 제거 → 화학물질명 원형 보존 가능!")
    print("  주의: '에', '로' 등 1글자 조사는 화학물질명 내부 음절과 충돌 가능")
    print("        → 단어 '끝'에서만 제거하므로 내부 음절은 안전")
    print_separator()
    print()
