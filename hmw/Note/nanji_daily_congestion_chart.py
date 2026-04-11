from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parent
PREDICTION_PATH = ROOT / "nanji_outputs" / "nanji_test_predictions.csv"
DEFAULT_MODEL_COLUMN = "weather_only_final_prediction"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create an hourly congestion chart for one day from the final Ridge prediction. "
            "If total capacity is given, the chart is rendered as occupancy percentage (0~100). "
            "If total capacity is omitted, a relative congestion index is rendered instead."
        )
    )
    parser.add_argument(
        "--date",
        default="2025-09-27",
        help="Target date in YYYY-MM-DD format. Default: 2025-09-27",
    )
    parser.add_argument(
        "--total-capacity",
        type=float,
        default=None,
        help="Total parking capacity. Required for true occupancy percentage.",
    )
    parser.add_argument(
        "--model-col",
        default=DEFAULT_MODEL_COLUMN,
        help=f"Prediction column to use. Default: {DEFAULT_MODEL_COLUMN}",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output image path. Saved under nanji_outputs by default.",
    )
    return parser.parse_args()


def build_daily_frame(date_str: str, model_col: str) -> pd.DataFrame:
    if not PREDICTION_PATH.exists():
        raise FileNotFoundError(f"Prediction file not found: {PREDICTION_PATH}")

    df = pd.read_csv(PREDICTION_PATH, parse_dates=["datetime"])
    if model_col not in df.columns:
        raise KeyError(f"Column not found: {model_col}")

    target_date = pd.to_datetime(date_str).date()
    daily = df[df["datetime"].dt.date == target_date].copy()
    if daily.empty:
        raise ValueError(f"No prediction rows found for date: {date_str}")

    daily["hour"] = daily["datetime"].dt.hour
    return daily.sort_values("datetime").reset_index(drop=True)


def add_congestion_columns(daily: pd.DataFrame, model_col: str, total_capacity: float | None) -> tuple[pd.DataFrame, str, str]:
    result = daily.copy()

    if total_capacity is not None:
        result["predicted_congestion"] = (result[model_col] / total_capacity * 100).clip(lower=0, upper=100)
        result["actual_congestion"] = (result["estimated_active_cars"] / total_capacity * 100).clip(lower=0, upper=100)
        y_label = "Congestion / Occupancy (%)"
        subtitle = f"Total capacity = {total_capacity:g}"
    else:
        peak_value = max(float(result[model_col].max()), 1.0)
        result["predicted_congestion"] = result[model_col] / peak_value * 100
        result["actual_congestion"] = result["estimated_active_cars"] / peak_value * 100
        y_label = "Relative Congestion Index (daily max prediction = 100)"
        subtitle = "Total capacity not provided, so this is a relative index"

    return result, y_label, subtitle


def make_output_path(date_str: str, total_capacity: float | None, explicit_output: str | None) -> Path:
    if explicit_output:
        return Path(explicit_output)

    mode = "occupancy" if total_capacity is not None else "relative"
    return ROOT / "nanji_outputs" / f"nanji_daily_congestion_{date_str}_{mode}.png"


def render_chart(daily: pd.DataFrame, date_str: str, y_label: str, subtitle: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        daily["hour"],
        daily["predicted_congestion"],
        marker="o",
        linewidth=2.4,
        color="#1f4e79",
        label="Predicted congestion",
    )
    ax.plot(
        daily["hour"],
        daily["actual_congestion"],
        marker="s",
        linewidth=1.8,
        linestyle="--",
        color="#d95f02",
        alpha=0.85,
        label="Actual reference",
    )
    ax.fill_between(
        daily["hour"],
        daily["predicted_congestion"],
        color="#1f4e79",
        alpha=0.10,
    )

    ax.set_title(f"Nanji Parking Hourly Congestion on {date_str}\n{subtitle}")
    ax.set_xlabel("Hour")
    ax.set_ylabel(y_label)
    ax.set_xticks(range(24))
    ax.set_ylim(0, max(100, float(daily["predicted_congestion"].max()) * 1.08))
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    ax.legend(frameon=True)

    for row in daily.itertuples(index=False):
        ax.text(
            row.hour,
            row.predicted_congestion + 1.2,
            f"{row.predicted_congestion:.1f}",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#1f4e79",
        )

    fig.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    args = parse_args()
    daily = build_daily_frame(args.date, args.model_col)
    daily, y_label, subtitle = add_congestion_columns(daily, args.model_col, args.total_capacity)
    output_path = make_output_path(args.date, args.total_capacity, args.output)
    render_chart(daily, args.date, y_label, subtitle, output_path)

    print(f"saved chart: {output_path}")
    if args.total_capacity is None:
        print("note: total capacity was not provided, so the chart shows a relative congestion index, not true occupancy percentage.")
    else:
        print("note: the chart shows occupancy percentage based on the provided total capacity.")


if __name__ == "__main__":
    main()
