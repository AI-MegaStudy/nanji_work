#!/usr/bin/env python3
"""
Nanji hourly parking prediction prototype

이 스크립트는 기존의 시간별 Nanji 데이터셋을 활용하여 1시간 앞 주차 점유율을 예측하는 기본 모델을 구성합니다.
- 데이터: ksm/nanji_hourly_modeling/nanji_hourly_model_dataset_2020_2026.csv
- 타깃: hourly_share (0~1)
- 기계학습 모델: RandomForestRegressor

필요 패키지:
  pip install pandas scikit-learn
"""

from pathlib import Path
import pickle
import sys

try:
    import pandas as pd
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, mean_squared_error
    from sklearn.model_selection import train_test_split
except ImportError as exc:
    raise SystemExit(
        "필수 패키지가 설치되어 있지 않습니다.\n"
        "pip install pandas scikit-learn\n"
        f"누락된 패키지: {exc.name}"
    )

DATASET_PATH = Path(__file__).resolve().parents[2] / 'ksm' / 'nanji_hourly_modeling' / 'nanji_hourly_model_dataset_2020_2026.csv'
MODEL_OUTPUT_PATH = Path(__file__).resolve().parent / 'nanji_hourly_model.pkl'
FEATURE_COLUMNS = [
    'hour',
    'year',
    'month',
    'day',
    'is_weekend',
    'daily_parking_count',
    'daily_usage_minutes',
    'avg_stay_minutes',
    'estimated_entries',
    'estimated_active_cars',
    'estimated_active_cars_change',
    'holiday_table_is_weekend',
    'is_holiday',
    'is_substitute_holiday',
    'is_holiday_or_weekend',
    'is_long_weekend',
    'bus_boardings',
    'bus_alightings',
    'subway_boardings',
    'subway_alightings',
    'bike_rentals',
    'bike_rental_minutes_sum',
    'bike_rental_distance_m_sum',
    'bike_returns',
    'event_count',
    'free_event_count',
    'paid_event_count',
    'evening_event_count',
    'nearby_public_parking_sites',
    'nearby_public_parking_capacity_sum',
    'nearby_kickboard_zone_count',
    'nearby_kickboard_stand_count',
]
CATEGORICAL_COLUMNS = ['day_of_week', 'season']
TARGET_COLUMN = 'hourly_share'


def load_dataset(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"데이터셋 파일을 찾을 수 없습니다: {path}")

    df = pd.read_csv(path, encoding='utf-8-sig')
    df['datetime'] = pd.to_datetime(df['datetime'])
    return df


def bool_to_int(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series.astype(int)
    return series.map({'True': 1, 'False': 0}).fillna(series).astype(int)


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    df = df.copy()

    for col in [
        'is_weekend',
        'holiday_table_is_weekend',
        'is_holiday',
        'is_substitute_holiday',
        'is_holiday_or_weekend',
        'is_long_weekend',
        'bus_feature_available',
        'subway_feature_available',
        'bike_feature_available',
        'culture_feature_available',
    ]:
        if col in df.columns:
            df[col] = bool_to_int(df[col])

    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            raise KeyError(f"필수 feature가 누락되었습니다: {col}")
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna(subset=FEATURE_COLUMNS + [TARGET_COLUMN])

    categorical_df = pd.get_dummies(df[CATEGORICAL_COLUMNS].astype(str), drop_first=True)
    X = pd.concat([df[FEATURE_COLUMNS], categorical_df], axis=1)
    y = pd.to_numeric(df[TARGET_COLUMN], errors='coerce')

    return X, y


def train_model(X: pd.DataFrame, y: pd.Series) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
        max_depth=12,
    )
    model.fit(X, y)
    return model


def evaluate_model(model: RandomForestRegressor, X: pd.DataFrame, y: pd.Series) -> dict:
    y_pred = model.predict(X)
    mae = mean_absolute_error(y, y_pred)
    rmse = mean_squared_error(y, y_pred, squared=False)
    mape = np.mean(np.abs((y - y_pred) / np.maximum(np.abs(y), 1e-6)))
    return {
        'MAE': float(mae),
        'RMSE': float(rmse),
        'MAPE': float(mape),
        'R2': float(model.score(X, y)),
    }


def save_model(model: RandomForestRegressor, feature_names: list[str]) -> None:
    with open(MODEL_OUTPUT_PATH, 'wb') as f:
        pickle.dump({'model': model, 'feature_names': feature_names}, f)
    print(f"모델 저장 완료: {MODEL_OUTPUT_PATH}")


def load_model(path: Path = MODEL_OUTPUT_PATH) -> dict:
    with open(path, 'rb') as f:
        return pickle.load(f)


def build_and_evaluate() -> None:
    df = load_dataset(DATASET_PATH)
    X, y = prepare_features(df)

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, shuffle=False
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, shuffle=False
    )

    print(f"데이터셋 로드 완료: {len(df)}행")
    print(f"학습: {len(X_train)}행, 검증: {len(X_val)}행, 테스트: {len(X_test)}행")

    model = train_model(X_train, y_train)

    print("\n[검증 평가]")
    metrics_val = evaluate_model(model, X_val, y_val)
    for k, v in metrics_val.items():
        print(f"  {k}: {v:.4f}")

    print("\n[테스트 평가]")
    metrics_test = evaluate_model(model, X_test, y_test)
    for k, v in metrics_test.items():
        print(f"  {k}: {v:.4f}")

    save_model(model, X.columns.tolist())

    print("\n최근 데이터로 1시간 후 점유율 예측 예시")
    last_row = X_test.iloc[-1:]
    pred = model.predict(last_row)[0]
    print(f"  현재 예상 hourly_share: {pred:.4f} (약 {pred*100:.1f}%)")


def main() -> None:
    build_and_evaluate()


if __name__ == '__main__':
    main()
