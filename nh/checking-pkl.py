import pickle

with open('child_documents.pkl', 'rb') as f:
    child_docs = pickle.load(f)

empty_docs = [d for d in child_docs if not d.page_content or not d.page_content.strip()]
print(f'빈 문서 수: {len(empty_docs)} / 전체: {len(child_docs)}')

none_meta = [d for d in child_docs if any(v is None for v in d.metadata.values())]
print(f'None 메타데이터 포함 문서 수: {len(none_meta)}')

first_batch = child_docs[:1000]
empty_in_batch = [d for d in first_batch if not d.page_content or not d.page_content.strip()]
print(f'첫 배치 빈 문서: {len(empty_in_batch)} / 1000')
