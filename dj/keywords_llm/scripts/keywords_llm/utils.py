"""특허 JSON 파싱 및 파일 I/O 유틸 함수."""

import json
import re
from pathlib import Path


def extract_patent_id(filepath: Path, data: dict) -> str:
    """patent_id를 JSON 내부 또는 파일명에서 추출한다.

    우선순위: claims.application_number > 파일명 숫자 추출
    """
    app_num = data.get("claims", {}).get("application_number", "")
    if app_num:
        return app_num

    match = re.search(r"(\d{10,13})", filepath.stem)
    if match:
        return match.group(1)

    return filepath.stem.replace("(refine)", "")


def extract_claims(data: dict) -> list[dict]:
    """last_version에서 텍스트가 있는 청구항만 추출한다."""
    claims = data.get("claims", {}).get("last_version", {}).get("claims", [])
    return [c for c in claims if c.get("text", "").strip()]


def format_claims_for_prompt(claims: list[dict]) -> str:
    """청구항 리스트를 프롬프트용 텍스트로 변환한다."""
    lines: list[str] = []
    for c in claims:
        refs = f" (참조: {c['refers_to']})" if c.get("refers_to") else ""
        lines.append(
            f"[청구항 {c['claim_number']}] ({c['claim_type']}){refs}\n{c['text']}"
        )
    return "\n\n".join(lines)


def save_result(output_dir: Path, patent_id: str, result: dict) -> None:
    """추출 결과를 JSON 파일로 저장한다."""
    output_path = output_dir / f"{patent_id}.json"
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_processed_ids(output_dir: Path) -> set[str]:
    """이미 처리된 patent_id 집합을 반환한다."""
    return {p.stem for p in output_dir.glob("*.json")}


def quick_patent_id(filepath: Path) -> str | None:
    """파일명에서 patent_id를 빠르게 추출한다 (JSON 읽기 전 스킵 판별용)."""
    match = re.search(r"(\d{10,13})", filepath.stem)
    return match.group(1) if match else None
