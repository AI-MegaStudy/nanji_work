from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI(title="Nanji Prediction API Example")


MODEL_INFO = {
    "model_name": "weather_only_extended_final",
    "r2": 0.7655,
    "rmse": 55.0747,
    "mae": 27.9298,
    "evaluated_on": "test",
}


class PredictionRequest(BaseModel):
    parking_zone: str = "nanji"
    target_time: datetime
    temperature_2m: float
    relative_humidity_2m: float
    weather_code: int
    wind_gusts_10m: float
    total_capacity: int | None = None


def predict_active_cars(_: PredictionRequest) -> float:
    # 실제 운영에서는 학습된 Ridge 모델을 로드한 뒤
    # 입력 feature를 만들어 model.predict(...)를 호출합니다.
    return 412.3


def build_hourly_data(request: PredictionRequest, generated_at: datetime) -> list[dict]:
    base_time = request.target_time.astimezone(ZoneInfo("Asia/Seoul")).replace(minute=0, second=0, microsecond=0)
    hourly_points: list[dict] = []

    # 예시용 더미 곡선입니다. 실제 운영에서는 각 시점별 feature를 만들어
    # 모델을 반복 호출한 뒤 predicted_active_cars를 채우면 됩니다.
    dummy_active_cars = [285.0, 338.0, 412.3, 468.0, 441.0, 376.0]

    for idx, active_cars in enumerate(dummy_active_cars):
        point_time = base_time + timedelta(hours=idx)
        # 앱 차트에서는 첫 포인트를 현재 기준값, 이후 포인트를 예측값으로
        # 구분해서 그리는 경우가 많으므로 예시도 같은 형태로 둡니다.
        is_prediction = idx != 0

        point = {
            "time": point_time.strftime("%H:%M"),
            "predicted_active_cars": round(active_cars, 1),
            "is_prediction": is_prediction,
        }

        if request.total_capacity is not None and request.total_capacity > 0:
            point["predicted_congestion_percent"] = round(min(active_cars / request.total_capacity * 100, 100), 1)
            point["predicted_available_spaces"] = int(round(max(request.total_capacity - active_cars, 0)))

        hourly_points.append(point)

    return hourly_points


def build_summary(hourly_data: list[dict]) -> dict:
    peak_point = max(hourly_data, key=lambda item: item["predicted_active_cars"])
    lowest_point = min(hourly_data, key=lambda item: item["predicted_active_cars"])

    return {
        "peak_time": peak_point["time"],
        "recommended_time_window": f"{lowest_point['time']} around",
    }


@app.post("/predict")
def predict(request: PredictionRequest) -> dict:
    generated_at = datetime.now(ZoneInfo("Asia/Seoul"))
    predicted_active_cars = predict_active_cars(request)
    hourly_data = build_hourly_data(request, generated_at)
    summary = build_summary(hourly_data)

    response = {
        "parking_zone": request.parking_zone,
        "target_time": request.target_time.astimezone(ZoneInfo("Asia/Seoul")).isoformat(),
        "generated_at": generated_at.isoformat(),
        "predicted_active_cars": round(predicted_active_cars, 1),
        "hourly_data": hourly_data,
        "peak_time": summary["peak_time"],
        "recommended_time_window": summary["recommended_time_window"],
        "model_info": MODEL_INFO,
    }

    if request.total_capacity is not None and request.total_capacity > 0:
        congestion_percent = min(predicted_active_cars / request.total_capacity * 100, 100)
        available_spaces = max(request.total_capacity - predicted_active_cars, 0)
        response["predicted_congestion_percent"] = round(congestion_percent, 1)
        response["predicted_available_spaces"] = int(round(available_spaces))

    return response


if __name__ == "__main__":
    example_request = PredictionRequest(
        parking_zone="nanji",
        target_time=datetime(2026, 4, 11, 15, 0, tzinfo=ZoneInfo("Asia/Seoul")),
        temperature_2m=21.4,
        relative_humidity_2m=54.0,
        weather_code=1,
        wind_gusts_10m=4.8,
        total_capacity=800,
    )
    print(predict(example_request))
