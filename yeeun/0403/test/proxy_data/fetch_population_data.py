import requests
import json

# 서울시 실시간 인구데이터 API
API_KEY = 'your_api_key_here'

AREA_NAME = '상암동'

url = f'https://openapi.seoul.go.kr:8088/{API_KEY}/json/SPOP_LOCAL_REALTIME_POP/1/1/{AREA_NAME}'

response = requests.get(url)
data = response.json()

with open('proxy_data/seoul_population_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("서울시 실시간 인구데이터 저장 완료")