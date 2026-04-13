from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
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
import matplotlib.pyplot as plt


TARGET = "estimated_active_cars_change"
ALPHA_GRID = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
DAY_TYPE_ORDER = ["weekday", "offday"]
TOTAL_CAPACITY = 618.0
NOON_FREE_SPACES = 370.0
NOON_OCCUPIED = TOTAL_CAPACITY - NOON_FREE_SPACES
ANCHOR_HOUR = 12
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
WEATHER_ONLY_COLUMNS = [
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


def non_negative_only(values: np.ndarray) -> np.ndarray:
    return np.asarray(values, dtype=float)


def enforce_operating_hours(frame: pd.DataFrame, preds: np.ndarray) -> np.ndarray:
    adjusted = np.asarray(preds, dtype=float).copy()
    adjusted[~frame["hour"].isin(OPERATING_HOURS).to_numpy()] = 0.0
    return adjusted


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


def build_weight_maps(all_df: pd.DataFrame, base_df: pd.DataFrame, target: str) -> tuple[dict[int, float], dict[int, float]]:
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
    hour_weight_map = shrink_late_hour_weight(raw_hour_weight_map, hour_base)
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


def fit_best_ridge_model(train_frame: pd.DataFrame, valid_frame: pd.DataFrame, columns: list[str]) -> tuple[float, Pipeline]:
    best_alpha = 0.0
    best_model: Pipeline | None = None
    best_valid_rmse = math.inf

    for alpha in ALPHA_GRID:
        model = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge(alpha=alpha))])
        model.fit(train_frame[columns], train_frame[TARGET])
        preds = non_negative_only(model.predict(valid_frame[columns]))
        preds = enforce_operating_hours(valid_frame, preds)
        rmse = float(np.sqrt(np.mean((valid_frame[TARGET].to_numpy(dtype=float) - preds) ** 2)))
        if rmse < best_valid_rmse:
            best_valid_rmse = rmse
            best_alpha = alpha
            best_model = model

    if best_model is None:
        raise RuntimeError("Failed to fit weather_only_extended.")
    return best_alpha, best_model


def reconstruct_level_curve(summary: pd.DataFrame, anchor_hour: int, anchor_level: float) -> pd.DataFrame:
    out = summary.copy().sort_values("hour").reset_index(drop=True)
    levels = {}
    levels[anchor_hour] = anchor_level

    for hour in range(anchor_hour + 1, 24):
        prev_hour = hour - 1
        change_at_hour = float(out.loc[out["hour"] == hour, "prediction"].iloc[0])
        levels[hour] = levels[prev_hour] + change_at_hour

    for hour in range(anchor_hour - 1, -1, -1):
        next_hour = hour + 1
        change_at_next = float(out.loc[out["hour"] == next_hour, "prediction"].iloc[0])
        levels[hour] = levels[next_hour] - change_at_next

    out["predicted_occupied_cars"] = out["hour"].map(levels).astype(float)
    out.loc[~out["hour"].isin(OPERATING_HOURS), "predicted_occupied_cars"] = 0.0
    out["predicted_occupied_cars"] = out["predicted_occupied_cars"].clip(lower=0, upper=TOTAL_CAPACITY)
    out["predicted_free_spaces"] = (TOTAL_CAPACITY - out["predicted_occupied_cars"]).clip(lower=0, upper=TOTAL_CAPACITY)
    out["predicted_occupancy_rate"] = out["predicted_occupied_cars"] / TOTAL_CAPACITY * 100.0
    return out


def render_chart(curve_df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, axes = plt.subplots(2, 1, figsize=(13, 9), sharex=True, height_ratios=[1.4, 1.0])

    axes[0].plot(
        curve_df["hour"],
        curve_df["predicted_occupied_cars"],
        color="#1f4e79",
        linewidth=2.5,
        marker="o",
        label="Predicted occupied cars",
    )
    axes[0].plot(
        curve_df["hour"],
        curve_df["predicted_free_spaces"],
        color="#2e8b57",
        linewidth=2.0,
        marker="s",
        linestyle="--",
        label="Predicted free spaces",
    )
    axes[0].axhline(TOTAL_CAPACITY, color="gray", linestyle=":", linewidth=1.2, label="Total capacity")
    axes[0].scatter([ANCHOR_HOUR], [NOON_OCCUPIED], color="#d97a04", s=80, zorder=5, label="Anchor at 12:00")
    axes[0].set_title("April Weekday Parking Level Curve from Weather-Only Model")
    axes[0].set_ylabel("cars")
    axes[0].grid(axis="y", alpha=0.2, linestyle="--")
    axes[0].legend(frameon=True, ncol=2)

    axes[1].bar(curve_df["hour"], curve_df["prediction"], color="#7a4fb0", alpha=0.85)
    axes[1].axhline(0.0, color="gray", linestyle="--", linewidth=1.1)
    axes[1].set_title("Hourly Predicted Change")
    axes[1].set_xlabel("hour")
    axes[1].set_ylabel("change")
    axes[1].set_xticks(range(24))
    axes[1].grid(axis="y", alpha=0.2, linestyle="--")

    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    df = load_dataset()
    train_df = df[df["split"] == "train"].copy()
    base_df = fit_day_type_hour_models(train_df, TARGET)
    month_weight_map, hour_weight_map = build_weight_maps(train_df, base_df, TARGET)

    processed = {}
    for split_name in ["train", "valid", "test"]:
        processed[split_name] = attach_pattern_features(df[df["split"] == split_name].copy(), base_df, month_weight_map, hour_weight_map)

    columns = prune_correlated_features(processed["train"], {"weather_only_extended": WEATHER_ONLY_COLUMNS})["weather_only_extended"]
    alpha, model = fit_best_ridge_model(processed["train"], processed["valid"], columns)

    full_df = attach_pattern_features(df.copy(), base_df, month_weight_map, hour_weight_map)
    full_df["prediction"] = enforce_operating_hours(full_df, non_negative_only(model.predict(full_df[columns])))

    april_weekday = full_df[(full_df["month"] == 4) & (full_df["day_type"] == "weekday")].copy()
    summary = (
        april_weekday.groupby("hour", as_index=False)[["prediction", TARGET]]
        .mean()
        .sort_values("hour")
        .reset_index(drop=True)
    )
    curve_df = reconstruct_level_curve(summary, anchor_hour=ANCHOR_HOUR, anchor_level=NOON_OCCUPIED)

    png_path = OUTPUT_DIR / "nanji_april_weekday_level_curve.png"
    csv_path = OUTPUT_DIR / "nanji_april_weekday_level_curve.csv"
    render_chart(curve_df, png_path)
    curve_df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    print(f"alpha: {alpha}")
    print(f"anchor occupied cars at 12:00 = {NOON_OCCUPIED:.0f}")
    print(f"saved chart: {png_path}")
    print(f"saved curve data: {csv_path}")


if __name__ == "__main__":
    main()
