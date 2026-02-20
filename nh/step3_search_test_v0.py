"""
Step3. 벡터 DB 검색 테스트

1️. 사용자 질문 입력
2️. 구성요소 추출 (utils.extract_components)
3️. 검색어 조합 생성 (utils.create_search_queries_from_components)
4️. 모든 조합 검색 실행 (utils.search_patents_with_multiple_queries)
5️. 결과 출력


"""

import pickle
import os
import sys
from datetime import datetime
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from collections import Counter, defaultdict
from langchain_core.runnables import RunnablePassthrough
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


log_filename = f"search_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
sys.stdout = TeeLogger(log_filename)
from utils import (
    extract_components,
    create_search_queries_from_components,
    search_patents_with_multiple_queries
)
from langchain_openai import ChatOpenAI
load_dotenv()
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError('OPENAI_API_KEY not set')

embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=api_key)

# Vector Store 로드
vectorstore = Chroma(
    persist_directory="./chroma_db", #저장한 경로
    embedding_function=embeddings,
    collection_name="patent_claims" #저장시 설정한 컬렉션명
)

# Parent Store 로드
with open('parent_documents.pkl', 'rb') as f:
    parent_store = pickle.load(f)

print(f"✓ Vector Store 로드 완료")
print(f"✓ Parent Store 로드 완료: {len(parent_store)}개 특허")

# LLM
llm = ChatOpenAI(model="gpt-4o", temperature=0)


# 사용자 질문
query = "글리세린, 히알루론산, 우뭇가사리로 마스크 팩을 만들려고 해. 침해될까?"

# Step 1: 구성요소 추출
print(f"{'='*80}")
print("Step 1: 구성요소 추출")
print(f"{'='*80}\n")

components = extract_components(query, llm)
print("추출된 구성 요소:")
print(components)
print()

# Step 2: 검색어 조합 생성
print(f"{'='*80}")
print("Step 2: 검색어 조합 생성")
print(f"{'='*80}\n")

search_queries = create_search_queries_from_components(
    components_text=components,
    min_combination_size=2,
    max_combination_size=None,  # 모든 조합
    include_single_ingredients=False,
    verbose=True
)

# Step 3: 다중 검색어로 특허 검색
print(f"{'='*80}")
print("Step 3: 다중 검색어로 특허 검색")
print(f"{'='*80}\n")

patents_data = search_patents_with_multiple_queries(
    search_queries=search_queries,
    vectorstore=vectorstore,
    parent_store=parent_store,
    top_n=2,
    k_per_query=50
)

# Step 4: 최종 결과 출력
print(f"{'='*80}")
print("최종 검색 결과 요약")
print(f"{'='*80}\n")
for patent in patents_data:
    print(f"[{patent['rank']}] 특허명: {patent['title']}")
    print(f"    출원번호: {patent['application_number']}")
    print(f"    등록번호: {patent['register_number']}")
    print(f"    히트 횟수: {patent['hit_count']}")
    print(f"    최고 유사도: {patent['best_similarity_score']:.4f}")
    print(f"    평균 유사도: {patent['avg_similarity_score']:.4f}")
    print(f"    히트 검색어 ({len(patent['hit_queries'])}개):")
    for qi, (q, s) in enumerate(patent['hit_queries'], 1):
        print(f"      {qi}. [{s:.4f}] {q}")
    print(f"    청구항 내용:{patent['all_claims']}\n")
