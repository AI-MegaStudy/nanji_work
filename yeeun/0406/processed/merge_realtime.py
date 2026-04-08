import pandas as pd
from pathlib import Path

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "Data"
MODEL_DIR = BASE_DIR / "ksm" / "nanji_hourly_modeling"

# 기존 데이터셋 로드
existing_file = MODEL_DIR / "nanji_hourly_model_dataset_2020_2026.csv"
df_existing = pd.read_csv(existing_file, encoding='utf-8-sig')

# 실시간 데이터 로드
realtime_file = DATA_DIR / "nanji_realtime.csv"
df_realtime = pd.read_csv(realtime_file, encoding='utf-8-sig')

# 실시간 데이터에서 필요한 컬럼 추출 (난지 주차장만)
# NOW_PRK_VHCL_CNT: 현재 주차 차량 수
# TPKCT: 총 주차면 수
realtime_info = df_realtime[['NOW_PRK_VHCL_CNT', 'TPKCT']].iloc[0]  # 첫 번째 행 사용

# 기존 데이터셋에 실시간 정보 추가
df_existing['realtime_current_parking'] = realtime_info['NOW_PRK_VHCL_CNT']
df_existing['realtime_total_capacity'] = realtime_info['TPKCT']

# 새로운 파일로 저장
output_file = DATA_DIR / "nanji_hourly_model_dataset_2020_2026_update.csv"
df_existing.to_csv(output_file, index=False, encoding='utf-8-sig')

print(f"업데이트된 데이터셋 저장 완료: {output_file}")
print(f"추가된 컬럼: realtime_current_parking, realtime_total_capacity")