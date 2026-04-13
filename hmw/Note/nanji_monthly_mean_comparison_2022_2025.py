from __future__ import annotations

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
WEATHER_DATA_DIR = ROOT / "ose/Data"
OUTPUT_DIR = ROOT / "hmw/Note/nanji_outputs_change"
os.environ.setdefault("MPLCONFIGDIR", str(OUTPUT_DIR / ".mplconfig"))
OPERATING_HOURS = list(range(6, 24))

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt


TARGET = "estimated_active_cars_change"
ALPHA_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
DAY_TYPE_ORDER = ["weekday", "offday"]
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
    return np.asarray(values, dtype=float)


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
    weather_df = (
        pd.concat(weather_frames, ignore_index=True)
        .sort_values("datetime")
        .drop_duplicates("datetime")
        .reset_index(drop=True)
    )
    weather_keep_cols = ["datetime", "weather_code_label", *WEATHER_FEATURE_COLUMNS]
    df = df.merge(weather_df[weather_keep_cols], on="datetime", how="left")
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


def fit_day_type_hour_models(train_df: pd.DataFrame, target: str) -> pd.DataFrame:
    base_rows = []
    for day_type in DAY_TYPE_ORDER:
        sub = (
            train_df[train_df["day_type"] == day_type]
            .groupby("hour", as_index=False)[target]
            .mean()
            .sort_values("hour")
        )
        angle = 2 * np.pi * sub["hour"].to_numpy(dtype=float) / 24.0
        x_mat = np.column_stack([np.ones(len(sub)), np.sin(angle), np.cos(angle)])
        y_vec = sub[target].to_numpy(dtype=float)
        beta, *_ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
        sub["base_value"] = x_mat @ beta
        sub["day_type"] = day_type
        base_rows.append(sub[["day_type", "hour", "base_value"]])
    return pd.concat(base_rows, ignore_index=True)


def safe_ratio(numerator, denominator, default: float = 1.0, eps: float = 1e-6) -> np.ndarray:
    numerator_arr = np.asarray(numerator, dtype=float)
    denominator_arr = np.asarray(denominator, dtype=float)
    result = np.full_like(numerator_arr, default, dtype=float)
    valid = np.abs(denominator_arr) > eps
    result[valid] = numerator_arr[valid] / denominator_arr[valid]
    return result


def shrink_late_hour_weight(
    hour_weight_map: dict[int, float],
    hour_base: pd.DataFrame,
    target_hour: int = 23,
    anchor_hour: int = 22,
) -> dict[int, float]:
    adjusted = {int(k): float(v) for k, v in hour_weight_map.items()}
    if target_hour not in adjusted or anchor_hour not in adjusted:
        return adjusted

    hour_target = hour_base[hour_base["hour"] == target_hour]["hour_ratio"].astype(float)
    if hour_target.empty:
        return adjusted

    raw_target = float(adjusted[target_hour])
    anchor = float(adjusted[anchor_hour])
    target_std = float(hour_target.std(ddof=1)) if len(hour_target) > 1 else 0.0
    target_mean = float(hour_target.mean())
    cv = target_std / max(abs(target_mean), 1e-6)
    reliability = 1.0 / (1.0 + cv)
    adjusted[target_hour] = float(reliability * raw_target + (1.0 - reliability) * anchor)

    mean_after = float(np.mean(list(adjusted.values())))
    return {int(k): float(v / mean_after) for k, v in adjusted.items()}


def build_weight_maps(
    all_df: pd.DataFrame,
    base_df: pd.DataFrame,
    target: str,
) -> tuple[dict[int, float], dict[int, float]]:
    all_base = all_df.merge(base_df, on=["day_type", "hour"], how="left")
    all_base["month_ratio"] = safe_ratio(all_base[target], all_base["base_value"], default=1.0)
    month_weight_map = all_base.groupby("month")["month_ratio"].mean().to_dict()
    month_mean = float(np.mean(list(month_weight_map.values())))
    month_weight_map = {int(k): float(v / month_mean) for k, v in month_weight_map.items()}

    all_base["month_weight"] = all_base["month"].map(month_weight_map).fillna(1.0)
    all_base["pattern_prior"] = all_base["base_value"] * all_base["month_weight"]

    hour_base = all_base[all_base["hour"].isin(OPERATING_HOURS)].copy()
    hour_base["hour_ratio"] = safe_ratio(hour_base[target], hour_base["pattern_prior"], default=1.0)
    raw_hour_weight_map = hour_base.groupby("hour")["hour_ratio"].mean().to_dict()
    hour_mean = float(np.mean(list(raw_hour_weight_map.values())))
    raw_hour_weight_map = {int(k): float(v / hour_mean) for k, v in raw_hour_weight_map.items()}
    hour_weight_map = shrink_late_hour_weight(raw_hour_weight_map, hour_base, target_hour=23, anchor_hour=22)
    return month_weight_map, hour_weight_map


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
    return out.fillna(0)


def prepare_split_frames(
    df: pd.DataFrame,
    base_df: pd.DataFrame,
    month_weight_map: dict[int, float],
    hour_weight_map: dict[int, float],
) -> dict[str, pd.DataFrame]:
    processed = {}
    for split_name in ["train", "valid", "test"]:
        part = df[df["split"] == split_name].copy()
        processed[split_name] = attach_pattern_features(part, base_df, month_weight_map, hour_weight_map)
    return processed


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
) -> dict[str, list[str]]:
    pruned_map: dict[str, list[str]] = {}
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
                        candidate = other
                    else:
                        dropped.add(other)
            if candidate not in dropped and candidate not in kept:
                kept.append(candidate)
        pruned_map[model_name] = kept
    return pruned_map


def fit_best_ridge_model(processed_splits: dict[str, pd.DataFrame], columns: list[str]) -> tuple[float, Pipeline]:
    best_alpha = 0.0
    best_model: Pipeline | None = None
    best_valid_rmse = math.inf

    x_train = processed_splits["train"][columns]
    y_train = processed_splits["train"][TARGET]
    x_valid = processed_splits["valid"][columns]
    y_valid = processed_splits["valid"][TARGET]

    for alpha in ALPHA_GRID:
        model = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=alpha))])
        model.fit(x_train, y_train)
        valid_pred = non_negative_only(model.predict(x_valid))
        valid_pred = enforce_operating_hours(processed_splits["valid"], valid_pred)
        metrics = calc_metrics(y_valid, valid_pred)
        if metrics["rmse"] < best_valid_rmse:
            best_valid_rmse = metrics["rmse"]
            best_alpha = alpha
            best_model = model

    if best_model is None:
        raise RuntimeError("Failed to fit Ridge model.")
    return best_alpha, best_model


def add_model_predictions(processed_splits: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    feature_map = prune_correlated_features(processed_splits["train"], feature_sets(), threshold=0.9)
    metrics_rows = []

    for model_name in ["weighted_core", "weighted_extended"]:
        columns = feature_map[model_name]
        alpha, model = fit_best_ridge_model(processed_splits, columns)
        for split_name in ["train", "valid", "test"]:
            preds = non_negative_only(model.predict(processed_splits[split_name][columns]))
            preds = enforce_operating_hours(processed_splits[split_name], preds)
            processed_splits[split_name][f"{model_name}_prediction"] = preds
            metrics_rows.append(
                {
                    "model_name": model_name,
                    "alpha": alpha,
                    "split": split_name,
                    **calc_metrics(processed_splits[split_name][TARGET], preds),
                }
            )

    weather_only_columns = [
        "base_value",
        "month_weight",
        "hour_weight",
        "pattern_prior",
        "corrected_pattern_prior",
        "day_type_offday",
        "hour_sin",
        "hour_cos",
        "month_sin",
        "month_cos",
        "is_holiday",
        "is_long_weekend",
        *WEATHER_FEATURE_COLUMNS,
        "weather_feature_available",
    ]
    weather_only_map = prune_correlated_features(
        processed_splits["train"],
        {"weather_only_extended": weather_only_columns},
        threshold=0.9,
    )
    weather_only_columns = weather_only_map["weather_only_extended"]
    weather_alpha, weather_model = fit_best_ridge_model(processed_splits, weather_only_columns)
    for split_name in ["train", "valid", "test"]:
        preds = non_negative_only(weather_model.predict(processed_splits[split_name][weather_only_columns]))
        preds = enforce_operating_hours(processed_splits[split_name], preds)
        processed_splits[split_name]["weather_only_extended_prediction"] = preds
        metrics_rows.append(
            {
                "model_name": "weather_only_extended",
                "alpha": weather_alpha,
                "split": split_name,
                **calc_metrics(processed_splits[split_name][TARGET], preds),
            }
        )

    return processed_splits, pd.DataFrame(metrics_rows)


def build_monthly_mean_frame(processed_splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    full_df = pd.concat(
        [processed_splits["train"], processed_splits["valid"], processed_splits["test"]],
        ignore_index=True,
    ).sort_values("datetime")
    monthly = (
        full_df.assign(month_start=full_df["datetime"].dt.to_period("M").dt.to_timestamp())
        .groupby("month_start", as_index=False)[
            [
                TARGET,
                "weighted_core_prediction",
                "weighted_extended_prediction",
                "weather_only_extended_prediction",
            ]
        ]
        .mean()
    )
    return monthly


def render_monthly_chart(monthly: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(16, 6))
    ax.plot(monthly["month_start"], monthly[TARGET], label="actual", linewidth=2.5, color="#1f4e79")
    ax.plot(
        monthly["month_start"],
        monthly["weighted_core_prediction"],
        label="weighted_core",
        linestyle="--",
        linewidth=2.0,
        color="#d97a04",
    )
    ax.plot(
        monthly["month_start"],
        monthly["weighted_extended_prediction"],
        label="weighted_extended",
        linestyle="-.",
        linewidth=2.0,
        color="#2e8b57",
    )
    ax.plot(
        monthly["month_start"],
        monthly["weather_only_extended_prediction"],
        label="weather_only_extended",
        linestyle=":",
        linewidth=2.3,
        color="#54A24B",
    )

    ax.set_title("Nanji Monthly Mean Comparison (2022-2025)")
    ax.set_xlabel("month")
    ax.set_ylabel(TARGET)
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.tick_params(axis="x", rotation=45)
    ax.grid(axis="y", alpha=0.2, linestyle="--")
    ax.legend(frameon=True, ncol=2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_dataset()
    train_df = df[df["split"] == "train"].copy()
    base_df = fit_day_type_hour_models(train_df, TARGET)
    month_weight_map, hour_weight_map = build_weight_maps(train_df, base_df, TARGET)
    processed_splits = prepare_split_frames(df, base_df, month_weight_map, hour_weight_map)
    processed_splits, metrics_df = add_model_predictions(processed_splits)

    monthly = build_monthly_mean_frame(processed_splits)
    png_path = OUTPUT_DIR / "nanji_monthly_mean_comparison_2022_2025.png"
    csv_path = OUTPUT_DIR / "nanji_monthly_mean_comparison_2022_2025.csv"
    metrics_path = OUTPUT_DIR / "nanji_monthly_mean_comparison_2022_2025_metrics.csv"

    render_monthly_chart(monthly, png_path)
    monthly.to_csv(csv_path, index=False, encoding="utf-8-sig")
    metrics_df.sort_values(["split", "model_name"]).to_csv(metrics_path, index=False, encoding="utf-8-sig")

    print(f"saved chart: {png_path}")
    print(f"saved monthly data: {csv_path}")
    print(f"saved metrics: {metrics_path}")


if __name__ == "__main__":
    main()
