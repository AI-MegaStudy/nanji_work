from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(title="Nanji Prediction API Example")


KST = ZoneInfo("Asia/Seoul")
NANJI_LATITUDE = 37.5686
NANJI_LONGITUDE = 126.8789
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_SECONDS = 10

MODEL_INFO = {
    "model_name": "weather_only_extended_final_change",
    "target": "estimated_active_cars_change",
    "serving_note": "current_actual_cars + predicted_change 누적 방식 예시",
}

WEATHER_FEATURE_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "weather_code",
    "wind_gusts_10m",
]


class PredictionRequest(BaseModel):
    parking_zone: str = "nanji"
    current_time: datetime
    current_actual_cars: float = Field(..., ge=0)
    horizon_hours: int = Field(default=6, ge=1, le=24)
    total_capacity: int | None = Field(default=None, gt=0)


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def fetch_hourly_forecast(base_time: datetime, horizon_hours: int) -> list[dict[str, Any]]:
    forecast_days = max(1, ((horizon_hours + 23) // 24) + 1)
    params = {
        "latitude": NANJI_LATITUDE,
        "longitude": NANJI_LONGITUDE,
        "timezone": "Asia/Seoul",
        "forecast_days": forecast_days,
        "hourly": ",".join(WEATHER_FEATURE_COLUMNS),
    }
    url = f"{OPEN_METEO_FORECAST_URL}?{urlencode(params)}"
    request = Request(url, headers={"User-Agent": "nanji-forecast-api-example/1.0"})

    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"weather api http error: {exc.code}") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail=f"weather api connection error: {exc.reason}") from exc

    import json

    data = json.loads(payload)
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    if not times:
        raise HTTPException(status_code=502, detail="weather api returned no hourly data")

    forecast_rows: list[dict[str, Any]] = []
    target_start = base_time.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    target_end = target_start + timedelta(hours=horizon_hours - 1)

    for idx, time_str in enumerate(times):
        point_time = datetime.fromisoformat(time_str).replace(tzinfo=KST)
        if point_time < target_start or point_time > target_end:
            continue

        row = {"time": point_time}
        for column in WEATHER_FEATURE_COLUMNS:
            values = hourly.get(column, [])
            row[column] = values[idx] if idx < len(values) else None
        forecast_rows.append(row)

    if len(forecast_rows) < horizon_hours:
        raise HTTPException(
            status_code=502,
            detail=f"weather api returned {len(forecast_rows)} rows, expected at least {horizon_hours}",
        )

    return forecast_rows[:horizon_hours]


def build_calendar_features(point_time: datetime) -> dict[str, Any]:
    hour = point_time.hour
    month = point_time.month
    is_weekend = int(point_time.weekday() >= 5)
    return {
        "hour": hour,
        "month": month,
        "day_type_offday": is_weekend,
        "is_holiday": 0,
        "hour_sin": math.sin(2 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2 * math.pi * hour / 24.0),
        "month_sin": math.sin(2 * math.pi * month / 12.0),
        "month_cos": math.cos(2 * math.pi * month / 12.0),
    }


def build_pattern_features(point_time: datetime) -> dict[str, float]:
    hour = point_time.hour

    # 예시용 패턴값입니다. 실제 운영에서는 학습 당시 저장한
    # base_value / month_weight / hour_weight 계산 결과를 불러와 사용합니다.
    base_value = max(0.0, 220.0 - abs(hour - 15) * 18.0)
    month_weight = 1.08 if point_time.month in [4, 5, 9, 10] else 0.96
    hour_weight = 1.15 if 13 <= hour <= 17 else 0.92
    pattern_prior = base_value * month_weight

    return {
        "base_value": round(base_value, 4),
        "month_weight": round(month_weight, 4),
        "hour_weight": round(hour_weight, 4),
        "pattern_prior": round(pattern_prior, 4),
        "corrected_pattern_prior": round(pattern_prior * hour_weight, 4),
    }


def build_model_features(point_time: datetime, weather_row: dict[str, Any]) -> dict[str, Any]:
    features = {}
    features.update(build_calendar_features(point_time))
    features.update(build_pattern_features(point_time))

    for column in WEATHER_FEATURE_COLUMNS:
        value = weather_row.get(column)
        if value is None:
            raise HTTPException(status_code=502, detail=f"missing weather field: {column}")
        features[column] = value

    return features


def predict_change(features: dict[str, Any]) -> float:
    # 실제 운영에서는 저장된 Ridge 모델을 로드하고
    # 아래 feature 순서에 맞춰 model.predict(...)를 호출하면 됩니다.
    change = (
        0.055 * features["pattern_prior"]
        + 0.35 * features["temperature_2m"]
        - 0.08 * features["relative_humidity_2m"]
        + 0.6 * features["day_type_offday"]
        - 0.45 * features["wind_gusts_10m"]
        - 0.03 * abs(features["hour"] - 15) * 10
    )
    if int(features["weather_code"]) >= 60:
        change -= 12.0
    return round(change, 2)


def build_forecast_points(request: PredictionRequest) -> list[dict[str, Any]]:
    current_time = to_kst(request.current_time)
    forecast_rows = fetch_hourly_forecast(current_time, request.horizon_hours)

    points: list[dict[str, Any]] = []
    running_cars = float(request.current_actual_cars)

    for weather_row in forecast_rows:
        point_time = weather_row["time"]
        features = build_model_features(point_time, weather_row)
        predicted_change = predict_change(features)
        running_cars = max(running_cars + predicted_change, 0.0)

        point = {
            "time": point_time.isoformat(),
            "predicted_change": round(predicted_change, 2),
            "predicted_active_cars": round(running_cars, 1),
            "weather": {
                column: weather_row[column]
                for column in WEATHER_FEATURE_COLUMNS
            },
        }

        if request.total_capacity is not None:
            point["predicted_available_spaces"] = int(round(max(request.total_capacity - running_cars, 0)))
            point["predicted_congestion_percent"] = round(
                min(running_cars / request.total_capacity * 100, 100),
                1,
            )

        points.append(point)

    return points


def build_today_series(
    current_time: datetime,
    current_actual_cars: float,
    forecast_points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    now_kst = to_kst(current_time).replace(minute=0, second=0, microsecond=0)
    start_of_day = now_kst.replace(hour=0)

    forecast_map = {
        datetime.fromisoformat(point["time"]).replace(minute=0, second=0, microsecond=0): point
        for point in forecast_points
    }

    series: list[dict[str, Any]] = []
    for hour in range(24):
        point_time = start_of_day + timedelta(hours=hour)
        item = {
            "time": point_time.isoformat(),
            "actual_cars": None,
            "predicted_cars": None,
            "is_prediction": point_time >= now_kst,
        }

        if point_time < now_kst:
            item["actual_cars"] = None
        elif point_time == now_kst:
            item["actual_cars"] = round(current_actual_cars, 1)
            item["predicted_cars"] = round(current_actual_cars, 1)

        if point_time in forecast_map:
            item["predicted_cars"] = forecast_map[point_time]["predicted_active_cars"]

        series.append(item)

    return series


def build_summary(forecast_points: list[dict[str, Any]]) -> dict[str, Any]:
    peak_point = max(forecast_points, key=lambda item: item["predicted_active_cars"])
    quiet_point = min(forecast_points, key=lambda item: item["predicted_active_cars"])

    return {
        "peak_time": peak_point["time"],
        "peak_predicted_active_cars": peak_point["predicted_active_cars"],
        "recommended_time_window": quiet_point["time"],
    }


@app.post("/predict")
def predict(request: PredictionRequest) -> dict[str, Any]:
    generated_at = datetime.now(KST)
    forecast_points = build_forecast_points(request)
    summary = build_summary(forecast_points)
    today_series = build_today_series(
        current_time=request.current_time,
        current_actual_cars=request.current_actual_cars,
        forecast_points=forecast_points,
    )

    response: dict[str, Any] = {
        "parking_zone": request.parking_zone,
        "current_time": to_kst(request.current_time).isoformat(),
        "generated_at": generated_at.isoformat(),
        "current_actual_cars": round(request.current_actual_cars, 1),
        "forecast_hours": request.horizon_hours,
        "predictions": forecast_points,
        "today_series": today_series,
        "peak_time": summary["peak_time"],
        "peak_predicted_active_cars": summary["peak_predicted_active_cars"],
        "recommended_time_window": summary["recommended_time_window"],
        "model_info": MODEL_INFO,
    }

    if request.total_capacity is not None:
        response["total_capacity"] = request.total_capacity

    return response


if __name__ == "__main__":
    example_request = PredictionRequest(
        parking_zone="nanji",
        current_time=datetime(2026, 4, 12, 14, 0, tzinfo=KST),
        current_actual_cars=312,
        horizon_hours=6,
        total_capacity=800,
    )
    print(predict(example_request))
