# Keywords 추출 파이프라인 진행 현황

## 개요

특허 JSON 파일(78,587건)에서 LLM(Gemini 2.0 Flash)을 사용하여 검색용 키워드를 추출하고,
MySQL `search_keywords` 테이블에 적재하는 파이프라인.

## 파일 구조

```
dj/
├── db/                          # DB 레이어
│   ├── __init__.py              # 모듈 export
│   ├── connection.py            # SQLAlchemy 엔진/세션 팩토리
│   ├── models.py                # SearchKeyword ORM 모델
│   ├── repository.py            # Repository 패턴 CRUD
│   └── schemas.py               # Pydantic 입출력 스키마
├── scripts/keywords/            # 키워드 추출 파이프라인
│   ├── __init__.py
│   ├── extract.py               # LLM 비동기 추출 스크립트
│   ├── load_to_db.py            # 추출 결과 → DB 적재 스크립트
│   ├── prompts.py               # LLM 시스템 프롬프트
│   └── utils.py                 # JSON 파싱/파일 I/O 유틸
├── data/
│   ├── json_refine/             # 입력: 특허 JSON 파일 (78,587건)
│   └── keywords_output/         # 출력: LLM 추출 결과 JSON (특허당 1개)
└── logs/                        # loguru 로그 파일
```

## 실행 명령어

```bash
# 1. 키워드 추출 (Gemini 2.0 Flash 비동기 호출)
conda activate patent310
cd C:\00AI\project\project_final\patent-rag\dj
python -m scripts.keywords.extract

# 2. DB 적재 (추출 완료 후)
python -m scripts.keywords.load_to_db
```

## 환경변수 (.env 위치: patent-rag/.env)

```
GOOGLE_API_KEY=...       # Gemini API 키 (필수)
GOOGLE_API_KEY_2=...     # 백업 API 키 (선택)
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/patent_db
```

## DB 스키마

### search_keywords 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | INT (PK, AUTO) | |
| patent_id | VARCHAR(20) | 출원번호 |
| claim_no | INT | 청구항 번호 |
| independent_key | VARCHAR(200) | 독립항 키워드 |
| dependent_key | VARCHAR(200), NULL | 종속항 구체 키워드 |

인덱스:
- `ix_search_keywords_dependent_key` (dependent_key)
- `ix_search_keywords_independent_key` (independent_key)
- `ix_search_keywords_patent_claim` (patent_id, claim_no)

동적 속성: `chunk_id` = `"{patent_id}_claim_{claim_no}"`

## 검색 기능 (repository.py)

- `search_by_term(term)`: independent_key 또는 dependent_key로 통합 검색
- `search_by_terms(terms)`: 여러 키워드 AND 검색 (모든 키워드 포함하는 patent만)

## extract.py 설정값

| 설정 | 값 | 설명 |
|------|-----|------|
| MAX_CONCURRENT | 30 | 동시 API 요청 수 (Semaphore) |
| MAX_RETRIES | 3 | 실패 시 재시도 횟수 |
| BATCH_SIZE | 100 | asyncio.gather 배치 크기 |
| model | gemini-2.0-flash | LLM 모델 |
| temperature | 0.1 | 낮은 창의성 (일관성 우선) |
| response_mime_type | application/json | JSON 강제 출력 |

## LLM 출력 형식

```json
{
  "patent_id": "1020070010798",
  "selected_claims": [1, 8, 9, 10],
  "mappings": [
    {"claim_no": 1, "independent_key": "구절초", "dependent_keys": []},
    {"claim_no": 1, "independent_key": "에탄올", "dependent_keys": []},
    {"claim_no": 8, "independent_key": "제조방법", "dependent_keys": []}
  ]
}
```

## 프롬프트 핵심 규칙

1. **독립항만 mapping 생성** — 종속항은 절대 별도 mapping 금지
2. **종속항은 dependent_keys에만 추가** — refers_to로 해당 독립항 찾아서
3. **수치/범위 추출 금지** — 함량, 배율, 시간, 온도, 비율
4. **모든 독립항 처리** — 1개만 선택 X, text 있는 independent 전부
5. **키워드 정규화** — 공백 제거, 조사 제거
6. **연결어 분리** — "A 또는 B" → ["A", "B"]
7. **제조방법 완전 분해** — 주재료, 부위, 동작, 용매, 용도 각각 추출
8. **종속항 직접 참조만** — refers_to가 독립항을 직접 가리키는 것만 처리
9. **상위-하위 관계 매핑** — 종속항의 새 상위 개념은 새 independent_key로

## 변경 이력

### 2025-02-19

- **type 컬럼 제거**: KeywordType Enum 삭제, DB/스키마/로딩 스크립트에서 type 관련 코드 전부 제거
  - models.py: KeywordType Enum, type Column 삭제
  - schemas.py: type 필드, KeywordType import 삭제
  - __init__.py: KeywordType export 삭제
  - load_to_db.py: type 파싱/삽입 로직 삭제

- **프롬프트 개선** (5차 개정):
  - 입력 JSON 구조 명시 (claims.last_version.claims)
  - 수치/범위 추출 금지 규칙 추가
  - 제조방법 청구항 완전 분해 규칙 추가
  - 구절초 특허 실제 예시 (53개 mapping) 추가
  - 종속항 직접 참조만 처리 규칙 추가
  - 상위-하위 관계 정확 매핑 규칙 추가

- **비동기 추출 구현**:
  - google.genai SDK (new) + client.aio.models.generate_content() 네이티브 async
  - BATCH_SIZE=100 배치 처리 (78K 태스크 한번에 gather 시 멈춤 방지)
  - Semaphore(30) 동시 요청 제한
  - 증분 저장: 특허당 1 JSON, 재시작 시 이미 처리된 건 스킵

## 알려진 이슈

- **Windows asyncio**: Ctrl+C로 중단 시 정상 종료 안 될 수 있음 → `taskkill /F /IM python.exe` 사용
- **API Tier 1 제한**: RPM 2000, TPM 4M, RPD 무제한 — MAX_CONCURRENT=30이면 충분
- **78K 전체 실행 미완료**: 프롬프트 개선 후 전체 재실행 필요

## TODO

- [ ] 프롬프트 최종 확정 후 78K 전체 추출 실행
- [ ] 추출 결과 품질 검증 (샘플링)
- [ ] load_to_db.py로 MySQL 적재
- [ ] 검색 기능 테스트
