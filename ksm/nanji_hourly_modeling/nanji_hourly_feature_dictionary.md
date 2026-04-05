# 난지 시간별 데이터셋 Feature Dictionary

대상 파일:
- `nanji_hourly_model_dataset_2020_2026.csv`

이 문서는 시간별 통합 데이터셋의 각 feature 의미를 정리한 데이터 사전입니다.

## 기본 시간 컬럼

### `datetime`
- 의미: 시간별 한 행의 기준 시각
- 형식: `YYYY-MM-DD HH:MM:SS`
- 예시: `2020-02-11 13:00:00`

### `date`
- 의미: 해당 행이 속한 날짜
- 형식: `YYYY-MM-DD`
- 예시: `2020-02-11`

### `hour`
- 의미: 시간대
- 범위: `0 ~ 23`
- 예시: `13`

### `year`
- 의미: 연도
- 예시: `2020`

### `month`
- 의미: 월
- 범위: `1 ~ 12`

### `day`
- 의미: 일
- 범위: `1 ~ 31`

### `day_of_week`
- 의미: 요일
- 예시: `Monday`, `Saturday`

### `is_weekend`
- 의미: 주말 여부
- 값:
  - `True`: 토요일 또는 일요일
  - `False`: 평일

### `season`
- 의미: 계절 구분
- 값:
  - `spring`
  - `summer`
  - `fall`
  - `winter`

## 일별 주차 원본 기반 컬럼

### `daily_parking_count`
- 의미: 해당 날짜 난지 주차장의 일별 총 주차대수
- 원본 출처: `hmw/Data/한강공원 주차장 일별 이용 현황.csv`
- 설명: 시간별 추정의 기준이 되는 핵심 원본 값

### `daily_usage_minutes`
- 의미: 해당 날짜 난지 주차장의 일별 총 이용시간 합
- 단위: 분
- 설명: 차량 체류시간 추정의 기반 값

### `avg_stay_minutes`
- 의미: 차량 1대당 평균 체류시간 추정값
- 계산식: `daily_usage_minutes / daily_parking_count`
- 단위: 분
- 설명: 시간별 활성 차량 수 추정에 사용

### `hourly_share`
- 의미: 하루 총 주차수요를 해당 시간에 배분하는 비율
- 범위: `0 ~ 1`
- 설명: 평일/주말과 계절별 프로필을 이용해 만든 시간 분배 비율

### `estimated_entries`
- 의미: 해당 시간에 주차장으로 들어온 차량 수의 추정값
- 설명: 실제 입차 로그가 아니라 규칙 기반 추정값

### `estimated_active_cars`
- 의미: 해당 시간에 주차장에 머물러 있는 차량 수의 추정값
- 설명: `estimated_entries`와 평균 체류시간을 이용해 계산한 활성 차량 수

### `estimated_active_cars_change`
- 의미: 이전 시간 대비 활성 차량 수 변화량 추정값
- 계산식: `현재 estimated_active_cars - 이전 시간 estimated_active_cars`
- 설명:
  - 양수: 주차장 혼잡이 증가하는 방향
  - 음수: 차량이 빠져나가며 혼잡이 감소하는 방향

## 공휴일 / 캘린더 feature

### `holiday_table_is_weekend`
- 의미: 공휴일 테이블 기준의 주말 여부
- 설명: `holiday_calendar_2020_2026.csv`에서 병합된 값

### `holiday_name`
- 의미: 공휴일 이름
- 예시: `설날`, `1월1일`
- 설명: 공휴일이 아닌 날은 비어 있을 수 있음

### `is_holiday`
- 의미: 법정 공휴일 여부
- 값:
  - `True`: 공휴일
  - `False`: 일반일

### `is_substitute_holiday`
- 의미: 대체공휴일 여부
- 값:
  - `True`: 대체공휴일
  - `False`: 그 외

### `is_holiday_or_weekend`
- 의미: 공휴일 또는 주말 여부
- 설명: 실제 레저 수요가 강해질 가능성이 높은 날짜를 넓게 잡는 feature

### `is_long_weekend`
- 의미: 연휴성 주말 여부
- 설명: 장기 연휴/연휴성 주말 패턴을 반영하기 위한 feature

## 버스 feature

### `bus_boardings`
- 의미: 난지 생활권 버스 정류장의 해당 월-해당 시간대 승차 총합
- 설명: 일별 실측이 아니라 월별 시간대 패턴형 feature

### `bus_alightings`
- 의미: 난지 생활권 버스 정류장의 해당 월-해당 시간대 하차 총합
- 설명: 버스 유입/유출 흐름을 간접적으로 보여줌

## 지하철 feature

### `subway_boardings`
- 의미: 난지 생활권 인근 지하철역의 해당 월-해당 시간대 승차 총합
- 설명: 합정, 홍대입구, 월드컵경기장, 디지털미디어시티 등 인근 역 수요 패턴 반영

### `subway_alightings`
- 의미: 난지 생활권 인근 지하철역의 해당 월-해당 시간대 하차 총합
- 설명: 유동인구 유입 측면에서 해석 가능

## 따릉이 feature

### `bike_rentals`
- 의미: 난지 생활권 관련 따릉이 대여 건수
- 단위: 건
- 설명: 일별-시간대 기준으로 집계된 대체 이동수단 수요

### `bike_rental_minutes_sum`
- 의미: 해당 시간대 따릉이 대여 건들의 총 이용시간 합
- 단위: 분
- 설명: 단순 건수보다 실제 이용 규모를 더 잘 보여줄 수 있음

### `bike_rental_distance_m_sum`
- 의미: 해당 시간대 따릉이 대여 건들의 총 이용거리 합
- 단위: 미터
- 설명: 이동량 규모를 반영하는 feature

### `bike_returns`
- 의미: 난지 생활권 관련 따릉이 반납 건수
- 단위: 건
- 설명: 대여뿐 아니라 반납 흐름까지 반영

## 문화행사 feature

### `event_count`
- 의미: 해당 날짜 난지 생활권(마포/상암/난지 인근) 행사 수
- 단위: 건
- 설명: 행사 수가 많을수록 방문 수요 증가 가능성을 반영

### `free_event_count`
- 의미: 무료 행사 수
- 단위: 건
- 설명: 무료 행사는 방문 장벽이 낮아 유입 증가 가능성이 있음

### `paid_event_count`
- 의미: 유료 행사 수
- 단위: 건
- 설명: 특정 시간대 집중 방문을 만들 수 있는 유료 이벤트 반영

### `evening_event_count`
- 의미: 저녁 시간대 행사 수
- 기준: 행사시간 문자열에 `18시 이후`가 포함된 경우 중심
- 설명: 저녁 주차 수요 증가 가능성을 보는 feature

## 정적 참고 feature

### `nearby_public_parking_sites`
- 의미: 난지 생활권 인근 공영주차장 개수
- 설명: 현재는 최신 스냅샷 기준 정적 값

### `nearby_public_parking_capacity_sum`
- 의미: 인근 공영주차장의 총 주차 가능 면수 합
- 설명: 난지 주변 대체 주차 인프라 규모를 보여줌

### `nearby_kickboard_zone_count`
- 의미: 난지 생활권 인근 전동킥보드 주차구역 수
- 설명: 대체 이동수단 인프라 규모 반영

### `nearby_kickboard_stand_count`
- 의미: 킥보드 주차구역 중 거치대가 있는 구역 수 합
- 설명: 킥보드 인프라의 물리적 수용 정도를 간접 반영

## feature availability 컬럼

### `bus_feature_available`
- 의미: 해당 행에서 버스 feature가 실제로 채워졌는지 여부
- 값:
  - `True`: 버스 승하차 값이 존재
  - `False`: 해당 시기 데이터 없음

### `subway_feature_available`
- 의미: 해당 행에서 지하철 feature가 실제로 채워졌는지 여부

### `bike_feature_available`
- 의미: 해당 행에서 따릉이 feature가 실제로 채워졌는지 여부

### `culture_feature_available`
- 의미: 해당 행에서 문화행사 feature가 실제로 채워졌는지 여부

## 해석 시 주의사항

- `estimated_entries`, `estimated_active_cars`, `estimated_active_cars_change`는 실측 시간별 주차 로그가 아니라 추정값입니다.
- `bus_boardings`, `bus_alightings`, `subway_boardings`, `subway_alightings`는 월별 시간대 패턴 feature입니다.
- `nearby_public_parking_*`, `nearby_kickboard_*`는 최신 스냅샷 기반 정적 feature입니다.
- 날씨는 현재 전 기간 병합이 아니라 별도 참고 데이터로 보관 중입니다.
