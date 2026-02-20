"""
형태소 분석기 비교 테스트: Kiwipiepy vs Okt vs Komoran
- 특허 화학물질명이 올바르게 추출되는지 확인
"""

from kiwipiepy import Kiwi
from konlpy.tag import Okt, Komoran

# ── 샘플 텍스트 ──
SAMPLES = [
    "하이드록시에틸셀룰로오스를 포함하는 안과용 조성물",
    "덱사메타손 및 포비돈-요오드를 포함하는 미생물 감염 치료용 조성물",
    "디알킬카보네이트를 포함하는 모발 컨디셔닝 조성물",
    "포스파티딜콜린, 콜레스테롤을 증발농축하여 박막을 형성하는 리포좀 제조방법",
]

# ── 분석기 초기화 ──
kiwi = Kiwi()
okt = Okt()
komoran = Komoran()


def extract_nouns_kiwi(text: str) -> list[str]:
    """Kiwi: NNG(일반명사) + NNP(고유명사) 태그 추출"""
    tokens = kiwi.tokenize(text)
    return [t.form for t in tokens if t.tag in ("NNG", "NNP")]


def extract_nouns_okt(text: str) -> list[str]:
    return okt.nouns(text)


def extract_nouns_komoran(text: str) -> list[str]:
    return komoran.nouns(text)


# ── 결과 출력 ──
def print_separator(char="═", width=120):
    print(char * width)


def print_comparison_table():
    print()
    print_separator()
    print("  형태소 분석기 비교: 특허 화학물질명 명사 추출")
    print_separator()

    for i, text in enumerate(SAMPLES, 1):
        print(f"\n  [{i}] \"{text}\"")
        print("  " + "─" * 116)

        kiwi_nouns = extract_nouns_kiwi(text)
        okt_nouns = extract_nouns_okt(text)
        komoran_nouns = extract_nouns_komoran(text)

        # 표 헤더
        print(f"  {'분석기':<12} {'추출 명사':<80} {'개수':>5}")
        print("  " + "─" * 116)
        print(f"  {'Kiwi':<12} {', '.join(kiwi_nouns):<80} {len(kiwi_nouns):>5}")
        print(f"  {'Okt':<12} {', '.join(okt_nouns):<80} {len(okt_nouns):>5}")
        print(f"  {'Komoran':<12} {', '.join(komoran_nouns):<80} {len(komoran_nouns):>5}")

        # 화학물질명 쪼개짐 분석
        print()
        print("  [화학물질명 보존 분석]")
        _analyze_chemical_preservation(text, kiwi_nouns, okt_nouns, komoran_nouns)

    print()
    print_separator()
    print_summary()


def _analyze_chemical_preservation(text, kiwi_nouns, okt_nouns, komoran_nouns):
    """화학물질명이 쪼개졌는지 간단 분석"""
    # 원문에서 화학물질 후보 (긴 한글 토큰)
    chemicals = [
        "하이드록시에틸셀룰로오스",
        "덱사메타손",
        "포비돈",
        "요오드",
        "디알킬카보네이트",
        "포스파티딜콜린",
        "콜레스테롤",
        "리포좀",
    ]

    relevant = [c for c in chemicals if c in text]
    if not relevant:
        return

    for chem in relevant:
        k = "O" if chem in kiwi_nouns else "X (쪼개짐)"
        o = "O" if chem in okt_nouns else "X (쪼개짐)"
        m = "O" if chem in komoran_nouns else "X (쪼개짐)"
        print(f"    {chem:<25} Kiwi: {k:<15} Okt: {o:<15} Komoran: {m}")


def print_summary():
    print("\n  [종합 요약]")
    print("  " + "─" * 116)
    print("  - Kiwi   : 사전 미등록 복합어를 형태소 단위로 분리하는 경향")
    print("  - Okt    : 미등록어를 통째로 보존하는 경향 (but 분석 정확도 낮을 수 있음)")
    print("  - Komoran : 사전 기반이라 미등록 화학물질명을 과도하게 분절할 수 있음")
    print("  → 특허 도메인에서는 사용자 사전 등록이 필수적")
    print_separator()
    print()


if __name__ == "__main__":
    print_comparison_table()
