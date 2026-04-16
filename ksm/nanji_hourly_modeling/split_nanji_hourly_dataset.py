from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
HOURLY_DATASET_PATH = ROOT / "ksm" / "nanji_hourly_modeling" / "nanji_hourly_model_dataset_2020_2026.csv"
RAW_DAILY_PATH = ROOT / "hmw" / "Data" / "한강공원 주차장 일별 이용 현황.csv"
OUTPUT_DIR = ROOT / "ksm" / "nanji_hourly_modeling"


def load_daily_parking_groups() -> pd.DataFrame:
    daily_df = pd.read_csv(RAW_DAILY_PATH, encoding="cp949")
    nanji_df = daily_df[daily_df["주차장명"].astype(str).str.contains("난지", na=False)].copy()
    nanji_df["date"] = pd.to_datetime(nanji_df["날짜"]).dt.strftime("%Y-%m-%d")
    nanji_df = nanji_df.rename(columns={"주차장명": "parking_group"})

    # Each date should map to a single source parking-group label.
    mapping_df = nanji_df[["date", "parking_group"]].drop_duplicates()
    duplicate_dates = mapping_df["date"].duplicated(keep=False)
    if duplicate_dates.any():
        duplicates = mapping_df.loc[duplicate_dates].sort_values("date")
        raise ValueError(
            "A single date maps to multiple parking groups in the raw daily source:\n"
            f"{duplicates.to_string(index=False)}"
        )

    return mapping_df


def main() -> None:
    hourly_df = pd.read_csv(HOURLY_DATASET_PATH)
    hourly_df["date"] = pd.to_datetime(hourly_df["date"]).dt.strftime("%Y-%m-%d")

    parking_group_map = load_daily_parking_groups()
    merged_df = hourly_df.merge(parking_group_map, on="date", how="left")

    missing_group_df = merged_df[merged_df["parking_group"].isna()]
    if not missing_group_df.empty:
        missing_dates = missing_group_df["date"].drop_duplicates().tolist()
        raise ValueError(
            "Some hourly dates could not be mapped back to a parking group: "
            f"{missing_dates[:10]}"
        )

    annotated_path = OUTPUT_DIR / "nanji_hourly_model_dataset_2020_2026_with_parking_group.csv"
    merged_df.to_csv(annotated_path, index=False)

    for parking_group, group_df in merged_df.groupby("parking_group", sort=True):
        safe_name = parking_group.replace(",", "_")
        output_path = OUTPUT_DIR / f"nanji_hourly_model_dataset_{safe_name}.csv"
        group_df.to_csv(output_path, index=False)
        print(
            f"saved {output_path.name}: rows={len(group_df)}, "
            f"date_range={group_df['date'].min()}~{group_df['date'].max()}"
        )

    print(f"saved {annotated_path.name}: rows={len(merged_df)}")


if __name__ == "__main__":
    main()
