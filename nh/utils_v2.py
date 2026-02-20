'''
유틸리티 함수 모음 (v2 - Parent DB 대응)

변경점: search_patents_with_multiple_queries에서
claim_type 필터를 선택적으로 적용 (filter_independent 파라미터)
'''
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from collections import defaultdict
from typing import List, Dict, Tuple, Any
import pickle
import os
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from collections import Counter, defaultdict
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI

from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('OPENAI_API_KEY')
if not api_key:
    raise ValueError('OPENAI_API_KEY not set')

from collections import defaultdict
from typing import List, Dict, Tuple, Any, Set
from itertools import combinations

# ============================================
# 유틸리티 함수 1: 구성요소 추출
# ============================================

def extract_components(query: str, llm) -> str:
    """
    사용자 질문에서 제품의 주요 구성 요소를 추출하는 함수

    Args:
        query (str): 사용자의 질문
        llm: LLM 모델 인스턴스

    Returns:
        str: 추출된 구성 요소 텍스트
    """

    extract_prompt = ChatPromptTemplate([
        ("system", """
너는 특허 침해 분석을 잘하는 변리사야.
사용자의 질문과 유사한 특허를 찾기 위해, 사용자의 질문으로 부터 제품의 구성 요소를 추출한다.

<example>
질문: 화피 추출물, 석류피 추출물, 염부수백피 추출물을 포함하여 여드름이나 염증성 피부 질환을 완화하는 데 효과적인 화장품을 만들었습니다.
이 제품을 시장에 출시해도 괜찮을까요?

구성요소: 화피, 석류피, 염부수백피,여드름, 염증, 피부질환, 화장
</example>

<example>
질문: 수분층 60중량%와 오일층 40 중량%로 구성된 마스크팩을 만들었습니다.
수분층에는 다마스크장미의 꽃을 수증기 증류하여 얻은 다마스크장미꽃수 50 중량%, 천연 트레할로스 10 중량%, 트리에틸시트레이트 10 중량%가 포함되어 있으며,
오일층에는 보검선인장씨오일, 기장씨추출물, 방패버섯추출물, 블랙커런트씨오일, 풍선덩굴꽃/잎/덩굴추출물, 해바라기씨오일불검화물, 블루탄지꽃오일이 각각 5 중량% 포함되어 있습니다.
또한, 락토바실러스발효물을 포함하는 첨가제를 추가하여 아토피 피부염과 건조에 기인한 피부 가려움증을 완화하는 용도로 사용하고자 합니다. 이 제품을 판매해도 될까요?

구성요소: 수분층, 오일층, 수층, 유층,
         다마스크장미, 장미, 트레할로스, 트리에틸시트레이트, 시트레이트, 시트르산,
         보검선인장씨오일, 선인장, 선인장 오일, 선인장시, 기장씨, 방패버섯, 버섯, 블랙커런트씨, 블랙커런트시오일, 풍선덩굴꽃, 풍선덩굴, 덩굴, 덩굴추출물, 해바라기씨오일, 해바라기씨, 블루탄지꽃오일, 블루탄지, 블루탄지꽃
         락토바실러스발효물, 락토바실러스, 아토피, 가려움, 피부가려움, 피부 건조, 마스크팩, 마스크, 팩

</example>
        """),
        ("user", "질문: {question}"),
    ])

    component_extract_chain = (
        {"question": RunnablePassthrough()}
        | extract_prompt
        | llm
    )

    result = component_extract_chain.invoke(query)

    # AIMessage 객체인 경우 content 추출
    if hasattr(result, 'content'):
        return result.content
    return str(result)


# ============================================
# 유틸리티 함수 2: 구성요소 파싱 및 분류 (LLM 기반)
# ============================================

def parse_components(components_text: str, llm) -> Dict[str, List[str]]:
    """
    LLM을 사용하여 추출된 구성요소를 성분과 용도/효능으로 분류

    Args:
        components_text (str): extract_components()로 추출된 텍스트
        llm: LLM 모델 인스턴스

    Returns:
        Dict[str, List[str]]: {'ingredients': [...], 'purposes': [...]}
    """

    classify_prompt = ChatPromptTemplate([
        ("system", """
너는 제품 구성요소를 '성분'과 '용도/효능'으로 분류하는 전문가이다.

<분류 기준>
- 성분: 물리적/화학적 물질, 원료, 재료, 추출물, 화합물 등
  예: 화피, 에탄올, 셀룰로오스 섬유, 다마스크장미꽃수, 장미, 보검선인장씨오일, 선인장

- 용도/효능: 제품의 목적, 효과, 기능, 용도, 카테고리 등
  예: 주름 완화, 화장품, 아토피 피부염 완화용, 보습, 미백, 마스크, 팩

<example>
입력:
화피, 석류피, 염부수백피,여드름, 염증, 피부질환, 화장

출력:
성분:
- 화피
- 석류피
- 염부수백피

용도/효능:
- 여드름
- 염증
- 피부질환
- 화장
</example>

<example>
입력:
1. 투명 섬유
2. 부직 섬유 집합체
3. 셀룰로오스 섬유
4. 에틸렌-비닐알코올계 섬유
5. 보액층
6. 보액 시트

출력:
성분:
- 투명 섬유
- 부직 섬유 집합체
- 용제 방사 셀룰로오스 섬유
- 에틸렌-비닐알코올계 섬유
- 보액층

용도/효능:
- 보액 시트
</example>

반드시 위 형식대로 "성분:"과 "용도/효능:" 섹션으로 구분하여 답변하라.
        """),
        ("user", "입력:\n{components}"),
    ])

    from langchain_openai import ChatOpenAI
    # LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    classify_chain = (
        {"components": RunnablePassthrough()}
        | classify_prompt
        | llm
    )

    result = classify_chain.invoke(components_text)

    # AIMessage 객체인 경우 content 추출
    if hasattr(result, 'content'):
        result_text = result.content
    else:
        result_text = str(result)

    # 결과 파싱
    ingredients = []
    purposes = []

    current_section = None

    for line in result_text.split('\n'):
        line = line.strip()

        if not line:
            continue

        if '성분' in line and ':' in line:
            current_section = 'ingredients'
            continue
        elif '용도' in line and ':' in line:
            current_section = 'purposes'
            continue

        # 리스트 항목 추출 (-, *, 번호 등)
        import re
        match = re.match(r'^[-*•]\s*(.+)$', line) or re.match(r'^\d+[\.)]\s*(.+)$', line)

        if match:
            item = match.group(1).strip()
            if current_section == 'ingredients':
                ingredients.append(item)
            elif current_section == 'purposes':
                purposes.append(item)

    return {
        'ingredients': ingredients,
        'purposes': purposes
    }


# ============================================
# 유틸리티 함수 3: 검색어 조합 생성
# ============================================

def generate_search_queries(
    ingredients: List[str],
    purposes: List[str],
    min_combination_size: int = 2,
    max_combination_size: int = None,
    include_single_ingredients: bool = False
) -> List[str]:
    """
    성분과 용도를 조합하여 가능한 모든 검색어를 생성

    Args:
        ingredients (List[str]): 주요 성분 리스트
        purposes (List[str]): 용도/효능 리스트 (기본 화장품 키워드와 자동 병합)
        min_combination_size (int): 최소 조합 크기 (기본값: 2)
        max_combination_size (int): 최대 조합 크기 (None이면 전체)
        include_single_ingredients (bool): 단일 성분 포함 여부 (기본값: False)

    Returns:
        List[str]: 생성된 검색어 리스트
    """

    # 기본 화장품 관련 키워드 추가
    default_cosmetic_keywords = ["화장품", "화장", "화장료", "미용"]

    # 기존 purposes에 기본 키워드들을 추가 (중복 제거)
    all_purposes = list(set(purposes + default_cosmetic_keywords))

    search_queries = set()

    if not ingredients:
        return list(search_queries)

    if max_combination_size is None:
        max_combination_size = len(ingredients)

    # 1. 단일 성분 (옵션)
    if include_single_ingredients:
        for ingredient in ingredients:
            search_queries.add(ingredient)

    # 2. 성분 + 용도 조합
    if all_purposes:
        for ingredient in ingredients:
            for purpose in all_purposes:
                search_queries.add(f"{ingredient} {purpose}")

    # 3. 성분들의 조합 (2개 이상)
    for size in range(min_combination_size, max_combination_size + 1):
        for combo in combinations(ingredients, size):
            search_queries.add(" ".join(combo))
            if all_purposes:
                for purpose in all_purposes:
                    search_queries.add(" ".join(combo) + f" {purpose}")

    # 4. 모든 성분 + 모든 용도
    if all_purposes and len(ingredients) >= min_combination_size:
        all_ingredients = " ".join(ingredients)
        for purpose in all_purposes:
            search_queries.add(f"{all_ingredients} {purpose}")
        all_components = " ".join(ingredients + all_purposes)
        search_queries.add(all_components)

    return sorted(list(search_queries))


# ============================================
# 유틸리티 함수 4: 구성요소 기반 검색어 생성 (통합 함수)
# ============================================

def create_search_queries_from_components(
    components_text: str,
    min_combination_size: int = 2,
    max_combination_size: int = None,
    include_single_ingredients: bool = False,
    verbose: bool = True
) -> List[str]:
    """
    구성요소 텍스트로부터 모든 가능한 검색어 조합을 생성하는 통합 함수
    """

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(model="gpt-4o", temperature=0)

    parsed = parse_components(components_text, llm)
    ingredients = parsed['ingredients']
    purposes = parsed['purposes']

    if verbose:
        print(f"{'='*80}")
        print("구성요소 파싱 결과")
        print(f"{'='*80}")
        print(f"\n주요 성분 ({len(ingredients)}개):")
        for i, ing in enumerate(ingredients, 1):
            print(f"  {i}. {ing}")

        print(f"\n용도/효능 ({len(purposes)}개):")
        for i, pur in enumerate(purposes, 1):
            print(f"  {i}. {pur}")
        print()

    search_queries = generate_search_queries(
        ingredients=ingredients,
        purposes=purposes,
        min_combination_size=min_combination_size,
        max_combination_size=max_combination_size,
        include_single_ingredients=include_single_ingredients
    )

    if verbose:
        print(f"{'='*80}")
        print(f"생성된 검색어 조합 (총 {len(search_queries)}개)")
        print(f"{'='*80}")
        print("\n[검색어 전체 목록]")
        for i, query in enumerate(search_queries, 1):
            print(f"  {i}. {query}")
        print()

    return search_queries


# ============================================
# 유틸리티 함수 5: 다중 검색어로 특허 검색
# ============================================

def search_patents_with_multiple_queries(
    search_queries: List[str],
    vectorstore,
    parent_store,
    top_n: int = 10,
    k_per_query: int = 50,
    filter_independent: bool = False
) -> List[Dict[str, Any]]:
    """
    여러 검색어를 사용하여 특허를 검색하고 결과를 통합

    Args:
        search_queries (List[str]): 검색어 리스트
        vectorstore: 벡터 데이터베이스 인스턴스
        parent_store: 부모 문서 저장소
        top_n (int): 최종 반환할 특허 개수
        k_per_query (int): 각 검색어당 가져올 문서 개수
        filter_independent (bool): True면 독립항만 필터링 (child DB용), False면 전부 포함 (parent DB용)

    Returns:
        List[Dict]: 특허 정보 리스트
    """

    print(f"{'='*80}")
    print(f"다중 검색어 기반 특허 검색 시작 (총 {len(search_queries)}개 검색어)")
    print(f"{'='*80}\n")


    all_patent_scores = {}  # {parent_id: [scores]}

    for idx, query in enumerate(search_queries, 1):
        if idx % 10 == 0 or idx == 1:
            print(f"진행 상황: {idx}/{len(search_queries)} 검색어 처리 중...")

        try:
            # 검색어를 키워드로 분리하여 AND 조건 필터 생성
            keywords = query.split()
            if len(keywords) >= 2:
                where_document = {"$and": [{"$contains": kw} for kw in keywords]}
            else:
                where_document = {"$contains": keywords[0]} if keywords else None

            results = vectorstore.similarity_search_with_score(
                query=query,
                k=k_per_query,
                where_document=where_document,
            )

            for doc, score in results:
                # child DB일 때만 독립항 필터링
                if filter_independent and doc.metadata.get('claim_type') != 'independent':
                    continue

                parent_id = doc.metadata['parent_id']

                if parent_id not in all_patent_scores:
                    all_patent_scores[parent_id] = {
                        'scores': [],
                        'best_doc': doc,
                        'best_score': score,
                        'hit_count': 0,
                        'hit_queries': []
                    }

                all_patent_scores[parent_id]['scores'].append(score)
                all_patent_scores[parent_id]['hit_count'] += 1
                all_patent_scores[parent_id]['hit_queries'].append((query, score))

                if score < all_patent_scores[parent_id]['best_score']:
                    all_patent_scores[parent_id]['best_score'] = score
                    all_patent_scores[parent_id]['best_doc'] = doc

        except Exception as e:
            print(f"⚠️ 검색어 '{query}' 처리 중 오류: {e}")
            continue

    print(f"\n검색 완료: 총 {len(all_patent_scores)}개 특허 발견\n")

    sorted_patents = sorted(
        all_patent_scores.items(),
        key=lambda x: (-x[1]['hit_count'], x[1]['best_score'])
    )

    print(f"{'='*80}")
    print("특허별 히트 통계 (상위 20개)")
    print(f"{'='*80}\n")

    for i, (parent_id, data) in enumerate(sorted_patents[:20], 1):
        avg_score = sum(data['scores']) / len(data['scores'])
        doc = data['best_doc']
        print(f"[{i}] 히트 횟수: {data['hit_count']}회")
        print(f"    특허명: {doc.metadata['title']}")
        print(f"    출원번호: {doc.metadata['application_number']}")
        print(f"    등록번호: {doc.metadata['register_number']}")
        print(f"    최고 유사도: {data['best_score']:.4f}")
        print(f"    평균 유사도: {avg_score:.4f}")
        sorted_hits = sorted(data['hit_queries'], key=lambda x: x[1])
        print(f"    히트 검색어 ({len(sorted_hits)}개):")
        for qi, (q, s) in enumerate(sorted_hits, 1):
            print(f"      {qi}. [{s:.4f}] {q}")
        print()

    top_patents = sorted_patents[:top_n]
    patents_full_data = []

    for rank, (parent_id, data) in enumerate(top_patents, 1):
        parent = parent_store.get(parent_id)

        if not parent:
            print(f"⚠️ 경고: parent_id {parent_id}에 대한 부모 문서를 찾을 수 없습니다.")
            continue

        all_claims = parent.get('all_claims', [])
        avg_score = sum(data['scores']) / len(data['scores'])

        patent_info = {
            'rank': rank,
            'parent_id': parent_id,
            'best_similarity_score': data['best_score'],
            'avg_similarity_score': avg_score,
            'hit_count': data['hit_count'],
            'application_number': parent['application_number'],
            'register_number': parent['register_number'],
            'title': parent['title'],
            'abstract': parent['abstract'],
            'ipc_codes': parent.get('ipc_codes', []),
            'register_status': parent['register_status'],
            'application_date': parent.get('application_date', ''),
            'register_date': parent.get('register_date', ''),
            'all_claims': all_claims,
            'claim_count': len(all_claims),
            'hit_queries': sorted(data['hit_queries'], key=lambda x: x[1])
        }

        patents_full_data.append(patent_info)

    print(f"{'='*80}")
    print(f"총 {len(patents_full_data)}개 특허 데이터 추출 완료")
    print(f"{'='*80}\n")

    return patents_full_data
