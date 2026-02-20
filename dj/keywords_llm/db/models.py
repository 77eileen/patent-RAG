"""SQLAlchemy ORM 모델."""

from sqlalchemy import Column, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class SearchKeyword(Base):
    """search_keywords 테이블 ORM 모델."""

    __tablename__ = "search_keywords"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    patent_id: str = Column(String(20), nullable=False)
    claim_no: int = Column(Integer, nullable=False)
    independent_key: str = Column(String(200), nullable=False)
    dependent_key: str | None = Column(String(200), nullable=True)

    __table_args__ = (
        Index("ix_search_keywords_dependent_key", "dependent_key"),
        Index("ix_search_keywords_independent_key", "independent_key"),
        Index("ix_search_keywords_patent_claim", "patent_id", "claim_no"),
    )

    @property
    def chunk_id(self) -> str:
        """chunk_id를 동적 생성한다."""
        return f"{self.patent_id}_claim_{self.claim_no}"

    def __repr__(self) -> str:
        return (
            f"<SearchKeyword(patent_id={self.patent_id!r}, "
            f"claim_no={self.claim_no}, key={self.independent_key!r})>"
        )
