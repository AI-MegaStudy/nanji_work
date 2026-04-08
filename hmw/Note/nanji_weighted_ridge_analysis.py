from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "ksm/nanji_hourly_modeling/nanji_hourly_model_dataset_2020_2026.csv"
METHODOLOGY_PATH = ROOT / "ksm/nanji_hourly_modeling/nanji_hourly_dataset_methodology.md"
RAW_DAILY_PATH = ROOT / "hmw/Data/한강공원 주차장 일별 이용 현황.csv"
WEATHER_DATA_DIR = ROOT / "ose/Data"
OUTPUT_DIR = ROOT / "hmw/Note/nanji_outputs"
REPORT_PATH = ROOT / "hmw/Note/nanji_weighted_ridge_modeling_report.md"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".mplconfig"))
OPERATING_HOURS = list(range(6, 24))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ALPHA_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
DAY_TYPE_ORDER = ["weekday", "offday"]
TARGET = "estimated_active_cars"
TARGET_LABEL = "estimated_active_cars (추정 활성 차량 수)"
WEATHER_FEATURE_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "snowfall",
    "snow_depth",
    "weather_code",
    "pressure_msl",
    "surface_pressure",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
]


def non_negative_only(values: np.ndarray) -> np.ndarray:
    return np.clip(values, 0, None)


def enforce_operating_hours(frame: pd.DataFrame, preds: np.ndarray) -> np.ndarray:
    adjusted = np.asarray(preds, dtype=float).copy()
    adjusted[~frame["hour"].isin(OPERATING_HOURS).to_numpy()] = 0.0
    return adjusted


def calc_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "r2": float(r2_score(y_true, y_pred)),
    }


def load_dataset() -> pd.DataFrame:
    df = pd.read_csv(DATASET_PATH, parse_dates=["datetime", "date"])
    df = df[df["year"].between(2022, 2025)].copy()
    weather_frames = []
    for year in range(2022, 2026):
        weather_path = WEATHER_DATA_DIR / f"open_meteo_nanji_{year}.csv"
        weather_df = pd.read_csv(weather_path, parse_dates=["datetime", "date"])
        weather_frames.append(weather_df)
    weather = pd.concat(weather_frames, ignore_index=True)
    weather = weather.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)
    weather_keep_cols = ["datetime", "weather_code_label", *WEATHER_FEATURE_COLUMNS]
    df = df.merge(weather[weather_keep_cols], on="datetime", how="left")
    df["weather_feature_available"] = df["temperature_2m"].notna().astype(int)
    df["day_type"] = np.where(df["is_holiday_or_weekend"].eq(1), "offday", "weekday")
    df["split"] = np.select(
        [
            df["year"].between(2022, 2023),
            df["year"].eq(2024),
            df["year"].eq(2025),
        ],
        ["train", "valid", "test"],
        default="other",
    )
    return df.sort_values("datetime").reset_index(drop=True)


def load_raw_daily_summary() -> pd.DataFrame:
    raw = pd.read_csv(RAW_DAILY_PATH, encoding="cp949")
    raw = raw[raw["주차장명"].astype(str).str.contains("난지", na=False)].copy()
    raw["날짜"] = pd.to_datetime(raw["날짜"])
    raw = raw[raw["날짜"].dt.year.between(2022, 2025)].copy()
    return (
        raw.groupby("날짜", as_index=False)
        .agg(
            daily_parking_count=("주차대수", "sum"),
            daily_usage_minutes=("이용시간", "sum"),
        )
        .sort_values("날짜")
        .reset_index(drop=True)
    )


def fit_day_type_hour_models(train_df: pd.DataFrame, target: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    formula_rows = []
    base_rows = []
    for day_type in DAY_TYPE_ORDER:
        sub = (
            train_df[train_df["day_type"] == day_type]
            .groupby("hour", as_index=False)[target]
            .mean()
            .sort_values("hour")
        )
        angle = 2 * np.pi * sub["hour"].to_numpy(dtype=float) / 24.0
        X = np.column_stack([np.ones(len(sub)), np.sin(angle), np.cos(angle)])
        y = sub[target].to_numpy(dtype=float)
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        sub["base_value"] = np.clip(X @ beta, 0, None)
        sub["day_type"] = day_type
        base_rows.append(sub[["day_type", "hour", "base_value"]])
        formula_rows.append(
            {
                "target": target,
                "day_type": day_type,
                "intercept": float(beta[0]),
                "sin_hour_coef": float(beta[1]),
                "cos_hour_coef": float(beta[2]),
                "formula": f"{beta[0]:.6f} + ({beta[1]:+.6f} * sin(2pi*hour/24)) + ({beta[2]:+.6f} * cos(2pi*hour/24))",
            }
        )
    return pd.DataFrame(formula_rows), pd.concat(base_rows, ignore_index=True)


def build_weight_maps(
    all_df: pd.DataFrame,
    base_df: pd.DataFrame,
    target: str,
) -> tuple[dict[int, float], dict[int, float], pd.DataFrame]:
    all_base = all_df.merge(base_df, on=["day_type", "hour"], how="left")
    all_base["month_ratio"] = np.where(all_base["base_value"] > 0, all_base[target] / all_base["base_value"], 1.0)
    month_weight_map = all_base.groupby("month")["month_ratio"].mean().to_dict()
    month_mean = float(np.mean(list(month_weight_map.values())))
    month_weight_map = {int(k): float(v / month_mean) for k, v in month_weight_map.items()}

    all_base["month_weight"] = all_base["month"].map(month_weight_map).fillna(1.0)
    all_base["pattern_prior"] = all_base["base_value"] * all_base["month_weight"]
    hour_base = all_base[all_base["hour"].isin(OPERATING_HOURS)].copy()
    hour_base["hour_ratio"] = np.where(hour_base["pattern_prior"] > 0, hour_base[target] / hour_base["pattern_prior"], 1.0)
    hour_weight_map = hour_base.groupby("hour")["hour_ratio"].mean().to_dict()
    hour_mean = float(np.mean(list(hour_weight_map.values())))
    hour_weight_map = {int(k): float(v / hour_mean) for k, v in hour_weight_map.items()}
    return month_weight_map, hour_weight_map, all_base


def attach_pattern_features(
    in_df: pd.DataFrame,
    base_df: pd.DataFrame,
    month_weight_map: dict[int, float],
    hour_weight_map: dict[int, float],
) -> pd.DataFrame:
    out = in_df.merge(base_df, on=["day_type", "hour"], how="left")
    out["month_weight"] = out["month"].map(month_weight_map).fillna(1.0)
    out["pattern_prior"] = out["base_value"] * out["month_weight"]
    out["hour_weight"] = out["hour"].map(hour_weight_map).fillna(1.0)
    out["corrected_pattern_prior"] = out["pattern_prior"] * out["hour_weight"]
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24.0)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24.0)
    out["month_sin"] = np.sin(2 * np.pi * out["month"] / 12.0)
    out["month_cos"] = np.cos(2 * np.pi * out["month"] / 12.0)
    out["day_type_offday"] = out["day_type"].eq("offday").astype(int)
    return out


def feature_sets() -> dict[str, list[str]]:
    core = [
        "base_value",
        "month_weight",
        "hour_weight",
        "pattern_prior",
        "corrected_pattern_prior",
        "day_type_offday",
    ]
    extended = core + [
        "hour_sin",
        "hour_cos",
        "month_sin",
        "month_cos",
        "is_holiday",
        "is_long_weekend",
        "bus_boardings",
        "bus_alightings",
        "subway_boardings",
        "subway_alightings",
        "bike_rentals",
        "bike_returns",
        "bike_rental_minutes_sum",
        "bike_rental_distance_m_sum",
        "event_count",
        "free_event_count",
        "paid_event_count",
        "evening_event_count",
        "bus_feature_available",
        "subway_feature_available",
        "bike_feature_available",
        "culture_feature_available",
        *WEATHER_FEATURE_COLUMNS,
        "weather_feature_available",
    ]
    return {"weighted_core": core, "weighted_extended": extended}


def prune_correlated_features(
    train_df: pd.DataFrame,
    feature_map: dict[str, list[str]],
    threshold: float = 0.9,
) -> tuple[dict[str, list[str]], pd.DataFrame]:
    pruned_map: dict[str, list[str]] = {}
    pruning_rows: list[dict[str, object]] = []

    for model_name, columns in feature_map.items():
        corr = train_df[columns].corr().abs()
        target_corr = train_df[columns].corrwith(train_df[TARGET]).abs()
        kept: list[str] = []
        dropped: set[str] = set()

        for col in columns:
            if col in dropped:
                continue
            candidate = col
            for other in columns:
                if other == candidate or other in dropped or other in kept:
                    continue
                corr_value = corr.loc[candidate, other]
                if pd.notna(corr_value) and corr_value >= threshold:
                    if float(target_corr.get(other, 0.0)) > float(target_corr.get(candidate, 0.0)):
                        dropped.add(candidate)
                        pruning_rows.append(
                            {
                                "model_name": model_name,
                                "kept_feature": other,
                                "dropped_feature": candidate,
                                "abs_corr": float(corr_value),
                                "threshold": threshold,
                            }
                        )
                        candidate = other
                    else:
                        dropped.add(other)
                        pruning_rows.append(
                            {
                                "model_name": model_name,
                                "kept_feature": candidate,
                                "dropped_feature": other,
                                "abs_corr": float(corr_value),
                                "threshold": threshold,
                            }
                        )
            if candidate not in dropped and candidate not in kept:
                kept.append(candidate)

        pruned_map[model_name] = kept

    pruning_df = pd.DataFrame(pruning_rows)
    return pruned_map, pruning_df


def prepare_split_frames(df: pd.DataFrame, base_df: pd.DataFrame, month_weight_map: dict[int, float], hour_weight_map: dict[int, float]) -> dict[str, pd.DataFrame]:
    splits = {}
    for split_name in ["train", "valid", "test"]:
        part = df[df["split"] == split_name].copy()
        processed = attach_pattern_features(part, base_df, month_weight_map, hour_weight_map)
        processed = processed.fillna(0)
        splits[split_name] = processed
    return splits


def train_models(
    processed_splits: dict[str, pd.DataFrame],
    feature_map: dict[str, list[str]],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    tuning_rows = []
    metric_rows = []
    importance_rows = []

    for model_name, columns in feature_map.items():
        best_alpha = None
        best_model = None
        best_valid_rmse = math.inf

        X_train = processed_splits["train"][columns]
        y_train = processed_splits["train"][TARGET]
        X_valid = processed_splits["valid"][columns]
        y_valid = processed_splits["valid"][TARGET]

        for alpha in ALPHA_GRID:
            model = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("ridge", Ridge(alpha=alpha)),
                ]
            )
            model.fit(X_train, y_train)
            valid_pred = non_negative_only(model.predict(X_valid))
            valid_pred = enforce_operating_hours(processed_splits["valid"], valid_pred)
            metrics = calc_metrics(y_valid, valid_pred)
            tuning_rows.append({"model_name": model_name, "alpha": alpha, **metrics})
            if metrics["rmse"] < best_valid_rmse:
                best_valid_rmse = metrics["rmse"]
                best_alpha = alpha
                best_model = model

        scaler = best_model.named_steps["scaler"]
        ridge = best_model.named_steps["ridge"]
        scaled_coefs = ridge.coef_ / scaler.scale_
        coef_abs_sum = float(np.abs(scaled_coefs).sum())
        importance_rows.extend(
            {
                "model_name": model_name,
                "feature": feature,
                "alpha": best_alpha,
                "coefficient": float(coef),
                "importance_abs": float(abs(coef)),
                "importance_ratio": float(abs(coef) / coef_abs_sum) if coef_abs_sum else 0.0,
            }
            for feature, coef in zip(columns, scaled_coefs)
        )

        for split_name in ["train", "valid", "test"]:
            frame = processed_splits[split_name]
            pred = non_negative_only(best_model.predict(frame[columns]))
            pred = enforce_operating_hours(frame, pred)
            metrics = calc_metrics(frame[TARGET], pred)
            metric_rows.append(
                {
                    "model_name": model_name,
                    "alpha": best_alpha,
                    "split": split_name,
                    **metrics,
                }
            )
            processed_splits[split_name][f"{model_name}_prediction"] = pred

    return pd.DataFrame(tuning_rows), pd.DataFrame(metric_rows), pd.DataFrame(importance_rows)


def quality_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        [
            {
                "rows": len(df),
                "unique_datetime": df["datetime"].nunique(),
                "duplicate_rows": int(len(df) - df["datetime"].nunique()),
                "target_missing": int(df[TARGET].isna().sum()),
                "target_min": float(df[TARGET].min()),
                "target_max": float(df[TARGET].max()),
                "date_min": df["datetime"].min(),
                "date_max": df["datetime"].max(),
            }
        ]
    )
    return summary


def data_availability_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "asset": "난지 시간별 통합 데이터셋",
            "path": str(DATASET_PATH.relative_to(ROOT)),
            "granularity": "1시간",
            "availability": "있음",
            "note": "주차 추정 타깃과 외생 변수 결합본",
        },
        {
            "asset": "난지 일별 주차 원본",
            "path": str(RAW_DAILY_PATH.relative_to(ROOT)),
            "granularity": "1일",
            "availability": "있음",
            "note": "시간별 타깃 생성을 위한 베이스 원본",
        },
        {
            "asset": "서울시 지하철 시간대 승하차",
            "path": "Data/서울시 지하철 호선별 역별 시간대별 승하차 인원 정보.csv",
            "granularity": "월-시간대",
            "availability": "있음",
            "note": "난지 인근 역 패턴이 통합 데이터셋에 반영됨",
        },
        {
            "asset": "서울시 시영주차장 실시간 주차대수",
            "path": "Data/서울시 시영주차장 실시간 주차대수 정보.csv",
            "granularity": "스냅샷/실시간",
            "availability": "있음",
            "note": "정적 참고용이며 난지 타깃 시계열로 직접 사용되진 않음",
        },
        {
            "asset": "난지 시간별 날씨 데이터",
            "path": "ose/Data/open_meteo_nanji_2022~2025.csv",
            "granularity": "1시간",
            "availability": "있음",
            "note": "기온, 강수, 운량, 풍속, 복사량 등 시간별 기상 feature",
        },
    ]
    availability_df = pd.DataFrame(rows)
    feature_rate = (
        df[
            [
                "bus_feature_available",
                "subway_feature_available",
                "bike_feature_available",
                "culture_feature_available",
                "weather_feature_available",
            ]
        ]
        .mean()
        .rename("coverage_rate")
        .reset_index()
        .rename(columns={"index": "feature"})
    )
    return availability_df, feature_rate


def top_missing_features(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.isna()
        .sum()
        .sort_values(ascending=False)
        .rename("missing_count")
        .reset_index()
        .rename(columns={"index": "feature"})
        .head(10)
    )


def plot_weights(weight_df: pd.DataFrame, x_col: str, title: str, output_name: str) -> None:
    plt.figure(figsize=(10, 4.5))
    plt.plot(weight_df[x_col], weight_df["value"], marker="o", linewidth=2.0, color="#1f4e79")
    plt.axhline(1.0, color="gray", linestyle="--", linewidth=1)
    plt.title(title)
    plt.xlabel(x_col)
    plt.ylabel("weight")
    plt.grid(axis="y", alpha=0.2, linestyle="--")
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=160)
    plt.close()


def plot_prediction_compare(test_df: pd.DataFrame, output_name: str) -> None:
    monthly = (
        test_df.assign(month_start=test_df["datetime"].dt.to_period("M").dt.to_timestamp())
        .groupby("month_start", as_index=False)[[TARGET, "weighted_core_prediction", "weighted_extended_prediction"]]
        .mean()
    )
    plt.figure(figsize=(10, 4.5))
    plt.plot(monthly["month_start"], monthly[TARGET], label="actual", linewidth=2.4, color="#1f4e79")
    plt.plot(monthly["month_start"], monthly["weighted_core_prediction"], label="weighted_core", linestyle="--", linewidth=2.0, color="#d97a04")
    plt.plot(monthly["month_start"], monthly["weighted_extended_prediction"], label="weighted_extended", linestyle="-.", linewidth=2.0, color="#2e8b57")
    plt.title("2025 monthly mean comparison")
    plt.xlabel("month")
    plt.ylabel(TARGET)
    plt.grid(axis="y", alpha=0.2, linestyle="--")
    plt.legend(frameon=True)
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / output_name, dpi=160)
    plt.close()


def to_markdown_table(df: pd.DataFrame, digits: int = 4) -> str:
    view = df.copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.{digits}f}")
    return view.to_markdown(index=False)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df = load_dataset()
    raw_daily = load_raw_daily_summary()
    train_df = df[df["split"] == "train"].copy()
    formula_df, base_df = fit_day_type_hour_models(train_df, TARGET)

    month_weight_map, hour_weight_map, all_base = build_weight_maps(train_df, base_df, TARGET)
    processed_splits = prepare_split_frames(df, base_df, month_weight_map, hour_weight_map)
    feature_map, pruning_df = prune_correlated_features(processed_splits["train"], feature_sets(), threshold=0.9)
    tuning_df, metrics_df, importance_df = train_models(processed_splits, feature_map)

    weight_rows = []
    weight_rows.extend({"weight_type": "month_weight", "key": k, "value": v} for k, v in month_weight_map.items())
    weight_rows.extend({"weight_type": "hour_weight", "key": k, "value": v} for k, v in hour_weight_map.items())
    weight_df = pd.DataFrame(weight_rows)

    test_prediction_base = df[df["split"] == "test"][["datetime", TARGET]].copy().reset_index(drop=True)
    for model_name in feature_sets().keys():
        pred_col = f"{model_name}_prediction"
        test_prediction_base[pred_col] = processed_splits["test"][pred_col].reset_index(drop=True)

    quality_df = quality_summary(df)
    availability_df, coverage_df = data_availability_summary(df)
    missing_df = top_missing_features(df)

    best_models = (
        metrics_df[metrics_df["split"] == "test"]
        .sort_values("r2", ascending=False)
        .reset_index(drop=True)
    )
    recommended_model = best_models.iloc[0]["model_name"]
    recommended_alpha = float(best_models.iloc[0]["alpha"])

    top_importance = (
        importance_df[importance_df["model_name"] == recommended_model]
        .sort_values("importance_ratio", ascending=False)
        .head(10)
        .reset_index(drop=True)
    )

    test_df = processed_splits["test"].copy()
    test_df["core_abs_error"] = np.abs(test_df[TARGET] - test_df["weighted_core_prediction"])
    test_df["extended_abs_error"] = np.abs(test_df[TARGET] - test_df["weighted_extended_prediction"])
    error_by_hour = (
        test_df.groupby("hour", as_index=False)[["core_abs_error", "extended_abs_error"]]
        .mean()
        .sort_values("extended_abs_error", ascending=False)
    )
    error_by_month = (
        test_df.groupby("month", as_index=False)[["core_abs_error", "extended_abs_error"]]
        .mean()
        .sort_values("extended_abs_error", ascending=False)
    )

    plot_weights(
        weight_df[weight_df["weight_type"] == "month_weight"].sort_values("key"),
        "key",
        "Nanji month weights",
        "nanji_month_weights.png",
    )
    plot_weights(
        weight_df[weight_df["weight_type"] == "hour_weight"].sort_values("key"),
        "key",
        "Nanji hour weights",
        "nanji_hour_weights.png",
    )
    compare_plot_df = test_prediction_base.copy()
    plot_prediction_compare(compare_plot_df, "nanji_2025_monthly_compare.png")

    metrics_df.to_csv(OUTPUT_DIR / "nanji_model_metrics.csv", index=False, encoding="utf-8-sig")
    tuning_df.to_csv(OUTPUT_DIR / "nanji_model_tuning.csv", index=False, encoding="utf-8-sig")
    importance_df.to_csv(OUTPUT_DIR / "nanji_feature_importance.csv", index=False, encoding="utf-8-sig")
    pruning_df.to_csv(OUTPUT_DIR / "nanji_feature_pruning.csv", index=False, encoding="utf-8-sig")
    weight_df.to_csv(OUTPUT_DIR / "nanji_weight_table.csv", index=False, encoding="utf-8-sig")
    test_prediction_base.to_csv(OUTPUT_DIR / "nanji_test_predictions.csv", index=False, encoding="utf-8-sig")

    methodology_lines = METHODOLOGY_PATH.read_text(encoding="utf-8").splitlines()
    methodology_excerpt = "\n".join(line for line in methodology_lines[4:18] if line.strip())

    model_metrics = metrics_df.sort_values(["split", "model_name"]).reset_index(drop=True)
    compare_test_metrics = metrics_df[metrics_df["split"] == "test"].sort_values("r2", ascending=False).reset_index(drop=True)

    report = f"""# 난지 한강공원 시간별 주차 예측 가중치 분석

## 1. 작업 범위

- 기준 노트: `hmw/Note/nanji_ML.ipynb`
- 참고 프로세스: 이전 통합 분석 노트북의 가중치 기반 흐름
- 제외한 단계: station 선정/랭킹/다중 station 비교
- 핵심 반영 요소: `day_type x hour` 기본 패턴 + `month/hour` 가중치 + Ridge 회귀
- 예측 대상: `{TARGET_LABEL}`

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

{to_markdown_table(availability_df, digits=3)}

### feature 가용률

{to_markdown_table(coverage_df, digits=3)}

## 4. 시간별 데이터가 만들어진 방식

`ksm/nanji_hourly_modeling/nanji_hourly_dataset_methodology.md` 기준 요약:

{methodology_excerpt}

원본 난지 일별 주차 데이터는 `hmw/Data/한강공원 주차장 일별 이용 현황.csv`에서 `주차장명 == 난지1,2,3,4주차장` 행을 사용했습니다. 이 일별 원본을 하루 24시간으로 확장한 뒤, 평일/오프데이와 계절성 프로필로 `estimated_entries`를 만들고, 평균 체류시간으로 `estimated_active_cars`를 계산한 구조입니다. 즉, 이번 예측 타깃은 **실측 시간 로그가 아니라 일별 원본 기반 추정 시간대 점유량**입니다.

### 원본/가공 범위 확인

- 일별 원본 기간: `{raw_daily["날짜"].min().date()}` ~ `{raw_daily["날짜"].max().date()}`
- 일별 원본 일수: `{len(raw_daily):,}`
- 시간별 통합 데이터 기간: `{df["datetime"].min()}` ~ `{df["datetime"].max()}`
- 시간별 통합 데이터 행수: `{len(df):,}`

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

{to_markdown_table(quality_df, digits=3)}

### 결측 상위 10개

{to_markdown_table(missing_df, digits=0)}

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

{to_markdown_table(formula_df, digits=4)}

### 가중치 요약

월 가중치:

{to_markdown_table(weight_df[weight_df["weight_type"] == "month_weight"].sort_values("key"), digits=4)}

시간 가중치 상위 10개:

{to_markdown_table(weight_df[weight_df["weight_type"] == "hour_weight"].sort_values("value", ascending=False).head(10), digits=4)}

시간 가중치 표에는 `0~5시`가 포함되지 않습니다. 해당 시간은 운영시간 외 구간으로 보고 `hour_weight` 계산에서 제외했습니다.

## 8. 모델 비교

{to_markdown_table(model_metrics, digits=4)}

### test 기준 직접 비교

{to_markdown_table(compare_test_metrics[["model_name", "alpha", "rmse", "mae", "r2"]], digits=4)}

오프라인 성능 기준 최고 모델은 `{recommended_model}` 이고, 선택 alpha는 `{recommended_alpha}` 입니다.

다만 **미래 시점(1시간 뒤, 3시간 뒤, 하루 뒤, 이틀 뒤 등)을 현재 시점까지의 정보만으로 예측하는 실사용 구조**로 보면, 실제 운용 모델은 `weighted_core`로 두는 것이 더 적절합니다. 이유는 `weighted_extended`에 포함된 버스/지하철/자전거/행사/날씨 변수는 미래 시점의 값을 예측 순간에 모두 안정적으로 알 수 없기 때문입니다.

### 높은 상관계수 feature 정리

이번 최종 학습에서는 `train(2022~2023)` 기준 절대 상관계수 `0.9` 이상인 feature 쌍이 있으면, 같은 모델 feature 세트 안에서 **타깃(`estimated_active_cars`)과의 절대 상관이 더 큰 feature를 남기고, 나머지는 제외**했습니다.

{to_markdown_table(pruning_df.head(20), digits=4) if not pruning_df.empty else "제거된 feature 없음"}

## 9. 추천 모델 해석

### 어떤 모델을 실사용용으로 볼 것인가

- `weighted_extended`는 오프라인 평가에서는 더 높은 `R²`를 보였지만, 미래 시점의 외생 변수를 실제 예측 순간에 알 수 없다는 한계가 있습니다.
- 특히 행사 정보와 시간별 날씨 정보는 사후적으로 해석할 때는 유용하지만, "3시간 뒤", "하루 뒤", "이틀 뒤"를 현재 시점 정보만으로 예측해야 하는 구조에서는 직접 feature로 넣기 어렵습니다.
- 따라서 이번 프로젝트의 **실사용용 미래 예측 모델**은 `weighted_core`로 보는 것이 맞습니다.
- `weighted_extended`는 "왜 특정 시기 오차가 줄었는지"를 확인하는 참고 모델, 또는 과거 데이터 해석용 비교 모델로만 두는 편이 안전합니다.
- 같은 이유로 `lag`, `rolling`, 자기회귀형 시계열 feature도 이번 구조에는 넣지 않았습니다. 이런 값들은 예측 시점 이후의 경로를 전제하거나, 시계열 모델로 구조가 바뀌기 때문입니다.

### 중요 feature 상위 10개

{to_markdown_table(top_importance[["feature", "coefficient", "importance_ratio"]], digits=4)}

### 2025 오차가 큰 시간대 상위 8개

{to_markdown_table(error_by_hour.head(8), digits=4)}

### 2025 오차가 큰 월 상위 8개

{to_markdown_table(error_by_month.head(8), digits=4)}

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
- 최종 `test(2025)` 기준에서는 `{recommended_model}`이 가장 높은 성능을 보였습니다.
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
"""

    REPORT_PATH.write_text(report, encoding="utf-8")

    summary = {
        "recommended_model": recommended_model,
        "recommended_alpha": recommended_alpha,
        "test_metrics": metrics_df[metrics_df["split"] == "test"].to_dict(orient="records"),
    }
    (OUTPUT_DIR / "nanji_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
