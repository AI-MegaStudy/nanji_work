from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data"
INPUT_PATH = DATA_DIR / "nanji_individual_realtime_history.csv"
OUTPUT_PATH = DATA_DIR / "nanji_individual_hourly_dataset.csv"


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_PATH}")

    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    if "collected_at" not in df.columns or "PKLT_NM" not in df.columns:
        raise ValueError("Input must include collected_at and PKLT_NM columns.")

    df["collected_at"] = pd.to_datetime(df["collected_at"])
    df["hour"] = df["collected_at"].dt.floor("h")

    numeric_columns = {
        "NOW_PRK_VHCL_CNT": "mean",
        "TPKCT": "max",
    }
    existing_numeric = {col: agg for col, agg in numeric_columns.items() if col in df.columns}

    hourly_df = (
        df.groupby(["PKLT_NM", "hour"], dropna=False)
        .agg(
            samples=("collected_at", "size"),
            **{column: (column, agg) for column, agg in existing_numeric.items()},
        )
        .reset_index()
        .rename(
            columns={
                "PKLT_NM": "parking_name",
                "NOW_PRK_VHCL_CNT": "current_parking_mean",
                "TPKCT": "capacity",
            }
        )
    )

    if "capacity" in hourly_df.columns and "current_parking_mean" in hourly_df.columns:
        hourly_df["available_spaces_est"] = hourly_df["capacity"] - hourly_df["current_parking_mean"]

    hourly_df["date"] = hourly_df["hour"].dt.date.astype(str)
    hourly_df["hour_of_day"] = hourly_df["hour"].dt.hour
    hourly_df["day_of_week"] = hourly_df["hour"].dt.day_name()
    hourly_df["is_weekend"] = hourly_df["hour"].dt.dayofweek >= 5

    hourly_df = hourly_df.sort_values(["parking_name", "hour"]).reset_index(drop=True)
    hourly_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(f"saved {OUTPUT_PATH}: rows={len(hourly_df)}")
    print(f"parking lots={hourly_df['parking_name'].nunique()}")


if __name__ == "__main__":
    main()
