"""SearchKeyword Repository — DB CRUD 로직.

Repository 패턴으로 세션을 주입받아 사용한다.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from db.connection import engine
from db.models import Base, SearchKeyword
from db.schemas import SearchKeywordCreate, SearchResult


class SearchKeywordRepository:
    """search_keywords 테이블에 대한 CRUD 오퍼레이션."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── DDL ──────────────────────────────────────────────

    @staticmethod
    def create_table() -> None:
        """search_keywords 테이블을 생성한다 (없으면 새로 생성)."""
        Base.metadata.create_all(bind=engine)

    # ── INSERT ───────────────────────────────────────────

    def bulk_insert(self, items: list[SearchKeywordCreate]) -> int:
        """여러 레코드를 한 번에 삽입한다.

        Args:
            items: 삽입할 레코드 리스트.

        Returns:
            삽입된 레코드 수.
        """
        records = [
            SearchKeyword(**item.model_dump()) for item in items
        ]
        self._session.add_all(records)
        self._session.commit()
        return len(records)

    # ── SEARCH ───────────────────────────────────────────

    def search_by_term(self, term: str) -> list[SearchResult]:
        """dependent_key 또는 independent_key로 통합 검색한다.

        Args:
            term: 검색 키워드.

        Returns:
            매칭된 (patent_id, claim_no, chunk_id) 리스트 (중복 제거).
        """
        stmt = (
            select(SearchKeyword.patent_id, SearchKeyword.claim_no)
            .where(
                or_(
                    SearchKeyword.dependent_key == term,
                    SearchKeyword.independent_key == term,
                )
            )
            .distinct()
        )
        rows = self._session.execute(stmt).all()
        return [
            SearchResult(
                patent_id=row.patent_id,
                claim_no=row.claim_no,
                chunk_id=f"{row.patent_id}_claim_{row.claim_no}",
            )
            for row in rows
        ]

    def search_by_terms(self, terms: list[str]) -> list[SearchResult]:
        """여러 키워드로 AND 검색한다.

        모든 키워드를 포함하는 patent_id만 반환한다.
        각 키워드는 dependent_key 또는 independent_key에 매칭된다.

        Args:
            terms: 검색 키워드 리스트.

        Returns:
            모든 키워드에 매칭된 (patent_id, claim_no, chunk_id) 리스트.
        """
        if not terms:
            return []

        # 첫 번째 키워드로 후보 patent_id 집합을 구한다
        candidate_patents = self._get_patent_ids_for_term(terms[0])

        # 나머지 키워드로 교집합을 줄여나간다
        for term in terms[1:]:
            candidate_patents &= self._get_patent_ids_for_term(term)
            if not candidate_patents:
                return []

        # 후보 patent_id에 해당하는 전체 결과를 조회한다
        stmt = (
            select(SearchKeyword.patent_id, SearchKeyword.claim_no)
            .where(SearchKeyword.patent_id.in_(candidate_patents))
            .distinct()
        )
        rows = self._session.execute(stmt).all()
        return [
            SearchResult(
                patent_id=row.patent_id,
                claim_no=row.claim_no,
                chunk_id=f"{row.patent_id}_claim_{row.claim_no}",
            )
            for row in rows
        ]

    # ── PRIVATE ──────────────────────────────────────────

    def _get_patent_ids_for_term(self, term: str) -> set[str]:
        """단일 키워드에 매칭되는 patent_id 집합을 반환한다."""
        stmt = (
            select(SearchKeyword.patent_id)
            .where(
                or_(
                    SearchKeyword.dependent_key == term,
                    SearchKeyword.independent_key == term,
                )
            )
            .distinct()
        )
        rows = self._session.execute(stmt).all()
        return {row.patent_id for row in rows}
