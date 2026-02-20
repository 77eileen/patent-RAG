"""
Step 2. 청구항 문서(Child Documents) 벡터 DB 저장

파일 실행시 chromadb/ 폴더(벡터 DB) 생성됨.
"""
import os
import time
import pickle
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError('OPENAI_API_KEY not set')

# ============================================
# 저장된 문서 로드
# ============================================

print("문서 로드 중...")

with open('child_documents.pkl', 'rb') as f:
    child_docs = pickle.load(f)

with open('parent_documents.pkl', 'rb') as f:
    parent_docs = pickle.load(f)

print(f"✓ Child Documents 로드완: {len(child_docs)}개")
print(f"✓ Parent Documents 로드완: {len(parent_docs)}개")


# ============================================
# 임베딩 모델 : OpenAIEmbeddings
# 추후 변경 가능
# ============================================

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=api_key  )

print("✓ OpenAI Embeddings 준비 완료!")


# ============================================
# Chroma Vector Store 구축
# ============================================

print("\nVector Store 구축 중!")
print("wait a moment ~")

# 배치 크기 설정 (토큰 제한 고려)
BATCH_SIZE = 1000 #한번에 처리할 문서 개수

first_batch = child_docs[:BATCH_SIZE]

vectorstore = Chroma.from_documents(
    documents=first_batch,
    embedding=embeddings,
    persist_directory="./chroma_db",#벡터db 저장 위치
    collection_name="patent_claims" #컬렉션 이름
)

print(f"✓ 첫 번째 배치 완료!: {len(first_batch)}개 문서")

#나머지 문서들을 배치로 추가
remaining_docs = child_docs[BATCH_SIZE:]
total_batches = len(remaining_docs) // BATCH_SIZE + (1 if len(remaining_docs) % BATCH_SIZE > 0 else 0)


for i in range(0, len(remaining_docs), BATCH_SIZE):
    batch_num = i // BATCH_SIZE + 2  # 첫 번째 배치 다음부터
    batch = remaining_docs[i:i + BATCH_SIZE]
    
    print(f"배치 {batch_num}/{total_batches + 1} 처리 중... ({len(batch)}개 문서)")
    
    try:
        vectorstore.add_documents(batch)
        print(f"배치 {batch_num} 완료!")
        
        # API 호출 제한 방지를 위한 잠시 대기
        time.sleep(1)
        
    except Exception as e:
        print(f"배치 {batch_num} 에러: {e}")
        # 에러 발생 시 더 작은 배치로 재시도
        smaller_batches = [batch[j:j+20] for j in range(0, len(batch), 20)]
        for small_batch in smaller_batches:
            try:
                vectorstore.add_documents(small_batch)
                time.sleep(0.5)
            except Exception as small_e:
                print(f"소 배치 에러: {small_e}")

print("벡터스토어 생성 완료!")
print(f"저장 경로: ./chroma_db")
print(f"컬렉션명: patent_claims")


# ============================================
print("\n" + "="*50)
print("벡터 DB 구축 완료!")
print("="*50)
print("\n다음 파일들이 생성되었습니다:")
print("  - chroma_db/ (벡터 저장소)")