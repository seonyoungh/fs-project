import xml.etree.ElementTree as ET
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# SQLAlchemy 설정
Base = declarative_base()
engine = create_engine('sqlite:///companies.db')
Session = sessionmaker(bind=engine)

# 회사 정보 모델 정의
class Company(Base):
    __tablename__ = 'companies'
    
    corp_code = Column(String(8), primary_key=True)
    corp_name = Column(String(100), index=True)
    stock_code = Column(String(6))
    
    def __repr__(self):
        return f"<Company(corp_name='{self.corp_name}', corp_code='{self.corp_code}', stock_code='{self.stock_code}')>"

def init_db():
    # 데이터베이스 테이블 생성
    # 데이터베이스 테이블 생성
    try:
        Base.metadata.create_all(engine)
    except Exception as e:
        raise RuntimeError(f"데이터베이스 테이블 생성 중 오류 발생: {e}")

    # XML 파일 파싱
    tree = ET.parse('CORPCODE.xml')
    root = tree.getroot()
    session = Session()
    
    print("데이터베이스 초기화 중...")
    # 기존 데이터 삭제
    session.query(Company).delete()
    
    # 새 데이터 추가
    companies = []
    for corp in root.findall('.//list'):
        company = Company()
        company.corp_code = corp.findtext('corp_code')
        company.corp_name = corp.findtext('corp_name')
        company.stock_code = corp.findtext('stock_code', '')
        companies.append(company)
        
        # 1000개씩 벌크 삽입
        if len(companies) >= 1000:
            session.bulk_save_objects(companies)
            session.commit()
            companies = []
    
    # 남은 데이터 삽입
    if companies:
        session.bulk_save_objects(companies)
        session.commit()
    
    print("데이터베이스 초기화 완료!")
    session.close()

if __name__ == "__main__":
    init_db() 