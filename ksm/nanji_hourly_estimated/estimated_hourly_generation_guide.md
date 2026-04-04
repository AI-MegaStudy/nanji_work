# 난지 주차장 시간별 추정 데이터 생성 가이드

이 문서는 `/Users/electrozone/Documents/GitHub/nanji_work/ksm/nanji_hourly_estimated` 폴더에 생성된 연도별 CSV가 어떤 방식으로 만들어졌는지 설명합니다.

중요:
- 이 데이터는 `실측 시간별 데이터`가 아닙니다.
- `일별 주차대수`와 `일별 이용시간`을 기반으로 만든 `시간별 추정 데이터`입니다.

---

## 1. 왜 시간별 추정 데이터를 만들었는가

현재 확보한 난지 데이터는 아래와 같습니다.

- 일별 주차대수
- 일별 이용시간
- 월별 주차대수
- 기상청 단기예보
- 문화행사 정보

하지만 목표는 `몇 시간 뒤 주차 가능 여부 예측`이기 때문에, 일별 데이터만으로는 부족합니다.

예를 들어 일별 데이터만 있으면:
- 어떤 날 사람이 많았는지
- 주말이 평일보다 얼마나 많은지
- 월별로 어떤 계절에 수요가 큰지

는 볼 수 있지만,
- 오후 2시에 몰리는지
- 저녁 6시에 빠지는지
- 하루 중 몇 시에 가장 혼잡한지

같은 시간대 패턴은 직접 알 수 없습니다.

그래서 일별 데이터를 바탕으로 `시간대별 프로필`을 만들어 1시간 단위 데이터로 확장했습니다.

---

## 2. 사용한 원본 데이터

원본 파일:
- `/Users/electrozone/Documents/GitHub/nanji_work/hmw/Data/한강공원 주차장 일별 이용 현황.csv`

사용한 주요 컬럼:
- `날짜`
- `주차장명`
- `주차대수`
- `이용시간`

난지 관련 주차장만 필터링한 뒤 같은 날짜끼리 합산했습니다.

즉 하루 단위 기준으로 아래 두 값이 만들어졌습니다.

- `daily_parking_count`
  - 그날 난지 주차장에 들어온 총 차량 수
- `daily_usage_minutes`
  - 그날 난지 주차장의 총 이용시간 합계

---

## 3. 시간별 데이터로 확장한 방법

### 3-1. 날짜별 총량 먼저 고정

하루 총 주차대수는 원본 일별 데이터에서 그대로 사용했습니다.

예:
- 2020-02-11 총 주차대수 = 1035대

즉 시간별 데이터를 만들 때도 하루 총량은 바꾸지 않았습니다.

---

### 3-2. 평일/주말과 계절별로 시간대 프로필을 다르게 설정

시간대 분배 비율은 아래 기준으로 다르게 만들었습니다.

- 평일 / 주말
- 봄 / 여름 / 가을 / 겨울

예:
- `weekday_winter`
- `weekday_spring`
- `weekend_summer`
- `weekend_fall`

이렇게 나눈 이유는 난지한강공원 특성상:
- 주말은 오후 피크가 더 크게 나타날 가능성이 높고
- 여름은 늦은 오후/저녁 이용이 상대적으로 많을 수 있고
- 겨울은 전반적으로 이른 시간에 수요가 줄 수 있기 때문입니다.

---

### 3-3. 시간대 비중은 가우시안(봉우리) 2개로 구성

하루 수요를 한 번에 몰아넣지 않고, 두 개의 봉우리를 가진 형태로 만들었습니다.

- 오전~점심 전후의 완만한 봉우리
- 오후~저녁 중심의 메인 봉우리

이 구조를 쓴 이유는 난지 방문 패턴이 보통:
- 아침부터 조금씩 유입
- 낮~오후에 가장 붐빔
- 저녁부터 점차 빠짐

형태를 보일 가능성이 크기 때문입니다.

즉 시간별 비율은 대략 이런 생각으로 만들어졌습니다.

- 00시~05시: 거의 0
- 06시 이후: 유입 시작
- 11시~13시: 1차 증가
- 14시~17시: 메인 피크
- 18시 이후: 점차 감소
- 23시 이후: 거의 0

---

### 3-4. 이용시간으로 평균 체류시간 계산

원본 데이터에는 `이용시간`이 있습니다.

그래서 날짜별 평균 체류시간을 다음처럼 계산했습니다.

`평균 체류시간(분) = 일별 이용시간 / 일별 주차대수`

예:
- 하루 이용시간이 34133분
- 하루 주차대수가 1035대

이면

- 평균 체류시간은 약 32.98분

이 값을 이용해서 단순히 “그 시간에 몇 대가 들어왔는가”만이 아니라,
“그 시간에 아직 머물러 있는 차량 수”도 추정했습니다.

---

### 3-5. 최종적으로 만든 값

CSV에는 아래 3개가 핵심입니다.

- `estimated_entries`
  - 해당 시간에 들어온 차량 수의 추정값

- `estimated_active_cars`
  - 해당 시간에 주차장 안에 머물러 있는 차량 수의 추정값

- `estimated_active_cars_change`
  - 바로 이전 시간 대비 활성 차량 수 변화량

이 중에서 실제 예측 프로젝트에서는 보통
- `estimated_active_cars`
- `estimated_active_cars_change`

를 가장 많이 보게 됩니다.

---

## 4. 생성된 CSV 주요 컬럼 설명

| 컬럼명 | 의미 |
| --- | --- |
| `datetime` | 시간별 시각 |
| `date` | 날짜 |
| `hour` | 시간(0~23) |
| `year` | 연도 |
| `month` | 월 |
| `day_of_week` | 요일 |
| `is_weekend` | 주말 여부 |
| `season` | 계절 |
| `profile_type` | 적용된 시간 프로필 종류 |
| `daily_parking_count` | 해당 날짜의 총 주차대수 |
| `daily_usage_minutes` | 해당 날짜의 총 이용시간 |
| `avg_stay_minutes` | 평균 체류시간 추정치 |
| `hourly_share` | 하루 총량 중 해당 시간 비중 |
| `estimated_entries` | 해당 시간 유입 차량 추정치 |
| `estimated_active_cars` | 해당 시간 활성 차량 추정치 |
| `estimated_active_cars_change` | 이전 시간 대비 변화량 |

---

## 5. 이 데이터의 장점

- 일별 데이터만 있을 때보다 훨씬 풍부한 패턴 분석이 가능함
- `몇 시간 뒤` 예측이라는 목표와 더 잘 맞음
- 평일/주말/계절 차이를 시간축으로 펼칠 수 있음
- 이후 날씨, 행사, 도로 소통 데이터를 붙이기 쉬움

---

## 6. 이 데이터의 한계

- 실측 시간별 주차 로그가 아니라 추정치임
- 실제 입차/출차 시간 분포를 정확히 반영하는 것은 아님
- 동일한 평일/주말/계절 안에서는 비슷한 형태의 시간 프로필이 반복됨
- 행사/우천/교통정체에 의한 시간대 왜곡은 아직 직접 반영하지 않음

즉 이 데이터는
- `정답 데이터`
가 아니라
- `패턴 기반 합리적 추정 데이터`
라고 보는 것이 맞습니다.

---

## 7. 발표할 때 이렇게 설명하면 좋음

추천 문장:

> 난지 주차장에는 과거 시간별 실측 데이터가 없어서, 일별 주차대수와 이용시간을 기반으로 평일/주말 및 계절별 시간 프로필을 적용해 1시간 단위 추정 데이터를 생성했습니다.

또는

> 본 시간별 데이터는 실제 센서 로그가 아닌 synthetic hourly profile이며, 난지 주차장의 일별 총량과 평균 체류시간을 유지하는 방향으로 구성했습니다.

---

## 8. 추천 시각화 자료

아래 그래프를 만들면 설명력이 좋습니다.

### 8-1. 하루 시간대별 평균 활성 차량 수

목적:
- 난지 주차장의 하루 혼잡 패턴을 보여줌

추천 그래프:
- x축: 시간
- y축: `estimated_active_cars`
- 선 그래프

비교 방법:
- 전체 평균
- 평일 vs 주말

---

### 8-2. 계절별 시간대 패턴 비교

목적:
- 봄/여름/가을/겨울에 피크 시간이 어떻게 다른지 설명

추천 그래프:
- x축: 시간
- y축: 평균 `estimated_active_cars`
- 계절별 4개 선 그래프

---

### 8-3. 연도별 평균 시간대 패턴 비교

목적:
- 2020~2026 사이 시간 패턴이 얼마나 비슷한지 비교

추천 그래프:
- x축: 시간
- y축: 평균 `estimated_active_cars`
- 연도별 선 그래프

---

### 8-4. 시간대별 변화량 그래프

목적:
- 언제 차량이 급증하고, 언제 빠지는지 확인

추천 그래프:
- x축: 시간
- y축: 평균 `estimated_active_cars_change`
- 막대그래프

해석 포인트:
- 양수면 혼잡 증가
- 음수면 차량 이탈

---

### 8-5. 히트맵

목적:
- 월/시간 또는 요일/시간 기준 혼잡 패턴을 한 번에 보기

추천 그래프:
- 행: 월 또는 요일
- 열: 시간
- 값: 평균 `estimated_active_cars`

---

## 9. 노트북에서 바로 쓸 수 있는 시각화 아이디어

### 시간대별 평균 활성 차량 수

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('/Users/electrozone/Documents/GitHub/nanji_work/ksm/nanji_hourly_estimated/nanji_hourly_estimated_2025.csv')

hourly_mean = df.groupby('hour')['estimated_active_cars'].mean()

plt.figure(figsize=(10, 5))
plt.plot(hourly_mean.index, hourly_mean.values, marker='o')
plt.title('2025 난지 시간대별 평균 활성 차량 수')
plt.xlabel('시간')
plt.ylabel('estimated_active_cars')
plt.grid(alpha=0.3)
plt.show()
```

### 평일 vs 주말 비교

```python
weekday_weekend = (
    df.groupby(['is_weekend', 'hour'])['estimated_active_cars']
    .mean()
    .reset_index()
)

plt.figure(figsize=(10, 5))
for flag, label in [(False, '평일'), (True, '주말')]:
    subset = weekday_weekend[weekday_weekend['is_weekend'] == flag]
    plt.plot(subset['hour'], subset['estimated_active_cars'], marker='o', label=label)

plt.title('2025 난지 평일/주말 시간대별 평균 활성 차량 수')
plt.xlabel('시간')
plt.ylabel('estimated_active_cars')
plt.legend()
plt.grid(alpha=0.3)
plt.show()
```

### 월-시간 히트맵

```python
import seaborn as sns

pivot = df.pivot_table(
    index='month',
    columns='hour',
    values='estimated_active_cars',
    aggfunc='mean'
)

plt.figure(figsize=(14, 5))
sns.heatmap(pivot, cmap='YlOrRd')
plt.title('2025 난지 월별-시간별 평균 활성 차량 수')
plt.xlabel('시간')
plt.ylabel('월')
plt.show()
```

---

## 10. 앞으로 더 좋아지게 하려면

현재는 시간 프로필만 적용한 1차 버전입니다.

다음 단계로는 아래를 붙이면 더 좋아집니다.

- 기상청 예보
- 문화행사 정보
- 서울시 실시간 도로 소통 정보
- 공휴일 정보

예:
- 행사 있는 날은 오후/저녁 비중 확대
- 비 오는 날은 낮 시간 비중 축소
- 도로 정체 심하면 피크 시간 지연

---

## 11. 결론

이 시간별 데이터는 실측 로그는 아니지만,

- 난지 주차장 일별 총량
- 평균 체류시간
- 평일/주말
- 계절성

을 반영한 `시간별 추정 프로필 데이터`입니다.

따라서 초기 예측 모델링, 패턴 분석, 시각화, 발표자료 작성에는 충분히 사용할 수 있습니다.
