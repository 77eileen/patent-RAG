"""
FTO 분석 메인 실행 모듈

- 각 특허별 개별 분석 (1건씩 LLM 호출)
- 미등록 특허는 LLM 스킵
- 전체 결과를 analysis_results로 모아서 HTML 조립
"""

import os
from datetime import datetime
from .fto_pipeline import analyze_single_patent
from .report_generator import generate_html_report


def run_fto_analysis(user_query: str, user_components: str, patents_data: list) -> str:
    """
    FTO 분석 전체 파이프라인 실행

    Args:
        user_query: 사용자 질문
        user_components: RAG에서 추출한 사용자 구성요소
        patents_data: RAG 검색 결과 특허 리스트

    Returns:
        str: 생성된 HTML 보고서 파일 경로
    """

    print(f"\n{'='*80}")
    print(f"FTO 침해 분석 시작: {len(patents_data)}건 특허")
    print(f"{'='*80}\n")

    # 각 특허별 개별 분석 → analysis_results에 수집
    analysis_results = []
    registered_count = 0
    unregistered_count = 0

    for i, patent in enumerate(patents_data, 1):
        title = patent.get('title', 'N/A')
        app_num = patent.get('application_number', 'N/A')
        reg_status = patent.get('register_status', 'N/A')

        print(f"[{i}/{len(patents_data)}] {title} ({app_num}) | 상태: {reg_status}")

        result = analyze_single_patent(patent, user_query, user_components)
        analysis_results.append(result)

        if result['is_registered']:
            registered_count += 1
            if result['success']:
                print(f"  -> [등록] 결론: {result['conclusion']}")
            else:
                print(f"  -> [등록] 분석 실패: {result['error']}")
        else:
            unregistered_count += 1
            print(f"  -> [미등록] 공개 문헌 - LLM 분석 스킵")

    print(f"\n분석 대상: 등록 {registered_count}건 (LLM 분석), 미등록 {unregistered_count}건 (템플릿)")

    # HTML 보고서 생성
    print(f"\n{'='*80}")
    print("HTML 보고서 생성 중...")
    print(f"{'='*80}\n")

    html_content = generate_html_report(user_query, user_components, analysis_results)

    # 저장
    os.makedirs('reports', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filepath = f"reports/fto_report_{timestamp}.html"

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"HTML 보고서 생성 완료: {filepath}")

    # 결과 요약
    success_count = sum(1 for r in analysis_results if r.get('is_registered') and r.get('success'))
    fail_count = sum(1 for r in analysis_results if r.get('is_registered') and not r.get('success'))
    print(f"등록 특허 분석: 성공 {success_count}건, 실패 {fail_count}건")
    print(f"미등록 특허: {unregistered_count}건 (모니터링 권장)")

    return filepath
