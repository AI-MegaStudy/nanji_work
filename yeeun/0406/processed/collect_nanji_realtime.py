import requests
import pandas as pd
from datetime import datetime
import time
import os

# API 키
API_KEY = '7078565a5579793036304e53595371'

# API URL
url = f'http://openapi.seoul.go.kr:8088/{API_KEY}/json/GetParkingInfo/1/1000/'

# Data 폴더 경로
data_dir = '/Users/electrozone/Desktop/nanji_work/Data'
os.makedirs(data_dir, exist_ok=True)

# 데이터 수집
response = requests.get(url)
data = response.json()

# 데이터프레임으로 변환
df = pd.DataFrame(data['GetParkingInfo']['row'])

# 난지 주차장 필터링
nanji_df = df[df['PKLT_NM'].str.contains('난지', na=False)]

# 현재 시간 추가
nanji_df['timestamp'] = datetime.now()

# CSV로 저장 (Data 폴더에)
output_path = os.path.join(data_dir, 'nanji_realtime.csv')
nanji_df.to_csv(output_path, index=False, encoding='utf-8-sig')

print(f"난지 주차장 실시간 데이터 수집 완료: {output_path}")
print(f"수집된 데이터 수: {len(nanji_df)}")