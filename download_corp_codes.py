import requests
import zipfile
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv
import io

# .env 파일에서 API 키 로드
load_dotenv()
API_KEY = os.getenv('OPEN_DART_API_KEY')

def download_corp_codes():
    # API URL
    url = f'https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}'
    
    print("회사 코드 파일 다운로드 중...")
    
    # GET 요청 보내기
    headers = {
        'Accept': 'application/zip',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers)
    
    # 응답 상태 확인
    if response.status_code != 200:
        print(f"에러 발생: HTTP {response.status_code}")
        return
    
    # ZIP 파일로 저장
    with open('corpCode.zip', 'wb') as f:
        f.write(response.content)
    
    print("ZIP 파일 압축 해제 중...")
    
    try:
        # ZIP 파일 압축 해제
        with zipfile.ZipFile('corpCode.zip') as zip_file:
            zip_file.extractall()
        
        # XML 파일 파싱
        tree = ET.parse('CORPCODE.xml')
        root = tree.getroot()
        
        print("\n회사 코드 예시 (처음 5개):")
        for i, company in enumerate(root.findall('.//list')):
            if i >= 5:  # 처음 5개 회사만 출력
                break
            corp_code = company.findtext('corp_code')
            corp_name = company.findtext('corp_name')
            stock_code = company.findtext('stock_code', '없음')
            print(f"회사명: {corp_name}, 고유번호: {corp_code}, 종목코드: {stock_code}")
        
        print("\n파일이 성공적으로 다운로드되었습니다.")
        print("- corpCode.zip: ZIP 파일")
        print("- CORPCODE.xml: 압축 해제된 XML 파일")
    except zipfile.BadZipFile:
        print("Error: 다운로드된 파일이 올바른 ZIP 파일이 아닙니다.")
        print("API 응답:", response.text[:200])  # 처음 200자만 출력

if __name__ == "__main__":
    download_corp_codes() 