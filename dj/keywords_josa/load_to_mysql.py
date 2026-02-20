"""
claim_keywords_full.csv → MySQL claim_keywords 테이블 로드
- .env에서 연결 정보 읽기
- 테이블 DROP/CREATE
- 배치 INSERT (10,000행 단위)
"""

import csv
import os
import time
from pathlib import Path

import pymysql

# ── .env 읽기 (dotenv 없이 직접 파싱) ──
ENV_PATH = Path(r"C:\00AI\project\project_final\patent-rag\.env")

def load_env(path: Path) -> dict:
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env

env = load_env(ENV_PATH)

DB_CONFIG = {
    "host": env["MYSQL_HOST"],
    "port": int(env["MYSQL_PORT"]),
    "user": env["MYSQL_USER"],
    "password": env["MYSQL_PASSWORD"],
    "database": env["MYSQL_DATABASE"],
    "charset": "utf8mb4",
}

CSV_PATH = Path(__file__).parent / "output" / "claim_keywords_full.csv"
BATCH_SIZE = 10_000


def main():
    print("=" * 60)
    print("  claim_keywords CSV → MySQL 로드")
    print("=" * 60)

    # 1. 연결 (DB 없으면 생성)
    db_name = DB_CONFIG.pop("database")
    print(f"\n  DB 연결: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{db_name}")
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4")
    cur.execute(f"USE `{db_name}`")
    conn.commit()

    # 2. 테이블 생성
    print("  테이블 생성 (DROP IF EXISTS → CREATE)...")
    cur.execute("DROP TABLE IF EXISTS claim_keywords")
    cur.execute("""
        CREATE TABLE claim_keywords (
            id INT AUTO_INCREMENT PRIMARY KEY,
            patent_id VARCHAR(20) NOT NULL,
            chunk_id VARCHAR(30) NOT NULL,
            keyword VARCHAR(500) NOT NULL,
            INDEX idx_keyword (keyword(100)),
            INDEX idx_chunk (chunk_id),
            INDEX idx_patent (patent_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    conn.commit()
    print("  → 완료")

    # 3. CSV 로드 (배치 INSERT)
    print(f"\n  CSV 로드: {CSV_PATH}")
    print(f"  배치 크기: {BATCH_SIZE:,}")

    start = time.time()
    total = 0
    batch = []

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            kw = row["keyword"][:500]  # 500자 초과 truncate
            batch.append((row["patent_id"], row["chunk_id"], kw))
            if len(batch) >= BATCH_SIZE:
                cur.executemany(
                    "INSERT INTO claim_keywords (patent_id, chunk_id, keyword) VALUES (%s, %s, %s)",
                    batch,
                )
                conn.commit()
                total += len(batch)
                batch = []

                elapsed = time.time() - start
                speed = total / elapsed if elapsed > 0 else 0
                print(f"    {total:>12,}행 | {elapsed:.0f}s ({speed:,.0f} rows/s)")

    # 남은 배치
    if batch:
        cur.executemany(
            "INSERT INTO claim_keywords (patent_id, chunk_id, keyword) VALUES (%s, %s, %s)",
            batch,
        )
        conn.commit()
        total += len(batch)

    elapsed = time.time() - start
    print(f"\n  로드 완료: {total:,}행 ({elapsed:.1f}s)")

    # 4. 확인 쿼리
    print("\n" + "=" * 60)
    print("  검증 쿼리")
    print("=" * 60)

    cur.execute("SELECT COUNT(*) FROM claim_keywords")
    print(f"\n  총 행 수:          {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(DISTINCT patent_id) FROM claim_keywords")
    print(f"  고유 patent_id:    {cur.fetchone()[0]:,}")

    cur.execute("SELECT COUNT(DISTINCT chunk_id) FROM claim_keywords")
    print(f"  고유 chunk_id:     {cur.fetchone()[0]:,}")

    print("\n  키워드 빈도 TOP 20:")
    print(f"  {'순위':>4}  {'keyword':<30}  {'count':>10}")
    print(f"  {'─'*4}  {'─'*30}  {'─'*10}")
    cur.execute("""
        SELECT keyword, COUNT(*) as cnt
        FROM claim_keywords
        GROUP BY keyword
        ORDER BY cnt DESC
        LIMIT 20
    """)
    for i, (kw, cnt) in enumerate(cur.fetchall(), 1):
        print(f"  {i:>4}  {kw:<30}  {cnt:>10,}")

    cur.close()
    conn.close()
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
