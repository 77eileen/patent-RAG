"""components CSV를 MySQL components 테이블에 적재하는 스크립트.

사용법:
    python load_to_db.py
"""

import csv
import os
import sys
import time
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# ── 경로 ─────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
ENV_PATH = SCRIPT_DIR.parents[1] / ".env"  # patent-rag/.env

load_dotenv(ENV_PATH)

# ── DB 설정 ───────────────────────────────────────────

DB_CONFIG = {
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", ""),
    "database": os.environ.get("MYSQL_DATABASE", "patent_fto"),
    "charset": "utf8mb4",
}

CSV_PATH = SCRIPT_DIR / "output" / "components.csv"
BATCH_SIZE = 10_000


# ── 메인 ──────────────────────────────────────────────


def main() -> None:
    """components.csv를 읽어 MySQL에 적재한다."""
    if not CSV_PATH.exists():
        print(f"CSV 파일 없음: {CSV_PATH}")
        sys.exit(1)

    db_name = DB_CONFIG.pop("database")
    print(f"DB 연결: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{db_name}")

    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
    cur.execute(f"USE `{db_name}`")
    conn.commit()

    # 테이블 생성 (DROP → CREATE)
    cur.execute("DROP TABLE IF EXISTS components")
    cur.execute("""
        CREATE TABLE components (
            chunk_id VARCHAR(30) PRIMARY KEY,
            patent_id VARCHAR(20) NOT NULL,
            components MEDIUMTEXT NOT NULL,
            note TEXT,
            INDEX idx_patent (patent_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    print("components 테이블 생성 완료")

    # CSV 로드 (배치 INSERT)
    start = time.time()
    total = 0
    batch = []

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            note = row.get("note", "") or None
            batch.append((row["chunk_id"], row["patent_id"], row["components"], note))

            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT INTO components (chunk_id, patent_id, components, note) "
                    "VALUES (%s, %s, %s, %s)",
                    batch,
                )
                conn.commit()
                total += len(batch)
                batch = []

                elapsed = time.time() - start
                speed = total / elapsed if elapsed > 0 else 0
                print(f"  {total:>12,}건 | {elapsed:.0f}s ({speed:,.0f} rows/s)")

    # 남은 배치
    if batch:
        cur.executemany(
            "INSERT INTO components (chunk_id, patent_id, components, note) "
            "VALUES (%s, %s, %s, %s)",
            batch,
        )
        conn.commit()
        total += len(batch)

    elapsed = time.time() - start

    # 검증 쿼리
    cur.execute("SELECT COUNT(*) FROM components")
    db_total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT patent_id) FROM components")
    unique_patents = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT chunk_id) FROM components")
    unique_chunks = cur.fetchone()[0]

    cur.close()
    conn.close()

    print("=" * 50)
    print(f"적재 완료 — 삽입: {total:,}건 ({elapsed:.1f}s)")
    print(f"DB 총 행 수: {db_total:,}")
    print(f"고유 patent_id: {unique_patents:,}")
    print(f"고유 chunk_id: {unique_chunks:,}")


if __name__ == "__main__":
    main()
