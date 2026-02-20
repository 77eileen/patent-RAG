"""특허 JSON에서 search_keywords용 키워드를 LLM으로 추출하는 비동기 스크립트.

사용법:
    python -m scripts.keywords.extract

환경변수:
    GOOGLE_API_KEY   - Gemini API 키 (필수)
    GOOGLE_API_KEY_2 - 백업 API 키 (선택)
"""

import asyncio
import json
import os
import re
import sys
from glob import glob
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from loguru import logger

from .prompts import SYSTEM_PROMPT
from .utils import (
    extract_claims,
    extract_patent_id,
    format_claims_for_prompt,
    get_processed_ids,
    quick_patent_id,
    save_result,
)

# ── 경로 설정 ───────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # dj/
PROJECT_ROOT = BASE_DIR.parent  # patent-rag/
DATA_DIR = BASE_DIR / "data" / "json_refine"
OUTPUT_DIR = BASE_DIR / "data" / "keywords_output"
LOG_DIR = BASE_DIR / "logs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 로깅 설정 ───────────────────────────────────────────

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    LOG_DIR / "extract_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    encoding="utf-8",
)

# ── 환경변수 / API 키 ──────────────────────────────────

load_dotenv(PROJECT_ROOT / ".env")

MAX_CONCURRENT = 30
MAX_RETRIES = 3
BATCH_SIZE = 100  # 한 번에 gather할 태스크 수


def _load_api_keys() -> list[str]:
    """환경변수에서 Gemini API 키를 로드한다."""
    keys: list[str] = []
    for key_name in ("GOOGLE_API_KEY", "GOOGLE_API_KEY_2"):
        val = os.environ.get(key_name, "")
        if val:
            keys.append(val)
    return keys


# ── 통계 ────────────────────────────────────────────────


class Stats:
    """비동기 안전한 처리 통계."""

    def __init__(self) -> None:
        self.success = 0
        self.failed = 0
        self.no_claims = 0
        self._lock = asyncio.Lock()

    async def inc(self, field: str) -> None:
        async with self._lock:
            setattr(self, field, getattr(self, field) + 1)

    @property
    def processed_total(self) -> int:
        return self.success + self.failed + self.no_claims


# ── LLM 호출 ───────────────────────────────────────────


async def call_gemini_async(
    semaphore: asyncio.Semaphore,
    client: genai.Client,
    claims_text: str,
    patent_id: str,
) -> dict | None:
    """Gemini 2.0 Flash를 네이티브 async로 호출한다."""
    user_prompt = f"출원번호: {patent_id}\n\n청구항:\n{claims_text}"

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[SYSTEM_PROMPT, user_prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.1,
                    ),
                )
                text = response.text.strip()
                return json.loads(text)

            except json.JSONDecodeError:
                cleaned = re.sub(r"```json\s*|\s*```", "", text)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    logger.warning(f"JSON 파싱 실패 (시도 {attempt+1}): {patent_id}")

            except Exception as e:
                logger.warning(
                    f"API 실패 (시도 {attempt+1}, {type(e).__name__}): {patent_id} - {e}"
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(2**attempt)

    return None


# ── 파일 처리 ───────────────────────────────────────────


async def process_file(
    semaphore: asyncio.Semaphore,
    client: genai.Client,
    filepath: Path,
    processed: set[str],
    stats: Stats,
    total: int,
) -> None:
    """특허 JSON 1건을 처리한다."""
    # 빠른 스킵
    qid = quick_patent_id(filepath)
    if qid and qid in processed:
        return

    # JSON 읽기
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"JSON 읽기 실패: {filepath.name} - {e}")
        await stats.inc("failed")
        return

    patent_id = extract_patent_id(filepath, data)
    if patent_id in processed:
        return

    # 청구항 추출
    claims = extract_claims(data)
    if not claims:
        save_result(
            OUTPUT_DIR,
            patent_id,
            {"patent_id": patent_id, "selected_claim": None, "mappings": []},
        )
        await stats.inc("no_claims")
        return

    # LLM 호출
    result = await call_gemini_async(
        semaphore, client, format_claims_for_prompt(claims), patent_id
    )

    if result is None:
        logger.error(f"LLM 추출 실패: {patent_id}")
        await stats.inc("failed")
    else:
        save_result(OUTPUT_DIR, patent_id, result)
        await stats.inc("success")

    # 진행 상황 (100건마다)
    done = stats.processed_total
    if done % 100 == 0:
        logger.info(f"진행: {done:,}/{total:,} (성공: {stats.success:,} | 실패: {stats.failed:,})")


# ── 메인 ────────────────────────────────────────────────


async def main() -> None:
    """전체 JSON 파일을 비동기로 순회하며 키워드를 추출한다."""
    api_keys = _load_api_keys()
    if not api_keys:
        logger.error("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    client = genai.Client(api_key=api_keys[0])
    logger.info(f"API 키 {len(api_keys)}개 로드 | 동시 요청: {MAX_CONCURRENT}개")

    json_files = sorted(glob(str(DATA_DIR / "**" / "*.json"), recursive=True))
    total = len(json_files)
    processed = get_processed_ids(OUTPUT_DIR)
    remaining = total - len(processed)
    logger.info(f"전체: {total:,} | 처리됨: {len(processed):,} | 남은: {remaining:,}")

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    stats = Stats()

    # 배치 단위로 처리 (78K개를 한번에 gather하면 멈춤)
    for batch_start in range(0, total, BATCH_SIZE):
        batch = json_files[batch_start : batch_start + BATCH_SIZE]
        tasks = [
            process_file(semaphore, client, Path(f), processed, stats, total)
            for f in batch
        ]
        await asyncio.gather(*tasks)

        done = stats.processed_total
        logger.info(
            f"배치 완료 [{batch_start+1}~{batch_start+len(batch)}] | "
            f"성공: {stats.success:,} | 실패: {stats.failed:,} | 청구항없음: {stats.no_claims:,}"
        )

    logger.info("=" * 50)
    logger.info(
        f"완료 — 성공: {stats.success:,} | 실패: {stats.failed:,} | 청구항없음: {stats.no_claims:,}"
    )
    logger.info(f"결과: {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
