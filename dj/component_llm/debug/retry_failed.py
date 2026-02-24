"""실패한 청구항 구성요소를 재시도하는 스크립트.

fix_no_cluster.py 패턴 참고:
- failed_patents.csv에서 대상 로드
- 재시도 (간격 넓힘, 참조 청구항 제한)
- 성공 시 components.csv에 append
"""

import asyncio
import csv
import json
from pathlib import Path

from google import genai
from google.genai import types
from loguru import logger

from .config import (
    DATA_DIR,
    GOOGLE_API_KEYS,
    MODEL_NAME,
    OUTPUT_DIR,
    TEMPERATURE,
)
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .utils import (
    extract_patent_id,
    find_dependent_numbers,
    find_referenced_claim_numbers,
    get_all_claims,
    get_independent_claims,
)

# ── 설정 ──
MAX_RETRIES = 5
RETRY_DELAY = 5  # 초 (넉넉히)
MAX_REF_CLAIMS = 10  # 참조 청구항 최대 포함 수

CSV_PATH = OUTPUT_DIR / "components.csv"
FAIL_CSV_PATH = OUTPUT_DIR / "failed_patents.csv"
CSV_HEADER = ["patent_id", "chunk_id", "components", "note"]


def _clean_response(text: str) -> str:
    marker = "구성요소:"
    idx = text.rfind(marker)
    if idx >= 0:
        return text[idx:].strip()
    return text


def load_failed() -> list[dict]:
    """failed_patents.csv에서 실패 목록 로드."""
    rows = []
    with open(FAIL_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def find_json_file(patent_id: str) -> Path | None:
    """patent_id로 JSON 파일을 찾는다."""
    for fp in DATA_DIR.rglob("*.json"):
        if patent_id in fp.name:
            return fp
    return None


async def call_gemini_retry(
    clients: list[genai.Client],
    user_prompt: str,
    patent_id: str,
    claim_number: int,
) -> str | None:
    """넉넉한 간격으로 재시도."""
    for key_idx, client in enumerate(clients):
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.aio.models.generate_content(
                    model=MODEL_NAME,
                    contents=[SYSTEM_PROMPT, user_prompt],
                    config=types.GenerateContentConfig(
                        temperature=TEMPERATURE,
                    ),
                )
                text = response.text.strip()
                if text:
                    return text
                logger.warning(
                    f"빈 응답 (키{key_idx+1}, 시도{attempt+1}): "
                    f"{patent_id} claim {claim_number}"
                )
            except Exception as e:
                logger.warning(
                    f"API 실패 (키{key_idx+1}, 시도{attempt+1}): "
                    f"{patent_id} claim {claim_number} - {e}"
                )
            await asyncio.sleep(RETRY_DELAY)

        if key_idx < len(clients) - 1:
            logger.info(f"키 {key_idx+1} 실패 → 키 {key_idx+2}로 전환")

    return None


async def main() -> None:
    failed = load_failed()
    if not failed:
        logger.info("실패 건 없음.")
        return

    logger.info(f"실패 건 {len(failed)}개 로드")

    clients = [genai.Client(api_key=k) for k in GOOGLE_API_KEYS]
    success_rows: list[list[str]] = []
    still_failed: list[dict] = []

    # patent_id → file 캐시
    file_cache: dict[str, Path | None] = {}
    data_cache: dict[str, dict] = {}

    for item in failed:
        patent_id = item["patent_id"]
        claim_num = int(item["claim_number"])

        logger.info(f"재시도: {patent_id} claim {claim_num}")

        # JSON 로드
        if patent_id not in file_cache:
            file_cache[patent_id] = find_json_file(patent_id)
        fp = file_cache[patent_id]
        if fp is None:
            logger.error(f"JSON 파일 없음: {patent_id}")
            still_failed.append(item)
            continue

        if patent_id not in data_cache:
            data_cache[patent_id] = json.loads(fp.read_text(encoding="utf-8"))
        data = data_cache[patent_id]

        all_claims = get_all_claims(data)
        target = next((c for c in all_claims if c["claim_number"] == claim_num), None)
        if not target:
            logger.error(f"청구항 없음: {patent_id} claim {claim_num}")
            still_failed.append(item)
            continue

        # 토큰 초과 방지 전략:
        # - claim 53,78,98 (긴 독립항): 종속항/참조 생략, 대상만 전송
        # - claim 148,161,164 (다수 참조): claim 1만 참조로 포함
        ref_nums = find_referenced_claim_numbers(target.get("text", ""))
        ref_nums = [n for n in ref_nums if n != claim_num]

        if ref_nums:
            # 참조가 있으면 claim 1만 포함
            claim_1 = next((c for c in all_claims if c["claim_number"] == 1), None)
            ref_claims = [claim_1] if claim_1 else None
            dep_claims = []
            dep_nums = []
            logger.info(f"참조 청구항 {len(ref_nums)}개 → claim 1만 포함")
        else:
            # 참조 없는 긴 독립항: 종속항/참조 모두 생략
            dep_claims = []
            dep_nums = []
            ref_claims = None
            logger.info(f"종속항/참조 생략 (대상 청구항만 전송)")

        # 프롬프트 & 호출
        user_prompt = build_user_prompt(target, dep_claims, patent_id, ref_claims)
        result = await call_gemini_retry(
            clients, user_prompt, patent_id, claim_num
        )

        if result is None:
            logger.error(f"재시도 실패: {patent_id} claim {claim_num}")
            still_failed.append(item)
            continue

        result = _clean_response(result)
        note = f"dep {','.join(map(str, dep_nums))}" if dep_nums else ""
        chunk_id = f"{patent_id}_claim_{claim_num}"
        success_rows.append([patent_id, chunk_id, result, note])
        logger.info(f"성공: {patent_id} claim {claim_num}")

        # 요청 간 딜레이
        await asyncio.sleep(RETRY_DELAY)

    # CSV append
    if success_rows:
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(success_rows)
        logger.info(f"{len(success_rows)}건 → {CSV_PATH} (append)")

    # 실패 목록 갱신
    if still_failed:
        with open(FAIL_CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["patent_id", "claim_number", "error"],
                quoting=csv.QUOTE_ALL,
            )
            writer.writeheader()
            writer.writerows(still_failed)
        logger.error(f"여전히 실패: {len(still_failed)}건")
    else:
        FAIL_CSV_PATH.unlink(missing_ok=True)
        logger.info("모든 실패 건 복구 완료!")

    logger.info("=" * 50)
    logger.info(
        f"결과 — 복구: {len(success_rows)} | 실패: {len(still_failed)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
