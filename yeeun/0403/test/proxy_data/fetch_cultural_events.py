import requests
import json

# 서울시 문화행사 정보 API
# 샘플 키로 테스트 가능
API_KEY = 'sample'  # 또는 your_api_key_here

url = f'https://openapi.seoul.go.kr:8088/{API_KEY}/json/SearchCulturalEventInformationByLocationService/1/5/'

response = requests.get(url)
data = response.json()

with open('proxy_data/cultural_events_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("서울시 문화행사 정보 저장 완료")