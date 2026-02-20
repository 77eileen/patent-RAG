"""DB 엔진 및 세션 팩토리.

환경변수 DATABASE_URL에서 MySQL 연결 정보를 로드한다.
예시: mysql+pymysql://user:password@localhost:3306/patent_db
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

DATABASE_URL: str = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, echo=False)
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)


def get_session() -> Session:
    """새 DB 세션을 생성하여 반환한다."""
    return SessionLocal()
