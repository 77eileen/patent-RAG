"""
FTO 분석 HTML 보고서 생성

- 등록 특허: 구성대비 + 판단 + 결론
- 미등록 특허: notice-box + 고정 템플릿
"""

import html
from datetime import datetime


def get_conclusion_badge(conclusion: str) -> str:
    """결론 텍스트에 맞는 HTML 배지 반환"""
    if '높은' in conclusion:
        return '<span class="badge badge-danger">침해 가능성 높음</span>'
    elif '낮은' in conclusion:
        return '<span class="badge badge-safe">침해 가능성 낮음</span>'
    elif '전문가' in conclusion:
        return '<span class="badge badge-warning">전문가 검토 필요</span>'
    elif '정보' in conclusion or '구체적' in conclusion:
        return '<span class="badge badge-info">추가 정보 필요</span>'
    else:
        return f'<span class="badge badge-info">{html.escape(conclusion)}</span>'


def get_conclusion_class(conclusion: str) -> str:
    """결론 텍스트에 맞는 CSS 클래스 반환"""
    if '높은' in conclusion:
        return 'conclusion-danger'
    elif '낮은' in conclusion:
        return 'conclusion-safe'
    elif '전문가' in conclusion:
        return 'conclusion-warning'
    else:
        return 'conclusion-info'


def get_match_class(match_status: str) -> str:
    """대응 여부에 맞는 CSS 클래스 반환"""
    if match_status == '대응':
        return 'match-ok'
    elif '균등' in match_status:
        return 'match-equiv'
    elif '내재성' in match_status:
        return 'match-inherent'
    elif '미대응' in match_status:
        return 'match-no'
    elif '확인불가' in match_status:
        return 'match-unknown'
    return ''


def generate_html_report(user_query: str, user_components: str, analysis_results: list) -> str:
    """
    FTO 분석 결과를 HTML 보고서로 생성

    Args:
        user_query: 사용자 질문
        user_components: 사용자 구성요소
        analysis_results: analyze_single_patent() 결과 리스트

    Returns:
        str: HTML 문자열
    """

    today = datetime.now().strftime('%Y-%m-%d')

    # ── 요약 테이블 ──
    summary_rows = ""
    for r in analysis_results:
        rank = r.get('rank', '-')
        app_num = html.escape(str(r.get('application_number', '-')))
        title = html.escape(str(r.get('title', '-')))

        if r.get('is_registered'):
            reg_num = html.escape(str(r.get('register_number', '-')))
            status = html.escape(str(r.get('register_status', '-')))

            if r.get('success'):
                badge = get_conclusion_badge(r.get('conclusion', '-'))
            else:
                badge = '<span class="badge badge-error">분석 실패</span>'

            summary_rows += f"""      <tr>
        <td>{rank}</td>
        <td>{app_num}</td>
        <td>{reg_num}</td>
        <td>{status}</td>
        <td>{title}</td>
        <td>{badge}</td>
      </tr>
"""
        else:
            # 미등록: 공개번호 표시
            pub_num = html.escape(str(r.get('pub_number', r.get('open_number', '-'))))
            status = html.escape(str(r.get('register_status', '공개')))

            summary_rows += f"""      <tr class="unregistered-row">
        <td>{rank}</td>
        <td>{app_num}</td>
        <td>{pub_num}</td>
        <td>{status}</td>
        <td>{title}</td>
        <td><span class="badge badge-monitor">공개 문헌 (모니터링 권장)</span></td>
      </tr>
"""

    # ── 상세 분석 섹션 ──
    detail_sections = ""
    for r in analysis_results:
        rank = r.get('rank', '-')
        app_num = html.escape(str(r.get('application_number', '-')))
        title = html.escape(str(r.get('title', '-')))

        # ── 미등록 특허: notice-box 템플릿 ──
        if not r.get('is_registered'):
            pub_num = html.escape(str(r.get('pub_number', r.get('open_number', '-'))))
            claims_text = html.escape(str(r.get('claims_text', '')))
            template_msg = html.escape(str(r.get('template_message', '')))

            detail_sections += f"""
    <div class="patent-section">
      <h3>[{rank}] 출원번호: {app_num} / 공개번호: {pub_num}</h3>
      <p class="patent-title">{title}</p>

      <h4>현재 청구항</h4>
      <div class="claims-box"><pre>{claims_text}</pre></div>

      <div class="notice-box">
        {template_msg}
      </div>
    </div>
"""
            continue

        # ── 분석 실패 ──
        if not r.get('success'):
            reg_num = html.escape(str(r.get('register_number', '-')))
            error_msg = html.escape(str(r.get('error', '알 수 없는 오류')))

            detail_sections += f"""
    <div class="patent-section">
      <h3>[{rank}] 출원번호: {app_num} / 등록번호: {reg_num}</h3>
      <p class="patent-title">{title}</p>
      <div class="error-box">분석 실패: {error_msg}</div>
    </div>
"""
            continue

        # ── 등록 특허: 정상 분석 ──
        reg_num = html.escape(str(r.get('register_number', '-')))
        display_num = reg_num if reg_num and reg_num != '-' else app_num

        # 구성대비 테이블
        comparison_rows = ""
        comparison_data = r.get('comparison', {}).get('comparison', [])
        for item in comparison_data:
            p_comp = html.escape(str(item.get('patent_component', '-')))
            u_comp = html.escape(str(item.get('user_component', '-')))
            match_st = str(item.get('match_status', '-'))
            match_cls = get_match_class(match_st)
            comparison_rows += f"""          <tr>
            <td>{p_comp}</td>
            <td>{u_comp}</td>
            <td class="{match_cls}">{html.escape(match_st)}</td>
          </tr>
"""

        judgment_text = html.escape(str(r.get('judgment', '-')))
        conclusion_text = str(r.get('conclusion', '-'))
        conclusion_cls = get_conclusion_class(conclusion_text)

        detail_sections += f"""
    <div class="patent-section">
      <h3>[{rank}] 출원번호: {app_num} / 등록번호: {reg_num}</h3>
      <p class="patent-title">{title}</p>
      <p class="intro-text">특허번호 {display_num}의 독립항의 모든 구성요소와 사용자가 실시하고자 하는 제품의 구성을 비교한 결과는 다음과 같습니다.</p>

      <h4>구성 대비</h4>
      <table class="comparison-table">
        <thead>
          <tr><th>특허 구성</th><th>사용자 제품 구성</th><th>대응 여부</th></tr>
        </thead>
        <tbody>
{comparison_rows}        </tbody>
      </table>

      <h4>판단</h4>
      <p class="judgment-text">{judgment_text}</p>

      <h4>결론</h4>
      <p class="conclusion {conclusion_cls}">{html.escape(conclusion_text)}</p>
    </div>
"""

    # ── 전체 HTML ──
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FTO REPORT</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif;
            background: #f0f2f5;
            color: #333;
            line-height: 1.7;
            word-break: keep-all;
        }}

        .report-container {{
            max-width: 1100px;
            margin: 30px auto;
            background: #fff;
            padding: 50px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}

        h1 {{
            font-size: 28px;
            color: #1a1a2e;
            border-bottom: 3px solid #16213e;
            padding-bottom: 12px;
            margin-bottom: 8px;
        }}

        .report-date {{
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
        }}

        h2 {{
            font-size: 20px;
            color: #16213e;
            margin-top: 40px;
            margin-bottom: 15px;
            padding-left: 12px;
            border-left: 4px solid #0f3460;
        }}

        h3 {{
            font-size: 17px;
            color: #0f3460;
            margin-bottom: 8px;
        }}

        h4 {{
            font-size: 15px;
            color: #444;
            margin-top: 25px;
            margin-bottom: 10px;
            padding-bottom: 5px;
            border-bottom: 1px solid #e0e0e0;
        }}

        .query-box {{
            background: #e8f4fd;
            border-left: 4px solid #2196f3;
            padding: 16px 20px;
            margin: 10px 0 20px 0;
            border-radius: 0 6px 6px 0;
            font-size: 15px;
        }}

        .components-box {{
            background: #f3e5f5;
            border-left: 4px solid #9c27b0;
            padding: 16px 20px;
            margin: 10px 0 20px 0;
            border-radius: 0 6px 6px 0;
            font-size: 14px;
        }}

        /* 테이블 */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 14px;
        }}

        thead th {{
            background: #16213e;
            color: #fff;
            padding: 12px 14px;
            text-align: left;
            font-weight: 600;
        }}

        tbody td {{
            padding: 10px 14px;
            border-bottom: 1px solid #e8e8e8;
        }}

        tbody tr:hover {{
            background: #f8f9fa;
        }}

        .comparison-table thead th {{
            background: #1a237e;
        }}

        .unregistered-row {{
            background: #f5f9ff;
        }}

        /* 배지 */
        .badge {{
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 700;
            white-space: nowrap;
        }}

        .badge-danger {{
            background: #ffebee;
            color: #c62828;
            border: 1px solid #ef9a9a;
        }}

        .badge-safe {{
            background: #e8f5e9;
            color: #2e7d32;
            border: 1px solid #a5d6a7;
        }}

        .badge-warning {{
            background: #fff3e0;
            color: #e65100;
            border: 1px solid #ffcc80;
        }}

        .badge-info {{
            background: #eceff1;
            color: #37474f;
            border: 1px solid #b0bec5;
        }}

        .badge-error {{
            background: #fce4ec;
            color: #880e4f;
            border: 1px solid #f48fb1;
        }}

        .badge-monitor {{
            background: #e3f2fd;
            color: #1565c0;
            border: 1px solid #90caf9;
        }}

        /* 대응 여부 색상 */
        .match-ok {{ color: #2e7d32; font-weight: 700; }}
        .match-no {{ color: #c62828; font-weight: 700; }}
        .match-equiv {{ color: #e65100; font-weight: 700; }}
        .match-inherent {{ color: #e65100; font-weight: 700; }}
        .match-unknown {{ color: #546e7a; font-weight: 700; }}

        /* 특허 섹션 */
        .patent-section {{
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 25px 30px;
            margin: 25px 0;
            background: #fafbfc;
        }}

        .patent-title {{
            color: #555;
            font-size: 14px;
            margin-bottom: 10px;
        }}

        .intro-text {{
            color: #555;
            font-size: 14px;
            margin: 10px 0;
        }}

        .judgment-text {{
            font-size: 14px;
            line-height: 1.8;
            color: #333;
            padding: 12px 16px;
            background: #fff;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }}

        /* 결론 */
        .conclusion {{
            font-size: 15px;
            font-weight: 700;
            padding: 16px 20px;
            border-radius: 8px;
            margin-top: 10px;
        }}

        .conclusion-danger {{
            background: #ffebee;
            color: #b71c1c;
            border: 1px solid #ef9a9a;
        }}

        .conclusion-safe {{
            background: #e8f5e9;
            color: #1b5e20;
            border: 1px solid #a5d6a7;
        }}

        .conclusion-warning {{
            background: #fff3e0;
            color: #bf360c;
            border: 1px solid #ffcc80;
        }}

        .conclusion-info {{
            background: #eceff1;
            color: #263238;
            border: 1px solid #b0bec5;
        }}

        /* 미등록 특허 notice-box */
        .notice-box {{
            background: #e3f2fd;
            border: 2px solid #42a5f5;
            border-radius: 8px;
            padding: 20px 24px;
            margin-top: 20px;
            color: #1565c0;
            font-size: 14px;
            line-height: 1.8;
        }}

        /* 청구항 표시 */
        .claims-box {{
            background: #fff;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            padding: 16px;
            margin: 10px 0;
            max-height: 300px;
            overflow-y: auto;
        }}

        .claims-box pre {{
            white-space: pre-wrap;
            word-wrap: break-word;
            font-family: 'Malgun Gothic', sans-serif;
            font-size: 13px;
            line-height: 1.6;
            color: #444;
        }}

        .error-box {{
            background: #fce4ec;
            border: 1px solid #f48fb1;
            padding: 16px;
            border-radius: 6px;
            color: #880e4f;
            font-size: 14px;
        }}

        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}

        @media print {{
            body {{ background: #fff; }}
            .report-container {{ box-shadow: none; padding: 20px; }}
            .patent-section {{ break-inside: avoid; }}
        }}
    </style>
</head>
<body>
  <div class="report-container">

    <h1>FTO REPORT</h1>
    <p class="report-date">분석일: {today}</p>

    <h2>사용자 질문</h2>
    <div class="query-box">{html.escape(user_query)}</div>

    <h2>사용자 제품 구성요소</h2>
    <div class="components-box">{html.escape(user_components)}</div>

    <h2>주요 특허 리스트</h2>
    <table>
      <thead>
        <tr>
          <th>순위</th>
          <th>출원번호</th>
          <th>등록/공개번호</th>
          <th>현재 상태</th>
          <th>발명의 명칭</th>
          <th>분석 결론</th>
        </tr>
      </thead>
      <tbody>
{summary_rows}      </tbody>
    </table>

    <h2>특허에 대한 상세 분석</h2>
{detail_sections}

    <div class="footer">
      본 보고서는 AI 기반 자동 분석 결과이며, 법적 효력을 갖지 않습니다. 정확한 판단을 위해 전문가 검토를 권고합니다.
    </div>

  </div>
</body>
</html>"""

    return html_content
