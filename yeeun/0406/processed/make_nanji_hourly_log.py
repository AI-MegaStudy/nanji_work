#!/usr/bin/env python3
"""
Nanji 시간별 로그 생성 스크립트

수집된 실시간 주차 데이터를 시간별로 집계하여
시간별 로그 파일을 생성합니다.

실행 방법:
    python make_nanji_hourly_log.py

주의:
- Data 폴더의 nanji_realtime.csv 파일을 읽음
- 시간별로 평균 주차 대수를 계산
"""

import os
import pandas as pd
from datetime import datetime
from pathlib import Path

# 경로 설정
DATA_DIR = Path(__file__).resolve().parents[3] / "Data"
OUTPUT_DIR = DATA_DIR / "processed"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def process_realtime_to_hourly(input_file: str, output_file: str):
    """실시간 데이터를 시간별 로그로 변환"""
    try:
        # 데이터 읽기
        df = pd.read_csv(input_file, encoding='utf-8-sig')

        # timestamp 컬럼이 있는지 확인
        if 'timestamp' not in df.columns:
            print("❌ timestamp 컬럼이 없습니다.")
            return False

        # timestamp를 datetime으로 변환
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 시간별로 그룹화하여 평균 계산
        df['hour'] = df['timestamp'].dt.floor('h')  # 시간 단위로 내림

        # 주차 대수 관련 컬럼 확인 (NOW_PRK_VHCL_CNT)
        if 'NOW_PRK_VHCL_CNT' not in df.columns:
            print("❌ NOW_PRK_VHCL_CNT 컬럼이 없습니다.")
            return False

        # 시간별 평균 주차 대수 계산
        hourly_stats = df.groupby('hour').agg({
            'NOW_PRK_VHCL_CNT': ['mean', 'min', 'max', 'count'],
            'TPKCT': 'first'  # 총 주차면수 (첫 번째 값 사용)
        }).round(2)

        # 컬럼명 정리
        hourly_stats.columns = ['avg_parking', 'min_parking', 'max_parking', 'data_points', 'total_capacity']
        hourly_stats = hourly_stats.reset_index()

        # 결과 저장
        hourly_stats.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"✅ 시간별 로그 생성 완료: {output_file}")
        print(f"   - 총 {len(hourly_stats)} 시간 기록")
        print(f"   - 데이터 포인트: {hourly_stats['data_points'].sum()}")

        return True

    except Exception as e:
        print(f"❌ 처리 중 오류 발생: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("🚀 Nanji 시간별 로그 생성 시작...")

    # 입력 파일
    input_file = DATA_DIR / "nanji_realtime.csv"
    if not input_file.exists():
        print(f"❌ 입력 파일이 존재하지 않습니다: {input_file}")
        return

    # 출력 파일
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = OUTPUT_DIR / f"nanji_hourly_log_{timestamp}.csv"

    print(f"📁 입력: {input_file}")
    print(f"📁 출력: {output_file}")

    # 처리 실행
    success = process_realtime_to_hourly(str(input_file), str(output_file))

    if success:
        print("✅ 완료!")
    else:
        print("❌ 실패!")

if __name__ == "__main__":
    main()