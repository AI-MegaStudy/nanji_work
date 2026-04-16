from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "Data"
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_PATH = DATA_DIR / "nanji_individual_realtime_history.csv"
API_URL_TEMPLATE = "http://openapi.seoul.go.kr:8088/{api_key}/json/GetParkingInfo/1/1000/"


def fetch_nanji_rows(api_key: str) -> pd.DataFrame:
    response = requests.get(API_URL_TEMPLATE.format(api_key=api_key), timeout=30)
    response.raise_for_status()
    payload = response.json()

    rows = payload.get("GetParkingInfo", {}).get("row", [])
    if not rows:
        raise ValueError("No parking rows returned from GetParkingInfo API.")

    df = pd.DataFrame(rows)
    nanji_df = df[df["PKLT_NM"].astype(str).str.contains("난지", na=False)].copy()
    if nanji_df.empty:
        raise ValueError("No Nanji parking rows found in the API response.")

    nanji_df["collected_at"] = datetime.now().isoformat(timespec="seconds")
    return nanji_df


def append_history(snapshot_df: pd.DataFrame, output_path: Path) -> None:
    if output_path.exists():
        history_df = pd.read_csv(output_path, encoding="utf-8-sig")
        combined_df = pd.concat([history_df, snapshot_df], ignore_index=True)
    else:
        combined_df = snapshot_df.copy()

    combined_df.to_csv(output_path, index=False, encoding="utf-8-sig")


def main() -> None:
    api_key = os.getenv("SEOUL_OPEN_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "Set SEOUL_OPEN_API_KEY before running this script."
        )

    snapshot_df = fetch_nanji_rows(api_key)
    append_history(snapshot_df, OUTPUT_PATH)

    print(f"saved {len(snapshot_df)} Nanji rows to {OUTPUT_PATH}")
    print("parking lots:", ", ".join(sorted(snapshot_df["PKLT_NM"].astype(str).unique())))


if __name__ == "__main__":
    main()
