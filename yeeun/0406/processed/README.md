#!/usr/bin/env python3
"""
Nanji 실시간 데이터로부터 시간별 로그 생성 스크립트

수집된 실시간 데이터를 시간별로 집계하여
진짜 시간별 주차 로그를 생성합니다.

실행 방법:
    python make_nanji_hourly_log.py

주의:
- collect_nanji_realtime.py로 데이터를 먼저 수집해야 함
- API 응답 필드명에 따라 rename_map 조정 필요
"""

import pandas as pd
from pathlib import Path

# 경로 설정
RAW_DIR = Path(__file__).resolve().parent / "data" / "raw_realtime"
OUT_FILE = Path(__file__).resolve().parent / "data" / "processed" / "nanji_true_hourly_log.csv"
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# API 응답 필드명 매핑 (실제 응답에 맞춰 조정 필요)
# 서울시 실시간 주차 API 필드명 참고
RENAME_MAP = {
    "collected_at": "timestamp",
    "PARKING_NAME": "parking_name",  # 주차장명
    "ADDR": "address",  # 주소
    "TEL": "tel",  # 전화번호
    "CAPACITY": "capacity",  # 총 주차면
    "CUR_PARKING": "current_parking",  # 현재 주차중인 대수
    "CUR_PARKING_TIME": "current_parking_time",  # 현재 주차시간
    "PAY_YN": "pay_yn",  # 유무료구분
    "PAY_NM": "pay_nm",  # 유무료구분명
    "NIGHT_FREE_OPEN": "night_free_open",  # 야간무료개방여부
    "NIGHT_FREE_OPEN_NM": "night_free_open_nm",  # 야간무료개방여부명
    "WEEKDAY_BEGIN_TIME": "weekday_begin_time",  # 평일 운영 시작시각
    "WEEKDAY_END_TIME": "weekday_end_time",  # 평일 운영 종료시각
    "WEEKEND_BEGIN_TIME": "weekend_begin_time",  # 주말 운영 시작시각
    "WEEKEND_END_TIME": "weekend_end_time",  # 주말 운영 종료시각
    "HOLIDAY_BEGIN_TIME": "holiday_begin_time",  # 공휴일 운영 시작시각
    "HOLIDAY_END_TIME": "holiday_end_time",  # 공휴일 운영 종료시각
    "SATURDAY_PAY_YN": "saturday_pay_yn",  # 토요일 유,무료 구분
    "SATURDAY_PAY_NM": "saturday_pay_nm",  # 토요일 유,무료 구분명
    "HOLIDAY_PAY_YN": "holiday_pay_yn",  # 공휴일 유,무료 구분
    "HOLIDAY_PAY_NM": "holiday_pay_nm",  # 공휴일 유,무료 구분명
    "FULLTIME_MONTHLY_POP": "fulltime_monthly_pop",  # 월 정기권 금액
    "GRP_PARKNM": "grp_parknm",  # 노상 주차장 관리그룹번호
    "RATES": "rates",  # 기본 주차 요금
    "TIME_RATES": "time_rates",  # 기본 주차 시간(분 단위)
    "ADD_RATES": "add_rates",  # 추가 단위 요금
    "ADD_TIME_RATES": "add_time_rates",  # 추가 단위 시간(분 단위)
    "BUS_RATES": "bus_rates",  # 버스 기본 주차 요금
    "BUS_TIME_RATES": "bus_time_rates",  # 버스 기본 주차 시간(분 단위)
    "BUS_ADD_RATES": "bus_add_rates",  # 버스 추가 단위 요금
    "BUS_ADD_TIME_RATES": "bus_add_time_rates",  # 버스 추가 단위 시간(분 단위)
    "DAY_MAXIMUM": "day_maximum",  # 일 최대 요금
    "LAT": "lat",  # 위도
    "LNG": "lng",  # 경도
    "ASSIGN_CODE": "assign_code",  # 배정코드
    "GRP_NAME": "grp_name",  # 공유 주차장 관리업체명
    "SHARE_YN": "share_yn",  # 공유 주차장 여부
    "SHARE_LINK": "share_link",  # 공유 주차장 관리업체 링크
    "SHARE_DESC": "share_desc",  # 공유 주차장 기타사항
}

def load_raw_data():
    """수집된 raw 데이터 파일들 로드"""
    files = sorted(RAW_DIR.glob("nanji_realtime_*.csv"))
    if not files:
        raise FileNotFoundError(f"Raw realtime files not found in {RAW_DIR}")

    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f, encoding="utf-8-sig")
            dfs.append(df)
            print(f"📄 Loaded {len(df)} rows from {f.name}")
        except Exception as e:
            print(f"❌ Failed to load {f}: {e}")

    if not dfs:
        raise ValueError("No valid data files loaded")

    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"📊 Total raw data: {len(combined_df)} rows")
    return combined_df

def process_hourly_log(df: pd.DataFrame) -> pd.DataFrame:
    """시간별 로그로 집계"""
    # 필드명 매핑
    df = df.rename(columns={k: v for k, v in RENAME_MAP.items() if k in df.columns})

    # timestamp 변환
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"])

    # 시간 단위로 그룹화
    df["hour"] = df["timestamp"].dt.floor("H")

    # 그룹화 컬럼 설정
    group_cols = ["hour"]
    if "parking_name" in df.columns:
        group_cols.append("parking_name")

    # 집계
    agg_dict = {}
    if "current_parking" in df.columns:
        agg_dict["current_parking"] = "mean"  # 평균 주차대수
    if "capacity" in df.columns:
        agg_dict["capacity"] = "max"  # 최대 용량

    if not agg_dict:
        raise ValueError("No aggregatable columns found. Check API field names.")

    hourly_df = df.groupby(group_cols, as_index=False).agg(agg_dict)

    # 추가 파생 컬럼
    if "capacity" in hourly_df.columns and "current_parking" in hourly_df.columns:
        hourly_df["occupied_est"] = hourly_df["capacity"] - hourly_df["current_parking"]
        hourly_df["occupancy_rate"] = hourly_df["occupied_est"] / hourly_df["capacity"]

    # 시간 관련 컬럼
    hourly_df["date"] = hourly_df["hour"].dt.date
    hourly_df["weekday"] = hourly_df["hour"].dt.weekday
    hourly_df["month"] = hourly_df["hour"].dt.month
    hourly_df["day"] = hourly_df["hour"].dt.day
    hourly_df["hour_of_day"] = hourly_df["hour"].dt.hour

    return hourly_df

def main():
    """메인 실행 함수"""
    print("🔄 Processing Nanji realtime data to hourly log...")

    try:
        # 데이터 로드
        raw_df = load_raw_data()

        # 시간별 로그 생성
        hourly_df = process_hourly_log(raw_df)

        # 저장
        hourly_df.to_csv(OUT_FILE, index=False, encoding="utf-8-sig")
        print(f"✅ Saved hourly log: {len(hourly_df)} rows -> {OUT_FILE}")

        # 요약 정보
        print("📈 Summary:")
        print(f"   Date range: {hourly_df['date'].min()} ~ {hourly_df['date'].max()}")
        print(f"   Total hours: {len(hourly_df)}")
        if "parking_name" in hourly_df.columns:
            print(f"   Parking lots: {hourly_df['parking_name'].nunique()}")

    except Exception as e:
        print(f"❌ Processing failed: {e}")
        raise

if __name__ == "__main__":
    main()
</content>
<parameter name="filePath">/Users/electrozone/Desktop/nanji_work/yeeun/0406/make_nanji_hourly_log.py