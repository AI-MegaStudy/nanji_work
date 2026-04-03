import requests
import json

# 서울시 공공자전거 시간대별 이용정보 API
API_KEY = 'sample'  # 또는 your_api_key_here

url = f'https://openapi.seoul.go.kr:8088/{API_KEY}/json/tbCycleUseTimeRentInfo/1/5/'

response = requests.get(url)
data = response.json()

with open('proxy_data/bike_usage_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("서울시 공공자전거 시간대별 이용정보 저장 완료")