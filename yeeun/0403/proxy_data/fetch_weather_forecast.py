import requests
import json

# 기상청 단기예보 API
API_KEY = 'your_api_key_here'  # data.go.kr에서 발급

# 난지 위치: 서울 마포구, nx=53, ny=126 (대략)
nx = 53
ny = 126
base_date = '20260403'  # YYYYMMDD
base_time = '0600'  # 발표시간

url = f'http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst?serviceKey={API_KEY}&numOfRows=10&pageNo=1&dataType=JSON&base_date={base_date}&base_time={base_time}&nx={nx}&ny={ny}'

response = requests.get(url)
data = response.json()

with open('proxy_data/weather_forecast_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("기상청 단기예보 데이터 저장 완료")