# 단기예보, 중기예보 수집 스크립트
# 파일 실행하면 ose/weather_outputs 폴더 생성 및 예보 결과 json, md 파일 저장되어 내용 확인 가능합니다.

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# 공통 설정
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / "api_keys.env"
OUTPUT_DIR = BASE_DIR / "weather_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_TYPE = "JSON"
PAGE_NO = "1"
NUM_OF_ROWS = "1000"
TIMEOUT_SECONDS = 15

REGION_NAME = "난지 한강공원"
MID_REGION_NAME = "서울·인천·경기권"

LATITUDE = 37.5686
LONGITUDE = 126.8789
GRID_X = "60"
GRID_Y = "127"

MID_LAND_REG_ID = "11B00000"
MID_TEMP_REG_ID = "11B10101"

SHORT_TERM_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
MID_TERM_BASE_URL = "https://apis.data.go.kr/1360000/MidFcstInfoService"


# 공통 유틸
def load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env_file(ENV_PATH)

SHORT_TERM_SERVICE_KEY = os.getenv("SHORT_TERM_SERVICE_KEY", "").strip()
MID_TERM_SERVICE_KEY = os.getenv("MID_TERM_SERVICE_KEY", "").strip()


def fetch_json(url: str, params: Dict[str, str]) -> Dict:
    request = Request(
        "{0}?{1}".format(url, urlencode(params, doseq=True)),
        headers={"Accept": "application/json", "User-Agent": "weather-checker/1.0"},
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def get_items(payload: Dict) -> List[Dict]:
    return payload.get("response", {}).get("body", {}).get("items", {}).get("item", [])


def get_result(payload: Dict) -> Tuple[str, str]:
    header = payload.get("response", {}).get("header", {})
    return header.get("resultCode", ""), header.get("resultMsg", "")


def require_key(service_key: str, name: str) -> None:
    if not service_key or service_key.startswith("YOUR_"):
        raise ValueError("{0}를 설정하세요.".format(name))


# 파일 저장 함수
def save_json(filename: str, payload: Dict) -> None:
    (OUTPUT_DIR / filename).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_text(filename: str, content: str) -> None:
    (OUTPUT_DIR / filename).write_text(content, encoding="utf-8")


# 단기예보 시각 후보 (최신 날짜 데이터 출력)
def short_candidates(now: Optional[datetime] = None) -> List[Tuple[str, str]]:
    if now is None:
        now = datetime.now()

    base_times = ["0200", "0500", "0800", "1100", "1400", "1700", "2000", "2300"]
    result = []

    for day_offset in range(0, 2):
        day = now - timedelta(days=day_offset)
        date_str = day.strftime("%Y%m%d")
        for base_time in reversed(base_times):
            if day_offset == 0 and base_time > now.strftime("%H%M"):
                continue
            result.append((date_str, base_time))

    return result


# 중기예보 시각 후보 (최신 날짜 데이터 출력)
def mid_candidates(now: Optional[datetime] = None) -> List[str]:
    if now is None:
        now = datetime.now()

    result = []
    for day_offset in range(0, 4):
        day = now - timedelta(days=day_offset)
        date_str = day.strftime("%Y%m%d")
        for hhmm in ["1800", "0600"]:
            tm_fc = "{0}{1}".format(date_str, hhmm)
            if tm_fc <= now.strftime("%Y%m%d%H%M"):
                result.append(tm_fc)

    return result


# 단기예보 해석
def sky_text(sky: str, pty: str) -> str:
    if pty == "1":
        return "비"
    if pty == "2":
        return "비 또는 눈"
    if pty == "3":
        return "눈"
    if pty == "4":
        return "소나기"
    return {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(sky, "알 수 없음")


# 단기예보 md 내용 생성
def short_summary_md(base_date: str, base_time: str, items: List[Dict]) -> str:
    grouped = {}
    for item in items:
        key = "{0} {1}".format(item.get("fcstDate"), item.get("fcstTime"))
        grouped.setdefault(key, {})[item.get("category")] = item.get("fcstValue")

    sorted_keys = sorted(grouped.keys())
    first_key = sorted_keys[0]
    first_values = grouped[first_key]
    first_desc = sky_text(first_values.get("SKY", ""), first_values.get("PTY", "0"))

    lines = [
        "# 단기예보 설명",
        "",
        "지역: {0}".format(REGION_NAME),
        "위도: {0}".format(LATITUDE),
        "경도: {0}".format(LONGITUDE),
        "격자X: {0}".format(GRID_X),
        "격자Y: {0}".format(GRID_Y),
        "기준시각: {0} {1}".format(base_date, base_time),
        "",
        "## item 요소 설명",
        "- 발표일자(baseDate): 예보 발표 날짜",
        "- 발표시각(baseTime): 예보 발표 시각",
        "- 예보일자(fcstDate): 실제 예보 대상 날짜",
        "- 예보시각(fcstTime): 실제 예보 대상 시각",
        "- 예보항목코드(category): 예보 종류 코드",
        "- 예보값(fcstValue): 항목별 예보 값",
        "- 격자X(nx): 기상청 격자 X",
        "- 격자Y(ny): 기상청 격자 Y",
        "",
        "## category 의미",
        "- TMP: 기온",
        "- PCP: 1시간 강수량",
        "- REH: 습도",
        "- WSD: 풍속",
        "- SKY: 하늘상태",
        "- PTY: 강수형태",
        "",
        "## 현재에 가까운 예보 요약",
        "- 시각: {0}".format(first_key),
        "- 설명: {0}".format(first_desc),
        "- 기온: {0}C".format(first_values.get("TMP", "정보없음")),
        "- 강수량: {0}".format(first_values.get("PCP", "정보없음")),
        "- 습도: {0}%".format(first_values.get("REH", "정보없음")),
        "- 풍속: {0}m/s".format(first_values.get("WSD", "정보없음")),
        "",
        "## 시간대별 요약",
    ]

    for key in sorted_keys[:12]:
        values = grouped[key]
        desc = sky_text(values.get("SKY", ""), values.get("PTY", "0"))
        lines.append(
            "- {0}: {1} / {2}C / 강수량 {3} / 습도 {4}% / 풍속 {5}m/s".format(
                key,
                desc,
                values.get("TMP", "정보없음"),
                values.get("PCP", "정보없음"),
                values.get("REH", "정보없음"),
                values.get("WSD", "정보없음"),
            )
        )

    return "\n".join(lines) + "\n"


# 중기예보 해석
def build_mid_day_sentence(day: int, land_item: Dict, temp_item: Dict) -> str:
    min_temp = temp_item.get("taMin{0}".format(day), "정보없음")
    max_temp = temp_item.get("taMax{0}".format(day), "정보없음")

    if day <= 7:
        am_text = land_item.get("wf{0}Am".format(day), "정보없음")
        pm_text = land_item.get("wf{0}Pm".format(day), "정보없음")
        return "{0}일 후: 오전 {1} / 오후 {2} / {3}C ~ {4}C".format(
            day,
            am_text,
            pm_text,
            min_temp,
            max_temp,
        )

    day_text = land_item.get("wf{0}".format(day), "정보없음")
    return "{0}일 후: {1} / {2}C ~ {3}C".format(
        day,
        day_text,
        min_temp,
        max_temp,
    )


# 중기예보 md 내용 생성
def mid_summary_md(tm_fc: str, land_item: Dict, temp_item: Dict) -> str:
    lines = [
        "# 중기예보 설명",
        "",
        "지역: {0}".format(REGION_NAME),
        "권역: {0}".format(MID_REGION_NAME),
        "위도: {0}".format(LATITUDE),
        "경도: {0}".format(LONGITUDE),
        "격자X: {0}".format(GRID_X),
        "격자Y: {0}".format(GRID_Y),
        "발표시각: {0}".format(tm_fc),
        "",
        "## 중기육상예보 요소 설명",
        "- wf4Am~wf7Pm: 4~7일 후 오전/오후 날씨",
        "- wf8~wf10: 8~10일 후 날씨",
        "",
        "## 중기기온예보 요소 설명",
        "- taMin4~taMin10: 4~10일 후 최저기온",
        "- taMax4~taMax10: 4~10일 후 최고기온",
        "",
        "## 날짜별 요약",
    ]

    for day in range(4, 11):
        lines.append("- {0}".format(build_mid_day_sentence(day, land_item, temp_item)))

    return "\n".join(lines) + "\n"


# 단기예보 결과 저장
def run_short() -> None:
    require_key(SHORT_TERM_SERVICE_KEY, "SHORT_TERM_SERVICE_KEY")
    last_error = "NO_DATA"

    for base_date, base_time in short_candidates():
        payload = fetch_json(
            SHORT_TERM_BASE_URL,
            {
                "serviceKey": SHORT_TERM_SERVICE_KEY,
                "pageNo": PAGE_NO,
                "numOfRows": NUM_OF_ROWS,
                "dataType": DATA_TYPE,
                "base_date": base_date,
                "base_time": base_time,
                "nx": GRID_X,
                "ny": GRID_Y,
            },
        )

        code, msg = get_result(payload)
        items = get_items(payload)

        if code == "00" and items:
            save_json("단기예보-{0}-{1}.json".format(base_date, base_time), payload)
            save_text(
                "단기예보-{0}-{1}.md".format(base_date, base_time),
                short_summary_md(base_date, base_time, items),
            )
            print("SUCCESS: 단기예보 저장 완료")
            return

        last_error = msg

    print("ERROR: 단기예보 저장 실패 - {0}".format(last_error))


# 중기예보 조회
def fetch_mid(path: str, extra: Dict[str, str]) -> Tuple[Optional[Dict], str, str]:
    last_msg = "NO_DATA"

    for tm_fc in mid_candidates():
        payload = fetch_json(
            "{0}/{1}".format(MID_TERM_BASE_URL, path),
            dict(
                {
                    "serviceKey": MID_TERM_SERVICE_KEY,
                    "pageNo": PAGE_NO,
                    "numOfRows": "10",
                    "dataType": DATA_TYPE,
                    "tmFc": tm_fc,
                },
                **extra
            ),
        )

        code, msg = get_result(payload)
        items = get_items(payload)

        if code == "00" and items:
            return payload, tm_fc, ""

        last_msg = msg

    return None, "", last_msg


# 중기예보 결과 저장
def run_mid() -> None:
    require_key(MID_TERM_SERVICE_KEY, "MID_TERM_SERVICE_KEY")

    land_payload, tm_fc, land_error = fetch_mid("getMidLandFcst", {"regId": MID_LAND_REG_ID})
    temp_payload, _, temp_error = fetch_mid("getMidTa", {"regId": MID_TEMP_REG_ID})

    if not land_payload:
        print("ERROR: 중기육상예보 저장 실패 - {0}".format(land_error))
        return

    if not temp_payload:
        print("ERROR: 중기기온예보 저장 실패 - {0}".format(temp_error))
        return

    land_items = get_items(land_payload)
    temp_items = get_items(temp_payload)

    date_text = tm_fc[:8]
    time_text = tm_fc[8:]

    save_json("중기육상예보-{0}-{1}.json".format(date_text, time_text), land_payload)
    save_json("중기기온예보-{0}-{1}.json".format(date_text, time_text), temp_payload)
    save_text(
        "중기예보-{0}-{1}.md".format(date_text, time_text),
        mid_summary_md(tm_fc, land_items[0], temp_items[0]),
    )

    print("SUCCESS: 중기예보 저장 완료")


# 실행
if __name__ == "__main__":
    run_short()
    run_mid()
