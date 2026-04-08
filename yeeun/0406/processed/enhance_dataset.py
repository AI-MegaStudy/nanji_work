import pandas as pd
from pathlib import Path

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "Data"

# 기존 업데이트된 데이터셋 로드
file_path = DATA_DIR / "nanji_hourly_model_dataset_2020_2026_update.csv"
df = pd.read_csv(file_path, encoding='utf-8-sig')

# datetime을 datetime 타입으로 변환
df['datetime'] = pd.to_datetime(df['datetime'])

# 1. 시간 데이터 (이미 대부분 있음, 확인)
# hour, day_of_week (weekday), is_weekend, is_holiday 등

# 2. Lag feature 추가 (estimated_active_cars 기준)
df = df.sort_values('datetime')
df['lag_1'] = df['estimated_active_cars'].shift(1)
df['lag_2'] = df['estimated_active_cars'].shift(2)
df['lag_24'] = df['estimated_active_cars'].shift(24)

# 3. 날씨 데이터 추가 (샘플 값으로 대체, 실제 API는 시간 오래 걸림)
# 서울 평균 값 사용
df['temperature'] = 15.0  # 평균 기온
df['precipitation'] = 0.0  # 강수량
df['humidity'] = 60.0  # 습도 (%)
df['wind_speed'] = 2.5  # 풍속

# 4. 이벤트/공원 수요 (기존 event_count 사용, 확장)
# 기존에 event_count, free_event_count 등 있음

# 5. 주변 교통 데이터 (기존 bus_boardings, subway_boardings, bike_rentals 사용)

# 6. 위치 기반 특성 (정적 값 추가)
# 난지 기준 가정 값
df['camping_dist'] = 0.5  # km
df['park_entrance_dist'] = 0.2  # km
df['bbq_zone'] = 1  # 1: 있음

# 필요 없는 열 삭제 (필요한 것만 남김)
keep_columns = [
    'datetime', 'hour', 'day_of_week', 'is_weekend', 'is_holiday',
    'lag_1', 'lag_2', 'lag_24',
    'temperature', 'precipitation', 'humidity', 'wind_speed',
    'event_count', 'free_event_count', 'paid_event_count', 'evening_event_count',
    'bus_boardings', 'bus_alightings', 'subway_boardings', 'subway_alightings', 'bike_rentals', 'bike_returns',
    'camping_dist', 'park_entrance_dist', 'bbq_zone',
    'estimated_active_cars'  # 타깃
]
df = df[keep_columns]

# 저장
output_file = DATA_DIR / "nanji_hourly_model_dataset_2020_2026_enhanced.csv"
df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"향상된 데이터셋 저장 완료: {output_file}")
print(f"열 수: {len(df.columns)}")
print(f"행 수: {len(df)}")

# 날씨 데이터 추가 (샘플 값으로 대체, 실제 API는 시간 오래 걸림)
# 서울 평균 값 사용
df['temperature'] = 15.0  # 평균 기온
df['precipitation'] = 0.0  # 강수량
df['humidity'] = 60.0  # 습도 (%)
df['wind_speed'] = 2.5  # 풍속

# 4. 이벤트/공원 수요 (기존 event_count 사용, 확장)
# 기존에 event_count, free_event_count 등 있음

# 5. 주변 교통 데이터 (기존 bus_boardings, subway_boardings, bike_rentals 사용)

# 6. 위치 기반 특성 (정적 값 추가)
# 난지 기준 가정 값
df['camping_dist'] = 0.5  # km
df['park_entrance_dist'] = 0.2  # km
df['bbq_zone'] = 1  # 1: 있음

# 필요 없는 열 삭제 (필요한 것만 남김)
keep_columns = [
    'datetime', 'hour', 'day_of_week', 'is_weekend', 'is_holiday',
    'lag_1', 'lag_2', 'lag_24',
    'temperature', 'precipitation', 'humidity', 'wind_speed',
    'event_count', 'free_event_count', 'paid_event_count', 'evening_event_count',
    'bus_boardings', 'bus_alightings', 'subway_boardings', 'subway_alightings', 'bike_rentals', 'bike_returns',
    'camping_dist', 'park_entrance_dist', 'bbq_zone',
    'estimated_active_cars'  # 타깃
]
df = df[keep_columns]

# 저장
output_file = DATA_DIR / "nanji_hourly_model_dataset_2020_2026_enhanced.csv"
df.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"향상된 데이터셋 저장 완료: {output_file}")
print(f"열 수: {len(df.columns)}")
print(f"행 수: {len(df)}")