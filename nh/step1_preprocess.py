"""


Step 1. 특허 json 파일 전처리 및 저장
코드 실행시 child_documents.pkl, parent_documents.pkl 파일 생성됨.

- child_documents.pkl: 청구항 단위의 Document 리스트 
- parent_documents.pkl: 특허 문헌 단위, 전체 청구항 보관

"""

import json
import glob
import os
import pickle
from typing import List, Dict
from langchain_core.documents import Document


# 1. 데이터 로드 및 전처리

# json 파일이 들어있는 경로 설정
patent_paths = [r"data\json_refine"]

# Child Documents (Vector Store용 - 청구항들)
child_docs = []

# Parent Documents (Document Store용 - 전체 특허 정보)
parent_docs = {}

# json -> Document 변환
# 각 경로 순회
for path in patent_paths:
    print(f"처리 중인 경로: {path}")
    
    for file_path in glob.glob(os.path.join(path, "**", "*.json"), recursive=True):
        try:
            # JSON 로드
            with open(file_path, "r", encoding="utf-8") as f:
                raw_patent = json.load(f)
            
            # Bibliographic 정보 추출
            biblio = raw_patent.get('biblioSummaryInfoArray', {}).get('biblioSummaryInfo', {})
            
            # IPC 코드 추출
            ipc_list = raw_patent.get('ipcInfoArray', {}).get('ipcInfo', [])
            if isinstance(ipc_list, dict):
                ipc_list = [ipc_list]
            elif not isinstance(ipc_list, list):
                ipc_list = []
            ipc_codes = [ipc.get('ipcNumber', '') for ipc in ipc_list]
            
            # 초록 추출
            abstract = raw_patent.get('abstractInfoArray', {}).get('abstractInfo', {}).get('astrtCont', '')
            
            # Claims 추출
            claims_data = raw_patent.get('claims', {})

            # 공개청구항 
            open_claims = claims_data.get('first_version', {}).get('claims', [])

            # (status=등록) 등록청구항 / (status=공개) 가장 마지막 변동이력인 공개청구항
            register_claims = claims_data.get('last_version', {}).get('claims', [])

            #변동이력
            total_amendments = claims_data.get('total_amendments', '')
            
            # 기본 정보
            app_number = biblio.get('applicationNumber', '') # 출원번호
            title = biblio.get('inventionTitle', '') # 특허명
            
            if not app_number:
                continue
            
            # ============================================
            # Child Documents 생성 (각 청구항)
            # ============================================

            # 등록번호 확인
            register_number = biblio.get('registerNumber', '')
            
            # last_version 청구항 저장
            for claim in register_claims:

                # 문서 내용: 청구항 
                page_content = claim.get('text', '')
                
                if not page_content.strip():
                    continue
                
                # 메타데이터 구성
                metadata = {

                    'parent_id': app_number, # 출원번호(부모 문서 ID)
                    'claim_number': claim.get('claim_number'), # 청구항 번호
                    'claim_type': claim.get('claim_type', ''), # 청구항 유형 (독립항/종속항)
                    'total_amendments': total_amendments, # 변동이력

                    # 서지정보
                    'application_number': app_number, # 출원번호
                    'open_number': biblio.get('openNumber', ''), # 공개번호
                    'register_number': register_number, # 등록번호
                    'title': title, # 특허명
                    'title_eng': biblio.get('inventionTitleEng', ''), # 영문 특허명'
                    'application_date': biblio.get('applicationDate', ''), # 출원일
                    'open_date': biblio.get('openDate', ''), # 공개일
                    'register_date': biblio.get('registerDate', ''), # 등록일
                    'register_status': biblio.get('registerStatus', ''), # 등록상태
                    'ipc_codes': ','.join(ipc_codes), # IPC 코드들
                    'abstract': abstract, # 초록

                    #기존 메타데이터에 source_type 추가
                    'source_type' : 'last_version', # 문서 유형: 마지막 변동
                }
                
                child_docs.append(Document(
                    page_content=page_content,
                    metadata=metadata
                ))


            # first_version 청구항 저장 (등록번호가 있는 경우만)
            if register_number:
                for claim in open_claims:

                    # 문서 내용: 청구항 
                    page_content = claim.get('text', '')
                    
                    if not page_content.strip():
                        continue
                    
                    # 메타데이터 구성
                    metadata = {

                        'parent_id': app_number, # 출원번호(부모 문서 ID)
                        'claim_number': claim.get('claim_number'), # 청구항 번호
                        'claim_type': claim.get('claim_type', ''), # 청구항 유형 (독립항/종속항)
                        'total_amendments': total_amendments, # 변동이력

                        # 서지정보
                        'application_number': app_number, # 출원번호
                        'open_number': biblio.get('openNumber', ''), # 공개번호
                        'register_number': register_number, # 등록번호
                        'title': title, # 특허명
                        'title_eng': biblio.get('inventionTitleEng', ''), # 영문 특허명'
                        'application_date': biblio.get('applicationDate', ''), # 출원일
                        'open_date': biblio.get('openDate', ''), # 공개일
                        'register_date': biblio.get('registerDate', ''), # 등록일
                        'register_status': biblio.get('registerStatus', ''), # 등록상태
                        'ipc_codes': ','.join(ipc_codes), # IPC 코드들
                        'abstract': abstract, # 초록

                        # 기존에 없던 항목
                        'source_type' : 'first_version', # 문서 유형: 최초 변동

                    }
                    
                    child_docs.append(Document(
                        page_content=page_content,
                        metadata=metadata
                    ))
            

            
            # ============================================
            # Parent Document 생성 (전체 특허)
            # ============================================
           
            # 필요한 필드(claim_number, claim_type, text, source_type)만 추출
            all_claims = []
            
            # last_version 청구항 (등록/공개 청구항)
            for claim in register_claims:
                all_claims.append({
                    'claim_number': claim.get('claim_number'),
                    'claim_type': claim.get('claim_type', ''),
                    'text': claim.get('text', ''),
                    'source_type': 'last_version'
                })
            
            # first_version 청구항 (등록특허인 경우만)
            if register_number:
                for claim in open_claims:
                    all_claims.append({
                        'claim_number': claim.get('claim_number'),
                        'claim_type': claim.get('claim_type', ''),
                        'text': claim.get('text', ''),
                        'source_type': 'first_version'
                    })
            
            parent_docs[app_number] = {
                'parent_id': app_number,
                'title': title,
                'application_number': app_number,
                'open_number': biblio.get('openNumber', ''),
                'register_number': register_number,
                'application_date': biblio.get('applicationDate', ''),
                'open_date': biblio.get('openDate', ''),
                'register_date': biblio.get('registerDate', ''),
                'register_status': biblio.get('registerStatus', ''),
                'ipc_codes': ipc_codes,
                'abstract': abstract,
                'all_claims': all_claims, # 모든 청구항 정보 (source_type 포함)
                'claim_count': len(all_claims)
            }
            
        except Exception as e:
            print(f"오류 발생 ({file_path}): {e}")
            continue

print(f"\n총 {len(child_docs)}개의 청구항 문서 생성")
print(f"총 {len(parent_docs)}개의 특허 문헌 저장")


# ============================================
# 문서 저장
# ============================================

# Child Documents 저장
with open('child_documents.pkl', 'wb') as f:
    pickle.dump(child_docs, f)
print(f"✓ Child Documents 저장 완료: child_documents.pkl")

# Parent Documents 저장
with open('parent_documents.pkl', 'wb') as f:
    pickle.dump(parent_docs, f)
print(f"✓ Parent Documents 저장 완료: parent_documents.pkl")


# ============================================
# 잘만들어졌는지 확인
# ============================================

# Child Documents 로드
with open('child_documents.pkl', 'rb') as f:
    child_docs = pickle.load(f)
print(f"✓ Child Documents 로드 완료: child_documents.pkl")

# Parent Documents 로드
with open('parent_documents.pkl', 'rb') as f:
    parent_docs = pickle.load(f)
print(f"✓ Parent Documents 로드 완료: parent_documents.pkl")

print("\n" + "="*50)
print("Child Document 샘플 (청구항)")
print("="*50)

for i in range(min(3, len(child_docs))):
    doc = child_docs[i]
    print(f"\n[청구항 {i+1}]")
    print(f"내용: {doc.page_content[:150]}...")
    print(f"특허명: {doc.metadata['title']}")
    print(f"출원번호: {doc.metadata['application_number']}")
    print(f"출원일자: {doc.metadata['application_date']}")
    print(f"공개번호: {doc.metadata['open_number']}")
    print(f"등록번호: {doc.metadata['register_number']}")
    print(f"등록상태: {doc.metadata['register_status']}")
    print(f"청구항 번호: {doc.metadata['claim_number']} ({doc.metadata['claim_type']})")   
    print(f"변동이력: {doc.metadata['total_amendments']}")
    print(f"소스 유형: {doc.metadata['source_type']}")

print("\n" + "="*50)
print("Parent Document 샘플 (전체 특허)")
print("="*50)

for i, (parent_id, parent) in enumerate(list(parent_docs.items())[:1]):
    print(f"\n[특허 {i+1}]")
    print(f"출원번호: {parent['parent_id']}")
    print(f"출원일자: {parent['application_date']}")
    print(f"공개번호: {parent['open_number']}")
    print(f"등록번호: {parent['register_number']}")
    print(f"등록상태: {parent['register_status']}")
    print(f"특허명: {parent['title']}")
    print(f"모든 청구항 텍스트: {parent['all_claims']}")
    print(f"청구항 수: {parent['claim_count']}")
    print(f"IPC 코드: {', '.join(parent['ipc_codes'][:3])}")
