# component_llm

특허 청구항에서 **구성요소(components)**를 Gemini 2.0 Flash로 추출하여 CSV/MySQL에 저장하는 파이프라인.

## 구조

```
component_llm/
├── config.py                 # 경로, API 키, 추출 설정
├── utils.py                  # JSON 파싱 유틸 (독립항/종속항/참조 추출)
├── prompts.py                # 시스템 프롬프트 + 유저 프롬프트 빌더
├── extract.py                # 구성요소 추출 메인 (비동기, Gemini API)
├── component_load_to_db.py   # CSV → MySQL 적재 (독립 실행 가능)
├── __init__.py
├── output/                   # 추출 결과 CSV
│   └── components.csv
├── logs/                     # 실행 로그
├── debug/                    # 디버깅/복구 스크립트
│   ├── retry_failed.py       # 실패 건 재시도
│   ├── check_failed.py       # 실패 청구항 정보 확인
│   └── check_max_len.py      # CSV 컬럼 최대 길이 확인
└── README.md
```

## 실행 방법

### 1. 구성요소 추출 (Gemini API)

```bash
cd dj
python -m component_llm.extract              # 전체 실행
python -m component_llm.extract --sample 5   # 샘플 5건
```

- 데이터 소스: `dj/data/json_refine/` (78,587개 JSON)
- 대상: `last_version.claims` 중 독립항 (claim_type=independent, text 비어있지 않음, change_code != D)
- 출력: `component_llm/output/components.csv`
- 이어하기: 기존 CSV의 chunk_id를 읽어 자동 스킵
- API 키: `.env`의 `GOOGLE_API_KEY`, `GOOGLE_API_KEY_2` (fallback)

### 2. MySQL 적재

```bash
python component_load_to_db.py
```

- DB: `patent_fto.components`
- 필요 패키지: `pymysql`, `python-dotenv`
- `.env`에서 DB 접속 정보 읽음

### 3. 실패 건 복구

```bash
python -m component_llm.debug.retry_failed
```

## DB 스키마

```sql
CREATE TABLE components (
    chunk_id   VARCHAR(30)  PRIMARY KEY,   -- {patent_id}_claim_{N}
    patent_id  VARCHAR(20)  NOT NULL,
    components MEDIUMTEXT   NOT NULL,       -- "구성요소:\n1. ...\n2. ..."
    note       TEXT,                        -- "dep 2,3,4" (종속항 번호)
    INDEX idx_patent (patent_id)
);
```

## CSV 컬럼

| 컬럼 | 설명 | 예시 |
|------|------|------|
| patent_id | 출원번호 | 1020140111006 |
| chunk_id | PK (patent_id + claim번호) | 1020140111006_claim_1 |
| components | 추출된 구성요소 목록 | 구성요소:\n1. A\n2. B |
| note | 참조한 종속항 번호 | dep 2,3,4 |

## 추출 결과

- 전체 파일: 78,587개
- 추출 성공: 254,827건 (파일당 평균 ~3.2개 독립항)
- 실패: 0건 (6건 복구 완료)
- DB 적재: 259,687건
