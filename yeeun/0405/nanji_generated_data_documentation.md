# Nanji Generated Data Documentation

이 문서는 `yeeun/Data`로 이동한 세 개의 Nanji 관련 생성 데이터 파일에 대한 설명과 사용 방법을 정리합니다.

## 대상 파일

1. `yeeun/Data/nanji_daily_parking_summary.csv`
2. `yeeun/Data/nanji_daily_parking_with_lags.csv`
3. `yeeun/Data/holiday_calendar_2022_2025.csv`

## 생성 배경

원본 데이터는 `hmw/Data/한강공원 주차장 일별 이용 현황.csv`와 `Data/서울시 시영주차장 실시간 주차대수 정보.csv`, `Data/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv`에서 가져온 정보입니다. 해당 데이터를 기반으로 Nanji 모델링에 필요한 시간 및 시계열 feature를 생성했습니다.

### 생성 방식 요약

- `hmw/Data/한강공원 주차장 일별 이용 현황.csv`에서 `난지` 주차장 데이터만 필터링
- 날짜별 주차대수 및 이용시간 합산 후 평균 체류시간 계산
- 기본 날짜/요일/주말/공휴일/연휴 플래그 추가
- lag 및 rolling mean 시계열 변수 생성
- 공휴일 달력은 수동으로 정의한 한국 법정 공휴일 및 대체공휴일 목록을 사용

## 파일별 설명

### 1. `yeeun/Data/nanji_daily_parking_summary.csv`

- 목적: Nanji 주차장 일별 요약 데이터
- 주요 컬럼:
  - `date`: 기준 날짜
  - `year`, `month`, `day`: 연도/월/일
  - `day_of_week`: 요일
  - `is_weekend`: 주말 여부
  - `is_holiday`: 공휴일 여부
  - `holiday_name`: 공휴일 이름
  - `is_substitute_holiday`: 대체공휴일 여부
  - `is_holiday_or_weekend`: 공휴일 또는 주말 여부
  - `is_long_weekend`: 3일 이상 연휴성 기간 여부
  - `daily_parking_count`: 일별 총 주차대수
  - `daily_usage_minutes`: 일별 총 이용시간
  - `avg_stay_minutes`: 1대당 평균 체류시간

### 2. `yeeun/Data/nanji_daily_parking_with_lags.csv`

- 목적: Nanji 일별 주차 데이터에 시계열 lag feature 추가
- 추가 컬럼:
  - `lag_1d_parking`: 1일 전 주차대수
  - `lag_7d_parking`: 7일 전 주차대수
  - `rolling_mean_3d_parking`: 최근 3일 평균 주차대수
  - `rolling_mean_7d_parking`: 최근 7일 평균 주차대수

- 활용:
  - 모델의 과거 상태 반영 feature
  - 계절적·주중 패턴과 함께 사용 시 예측력이 크게 개선됨

### 3. `yeeun/Data/holiday_calendar_2022_2025.csv`

- 목적: 날짜별 공휴일/주말 reference 테이블
- 주요 컬럼:
  - `date`, `year`, `month`, `day`
  - `day_of_week`
  - `is_weekend`
  - `is_holiday`
  - `holiday_name`
  - `is_substitute_holiday`
  - `is_holiday_or_weekend`
  - `is_long_weekend`

- 특징:
  - 데이터 범위 내 모든 날짜를 포함
  - 파일 크기 약 64MB로 비교적 큼
  - 모델링 시 날짜 컬럼과 병합하여 공휴일/연휴 플래그를 추가할 때 사용

## 사용 권장 방법

1. `nanji_daily_parking_summary.csv`를 기본 입력 테이블로 사용
2. `nanji_daily_parking_with_lags.csv`에서 lag/rolling feature를 추출하여 학습 데이터에 추가
3. `holiday_calendar_2022_2025.csv`는 추가적인 날짜/공휴일 확인이나 신뢰도 높은 캘린더 병합용 reference로 활용

## 주의 사항

- `yeeun/Data/holiday_calendar_2022_2025.csv`는 GitHub에서 권장하는 50MB 제한을 초과하는 파일입니다. Git LFS 도입이 필요하거나, 문서화된 데이터 관리 방식에 따라 별도 데이터 스토리지로 관리하는 것이 좋습니다.
- 현재 데이터는 `nanji_daily_parking_summary.csv`와 `nanji_daily_parking_with_lags.csv`가 일별 단위입니다. 시간별 학습 데이터가 필요한 경우, 추가로 시간 프로필 기반 변환 로직을 적용해야 합니다.

## 참고

이 문서는 Nanji 모델링 기초 데이터를 빠르게 이해하고, `yeeun/0406` 폴더에서 바로 참고할 수 있도록 정리했습니다.
