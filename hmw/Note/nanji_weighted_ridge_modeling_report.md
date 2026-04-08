# 난지 한강공원 시간별 주차 예측 가중치 분석

## 1. 작업 범위

- 기준 노트: `hmw/Note/nanji_ML.ipynb`
- 참고 프로세스: 이전 통합 분석 노트북의 가중치 기반 흐름
- 제외한 단계: station 선정/랭킹/다중 station 비교
- 핵심 반영 요소: `day_type x hour` 기본 패턴 + `month/hour` 가중치 + Ridge 회귀
- 예측 대상: `estimated_active_cars (추정 활성 차량 수)`

## 2. 전체 프로세스 한눈에 보기

이번 작업은 아래 순서로 진행했습니다.

1. 난지 시간별 데이터가 이미 존재하는지 확인
2. 시간별 데이터가 어떤 원천으로부터 만들어졌는지 역추적
3. 일별 주차 원본과 통합 시간별 CSV의 관계를 정리
4. 운영시간 조건(`06:00~23:00`)과 시간축 구조를 검증
5. 결측, 기간, feature 가용률 등 데이터 품질 점검
6. 참고 통합 분석 노트북의 패턴 회귀식 + 가중치 생성 로직을 난지 단일 사이트용으로 이식
7. `month_weight`와 `hour_weight` 중심 baseline을 학습 및 검증
9. 최종적으로 `estimated_active_cars`를 `여유 주차공간 수`로 변환하는 방법까지 정리

## 3. 시간별 데이터 사용 가능 여부

난지 주차장의 직접적인 실측 시간별 주차 로그는 워크스페이스에서 확인되지 않았습니다. 대신 아래와 같이 **시간별 통합 데이터셋**이 이미 준비되어 있어 모델링이 가능합니다.

| asset                             | path                                                               | granularity   | availability   | note                                                  |
|:----------------------------------|:-------------------------------------------------------------------|:--------------|:---------------|:------------------------------------------------------|
| 난지 시간별 통합 데이터셋         | ksm/nanji_hourly_modeling/nanji_hourly_model_dataset_2020_2026.csv | 1시간         | 있음           | 주차 추정 타깃과 외생 변수 결합본                     |
| 난지 일별 주차 원본               | hmw/Data/한강공원 주차장 일별 이용 현황.csv                        | 1일           | 있음           | 시간별 타깃 생성을 위한 베이스 원본                   |
| 서울시 지하철 시간대 승하차       | Data/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv       | 월-시간대     | 있음           | 난지 인근 역 패턴이 통합 데이터셋에 반영됨            |
| 서울시 시영주차장 실시간 주차대수 | Data/서울시 시영주차장 실시간 주차대수 정보.csv                    | 스냅샷/실시간 | 있음           | 정적 참고용이며 난지 타깃 시계열로 직접 사용되진 않음 |
| 난지 시간별 날씨 데이터           | ose/Data/open_meteo_nanji_2022~2025.csv                            | 1시간         | 있음           | 기온, 강수, 운량, 풍속, 복사량 등 시간별 기상 feature |

### feature 가용률

| feature                   |   coverage_rate |
|:--------------------------|----------------:|
| bus_feature_available     |           0.72  |
| subway_feature_available  |           0.924 |
| bike_feature_available    |           0.332 |
| culture_feature_available |           0.188 |
| weather_feature_available |           1     |

## 4. 시간별 데이터가 만들어진 방식

`ksm/nanji_hourly_modeling/nanji_hourly_dataset_methodology.md` 기준 요약:

- 난지 한강공원 주차 예측을 위한 `시간별 학습 데이터셋`을 만든다.
- 실제 시간별 주차 로그가 없기 때문에, 일별 주차 원본을 시간축으로 확장한 뒤 난지 선택 데이터를 feature로 결합한다.
## 생성 흐름
1. `hmw/Data/한강공원 주차장 일별 이용 현황.csv`에서 난지 주차장 행만 선택
2. 날짜별 `주차대수`, `이용시간` 합산
3. 평일/주말 + 계절별 시간 프로필로 `estimated_entries` 생성
4. 평균 체류시간 기반으로 `estimated_active_cars` 생성
5. 공휴일 달력 병합
6. 버스/지하철 월별 시간대 패턴 병합
7. 자전거 대여이력의 일별-시간대 집계 병합
8. 문화행사 일별 집계 병합
9. 정적 참고 데이터(주변 공영주차장, 킥보드 주차구역) 요약치 추가

원본 난지 일별 주차 데이터는 `hmw/Data/한강공원 주차장 일별 이용 현황.csv`에서 `주차장명 == 난지1,2,3,4주차장` 행을 사용했습니다. 이 일별 원본을 하루 24시간으로 확장한 뒤, 평일/오프데이와 계절성 프로필로 `estimated_entries`를 만들고, 평균 체류시간으로 `estimated_active_cars`를 계산한 구조입니다. 즉, 이번 예측 타깃은 **실측 시간 로그가 아니라 일별 원본 기반 추정 시간대 점유량**입니다.

### 원본/가공 범위 확인

- 일별 원본 기간: `2022-01-01` ~ `2025-12-31`
- 일별 원본 일수: `1,455`
- 시간별 통합 데이터 기간: `2022-01-01 00:00:00` ~ `2025-12-31 23:00:00`
- 시간별 통합 데이터 행수: `34,920`

### 어떤 자료들을 근거로 시간별 데이터가 만들어졌는가

| 자료 유형 | 파일/근거 | 역할 |
|:--|:--|:--|
| 일별 주차 원본 | `hmw/Data/한강공원 주차장 일별 이용 현황.csv` | 날짜별 `주차대수`, `이용시간`의 기준 원본 |
| 생성 방법론 | `ksm/nanji_hourly_modeling/nanji_hourly_dataset_methodology.md` | 시간별 확장 규칙과 병합 순서 설명 |
| 컬럼 사전 | `ksm/nanji_hourly_modeling/nanji_hourly_feature_dictionary.md` | 각 feature의 의미와 출처 정리 |
| 지하철 시간대 데이터 | `Data/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv` | 난지 생활권 대중교통 수요 프록시 |
| 버스 시간대 패턴 | 통합 데이터셋의 버스 관련 feature | 시간대 유동 수요 프록시 |
| 자전거 대여/반납 집계 | 통합 데이터셋의 자전거 관련 feature | 대체 이동수단 수요 프록시 |
| 문화행사 집계 | 통합 데이터셋의 행사 관련 feature | 방문 수요 급증 가능성 반영 |
| 주변 주차/킥보드 정적 정보 | 통합 데이터셋의 정적 feature | 주변 인프라 규모 반영 |

## 5. 데이터 품질 점검

|   rows |   unique_datetime |   duplicate_rows |   target_missing |   target_min |   target_max | date_min            | date_max            |
|-------:|------------------:|-----------------:|-----------------:|-------------:|-------------:|:--------------------|:--------------------|
|  34920 |             34920 |                0 |                0 |            0 |      1219.57 | 2022-01-01 00:00:00 | 2025-12-31 23:00:00 |

### 결측 상위 10개

| feature              |   missing_count |
|:---------------------|----------------:|
| holiday_name         |           33144 |
| bus_boardings        |            9781 |
| bus_alightings       |            9781 |
| dew_point_2m         |               0 |
| snowfall             |               0 |
| rain                 |               0 |
| precipitation        |               0 |
| apparent_temperature |               0 |
| relative_humidity_2m |               0 |
| weather_code         |               0 |

해석:

- `holiday_name` 결측은 비휴일 날짜에서 자연스러운 값입니다.
- `bus_*`는 전체 기간의 약 절반 수준만 채워져 있어 보조 feature 성격이 강합니다.
- `subway_*`는 대부분 채워져 있고, `bike_*`, `culture_*`는 적용 기간이 짧습니다.

## 6. 운영시간 검증

질문에서 주신 운영시간 조건인 `06:00~23:00`을 현재 시간별 CSV가 얼마나 반영하는지 확인했습니다.

- `0~5시` 행은 존재함
- 하지만 `estimated_entries`, `estimated_active_cars`는 전 기간 동안 모두 `0`
- `6~23시`는 실질적인 운영시간 패턴을 가짐

즉, 현재 데이터는 **운영시간 외 구간을 행으로는 남겨두되, `0~5시` 수요를 0으로 간주한 구조**입니다.

추가로 이번 모델에서는 `hour_weight`를 계산할 때 `6~23시`만 사용하고, `0~5시`는 가중치 산출 대상에서 제외했습니다. 최종 예측값도 운영시간 외 구간은 `0`으로 고정했습니다.

## 7. 참고 프로세스의 난지 단일 사이트 재구성

이전 통합 분석 노트북의 핵심을 station 선정 없이 난지 단일 사이트용으로 옮겼습니다.

1. `train(2022-2023)`에서 `day_type x hour` 평균으로 기본 패턴식을 적합
2. `train` 실제값 / 기본패턴 비율로 `month_weight` 계산
3. `pattern_prior = base_value * month_weight`를 구성
4. `train`의 `6~23시` 운영시간 구간에서만 `pattern_prior` 대비 비율로 `hour_weight` 계산
5. `corrected_pattern_prior = pattern_prior * hour_weight`
6. 이 구조를 baseline 모델로 평가

주의:

- 누수를 막기 위해 `month/hour weight`는 모두 `train(2022-2023)`만 보고 계산했습니다.
- 이번 구조에서는 `year_weight`를 아예 사용하지 않습니다.

### 기본 패턴식

| target                | day_type   |   intercept |   sin_hour_coef |   cos_hour_coef | formula                                                                         |
|:----------------------|:-----------|------------:|----------------:|----------------:|:--------------------------------------------------------------------------------|
| estimated_active_cars | weekday    |     61.4373 |        -46.3292 |        -70.4183 | 61.437302 + (-46.329213 * sin(2pi*hour/24)) + (-70.418263 * cos(2pi*hour/24))   |
| estimated_active_cars | offday     |    128.203  |       -138.708  |        -91.8155 | 128.203422 + (-138.708299 * sin(2pi*hour/24)) + (-91.815457 * cos(2pi*hour/24)) |

### 가중치 요약

월 가중치:

| weight_type   |   key |   value |
|:--------------|------:|--------:|
| month_weight  |     1 |  0.5817 |
| month_weight  |     2 |  0.6506 |
| month_weight  |     3 |  0.8874 |
| month_weight  |     4 |  1.1826 |
| month_weight  |     5 |  1.3132 |
| month_weight  |     6 |  1.2688 |
| month_weight  |     7 |  1.0716 |
| month_weight  |     8 |  1.0972 |
| month_weight  |     9 |  1.2764 |
| month_weight  |    10 |  1.111  |
| month_weight  |    11 |  0.8763 |
| month_weight  |    12 |  0.6832 |

시간 가중치 상위 10개:

| weight_type   |   key |   value |
|:--------------|------:|--------:|
| hour_weight   |    14 |  1.3457 |
| hour_weight   |    15 |  1.334  |
| hour_weight   |    13 |  1.3063 |
| hour_weight   |    16 |  1.272  |
| hour_weight   |    12 |  1.2214 |
| hour_weight   |    17 |  1.1684 |
| hour_weight   |    11 |  1.1023 |
| hour_weight   |    23 |  1.0736 |
| hour_weight   |    18 |  1.038  |
| hour_weight   |    10 |  0.9646 |

시간 가중치 표에는 `0~5시`가 포함되지 않습니다. 해당 시간은 운영시간 외 구간으로 보고 `hour_weight` 계산에서 제외했습니다.

## 8. 모델 비교

| model_name        |   alpha | split   |    rmse |     mae |     r2 |
|:------------------|--------:|:--------|--------:|--------:|-------:|
| weighted_core     |    1000 | test    | 59.5412 | 30.0448 | 0.726  |
| weighted_extended |    1000 | test    | 56.5413 | 28.0469 | 0.7529 |
| weighted_core     |    1000 | train   | 53.0312 | 27.5288 | 0.7839 |
| weighted_extended |    1000 | train   | 50.335  | 26.1202 | 0.8053 |
| weighted_core     |    1000 | valid   | 54.6437 | 28.9268 | 0.7437 |
| weighted_extended |    1000 | valid   | 50.6555 | 28.6089 | 0.7797 |

### test 기준 직접 비교

| model_name        |   alpha |    rmse |     mae |     r2 |
|:------------------|--------:|--------:|--------:|-------:|
| weighted_extended |    1000 | 56.5413 | 28.0469 | 0.7529 |
| weighted_core     |    1000 | 59.5412 | 30.0448 | 0.726  |

오프라인 성능 기준 최고 모델은 `weighted_extended` 이고, 선택 alpha는 `1000.0` 입니다.

다만 **미래 시점(1시간 뒤, 3시간 뒤, 하루 뒤, 이틀 뒤 등)을 현재 시점까지의 정보만으로 예측하는 실사용 구조**로 보면, 실제 운용 모델은 `weighted_core`로 두는 것이 더 적절합니다. 이유는 `weighted_extended`에 포함된 버스/지하철/자전거/행사/날씨 변수는 미래 시점의 값을 예측 순간에 모두 안정적으로 알 수 없기 때문입니다.

### 높은 상관계수 feature 정리

이번 최종 학습에서는 `train(2022~2023)` 기준 절대 상관계수 `0.9` 이상인 feature 쌍이 있으면, 같은 모델 feature 세트 안에서 **타깃(`estimated_active_cars`)과의 절대 상관이 더 큰 feature를 남기고, 나머지는 제외**했습니다.

| model_name        | kept_feature            | dropped_feature            |   abs_corr |   threshold |
|:------------------|:------------------------|:---------------------------|-----------:|------------:|
| weighted_core     | pattern_prior           | base_value                 |     0.9418 |         0.9 |
| weighted_core     | pattern_prior           | corrected_pattern_prior    |     0.9752 |         0.9 |
| weighted_extended | pattern_prior           | base_value                 |     0.9418 |         0.9 |
| weighted_extended | pattern_prior           | corrected_pattern_prior    |     0.9752 |         0.9 |
| weighted_extended | day_type_offday         | is_long_weekend            |     0.9779 |         0.9 |
| weighted_extended | bus_alightings          | bus_boardings              |     0.989  |         0.9 |
| weighted_extended | bike_rentals            | bike_returns               |     0.9922 |         0.9 |
| weighted_extended | bike_rental_minutes_sum | bike_rentals               |     0.9607 |         0.9 |
| weighted_extended | bike_rental_minutes_sum | bike_rental_distance_m_sum |     0.9926 |         0.9 |
| weighted_extended | temperature_2m          | dew_point_2m               |     0.9279 |         0.9 |
| weighted_extended | temperature_2m          | apparent_temperature       |     0.9928 |         0.9 |
| weighted_extended | precipitation           | rain                       |     0.9989 |         0.9 |
| weighted_extended | pressure_msl            | surface_pressure           |     0.9999 |         0.9 |
| weighted_extended | wind_gusts_10m          | wind_speed_10m             |     0.9158 |         0.9 |
| weighted_extended | shortwave_radiation     | direct_radiation           |     0.9578 |         0.9 |

## 9. 추천 모델 해석

### 어떤 모델을 실사용용으로 볼 것인가

- `weighted_extended`는 오프라인 평가에서는 더 높은 `R²`를 보였지만, 미래 시점의 외생 변수를 실제 예측 순간에 알 수 없다는 한계가 있습니다.
- 특히 행사 정보와 시간별 날씨 정보는 사후적으로 해석할 때는 유용하지만, "3시간 뒤", "하루 뒤", "이틀 뒤"를 현재 시점 정보만으로 예측해야 하는 구조에서는 직접 feature로 넣기 어렵습니다.
- 따라서 이번 프로젝트의 **실사용용 미래 예측 모델**은 `weighted_core`로 보는 것이 맞습니다.
- `weighted_extended`는 "왜 특정 시기 오차가 줄었는지"를 확인하는 참고 모델, 또는 과거 데이터 해석용 비교 모델로만 두는 편이 안전합니다.
- 같은 이유로 `lag`, `rolling`, 자기회귀형 시계열 feature도 이번 구조에는 넣지 않았습니다. 이런 값들은 예측 시점 이후의 경로를 전제하거나, 시계열 모델로 구조가 바뀌기 때문입니다.

### 중요 feature 상위 10개

| feature                  |   coefficient |   importance_ratio |
|:-------------------------|--------------:|-------------------:|
| snow_depth               |      -71.6142 |             0.2786 |
| hour_weight              |       59.4609 |             0.2313 |
| month_weight             |       36.9751 |             0.1438 |
| snowfall                 |       28.856  |             0.1122 |
| is_holiday               |      -18.8699 |             0.0734 |
| month_cos                |       12.9056 |             0.0502 |
| hour_cos                 |        7.8804 |             0.0307 |
| hour_sin                 |        6.334  |             0.0246 |
| subway_feature_available |       -3.4656 |             0.0135 |
| month_sin                |        3.1923 |             0.0124 |

### 2025 오차가 큰 시간대 상위 8개

|   hour |   core_abs_error |   extended_abs_error |
|-------:|-----------------:|---------------------:|
|     15 |          63.0892 |              58.3064 |
|     16 |          63.1185 |              58.0314 |
|     17 |          62.1346 |              57.2977 |
|     14 |          61.8647 |              57.1962 |
|     18 |          58.6647 |              54.1142 |
|     13 |          58.8771 |              54.0233 |
|     12 |          53.6039 |              49.6898 |
|     19 |          51.3869 |              45.2467 |

### 2025 오차가 큰 월 상위 8개

|   month |   core_abs_error |   extended_abs_error |
|--------:|-----------------:|---------------------:|
|       9 |          49.6558 |              51.0024 |
|       4 |          42.6816 |              38.256  |
|       6 |          38.5284 |              35.392  |
|      10 |          35.5055 |              33.6522 |
|       5 |          35.9152 |              32.7722 |
|       8 |          29.3399 |              26.9781 |
|       7 |          28.6033 |              25.5594 |
|       3 |          25.0353 |              21.4082 |

## 10. 여유 주차공간 수를 구하는 방법

이번 프로젝트의 최종적으로 해석하고 싶은 값은 `여유 주차공간 수`입니다. 현재 모델이 직접 예측하는 값은 `estimated_active_cars`이므로, 이를 **추정 점유 차량 수**로 보고 아래처럼 변환해야 합니다.

### 기본 정의

- `predicted_occupied_cars = 모델이 예측한 estimated_active_cars`
- `total_capacity = 난지 주차장의 총 주차면 수`
- `available_spaces = max(total_capacity - predicted_occupied_cars, 0)`

즉, **총 주차면 수에서 해당 시각의 추정 점유 차량 수를 뺀 값**이 여유 주차공간 수입니다.

### 왜 `estimated_entries`가 아니라 `estimated_active_cars`를 써야 하는가

- `estimated_entries`는 해당 시간에 들어온 차량 수 추정치라서, 그 시점에 실제로 몇 대가 주차장 안에 머무는지는 직접 보여주지 못합니다.
- 반면 `estimated_active_cars`는 평균 체류시간을 반영해 **현재 시간에 머물고 있는 차량 수**를 추정한 값이므로, 여유 주차공간 계산에 더 적합합니다.

### 운영시간을 반영한 계산 규칙

난지 주차장의 운영시간을 `06:00~23:00`으로 본다면, 여유 주차공간 수 계산은 아래처럼 해석하는 것이 안전합니다.

- `06~23시`: `max(total_capacity - predicted_occupied_cars, 0)`
- `00~05시`: 이번 분석에서는 운영시간 외 구간으로 보고 점유 추정값과 여유 주차공간 계산의 기준을 모두 `0`으로 간주하며, `hour_weight` 계산에서도 제외하고 최종 예측값도 `0`으로 고정

즉, 이번 분석에서는 운영시간 외 구간을 별도 예측 대상으로 보지 않고, **0으로 고정된 비운영시간**으로 처리합니다.

### 현재 데이터 기준 한계

현재 워크스페이스의 난지 시간별 통합 CSV에는 **난지 메인 주차장의 확정 총 주차면 수(`total_capacity`)가 직접 들어 있지 않습니다.**

- `nearby_public_parking_capacity_sum`은 난지 주변 대체 공영주차장의 총 면수 합이라서, 난지 주차장 자체의 총 면수로 쓰면 안 됩니다.
- 따라서 최종적인 `여유 주차공간 수`를 절대값으로 계산하려면, 난지 주차장의 실제 총 면수를 별도 기준값으로 넣어야 합니다.

### 실무 적용 예시

만약 난지 주차장의 총 주차면 수를 `C`라고 두면:

- `predicted_available_spaces_t = max(C - predicted_active_cars_t, 0)`
- `predicted_occupancy_rate_t = predicted_active_cars_t / C`

예를 들어 총 주차면이 `800`이고 특정 시점 예측 점유 차량 수가 `620`이면:

- `여유 주차공간 수 = 800 - 620 = 180`
- `점유율 = 620 / 800 = 77.5%`

즉, 현재 모델은 **여유 주차공간 수를 직접 예측하는 모델이 아니라, 여유 주차공간 수로 변환 가능한 점유 추정량 모델**이라고 보는 것이 정확합니다.

## 11. 결론

- 난지 주차장의 사용 가능한 시간별 타깃은 **이미 구축된 추정형 시간별 데이터셋**이며, 직접 실측 시간 로그는 현재 워크스페이스에서 확인되지 않았습니다.
- 이 시간별 데이터는 일별 주차 원본, 방법론 문서, 컬럼 사전, 대중교통/행사/주변 인프라 자료와 별도 수집한 시간별 날씨 데이터를 근거로 구성된 통합 데이터입니다.
- 이번 분석에서는 `0~5시`를 운영시간 외 구간으로 보고, 점유량 관련 계산에서 `0`으로 간주했으며 `hour_weight` 산출에서도 제외했고 최종 예측값도 `0`으로 고정했습니다.
- 누수를 막기 위해 `month/year/hour weight`는 `train(2022-2023)` 기준으로만 계산했습니다.
- 이번 정리에서는 `year_weight`를 제외하고 `month_weight`와 `hour_weight` 중심 구조만 남겼습니다.
- 최종 `test(2025)` 기준에서는 `weighted_extended`이 가장 높은 성능을 보였습니다.
- 다만 현재 시점까지의 정보만으로 `1시간 뒤 ~ 48시간 뒤`를 예측하는 실사용 관점에서는, 미래 시점 외생 변수를 몰라도 되는 `weighted_core`를 운용 모델로 두는 것이 더 적절합니다.
- 행사 데이터와 교통/날씨 관련 변수는 실시간 미래예측 입력값이라기보다, 과거 수요 변동과 연도/시기 차이를 설명하는 참고 근거로 해석하는 편이 맞습니다.
- `lag`, `rolling` 같은 시계열 패턴 변수는 이번 설계 원칙상 사용하지 않았습니다.
- 다만 현재 타깃 자체가 `estimated_active_cars`인 만큼, 결과 해석은 **실제 점유면수 예측**이 아니라 **추정 점유량 예측**으로 다루는 것이 안전합니다.

## 12. 산출물

- 보고서: `hmw/Note/nanji_weighted_ridge_modeling_report.md`
- 노트북: `hmw/Note/nanji_ML.ipynb`
- 지표 CSV: `hmw/Note/nanji_outputs/nanji_model_metrics.csv`
- 가중치 CSV: `hmw/Note/nanji_outputs/nanji_weight_table.csv`
- feature pruning CSV: `hmw/Note/nanji_outputs/nanji_feature_pruning.csv`
- 예측 CSV: `hmw/Note/nanji_outputs/nanji_test_predictions.csv`
- 그림:
  - `hmw/Note/nanji_outputs/nanji_month_weights.png`
  - `hmw/Note/nanji_outputs/nanji_hour_weights.png`
  - `hmw/Note/nanji_outputs/nanji_2025_monthly_compare.png`
