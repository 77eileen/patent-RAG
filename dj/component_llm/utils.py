"""특허 JSON 파싱 유틸."""

import re
from pathlib import Path


def extract_patent_id(filepath: Path, data: dict) -> str:
    """patent_id를 추출한다 (claims.application_number > 파일명)."""
    app_num = data.get("claims", {}).get("application_number", "")
    if app_num:
        return app_num
    match = re.search(r"(\d{10,13})", filepath.stem)
    return match.group(1) if match else filepath.stem.replace("(refine)", "")


def get_independent_claims(data: dict) -> list[dict]:
    """last_version에서 독립항만 필터링한다.

    조건: claim_type=="independent", text 비어있지 않음, change_code!="D"
    """
    claims = data.get("claims", {}).get("last_version", {}).get("claims", [])
    return [
        c for c in claims
        if c.get("claim_type") == "independent"
        and c.get("text", "").strip()
        and c.get("change_code", "") != "D"
    ]


def get_all_claims(data: dict) -> list[dict]:
    """last_version의 전체 청구항을 반환한다 (프롬프트 참조용)."""
    return data.get("claims", {}).get("last_version", {}).get("claims", [])


def find_dependent_numbers(all_claims: list[dict], independent_num: int) -> list[int]:
    """특정 독립항을 참조하는 종속항 번호 리스트를 반환한다."""
    return sorted(
        c["claim_number"]
        for c in all_claims
        if c.get("claim_type") == "dependent"
        and independent_num in c.get("refers_to", [])
    )


def find_referenced_claim_numbers(text: str) -> list[int]:
    """청구항 텍스트에서 '제N항' 참조 번호를 추출한다.

    "제1항 내지 제3항" → [1, 2, 3]
    "제9항의" → [9]
    """
    nums: set[int] = set()

    # "제N항 내지 제M항" 범위 패턴
    for m in re.finditer(r"제\s*(\d+)\s*항\s*내지\s*제\s*(\d+)\s*항", text):
        start, end = int(m.group(1)), int(m.group(2))
        nums.update(range(start, end + 1))

    # "제N항" 단일 패턴
    for m in re.finditer(r"제\s*(\d+)\s*항", text):
        nums.add(int(m.group(1)))

    return sorted(nums)


def quick_patent_id(filepath: Path) -> str | None:
    """파일명에서 patent_id를 빠르게 추출한다 (스킵 판별용)."""
    match = re.search(r"(\d{10,13})", filepath.stem)
    return match.group(1) if match else None
