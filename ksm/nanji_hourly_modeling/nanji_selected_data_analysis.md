# 난지 선택 데이터 간단 분석

## 1. 최종 시간별 데이터셋 개요

- 생성 파일: `nanji_hourly_model_dataset_2020_2026.csv`
- 생성 범위: 2020-02-11 ~ 2026-04-02
- 단위: 1시간
- 기본 타깃: `estimated_entries`, `estimated_active_cars`, `estimated_active_cars_change`
- 기준 원본: `hmw/Data/한강공원 주차장 일별 이용 현황.csv`

## 2. 데이터별 역할 요약

### 주차 일별 원본
- 범위: 2020-02-11 ~ 2026-04-02
- 핵심 컬럼: `주차대수`, `이용시간`, `날짜`
- 역할: 시간별 추정 데이터의 베이스 타깃 생성

### 공휴일
- 범위: 2020 ~ 2026
- 핵심 컬럼: `is_holiday`, `is_holiday_or_weekend`, `is_long_weekend`
- 역할: 주말형 패턴과 특일 효과 반영

### 버스 시간대 승하차
- 적용 범위: 2023-01-01 ~ 2025-12-31
- 단위: 월별-시간대 합계 패턴
- 역할: 난지 생활권 버스 유동 수요 프록시

### 지하철 시간대 승하차
- 적용 범위: 2020-02-11 ~ 2026-03-31
- 단위: 월별-시간대 합계 패턴
- 역할: 합정, 홍대입구, 월드컵경기장, DMC 인근 유입 수요 프록시

### 따릉이 이력
- 적용 범위: 2023-01-01 ~ 2024-10-31
- 단위: 일별-시간대 대여/반납 집계
- 역할: 대체 이동수단 수요와 공원 접근성 신호 반영

### 문화행사
- 적용 범위: 2025-04-03 ~ 2026-04-02
- 단위: 일별 행사 수
- 역할: 마포/상암/난지 생활권 이벤트 효과 반영

### 날씨
- 현재 확보 상태: 2026-04-03 기준 단기예보 스냅샷 1회
- 역할: 미래 예측용 보정에는 사용 가능
- 한계: 2020~2026 전체 학습 데이터로는 범위가 부족해서 이번 통합 CSV에는 직접 병합하지 않음

### 실시간 공영주차장 / 킥보드 / 교통링크
- 역할: 정적 또는 최신 스냅샷 참고 데이터
- 반영 방식: `nearby_public_parking_sites`, `nearby_public_parking_capacity_sum`, `nearby_kickboard_zone_count`, `nearby_kickboard_stand_count`
- 한계: 시계열이 아니므로 시간별 변화 feature로는 제한적

## 3. 이번 통합 데이터셋에서 바로 쓸 수 있는 핵심 feature

- 캘린더: `year`, `month`, `day`, `hour`, `day_of_week`, `is_weekend`, `is_holiday`, `is_long_weekend`
- 주차 추정 타깃: `estimated_entries`, `estimated_active_cars`, `estimated_active_cars_change`
- 버스: `bus_boardings`, `bus_alightings`
- 지하철: `subway_boardings`, `subway_alightings`
- 자전거: `bike_rentals`, `bike_returns`, `bike_rental_minutes_sum`, `bike_rental_distance_m_sum`
- 행사: `event_count`, `free_event_count`, `paid_event_count`, `evening_event_count`

## 4. 해석할 때 주의할 점

- `estimated_entries`와 `estimated_active_cars`는 실측 시간별 로그가 아니라 일별 주차대수와 이용시간을 기반으로 만든 추정값입니다.
- 버스와 지하철은 월별-시간대 패턴 데이터라서, 특정 날짜의 실측치가 아니라 해당 월의 시간대 수요 프록시입니다.
- 문화행사는 2025~2026 위주, 날씨는 2026-04-03 스냅샷 위주라서 역사 전 구간을 설명하는 데이터로는 제한이 있습니다.
