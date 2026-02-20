"""
Step 2-2. 특허 문헌(Parent Documents) 벡터 DB 저장

parent_documents.pkl에서 특허별 전체 청구항을 하나의 문서로 합쳐서
chroma_db_parent/ 폴더에 벡터 DB를 생성함.
"""
import os
import time
import pickle
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError('OPENAI_API_KEY not set')

# ============================================
# 저장된 문서 로드
# ============================================

print("문서 로드 중...")

with open('parent_documents.pkl', 'rb') as f:
    parent_docs = pickle.load(f)

print(f"✓ Parent Documents 로드완: {len(parent_docs)}개")

# ============================================
# Parent Documents → Document 리스트 변환
# ============================================

print("\nParent Documents → Document 변환 중...")

parent_doc_list = []

for app_number, patent in parent_docs.items():
    # 전체 청구항 텍스트를 하나로 합침
    claim_texts = []
    for claim in patent.get('all_claims', []):
        text = claim.get('text', '').strip()
        if text:
            claim_num = claim.get('claim_number', '')
            claim_type = claim.get('claim_type', '')
            source_type = claim.get('source_type', '')
            claim_texts.append(f"[청구항 {claim_num}] ({claim_type}/{source_type}) {text}")

    if not claim_texts:
        continue

    page_content = "\n\n".join(claim_texts)

    # 메타데이터 (ChromaDB는 str, int, float, bool만 허용)
    metadata = {
        'parent_id': patent.get('parent_id', ''),
        'title': patent.get('title', ''),
        'application_number': patent.get('application_number', ''),
        'open_number': patent.get('open_number', ''),
        'register_number': patent.get('register_number', ''),
        'application_date': patent.get('application_date', ''),
        'open_date': patent.get('open_date', ''),
        'register_date': patent.get('register_date', ''),
        'register_status': patent.get('register_status', ''),
        'ipc_codes': ','.join(patent.get('ipc_codes', [])),
        'abstract': patent.get('abstract', ''),
        'claim_count': patent.get('claim_count', 0),
    }

    # None 값 제거
    metadata = {k: (v if v is not None else '') for k, v in metadata.items()}

    parent_doc_list.append(Document(
        page_content=page_content,
        metadata=metadata
    ))

print(f"✓ 변환 완료: {len(parent_doc_list)}개 문서")

# ============================================
# 임베딩 모델 : OpenAIEmbeddings
# ============================================

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=api_key)

print("✓ OpenAI Embeddings 준비 완료!")

# ============================================
# Chroma Vector Store 구축
# ============================================

print("\nParent Vector Store 구축 중!")
print("wait a moment ~")

BATCH_SIZE = 500

first_batch = parent_doc_list[:BATCH_SIZE]

vectorstore = Chroma.from_documents(
    documents=first_batch,
    embedding=embeddings,
    persist_directory="./chroma_db_parent",
    collection_name="patent_parent"
)

print(f"✓ 첫 번째 배치 완료!: {len(first_batch)}개 문서")

# 나머지 문서들을 배치로 추가
remaining_docs = parent_doc_list[BATCH_SIZE:]
total_batches = len(remaining_docs) // BATCH_SIZE + (1 if len(remaining_docs) % BATCH_SIZE > 0 else 0)

for i in range(0, len(remaining_docs), BATCH_SIZE):
    batch_num = i // BATCH_SIZE + 2
    batch = remaining_docs[i:i + BATCH_SIZE]

    print(f"배치 {batch_num}/{total_batches + 1} 처리 중... ({len(batch)}개 문서)")

    try:
        vectorstore.add_documents(batch)
        print(f"배치 {batch_num} 완료!")
        time.sleep(1)

    except Exception as e:
        print(f"배치 {batch_num} 에러: {e}")
        smaller_batches = [batch[j:j+20] for j in range(0, len(batch), 20)]
        for small_batch in smaller_batches:
            try:
                vectorstore.add_documents(small_batch)
                time.sleep(0.5)
            except Exception as small_e:
                print(f"소 배치 에러: {small_e}")

# ============================================
print("\n" + "="*50)
print("Parent 벡터 DB 구축 완료!")
print("="*50)
print(f"\n저장 경로: ./chroma_db_parent")
print(f"컬렉션명: patent_parent")
print(f"총 문서 수: {len(parent_doc_list)}개")
