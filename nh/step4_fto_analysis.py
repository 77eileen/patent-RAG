"""
Step4. FTO 침해 분석 (Gemini 2.0 Flash)

1. 사용자 질문 입력
2. 구성요소 추출 + 검색어 생성 + 특허 검색 (step3와 동일)
3. FTO 분석 파이프라인 (Step A -> B -> C)
4. HTML 보고서 생성

연결: step3 (utils_v3) -> step4 (fto_analyzer)
"""

import pickle
import os
import sys
import time
from datetime import datetime
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv


# ============================================
# 로그 저장: 터미널 출력을 파일에도 동시 기록
# ============================================
class TeeLogger:
    def __init__(self, log_path):
        self.terminal = sys.stdout
        self.log_file = open(log_path, 'w', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

    def close(self):
        self.log_file.close()
        sys.stdout = self.terminal


log_filename = f"log/fto_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
sys.stdout = TeeLogger(log_filename)

# step3와 동일한 유틸리티 함수 (utils_v3)
from utils_v3 import (
    extract_components,
    create_search_queries_from_components,
    search_patents_with_multiple_queries
)

# step4: FTO 분석기
from fto_analyzer import run_fto_analysis

load_dotenv()

# API 키 확인
openai_api_key = os.environ.get('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError('OPENAI_API_KEY not set (임베딩에 필요)')

google_api_key = os.environ.get('GOOGLE_API_KEY')
if not google_api_key:
    raise ValueError('GOOGLE_API_KEY not set (Gemini LLM에 필요)')

# ============================================
# 벡터 DB 및 모델 준비
# ============================================

# 임베딩 (OpenAI - 벡터 DB 호환)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)

# Vector Store 로드 (Parent DB)
vectorstore = Chroma(
    persist_directory="./chroma_db_parent",
    embedding_function=embeddings,
    collection_name="patent_parent"
)

# Parent Store 로드
with open('parent_documents.pkl', 'rb') as f:
    parent_store = pickle.load(f)

print(f"Vector Store (Parent DB) 로드 완료")
print(f"Parent Store 로드 완료: {len(parent_store)}개 특허")

# LLM: Gemini 2.0 Flash (구성요소 추출 + 검색어 생성용)
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
print(f"LLM: Gemini 2.0 Flash 준비 완료")


# ============================================
# 파이프라인 실행
# ============================================

start_time = time.time()

# 사용자 질문
query = "글리세린, 히알루론산, 우뭇가사리로 마스크 팩을 만들려고 해. 침해될까?"

# ── Step 1: 구성요소 추출 ──
print(f"\n{'='*80}")
print("Step 1: 구성요소 추출 (Gemini 2.0 Flash)")
print(f"{'='*80}\n")

components = extract_components(query, llm)
print("추출된 구성 요소:")
print(components)
print()

# ── Step 2: 검색어 조합 생성 ──
print(f"{'='*80}")
print("Step 2: 검색어 조합 생성 (Gemini 2.0 Flash)")
print(f"{'='*80}\n")

search_queries = create_search_queries_from_components(
    components_text=components,
    min_combination_size=2,
    max_combination_size=None,
    include_single_ingredients=False,
    verbose=True
)

# ── Step 3: 다중 검색어로 특허 검색 ──
print(f"{'='*80}")
print("Step 3: 다중 검색어로 특허 검색")
print(f"{'='*80}\n")

patents_data = search_patents_with_multiple_queries(
    search_queries=search_queries,
    vectorstore=vectorstore,
    parent_store=parent_store,
    top_n=10,
    k_per_query=50
)

# 검색 결과 요약
print(f"{'='*80}")
print(f"검색 완료: {len(patents_data)}건 특허 발견")
print(f"{'='*80}\n")

for patent in patents_data:
    print(f"[{patent['rank']}] {patent['title']}")
    print(f"    출원번호: {patent['application_number']}")
    print(f"    등록번호: {patent['register_number']}")
    print(f"    히트 횟수: {patent['hit_count']}")
    print(f"    최고 유사도: {patent['best_similarity_score']:.4f}")
    print()

# ── Step 4: FTO 침해 분석 ──
print(f"{'='*80}")
print("Step 4: FTO 침해 분석 시작")
print(f"{'='*80}\n")

report_path = run_fto_analysis(
    user_query=query,
    user_components=components,
    patents_data=patents_data
)

# ── 완료 ──
elapsed = time.time() - start_time
print(f"\n{'='*80}")
print(f"전체 파이프라인 완료!")
print(f"HTML 보고서: {report_path}")
print(f"총 소요 시간: {elapsed:.1f}초 ({elapsed/60:.1f}분)")
print(f"{'='*80}")
