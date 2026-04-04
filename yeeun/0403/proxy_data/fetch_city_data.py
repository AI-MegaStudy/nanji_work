import requests
import json

# 서울시 실시간 도시데이터 API
# API_KEY를 data.go.kr에서 발급받아 넣으세요.
API_KEY = 'your_api_key_here'  # 샘플로는 '광화문·덕수궁'만 가능

# 장소: 난지 인근, 예를 들어 '상암동' 또는 코드
AREA_NAME = '상암동'  # 또는 코드

url = f'https://openapi.seoul.go.kr:8088/{API_KEY}/json/SPOP_LOCAL_REALTIME/1/1/{AREA_NAME}'

response = requests.get(url)
data = response.json()

with open('proxy_data/seoul_city_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("서울시 실시간 도시데이터 저장 완료")