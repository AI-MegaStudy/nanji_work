# Open-Meteo 연도별 CSV 수집 스크립트
# 파일 실행하면 ose/Data 내 연도별 csv 파일 저장되어 내용 확인 가능합니다.

import csv
import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "Data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LATITUDE = 37.5686
LONGITUDE = 126.8789
TIMEZONE = "Asia/Seoul"
TIMEOUT_SECONDS = 30

HOURLY_VARIABLES = [
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
    "visibility",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "shortwave_radiation",
    "direct_radiation",
    "diffuse_radiation",
    "sunshine_duration",
]

WEATHER_CODE_LABELS = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분적으로 흐림",
    3: "흐림",
    45: "안개",
    48: "착빙 안개",
    51: "약한 이슬비",
    53: "보통 이슬비",
    55: "강한 이슬비",
    56: "약한 어는 이슬비",
    57: "강한 어는 이슬비",
    61: "약한 비",
    63: "보통 비",
    65: "강한 비",
    66: "약한 어는 비",
    67: "강한 어는 비",
    71: "약한 눈",
    73: "보통 눈",
    75: "강한 눈",
    77: "싸락눈",
    80: "약한 소나기",
    81: "보통 소나기",
    82: "강한 소나기",
    85: "약한 눈 소나기",
    86: "강한 눈 소나기",
    95: "뇌우",
    96: "약한 우박 동반 뇌우",
    99: "강한 우박 동반 뇌우",
}


def fetch_open_meteo_year(year: int, start_date: str, end_date: str) -> Dict:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": TIMEZONE,
    }
    url = "https://archive-api.open-meteo.com/v1/archive?{0}".format(
        urlencode(params)
    )
    request = Request(url, headers={"User-Agent": "nanji-open-meteo-export/1.0"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if "hourly" not in payload or "time" not in payload["hourly"]:
        raise ValueError(
            "{0}년 응답에 hourly 데이터가 없습니다: {1}".format(year, payload)
        )

    return payload


def build_rows(hourly: Dict[str, List]) -> Iterable[Dict[str, object]]:
    times = hourly["time"]
    for index, timestamp in enumerate(times):
        weather_code = hourly.get("weather_code", [])
        weather_code_value = weather_code[index] if index < len(weather_code) else None
        row = {
            "datetime": timestamp,
            "date": timestamp[:10],
            "hour": int(timestamp[11:13]),
            "year": int(timestamp[:4]),
            "month": int(timestamp[5:7]),
            "day": int(timestamp[8:10]),
            "weather_code_label": WEATHER_CODE_LABELS.get(
                weather_code_value,
                "미정의 코드",
            )
            if weather_code_value is not None
            else "",
        }
        for column in HOURLY_VARIABLES:
            values = hourly.get(column, [])
            row[column] = values[index] if index < len(values) else None
        yield row


def save_year_csv(year: int, rows: Iterable[Dict[str, object]]) -> Path:
    output_path = OUTPUT_DIR / "open_meteo_nanji_{0}.csv".format(year)
    fieldnames = [
        "datetime",
        "date",
        "hour",
        "year",
        "month",
        "day",
        "weather_code_label",
    ] + HOURLY_VARIABLES

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return output_path


def year_date_range(year: int, today: date) -> Dict[str, str]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)

    if year == 2020:
        start = date(2020, 1, 1)
    if year == today.year:
        end = today

    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


def main() -> None:
    today = date.today()

    for year in range(2020, 2027):
        range_info = year_date_range(year, today)
        payload = fetch_open_meteo_year(
            year=year,
            start_date=range_info["start_date"],
            end_date=range_info["end_date"],
        )
        output_path = save_year_csv(year, build_rows(payload["hourly"]))
        print(
            "{0} 저장 완료: {1} ({2} ~ {3})".format(
                year,
                output_path,
                range_info["start_date"],
                range_info["end_date"],
            )
        )


if __name__ == "__main__":
    main()
