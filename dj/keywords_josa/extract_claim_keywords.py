"""
특허 청구항 키워드 추출 파이프라인
- 독립항 기준 claim cluster 생성
- 정규표현식 기반 조사/어미 제거 (형태소 분석 없음)
- last_version claims 사용
"""

import csv
import json
import re
import sys
import time
from pathlib import Path

# ── 경로 ──
JSON_DIR = Path(r"C:\00AI\project\project_final\patent-rag\dj\data\json_refine")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_CSV = OUTPUT_DIR / "claim_keywords_output.csv"

SAMPLE_LIMIT = 5

# ── 정규식 패턴 ──
JOSA_1 = re.compile(r"(을|를|이|가|은|는|의|에|로|와|과)$")
EOMI_2 = re.compile(
    r"(으로부터|포함하는|구성되는|구성된|선택된|되는|하는|된|하여|으로|에서|이며|이고"
    r"|시키고|시켜|시키|시킨|시키지|하고|으로서|하기|하며|되고"
    # v2 추가: 로부터, 에게
    r"|로부터|에게"
    # v2 추가: ~거나 계열 (긴 패턴 우선)
    r"|시키거나|하거나|되거나|거나"
    # v2 추가: ~하되, ~하지, ~되지, ~하지만
    r"|하되|하지만|하지|되지"
    # v2 추가: ~도록 계열
    r"|시키도록|하도록|되도록|도록"
    # v2 추가: ~면서 계열
    r"|하면서|되면서"
    # v2 추가: ~으로써 계열 (긴 패턴 우선)
    r"|함으로써|됨으로써|으로써"
    # v2 추가: 시키 계열 확장
    r"|시키기|시킬|시키며|시켜서|시키고자|시킨다|시키는|시킴"
    r")$"
)

# 특수문자 정제
SPECIAL_CHARS = re.compile(r"[().,;:!?\[\]{}\"\']")

# 청구항 형식 문구 제거 (전처리)
CLAIM_PREFIX_PATTERNS = [
    re.compile(r"제\s*\d+\s*항에\s*있어서\s*[,.]?\s*"),
    re.compile(r"\d+\s*항에\s*있어서\s*[,.]?\s*"),
    re.compile(r"제\s*\d+\s*항\s*내지\s*제\s*\d+\s*항"),
    re.compile(r"제\s*\d+\s*항\s*또는\s*제\s*\d+\s*항"),
    re.compile(r"어느\s*한\s*항에\s*있어서\s*[,.]?\s*"),
]

# 노이즈 패턴 (토큰 단위)
NOISE_PATTERNS = [
    re.compile(r"^제\s*\d+\s*항?$"),
    re.compile(r"^\d+\s*항$"),
    re.compile(r"^제?\s*\d+\s*항에$"),
    re.compile(r"^\d+[a-z]?$"),
    re.compile(r"^[0-9.]+$"),
    re.compile(r"^\d+중량"),
    re.compile(r"^\d+%$"),
    re.compile(r"^-?\d+℃$"),
    re.compile(r"^\d+분$"),
    re.compile(r"^\d+시간$"),
    re.compile(r"^\d+rpm$"),
    re.compile(r"^\d+대\d+$"),
    re.compile(r"^[\d./~∼%\-]+$"),
    re.compile(r"^-?\d+[~∼]-?\d+$"),        # 5~20, -70∼-196
    re.compile(r"^\d+[x×]\d+$"),             # 3x5, 2×3
    # 수치+단위
    re.compile(r"^\d+wt%$"),
    re.compile(r"^\d+t%$"),
    re.compile(r"^\d+배$"),
    re.compile(r"^\d+단계$"),
    # 집단 표현
    re.compile(r"^제?\d+집단$"),
    # 화학식 변수
    re.compile(r"^[RC]\d+$"),
    re.compile(r"^C\d+~?C?\d*$"),
    re.compile(r"^[a-zA-Z]\d*[a-zA-Z]\d*[a-zA-Z]?$"),
    # 오류 토큰
    re.compile(r"^및[a-z]$"),
    # 숫자로 시작하는 패턴
    re.compile(r"^\d+이다$"),
    re.compile(r"^\d+인$"),
    # 숫자+수량 단위
    re.compile(r"^\d+종$"),
    re.compile(r"^\d+개$"),
    re.compile(r"^\d+회$"),
    re.compile(r"^\d+차$"),
    re.compile(r"^\d+일$"),
]

# ── 불용어 ──
STOPWORDS = {
    # 기본 불용어
    "본", "것", "및", "또는", "관한", "특히", "상기",
    "그", "이", "수", "등", "더", "각", "해당",
    # 청구항 형식어
    "것이다", "것으로서", "것으로써", "것인", "의한", "위한",
    "있다", "된다", "한다", "않", "있", "없", "됨", "함",
    "통한", "대한", "따른", "의할", "대해", "여기서",
    "더욱", "보다", "또", "매우", "가장", "다시",
    "하기", "상기식", "특징", "포함", "함유", "발명",
    "포함하는", "구성된", "있어서",
    # 수치/비율 관련
    "중량", "중량부", "중량%", "중량비", "함량", "비율", "농도",
    "몰비", "부피비", "범위", "내지", "이상", "이하", "미만", "초과",
    # 단위
    "g", "mg", "kg", "ml", "mL", "L", "wt%", "w/v%",
    "μm", "nm", "mm", "cm", "m",
    "℃", "°C", "°F", "도",
    "rpm", "pH",
    # 시간 단위
    "회", "분", "초", "시간", "동안",
    # 일반 동작 (제조공정 키워드인 첨가/투입/반응/처리는 유지)
    "사용", "이용",
    # 불필요한 일반어
    "어느", "하나", "함께", "이루어진", "선택", "적어도",
    "가능한", "있으며", "나타내어질",
    # 동사 변형 (어근 없는 것만)
    "함유함", "포함함", "포함됨", "함유한",
    # 형용사/부사
    "동일한", "상이한", "특정", "최종",
    # 청구항 형식어 추가
    "의해", "각각", "이들", "추가", "청구항", "및/또",
    "독립적", "임의", "다음", "표시", "관련",
    # v2 추가: 형식어/부정어
    "이루어지", "경우", "통해", "이상인", "나타내",
    "않고", "있도록",
}


# ── 함수 ──
def build_claim_clusters(claims: list[dict]) -> dict[int, str]:
    """독립항 기준 cluster 생성. 종속항은 refers_to 따라 합침."""
    clusters = {}

    for c in claims:
        if c["claim_type"] == "independent" and c["text"]:
            clusters[c["claim_number"]] = c["text"]

    for c in claims:
        if c["claim_type"] == "dependent" and c["text"]:
            for ref in c["refers_to"]:
                if ref in clusters:
                    clusters[ref] += " " + c["text"]

    return clusters


def remove_claim_prefixes(text: str) -> str:
    """청구항 형식 문구 제거"""
    for pat in CLAIM_PREFIX_PATTERNS:
        text = pat.sub(" ", text)
    return text


def clean_special_chars(text: str) -> str:
    """특수문자 → 공백"""
    return SPECIAL_CHARS.sub(" ", text)


def remove_josa(word: str) -> str:
    """단어 끝 조사/어미 단계적 제거"""
    prev = None
    while prev != word:
        prev = word
        word = EOMI_2.sub("", word)
    word = JOSA_1.sub("", word)
    return word


def is_noise(token: str) -> bool:
    """노이즈 패턴 매칭"""
    return any(p.match(token) for p in NOISE_PATTERNS)


def extract_keywords(text: str) -> list[str]:
    """텍스트 → 키워드 리스트 (중복 제거, 순서 유지)"""
    text = remove_claim_prefixes(text)
    text = clean_special_chars(text)
    words = re.split(r"\s+", text)

    result = []
    seen = set()
    for w in words:
        cleaned = remove_josa(w.strip())
        if not cleaned:
            continue
        if len(cleaned) < 2:
            continue
        if cleaned in STOPWORDS:
            continue
        if is_noise(cleaned):
            continue
        if cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def parse_patent(filepath: Path) -> dict:
    """JSON → patent_id, last_version claims 추출"""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    biblio = data["biblioSummaryInfoArray"]["biblioSummaryInfo"]
    app_num = biblio["applicationNumber"].replace("-", "")
    title = biblio["inventionTitle"]

    claims_data = data.get("claims", {})
    last_ver = claims_data.get("last_version", {})
    claims = last_ver.get("claims", [])

    return {"patent_id": app_num, "title": title, "claims": claims}


def process_patents(limit: int = SAMPLE_LIMIT) -> list[dict]:
    """JSON 파일들 처리 → CSV 행 리스트"""
    json_files = sorted(JSON_DIR.glob("*.json"))[:limit]
    rows = []

    for fp in json_files:
        patent = parse_patent(fp)
        pid = patent["patent_id"]
        clusters = build_claim_clusters(patent["claims"])

        for claim_num, cluster_text in sorted(clusters.items()):
            chunk_id = f"{pid}_claim_{claim_num}"
            keywords = extract_keywords(cluster_text)
            for kw in keywords:
                rows.append({
                    "patent_id": pid,
                    "chunk_id": chunk_id,
                    "keyword": kw,
                })

    return rows


def save_csv(rows: list[dict], path: Path):
    """CSV 저장"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["patent_id", "chunk_id", "keyword"])
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict]):
    """결과 요약 출력"""
    print()
    print("=" * 90)
    print("  청구항 키워드 추출 결과 (Claim Cluster 기반)")
    print("=" * 90)

    # chunk별 그룹
    chunks = {}
    patent_titles = {}
    for r in rows:
        cid = r["chunk_id"]
        if cid not in chunks:
            chunks[cid] = []
        chunks[cid].append(r["keyword"])

    # 특허별 출력
    current_pid = None
    for cid, keywords in chunks.items():
        pid = cid.rsplit("_claim_", 1)[0]
        if pid != current_pid:
            current_pid = pid
            print(f"\n  [{pid}]")
            print(f"  {'─' * 85}")

        print(f"\n    {cid} ({len(keywords)}개 키워드):")
        for i in range(0, len(keywords), 8):
            chunk = keywords[i : i + 8]
            print(f"      {', '.join(chunk)}")

    # 전체 통계
    print(f"\n{'=' * 90}")
    patent_ids = {r["patent_id"] for r in rows}
    chunk_ids = {r["chunk_id"] for r in rows}
    print(f"  총 {len(patent_ids)}개 특허 / {len(chunk_ids)}개 cluster / {len(rows)}개 키워드 행")
    print(f"  저장: {OUTPUT_CSV}")
    print("=" * 90)
    print()


if __name__ == "__main__":
    rows = process_patents(limit=SAMPLE_LIMIT)
    save_csv(rows, OUTPUT_CSV)
    print_summary(rows)
