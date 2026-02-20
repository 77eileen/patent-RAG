"""component_llm 설정 및 상수."""

import os
from pathlib import Path

from dotenv import load_dotenv

# ── 경로 ──────────────────────────────────────────────
MODULE_DIR = Path(__file__).resolve().parent        # component_llm/
BASE_DIR = MODULE_DIR.parent                       # dj/
PROJECT_ROOT = BASE_DIR.parent                     # patent-rag/
DATA_DIR = BASE_DIR / "data" / "json_refine"
OUTPUT_DIR = MODULE_DIR / "output"
LOG_DIR = MODULE_DIR / "logs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── 환경변수 ──────────────────────────────────────────
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_API_KEYS: list[str] = [
    v for k in ("GOOGLE_API_KEY", "GOOGLE_API_KEY_2")
    if (v := os.environ.get(k, ""))
]

MYSQL_URL: str = (
    f"mysql+pymysql://{os.environ.get('MYSQL_USER', 'root')}"
    f":{os.environ.get('MYSQL_PASSWORD', '')}"
    f"@{os.environ.get('MYSQL_HOST', '127.0.0.1')}"
    f":{os.environ.get('MYSQL_PORT', '3306')}"
    f"/{os.environ.get('MYSQL_DATABASE', 'patent_fto')}"
)

# ── 추출 설정 ─────────────────────────────────────────
MAX_CONCURRENT = 5        # 동시 API 요청 수
MAX_RETRIES = 3           # API 실패 시 재시도
BATCH_SIZE = 100          # asyncio.gather 배치 크기
FLUSH_EVERY = 30          # CSV 버퍼 flush 간격 (건수)
MODEL_NAME = "gemini-2.0-flash"
TEMPERATURE = 0
