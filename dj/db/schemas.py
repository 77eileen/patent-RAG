"""Pydantic 스키마 (입출력 검증용)."""

from pydantic import BaseModel, Field


class SearchKeywordCreate(BaseModel):
    """search_keywords 레코드 생성용 스키마."""

    patent_id: str = Field(..., max_length=20, description="출원번호")
    claim_no: int = Field(..., ge=1, description="청구항 번호")
    independent_key: str = Field(..., max_length=200, description="독립항 용어")
    dependent_key: str | None = Field(None, max_length=200, description="종속항 용어")


class SearchResult(BaseModel):
    """검색 결과 응답 스키마."""

    patent_id: str
    claim_no: int
    chunk_id: str

    model_config = {"from_attributes": True}
