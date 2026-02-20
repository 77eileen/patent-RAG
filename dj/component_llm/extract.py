"""Gemini로 특허 청구항 구성요소를 추출하여 CSV로 저장하는 비동기 스크립트.

사용법:
    python -m component_llm.extract              # 전체 실행
    python -m component_llm.extract --sample 5   # 샘플 5건
"""

import asyncio
import csv
import json
import sys
from glob import glob
from pathlib import Path

from google import genai
from google.genai import types
from loguru import logger

from .config import (
    BATCH_SIZE,
    DATA_DIR,
    FLUSH_EVERY,
    GOOGLE_API_KEYS,
    LOG_DIR,
    MAX_CONCURRENT,
    MAX_RETRIES,
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
    quick_patent_id,
)

# ── 로깅 설정 ─────────────────────────────────────────

logger.remove()
logger.add(sys.stderr, level="INFO", format="{time:HH:mm:ss} | {level:<7} | {message}")
logger.add(
    LOG_DIR / "extract_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="30 days",
    encoding="utf-8",
)

# ── CSV 경로 ──────────────────────────────────────────

CSV_PATH = OUTPUT_DIR / "components.csv"
FAIL_CSV_PATH = OUTPUT_DIR / "failed_patents.csv"
CSV_HEADER = ["patent_id", "chunk_id", "components", "note"]
FAIL_HEADER = ["patent_id", "claim_number", "error"]


# ── 통계 ─────────────────────────────────────────────


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
    def total(self) -> int:
        return self.success + self.failed + self.no_claims


# ── CSV 버퍼 (크기 기반 flush) ────────────────────────


class CsvBuffer:
    """버퍼에 30건 쌓이면 CSV에 flush한다."""

    def __init__(self, path: Path, header: list[str], flush_every: int) -> None:
        self._path = path
        self._header = header
        self._flush_every = flush_every
        self._buffer: list[list[str]] = []
        self._lock = asyncio.Lock()
        # 기존 파일이 있으면 append 모드
        self._initialized = path.exists() and path.stat().st_size > 0

    async def append(self, row: list[str]) -> None:
        async with self._lock:
            self._buffer.append(row)
            if len(self._buffer) >= self._flush_every:
                self._flush()

    def _flush(self) -> None:
        if not self._buffer:
            return
        mode = "a" if self._initialized else "w"
        with open(self._path, mode, newline="", encoding="utf-8") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            if not self._initialized:
                writer.writerow(self._header)
                self._initialized = True
            writer.writerows(self._buffer)
        logger.debug(f"CSV flush: {len(self._buffer)}건 → {self._path.name}")
        self._buffer.clear()

    async def flush_remaining(self) -> None:
        async with self._lock:
            self._flush()


# ── 이미 처리된 chunk_id 로드 ─────────────────────────


def get_processed_chunk_ids() -> set[str]:
    """기존 CSV에서 처리 완료된 chunk_id 집합을 로드한다."""
    if not CSV_PATH.exists():
        return set()
    ids: set[str] = set()
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ids.add(row["chunk_id"])
    return ids


# ── Gemini 클라이언트 생성 ────────────────────────────


def _build_clients() -> list[genai.Client]:
    """API 키별 Gemini 클라이언트 리스트를 생성한다."""
    return [genai.Client(api_key=k) for k in GOOGLE_API_KEYS]


# ── LLM 호출 (키 fallback 포함) ──────────────────────


async def call_gemini(
    semaphore: asyncio.Semaphore,
    clients: list[genai.Client],
    user_prompt: str,
    patent_id: str,
    claim_number: int,
) -> str | None:
    """Gemini를 호출하여 구성요소 텍스트를 반환한다.

    첫 번째 API 키로 MAX_RETRIES 시도 후 실패하면 다음 키로 재시도.
    """
    async with semaphore:
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
                    if not text:
                        logger.warning(
                            f"빈 응답 (키{key_idx+1}, 시도{attempt+1}): "
                            f"{patent_id} claim {claim_number}"
                        )
                        continue
                    return text

                except Exception as e:
                    logger.warning(
                        f"API 실패 (키{key_idx+1}, 시도{attempt+1}, "
                        f"{type(e).__name__}): {patent_id} claim {claim_number} - {e}"
                    )
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(2**attempt)

            # 현재 키 전부 실패 → 다음 키 시도
            if key_idx < len(clients) - 1:
                logger.info(f"API 키 {key_idx+1} 실패 → 키 {key_idx+2}로 전환")

    return None


# ── 후처리 ────────────────────────────────────────────


def _clean_response(text: str) -> str:
    """응답에서 '구성요소:' 이후 텍스트만 추출한다."""
    marker = "구성요소:"
    idx = text.rfind(marker)
    if idx >= 0:
        return text[idx:].strip()
    return text


# ── 파일 처리 ─────────────────────────────────────────


async def process_file(
    semaphore: asyncio.Semaphore,
    clients: list[genai.Client],
    filepath: Path,
    processed: set[str],
    stats: Stats,
    csv_buf: CsvBuffer,
    fail_buf: CsvBuffer,
    total_files: int,
) -> None:
    """특허 JSON 1건의 모든 독립항을 처리한다."""
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"JSON 읽기 실패: {filepath.name} - {e}")
        await stats.inc("failed")
        return

    patent_id = extract_patent_id(filepath, data)
    independent_claims = get_independent_claims(data)

    if not independent_claims:
        await stats.inc("no_claims")
        return

    all_claims = get_all_claims(data)

    for claim in independent_claims:
        claim_num = claim["claim_number"]
        chunk_id = f"{patent_id}_claim_{claim_num}"

        if chunk_id in processed:
            continue

        # 종속항 찾기
        dep_nums = find_dependent_numbers(all_claims, claim_num)
        dep_claims = [c for c in all_claims if c["claim_number"] in dep_nums]

        # 텍스트에서 참조하는 다른 청구항 찾기
        ref_nums = find_referenced_claim_numbers(claim.get("text", ""))
        ref_nums = [n for n in ref_nums if n != claim_num]
        ref_claims = (
            [c for c in all_claims if c["claim_number"] in ref_nums]
            if ref_nums else None
        )

        # 프롬프트 빌드 & Gemini 호출
        user_prompt = build_user_prompt(
            claim, dep_claims, patent_id, ref_claims
        )
        result = await call_gemini(
            semaphore, clients, user_prompt, patent_id, claim_num
        )

        if result is None:
            logger.error(f"추출 실패: {patent_id} claim {claim_num}")
            await fail_buf.append([patent_id, str(claim_num), "LLM 응답 실패"])
            await stats.inc("failed")
            continue

        # 후처리: "구성요소:" 이후만 추출
        result = _clean_response(result)

        # note: 종속항 번호
        note = f"dep {','.join(map(str, dep_nums))}" if dep_nums else ""

        await csv_buf.append([patent_id, chunk_id, result, note])
        await stats.inc("success")

    # 진행 로그 (100건마다)
    done = stats.total
    if done > 0 and done % 100 == 0:
        logger.info(
            f"진행: {done:,}/{total_files:,} "
            f"(성공: {stats.success:,} | 실패: {stats.failed:,})"
        )


# ── 메인 ──────────────────────────────────────────────


async def main(sample: int = 0, skip: int = 0) -> None:
    """전체(또는 샘플) JSON 파일을 비동기로 순회하며 구성요소를 추출한다."""
    if not GOOGLE_API_KEYS:
        logger.error("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")
        sys.exit(1)

    clients = _build_clients()
    logger.info(f"API 키 {len(clients)}개 로드 | 동시 요청: {MAX_CONCURRENT}개")

    json_files = sorted(glob(str(DATA_DIR / "**" / "*.json"), recursive=True))
    total = len(json_files)

    if skip > 0:
        json_files = json_files[skip:]
        logger.info(f"스킵: {skip}건")
    if sample > 0:
        json_files = json_files[:sample]
        logger.info(f"샘플 모드: {sample}건만 처리")

    processed = get_processed_chunk_ids()
    logger.info(
        f"전체: {total:,} | 기처리 chunk: {len(processed):,} | 대상: {len(json_files):,}"
    )

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    stats = Stats()
    csv_buf = CsvBuffer(CSV_PATH, CSV_HEADER, FLUSH_EVERY)
    fail_buf = CsvBuffer(FAIL_CSV_PATH, FAIL_HEADER, FLUSH_EVERY)

    # 배치 처리
    file_count = len(json_files)
    for batch_start in range(0, file_count, BATCH_SIZE):
        batch = json_files[batch_start : batch_start + BATCH_SIZE]
        tasks = [
            process_file(
                semaphore, clients, Path(f), processed, stats,
                csv_buf, fail_buf, file_count,
            )
            for f in batch
        ]
        await asyncio.gather(*tasks)

        logger.info(
            f"배치 [{batch_start+1}~{batch_start+len(batch)}] | "
            f"성공: {stats.success:,} | 실패: {stats.failed:,} | "
            f"청구항없음: {stats.no_claims:,}"
        )

    # 잔여분 flush
    await csv_buf.flush_remaining()
    await fail_buf.flush_remaining()

    logger.info("=" * 50)
    logger.info(
        f"완료 — 성공: {stats.success:,} | 실패: {stats.failed:,} | "
        f"청구항없음: {stats.no_claims:,}"
    )
    logger.info(f"CSV: {CSV_PATH}")
    if stats.failed > 0:
        logger.info(f"실패 목록: {FAIL_CSV_PATH}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=0)
    parser.add_argument("--skip", type=int, default=0)
    args = parser.parse_args()
    asyncio.run(main(sample=args.sample, skip=args.skip))
