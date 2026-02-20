"""
전체 특허 청구항 키워드 추출 (배치 저장 + 에러 스킵)
- 1000개마다 CSV append 저장 (중간 크래시해도 직전 배치까지 보존)
- 오류 파일은 skip하고 errors.log에 기록
"""

import csv
import sys
import time
from pathlib import Path

# 같은 폴더의 extract_claim_keywords.py에서 함수 임포트
sys.path.insert(0, str(Path(__file__).parent))
from extract_claim_keywords import (
    build_claim_clusters,
    extract_keywords,
    parse_patent,
)

# ── 설정 ──
JSON_DIR = Path(r"C:\00AI\project\project_final\patent-rag\dj\data\json_refine")
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_CSV = OUTPUT_DIR / "claim_keywords_full.csv"
ERROR_LOG = OUTPUT_DIR / "errors.log"

BATCH_SIZE = 1000
FIELDNAMES = ["patent_id", "chunk_id", "keyword"]


def write_header(path: Path):
    """CSV 헤더 작성 (새 파일)"""
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()


def append_rows(path: Path, rows: list[dict]):
    """CSV에 행 추가 (append 모드)"""
    with open(path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerows(rows)


def process_single(filepath: Path) -> list[dict]:
    """파일 1개 처리 → 키워드 행 리스트"""
    patent = parse_patent(filepath)
    pid = patent["patent_id"]
    clusters = build_claim_clusters(patent["claims"])

    rows = []
    for claim_num, cluster_text in sorted(clusters.items()):
        chunk_id = f"{pid}_claim_{claim_num}"
        for kw in extract_keywords(cluster_text):
            rows.append({
                "patent_id": pid,
                "chunk_id": chunk_id,
                "keyword": kw,
            })
    return rows


def main():
    json_files = sorted(JSON_DIR.rglob("*.json"))
    total = len(json_files)
    print(f"총 {total}개 파일 처리 시작")
    print(f"출력: {OUTPUT_CSV}")
    print(f"에러: {ERROR_LOG}")
    print("=" * 70)

    # CSV 헤더 작성
    write_header(OUTPUT_CSV)

    # 에러 로그 초기화
    with open(ERROR_LOG, "w", encoding="utf-8") as f:
        f.write("")

    start = time.time()
    batch_rows = []
    total_rows = 0
    ok_count = 0
    err_count = 0
    no_claim_count = 0

    for i, fp in enumerate(json_files, 1):
        try:
            rows = process_single(fp)
            if rows:
                batch_rows.extend(rows)
                ok_count += 1
            else:
                no_claim_count += 1
        except Exception as e:
            err_count += 1
            with open(ERROR_LOG, "a", encoding="utf-8") as f:
                f.write(f"{fp.name}\t{type(e).__name__}: {e}\n")

        # 배치 저장
        if i % BATCH_SIZE == 0 or i == total:
            if batch_rows:
                append_rows(OUTPUT_CSV, batch_rows)
                total_rows += len(batch_rows)
                batch_rows = []

            elapsed = time.time() - start
            speed = i / elapsed if elapsed > 0 else 0
            remaining = (total - i) / speed if speed > 0 else 0
            print(
                f"  [{i:>6}/{total}] "
                f"키워드: {total_rows:>8}행 | "
                f"성공: {ok_count} | 청구항없음: {no_claim_count} | 에러: {err_count} | "
                f"{elapsed:.0f}s ({speed:.0f}files/s, 남은시간: {remaining:.0f}s)"
            )

    print("=" * 70)
    print(f"완료! {total_rows}개 키워드 행 저장 → {OUTPUT_CSV}")
    if err_count:
        print(f"에러 {err_count}건 → {ERROR_LOG}")
    print(f"소요시간: {time.time() - start:.1f}s")


if __name__ == "__main__":
    main()
