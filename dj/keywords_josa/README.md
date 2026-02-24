# keywords_josa - 특허 청구항 키워드 추출 파이프라인

정규표현식 기반 조사/어미 제거 방식으로 특허 청구항에서 키워드를 추출한다.
형태소 분석기(Kiwi, Okt, Komoran)는 화학 화합물명을 내부 분해하므로 사용하지 않는다.

## 왜 형태소 분석기가 아닌 정규식인가?

| 방식 | 입력 | 출력 | 문제 |
|------|------|------|------|
| Kiwi 형태소 분석 | `트리에탄올아민에` | `트리`, `에탄올`, `아민`, `에` | 화합물명 분해됨 |
| 정규식 조사 제거 | `트리에탄올아민에` | `트리에탄올아민` | 화합물명 보존 |

`에`, `로` 같은 조사가 화합물명 내부에 있어도, 공백 기준 토큰의 **끝**에서만 제거하므로 안전하다.

## 파이프라인 구조

```
JSON 파일 (78,587개)
    │
    ▼
[1] parse_patent()          → patent_id, claims 추출 (last_version)
    │
    ▼
[2] build_claim_clusters()  → 독립항 기준 클러스터 생성
    │                         (종속항은 refers_to로 합침)
    ▼
[3] extract_keywords()
    ├─ remove_claim_prefixes()  → "제N항에 있어서" 등 제거
    ├─ clean_special_chars()    → ().,;:!? → 공백
    ├─ remove_josa()            → EOMI_2 반복 제거 → JOSA_1 1회 제거
    ├─ STOPWORDS 필터           → 불용어 제거
    └─ NOISE_PATTERNS 필터      → 숫자+단위, 화학식 변수 등 제거
    │
    ▼
CSV 출력 (patent_id, chunk_id, keyword)
    │
    ▼
MySQL 로드 (patent_fto.claim_keywords)
```

## 조사/어미 제거 로직

2단계로 나눠서 과도한 제거를 방지한다.

**EOMI_2** (2글자 이상 어미, 반복 제거):
```
# v1 기본
으로부터, 포함하는, 구성되는, 구성된, 선택된, 되는, 하는, 된, 하여,
으로, 에서, 이며, 이고, 시키고, 시켜, 시키, 시킨, 시키지,
하고, 으로서, 하기, 하며, 되고

# v2 추가
로부터, 에게,
시키거나, 하거나, 되거나, 거나,
하되, 하지만, 하지, 되지,
시키도록, 하도록, 되도록, 도록,
하면서, 되면서,
함으로써, 됨으로써, 으로써,
시키기, 시킬, 시키며, 시켜서, 시키고자, 시킨다, 시키는, 시킴
```

**JOSA_1** (1글자 조사, 1회만 제거):
```
을, 를, 이, 가, 은, 는, 의, 에, 로, 와, 과
```

1글자를 반복 제거하면 `효과의` → `효과` → `효`처럼 의미가 깨지므로 1회만 적용한다.

## 폴더 구조

```
keywords_josa/
├── extract_claim_keywords.py          ← 핵심 로직 (쿼리 전처리에도 사용)
├── run_full.py                        ← 전체 78,587개 실행
├── prefilter_keywoards_load_to_mysql.py  ← CSV → MySQL 로드
├── README.md
├── output/                            ← 출력 데이터/로그 (git 제외)
│   ├── claim_keywords_full.csv
│   ├── errors.log
│   └── recovery.log
└── debug/                             ← 디버그/1회성 스크립트
    └── fix_no_cluster.py              ← 4건 복구 (fallback 전략)
```

## 실행 방법

```bash
# conda 환경
conda activate patent310

# 1. 샘플 테스트 (5개)
python extract_claim_keywords.py

# 2. 전체 실행 (78,587개 → ~8분)
python run_full.py

# 3. 클러스터 실패 복구 (4건)
python debug/fix_no_cluster.py

# 4. MySQL 로드 (~17분)
python prefilter_keywoards_load_to_mysql.py
```

## 실행 결과 (v2)

| 항목 | v1 | v2 |
|------|-----|-----|
| 처리 파일 수 | 78,587 | 78,587 |
| 총 키워드 행 | 10,602,457 | **10,358,451** |
| 고유 patent_id | 78,587 | 78,583 |
| 고유 chunk_id | 259,667 | 259,663 |

v2에서 약 24만 행 감소 (불필요한 어미 패턴 제거)

### 키워드 빈도 TOP 10 (v2)

| 순위 | keyword | count |
|------|---------|-------|
| 1 | 조성물 | 141,356 |
| 2 | 방법 | 73,633 |
| 3 | 화합물 | 61,056 |
| 4 | 치료 | 58,471 |
| 5 | 단계 | 55,036 |
| 6 | 예방 | 46,138 |
| 7 | 투여 | 45,400 |
| 8 | 허용 | 44,012 |
| 9 | 서열 | 42,512 |
| 10 | 약학적 | 42,049 |

## 사용자 쿼리 전처리 (팀원용)

DB에 저장된 키워드와 매칭하려면, 사용자 질문도 **같은 함수로 전처리**해야 한다.

```python
from extract_claim_keywords import extract_keywords

# 사용자 질문 → 키워드 리스트
query = "트리에탄올아민을 포함하는 화장료 조성물"
keywords = extract_keywords(query)
# → ['트리에탄올아민', '화장료', '조성물']
```

```python
# DB 검색
placeholders = ",".join(["%s"] * len(keywords))
sql = f"""
    SELECT patent_id, chunk_id, COUNT(*) as match_count
    FROM claim_keywords
    WHERE keyword IN ({placeholders})
    GROUP BY patent_id, chunk_id
    ORDER BY match_count DESC
    LIMIT 20
"""
cur.execute(sql, keywords)
```

## MySQL 테이블

```sql
-- DB: patent_fto
CREATE TABLE claim_keywords (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patent_id VARCHAR(20) NOT NULL,
    chunk_id VARCHAR(30) NOT NULL,
    keyword VARCHAR(500) NOT NULL,
    INDEX idx_keyword (keyword(100)),
    INDEX idx_chunk (chunk_id),
    INDEX idx_patent (patent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 데이터 소스

- 입력: `dj/data/json_refine/` (날짜별 하위 디렉토리, 78,587개 JSON)
- JSON 구조: `claims.last_version.claims[]` 에서 `claim_type`, `claim_number`, `refers_to`, `text` 사용
