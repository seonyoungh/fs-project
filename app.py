from flask import Flask, render_template, request, jsonify
import sqlite3
import requests
import os
from dotenv import load_dotenv
import json
from datetime import datetime
from google import genai

# 환경 변수 로드
load_dotenv()
API_KEY = os.getenv('OPEN_DART_API_KEY')
print(f"Loaded API_KEY: {'설정됨' if API_KEY else '설정되지 않음'}")  # API 키 로드 확인

# Gemini API 키 로드
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print('경고: GEMINI_API_KEY가 설정되지 않았습니다.')

app = Flask(__name__)

def get_db_connection():
    conn = sqlite3.connect('companies.db')
    conn.row_factory = sqlite3.Row
    return conn

def format_number(number):
    """숫자를 한국어 단위로 포맷팅"""
    if number >= 1000000000000:
        return f'{round(number/1000000000000, 2)}조'
    elif number >= 100000000:
        return f'{round(number/100000000, 2)}억'
    elif number >= 10000:
        return f'{round(number/10000, 2)}만'
    else:
        return format(number, ',')

@app.route('/')
def index():
    # 현재 연도 계산
    current_year = datetime.now().year
    # 1분기(5월), 반기(8월), 3분기(11월), 사업보고서(3월) 공시 일정 고려
    available_years = list(range(current_year-5, current_year+1))
    return render_template('index.html', available_years=available_years)

@app.route('/search_company')
def search_company():
    query = request.args.get('query', '')
    conn = get_db_connection()
    companies = conn.execute(
        "SELECT corp_name, corp_code, stock_code FROM companies WHERE corp_name LIKE ? LIMIT 10",
        (f'%{query}%',)
    ).fetchall()
    conn.close()
    return jsonify([{'corp_name': c['corp_name'], 'corp_code': c['corp_code'], 'stock_code': c['stock_code']} for c in companies])

@app.route('/financial_data')
def get_financial_data():
    corp_code = request.args.get('corp_code')
    bsns_year = request.args.get('bsns_year', str(datetime.now().year-1))
    reprt_code = request.args.get('reprt_code', '11011')  # 사업보고서

    url = 'https://opendart.fss.or.kr/api/fnlttSinglAcnt.json'
    params = {
        'crtfc_key': API_KEY,
        'corp_code': corp_code,
        'bsns_year': bsns_year,
        'reprt_code': reprt_code
    }
    
    print(f"Requesting financial data with params: {params}")  # API 요청 파라미터 출력
    
    response = requests.get(url, params=params)
    print(f"API Response status: {response.status_code}")  # API 응답 상태 코드 출력
    
    if response.status_code == 200:
        data = response.json()
        print(f"API Response data: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}...")  # API 응답 데이터 출력
        
        if data.get('status') == '000':
            # 재무제표 데이터 필터링 및 구조화
            financial_data = {
                'bs': [],  # 재무상태표
                'is': [],  # 손익계산서
                'cf': [],  # 현금흐름표
                'sc': [],  # 자본변동표
                'years': {
                    'thstrm': '',  # 당기 연도
                    'frmtrm': '',  # 전기 연도
                    'bfefrmtrm': ''  # 전전기 연도
                }
            }
            
            # 연도 정보 추출 (첫 번째 항목에서)
            if data.get('list'):
                first_item = data['list'][0]
                financial_data['years'] = {
                    'thstrm': first_item.get('thstrm_dt', '').split('.')[0] + '년',  # 2023.12.31 → 2023년
                    'frmtrm': first_item.get('frmtrm_dt', '').split('.')[0] + '년',  # 2022.12.31 → 2022년
                    'bfefrmtrm': first_item.get('bfefrmtrm_dt', '').split('.')[0] + '년' if 'bfefrmtrm_dt' in first_item else ''
                }
            
            for item in data.get('list', []):
                print(f"sj_div: {item['sj_div']}, account_nm: {item['account_nm']}")  # 모든 항목 로깅
                if item['sj_div'] in ['BS', 'IS', 'CF', 'SC']:
                    try:
                        # 금액 데이터 처리
                        thstrm_amount = item['thstrm_amount'].replace(',', '')
                        frmtrm_amount = item['frmtrm_amount'].replace(',', '')
                        bfefrmtrm_amount = item.get('bfefrmtrm_amount', '0').replace(',', '')

                        entry = {
                            'account_nm': item['account_nm'],
                            'thstrm_amount': thstrm_amount,
                            'frmtrm_amount': frmtrm_amount,
                            'bfefrmtrm_amount': bfefrmtrm_amount
                        }
                        
                        if item['sj_div'] == 'BS':
                            financial_data['bs'].append(entry)
                        elif item['sj_div'] == 'IS':
                            financial_data['is'].append(entry)
                        elif item['sj_div'] == 'CF':
                            financial_data['cf'].append(entry)
                        elif item['sj_div'] == 'SC':
                            financial_data['sc'].append(entry)
                    except Exception as e:
                        print(f"Error processing item: {item}")
                        print(f"Error details: {str(e)}")
                        continue
            
            print(f"Processed financial data: {json.dumps(financial_data, indent=2, ensure_ascii=False)[:500]}...")  # 처리된 데이터 출력
            return jsonify(financial_data)
        else:
            error_msg = f"API Error: {data.get('message', '알 수 없는 오류가 발생했습니다.')}"
            print(error_msg)
            return jsonify({'error': error_msg})
    
    return jsonify({'error': '데이터를 가져오는데 실패했습니다.'})

@app.route('/explain_financial', methods=['POST'])
def explain_financial():
    data = request.get_json()
    # 재무제표 데이터와 회사명 등 프롬프트 구성
    company = data.get('company', '해당 회사')
    years = data.get('years', {})
    bs = data.get('bs', [])
    is_ = data.get('is', [])
    cf = data.get('cf', [])
    sc = data.get('sc', [])

    # 프롬프트 예시
    prompt = f"""
아래는 {company}의 재무제표(재무상태표, 손익계산서, 현금흐름표, 자본변동표)입니다. 숫자는 최근 3개년치입니다. 비전문가도 이해할 수 있도록 쉽게 요약, 해석, 특징을 설명해 주세요. (숫자 단위: 원)

[연도 정보]
- 당기: {years.get('thstrm', '')}
- 전기: {years.get('frmtrm', '')}
- 전전기: {years.get('bfefrmtrm', '')}

[재무상태표]\n"""
    for item in bs:
        prompt += f"- {item['account_nm']}: {item['thstrm_amount']} (당기), {item['frmtrm_amount']} (전기), {item.get('bfefrmtrm_amount', '0')} (전전기)\n"
    prompt += "\n[손익계산서]\n"
    for item in is_:
        prompt += f"- {item['account_nm']}: {item['thstrm_amount']} (당기), {item['frmtrm_amount']} (전기), {item.get('bfefrmtrm_amount', '0')} (전전기)\n"
    prompt += "\n[현금흐름표]\n"
    for item in cf:
        prompt += f"- {item['account_nm']}: {item['thstrm_amount']} (당기), {item['frmtrm_amount']} (전기), {item.get('bfefrmtrm_amount', '0')} (전전기)\n"
    prompt += "\n[자본변동표]\n"
    for item in sc:
        prompt += f"- {item['account_nm']}: {item['thstrm_amount']} (당기), {item['frmtrm_amount']} (전기), {item.get('bfefrmtrm_amount', '0')} (전전기)\n"
    prompt += "\n설명: "

    try:
        model = genai.GenerativeModel('gemini-pro', api_key=GEMINI_API_KEY)
        response = model.generate_content(prompt)
        explanation = response.text
    except Exception as e:
        print(f"Gemini API 오류: {e}")
        return jsonify({'error': f'Gemini API 호출 중 오류가 발생했습니다. 상세: {e}'}), 500

    return jsonify({'explanation': explanation})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003) 