"""
청구항 클러스터 생성 실패 특허 복구 스크립트
- 독립항이 없거나 잘못 태깅된 경우 fallback 로직 적용
- 복구된 키워드를 claim_keywords_full.csv에 append

Fallback 전략 (순서대로 시도):
1. last_version에서 text 있는 첫 claim을 독립항으로 간주
2. 실패 시 all_versions 최신 버전에서 독립항 탐색
3. 그래도 없으면 all_versions 최신에서 text 있는 첫 claim 사용
"""

import csv
import json
from pathlib import Path

from extract_claim_keywords import (
    build_claim_clusters,
    extract_keywords,
)

# ── 경로 ──
JSON_DIR = Path(r"C:\00AI\project\project_final\patent-rag\dj\data\json_refine")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_CSV = OUTPUT_DIR / "claim_keywords_full.csv"
RECOVERY_LOG = OUTPUT_DIR / "recovery.log"

FIELDNAMES = ["patent_id", "chunk_id", "keyword"]


def find_no_cluster_files() -> list[Path]:
    """정상 클러스터 생성 불가한 파일 탐색"""
    no_cluster = []
    for fp in sorted(JSON_DIR.rglob("*.json")):
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        claims = data.get("claims", {}).get("last_version", {}).get("claims", [])
        clusters = build_claim_clusters(claims)
        if not clusters:
            no_cluster.append(fp)
    return no_cluster


def fallback_from_last_version(claims: list[dict]) -> dict[int, str]:
    """Fallback 1: text 있는 첫 claim을 독립항으로, 나머지를 종속항으로"""
    # text가 있는 claim 수집
    with_text = [c for c in claims if c.get("text", "").strip()]
    if not with_text:
        return {}

    # 첫 번째를 독립항으로 간주
    root = with_text[0]
    root_num = root["claim_number"]
    cluster_text = root["text"]

    # 나머지를 종속항으로 합침
    for c in with_text[1:]:
        cluster_text += " " + c["text"]

    return {root_num: cluster_text}


def fallback_from_all_versions(data: dict) -> dict[int, str]:
    """Fallback 2: all_versions 최신 버전에서 클러스터 시도"""
    all_versions = data.get("claims", {}).get("all_versions", [])
    if not all_versions:
        return {}

    # 최신 버전 (마지막)
    latest = all_versions[-1]
    claims = latest.get("claims", [])

    # 정상 클러스터 시도
    clusters = build_claim_clusters(claims)
    if clusters:
        return clusters

    # 그래도 안 되면 fallback_from_last_version과 동일 로직
    return fallback_from_last_version(claims)


def recover_patent(fp: Path) -> tuple[str, dict[int, str], str]:
    """파일 1개 복구. (patent_id, clusters, 복구방법) 반환"""
    with open(fp, encoding="utf-8") as f:
        data = json.load(f)

    biblio = data["biblioSummaryInfoArray"]["biblioSummaryInfo"]
    pid = biblio["applicationNumber"].replace("-", "")

    # Fallback 1: last_version에서 text 있는 claim 사용
    last_claims = data.get("claims", {}).get("last_version", {}).get("claims", [])
    clusters = fallback_from_last_version(last_claims)
    if clusters:
        return pid, clusters, "last_version fallback (첫 claim을 독립항으로)"

    # Fallback 2: all_versions 최신
    clusters = fallback_from_all_versions(data)
    if clusters:
        return pid, clusters, "all_versions fallback"

    return pid, {}, "복구 실패"


def main():
    print("=" * 70)
    print("  청구항 클러스터 복구 스크립트")
    print("=" * 70)

    # 1. 대상 파일 탐색
    print("\n  클러스터 생성 불가 파일 탐색 중...")
    no_cluster_files = find_no_cluster_files()
    print(f"  → {len(no_cluster_files)}건 발견")

    if not no_cluster_files:
        print("  복구 대상 없음. 종료.")
        return

    # 2. 복구
    all_rows = []
    log_lines = []

    for fp in no_cluster_files:
        pid, clusters, method = recover_patent(fp)
        log_line = f"{pid}\t{fp.name}\t{method}\tclusters={len(clusters)}"

        if clusters:
            for claim_num, cluster_text in sorted(clusters.items()):
                chunk_id = f"{pid}_claim_{claim_num}"
                keywords = extract_keywords(cluster_text)
                for kw in keywords:
                    all_rows.append({
                        "patent_id": pid,
                        "chunk_id": chunk_id,
                        "keyword": kw,
                    })
                log_line += f"\tkeywords={len(keywords)}"

        log_lines.append(log_line)
        print(f"  [{pid}] {method} → {sum(1 for r in all_rows if r['patent_id'] == pid)}개 키워드")

    # 3. CSV append
    if all_rows:
        with open(OUTPUT_CSV, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writerows(all_rows)
        print(f"\n  {len(all_rows)}개 키워드 행 → {OUTPUT_CSV} (append)")

    # 4. 로그 저장
    with open(RECOVERY_LOG, "w", encoding="utf-8") as f:
        f.write("patent_id\tfilename\tmethod\tdetail\n")
        for line in log_lines:
            f.write(line + "\n")
    print(f"  복구 로그 → {RECOVERY_LOG}")

    print("=" * 70)


if __name__ == "__main__":
    main()
