"""components CSV를 MySQL components 테이블에 적재하는 스크립트.

사용법:
    python -m component_llm.load_to_db
"""

import csv
import sys

from loguru import logger
from sqlalchemy import Column, Index, String, Text, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from .config import LOG_DIR, MYSQL_URL, OUTPUT_DIR

# ── 로깅 설정 ─────────────────────────────────────────

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    LOG_DIR / "load_to_db_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    encoding="utf-8",
)

# ── DB 설정 ───────────────────────────────────────────

Base = declarative_base()


class Component(Base):
    __tablename__ = "components"

    chunk_id = Column(String(30), primary_key=True)
    patent_id = Column(String(20), nullable=False, index=True)
    components = Column(Text, nullable=False)
    note = Column(String(100), nullable=True)

    __table_args__ = (
        Index("idx_patent", "patent_id"),
    )


# ── CSV 경로 ──────────────────────────────────────────

CSV_PATH = OUTPUT_DIR / "components.csv"
COMMIT_EVERY = 1000


# ── 메인 ──────────────────────────────────────────────


def main() -> None:
    """components.csv를 읽어 MySQL에 적재한다."""
    if not CSV_PATH.exists():
        logger.error(f"CSV 파일 없음: {CSV_PATH}")
        sys.exit(1)

    engine = create_engine(MYSQL_URL, pool_pre_ping=True, echo=False)
    Base.metadata.create_all(bind=engine)
    logger.info("components 테이블 확인 완료")

    SessionLocal = sessionmaker(bind=engine)
    session: Session = SessionLocal()

    # 이미 적재된 chunk_id 조회 (중복 방지)
    existing = {row[0] for row in session.query(Component.chunk_id).all()}
    logger.info(f"DB 기존 레코드: {len(existing):,}건")

    loaded = 0
    skipped = 0
    failed = 0

    try:
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader, 1):
                chunk_id = row["chunk_id"]

                if chunk_id in existing:
                    skipped += 1
                    continue

                try:
                    obj = Component(
                        patent_id=row["patent_id"],
                        chunk_id=chunk_id,
                        components=row["components"],
                        note=row.get("note", "") or None,
                    )
                    session.add(obj)
                    loaded += 1
                except Exception as e:
                    logger.error(f"[{idx}] 삽입 실패: {chunk_id} - {e}")
                    session.rollback()
                    failed += 1
                    continue

                if loaded % COMMIT_EVERY == 0:
                    session.commit()
                    logger.info(f"중간 커밋 — 누적 {loaded:,}건")

        session.commit()
    finally:
        session.close()
        engine.dispose()

    logger.info("=" * 50)
    logger.info(f"적재 완료 — 삽입: {loaded:,}건 | 스킵: {skipped:,} | 실패: {failed:,}")


if __name__ == "__main__":
    main()
