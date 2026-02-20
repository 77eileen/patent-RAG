"""keywords_output JSON을 search_keywords 테이블에 적재하는 스크립트.

사용법:
    python -m scripts.keywords.load_to_db

환경변수:
    DATABASE_URL - MySQL 연결 URL (필수)
"""

import json
import sys
from glob import glob
from pathlib import Path

from loguru import logger

# ── 경로 설정 ───────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUTPUT_DIR = BASE_DIR / "data" / "keywords_output"
LOG_DIR = BASE_DIR / "logs"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 로깅 설정 ───────────────────────────────────────────

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    LOG_DIR / "load_to_db_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    encoding="utf-8",
)


def parse_output_file(filepath: Path) -> list[dict]:
    """keywords_output JSON 1개를 search_keywords 레코드 리스트로 변환한다.

    LLM 출력 형식:
        {"patent_id": "...", "selected_claim": N, "mappings": [...]}

    DB 레코드 형식:
        {"patent_id", "claim_no", "independent_key", "dependent_key"}
    """
    data = json.loads(filepath.read_text(encoding="utf-8"))

    mappings = data.get("mappings", [])
    if not mappings:
        return []

    patent_id = data.get("patent_id", filepath.stem)
    records: list[dict] = []

    for m in mappings:
        claim_no = m.get("claim_no")
        independent_key = m.get("independent_key", "")

        dependent_keys = m.get("dependent_keys", [])
        if not dependent_keys:
            records.append({
                "patent_id": patent_id,
                "claim_no": claim_no,
                "independent_key": independent_key,
                "dependent_key": None,
            })
        else:
            for dep_key in dependent_keys:
                records.append({
                    "patent_id": patent_id,
                    "claim_no": claim_no,
                    "independent_key": independent_key,
                    "dependent_key": dep_key,
                })

    return records


def main() -> None:
    """keywords_output/ 전체 JSON을 DB에 적재한다."""
    # DB 모듈 import (DATABASE_URL 필요하므로 함수 내에서)
    from db.connection import get_session
    from db.models import Base, SearchKeyword
    from db.connection import engine
    from db.schemas import SearchKeywordCreate

    # 테이블 생성
    Base.metadata.create_all(bind=engine)
    logger.info("search_keywords 테이블 확인 완료")

    json_files = sorted(glob(str(OUTPUT_DIR / "*.json")))
    total = len(json_files)
    logger.info(f"적재 대상 JSON 파일: {total:,}개")

    session = get_session()
    loaded = 0
    skipped = 0
    failed = 0

    try:
        for idx, filepath_str in enumerate(json_files, 1):
            filepath = Path(filepath_str)

            try:
                records = parse_output_file(filepath)
            except Exception as e:
                logger.error(f"[{idx}/{total}] 파싱 실패: {filepath.name} - {e}")
                failed += 1
                continue

            if not records:
                skipped += 1
                continue

            try:
                items = [SearchKeywordCreate(**r) for r in records]
                objs = [SearchKeyword(**item.model_dump()) for item in items]
                session.add_all(objs)
                session.flush()
                loaded += len(objs)
            except Exception as e:
                logger.error(f"[{idx}/{total}] DB 삽입 실패: {filepath.name} - {e}")
                session.rollback()
                failed += 1
                continue

            if idx % 1000 == 0:
                session.commit()
                logger.info(f"[{idx}/{total}] 중간 커밋 — 누적 {loaded:,}건")

        session.commit()
    finally:
        session.close()

    logger.info("=" * 50)
    logger.info(f"적재 완료 — 레코드: {loaded:,}건 | 스킵: {skipped:,} | 실패: {failed:,}")


if __name__ == "__main__":
    main()
