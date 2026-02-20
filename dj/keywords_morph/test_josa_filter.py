"""
Kiwipiepy 품사 태깅 후 조사/어미만 제외하는 방식 테스트
- J로 시작하는 태그 (조사) 제외
- E로 시작하는 태그 (어미) 제외
- 나머지 토큰만 출력
"""

from kiwipiepy import Kiwi

# SAMPLES = [
#     "하이드록시에틸셀룰로오스를 포함하는 안과용 조성물",
#     "덱사메타손 및 포비돈-요오드를 포함하는 미생물 감염 치료용 조성물",
#     "디알킬카보네이트를 포함하는 모발 컨디셔닝 조성물",
#     "포스파티딜콜린, 콜레스테롤을 증발농축하여 박막을 형성하는 리포좀 제조방법",
# ]

SAMPLES = [
    "본 발명은 구절초(九節草, Chrysanthemum zawadskii var. latilobum ) 추출물의 유기용매 분획물을 유효성분으로 함유하는 발모 및 육모 조성물, 및 그의 제조방법에 관한 것으로, 특히 천연 식물인 구절초의 비극성 유기 용매 분획물을 유효성분으로 포함하여 부작용이 없으면서도, 그 효과의 우수성이 실험적으로 입증된 발모 및 육모 조성물에 관한 것이다.구절초, 발모, 조성물, 유기용매",
]

EXCLUDE_PREFIXES = ("J", "E")  # 조사, 어미

kiwi = Kiwi()


def print_separator(char="═", width=100):
    print(char * width)


def analyze(text: str, idx: int):
    tokens = kiwi.tokenize(text)

    print(f"\n  [{idx}] \"{text}\"")
    print("  " + "─" * 96)

    # 전체 토큰 + 태그 출력
    print(f"  {'토큰':<20} {'태그':<8} {'제외?':<8} 설명")
    print("  " + "─" * 96)
    for t in tokens:
        excluded = t.tag.startswith(EXCLUDE_PREFIXES)
        mark = "제외" if excluded else ""
        print(f"  {t.form:<20} {t.tag:<8} {mark:<8} {_tag_desc(t.tag)}")

    # 필터링 결과
    kept = [t.form for t in tokens if not t.tag.startswith(EXCLUDE_PREFIXES)]
    print()
    print(f"  → 조사/어미 제외 결과: {' + '.join(kept)}")
    print(f"  → 이어붙이기:          {''.join(kept)}")


def _tag_desc(tag: str) -> str:
    """주요 태그 한글 설명"""
    desc = {
        "NNG": "일반명사", "NNP": "고유명사", "NNB": "의존명사",
        "NR": "수사", "NP": "대명사",
        "VV": "동사", "VA": "형용사", "VX": "보조용언",
        "MAG": "일반부사", "MAJ": "접속부사",
        "JKS": "주격조사", "JKC": "보격조사", "JKG": "관형격조사",
        "JKO": "목적격조사", "JKB": "부사격조사", "JKV": "호격조사",
        "JKQ": "인용격조사", "JX": "보조사", "JC": "접속조사",
        "EP": "선어말어미", "EF": "종결어미", "EC": "연결어미",
        "ETN": "명사형어미", "ETM": "관형형어미",
        "XPN": "체언접두사", "XSN": "명사파생접미사",
        "XSV": "동사파생접미사", "XSA": "형용사파생접미사",
        "XR": "어근", "SF": "마침표등", "SP": "쉼표등",
        "SS": "따옴표등", "SE": "줄임표", "SO": "기타기호",
        "SW": "기타", "SH": "한자", "SL": "외국어", "SN": "숫자",
        "UN": "미분석",
    }
    return desc.get(tag, "")


if __name__ == "__main__":
    print()
    print_separator()
    print("  Kiwipiepy 품사 태깅: 조사(J*) / 어미(E*) 제외 테스트")
    print_separator()

    for i, text in enumerate(SAMPLES, 1):
        analyze(text, i)

    print()
    print_separator()
    print("  결론: 조사/어미만 제외해도 화학물질명이 이미 분절된 상태")
    print("  → 근본 원인은 '명사 추출' 이 아니라 '토크나이징 자체'에서 쪼개짐")
    print("  → 해결책: 사용자 사전 등록 or 원문 그대로 사용 (형태소 분석 생략)")
    print_separator()
    print()
