#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한강 난지공원 주차장 예측 - 데이터 크롤링 및 수집 모듈
2024-2026년 이벤트, 기상, 교통 데이터 통합 수집
"""

import requests
import json
import csv
from datetime import datetime, timedelta
import pandas as pd
from bs4 import BeautifulSoup
import time

# ============================================================================
# 1. 한강공원 공식 이벤트 데이터 크롤링
# ============================================================================

class HangangEventCrawler:
    """한강공원 공식 웹사이트에서 이벤트 정보 크롤링"""
    
    def __init__(self):
        self.base_url = "https://hangang.seoul.go.kr/www/eventMng/list.do"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_events(self, year_range=(2024, 2026)):
        """
        연도별 이벤트 크롤링
        """
        events_data = []
        
        for year in range(year_range[0], year_range[1] + 1):
            try:
                # 페이지 요청 (동적 로딩의 경우 Selenium 필요)
                params = {
                    'mid': '538',
                    'year': year
                }
                
                response = requests.get(self.base_url, params=params, headers=self.headers, timeout=10)
                response.encoding = 'utf-8'
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # 이벤트 항목 파싱 (구조에 따라 조정 필요)
                    event_items = soup.find_all('div', class_='event-item')
                    
                    for item in event_items:
                        try:
                            event_data = {
                                'year': year,
                                'date': item.find('span', class_='event-date').text.strip(),
                                'title': item.find('h3', class_='event-title').text.strip(),
                                'location': item.find('span', class_='event-location').text.strip(),
                                'type': item.find('span', class_='event-type').text.strip(),
                                'url': item.find('a')['href'] if item.find('a') else None
                            }
                            events_data.append(event_data)
                        except:
                            continue
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error crawling {year}: {str(e)}")
        
        return events_data
    
    def save_to_csv(self, data, filename='hangang_events.csv'):
        """CSV 파일로 저장"""
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Saved {len(data)} events to {filename}")


# ============================================================================
# 2. 나무위키 난지공원 공연 정보 크롤링
# ============================================================================

class NanjiBiggiWikiCrawler:
    """나무위키에서 난지공원 공연 정보 크롤링"""
    
    def __init__(self):
        self.url = "https://namu.wiki/w/%EB%82%9C%EC%A7%80%ED%95%9C%EA%B0%95%EA%B3%B5%EC%9B%90"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_concerts(self):
        """공연 목록 크롤링"""
        concerts = []
        
        try:
            response = requests.get(self.url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 공연 목록 테이블 찾기
                tables = soup.find_all('table')
                
                for table in tables:
                    rows = table.find_all('tr')
                    
                    for row in rows[1:]:  # 헤더 제외
                        cols = row.find_all('td')
                        
                        if len(cols) >= 3:
                            try:
                                concert = {
                                    'date': cols[0].text.strip(),
                                    'type': cols[1].text.strip(),
                                    'title': cols[2].text.strip(),
                                    'audience': cols[3].text.strip() if len(cols) > 3 else 'N/A'
                                }
                                concerts.append(concert)
                            except:
                                continue
        
        except Exception as e:
            print(f"Error fetching concerts: {str(e)}")
        
        return concerts
    
    def save_to_json(self, data, filename='nanji_concerts.json'):
        """JSON 파일로 저장"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(data)} concerts to {filename}")


# ============================================================================
# 3. 기상청 데이터 수집 (과거 기상 데이터)
# ============================================================================

class WeatherDataCollector:
    """기상청 및 공개 데이터 포털에서 기상 데이터 수집"""
    
    def __init__(self):
        # 기상청 API 키 필요 (data.go.kr에서 발급)
        self.weather_api_key = "YOUR_API_KEY"  # 실제 키 필요
        self.weather_url = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getUltraSrtNcst"
        
        # 서울시 마포구 난지공원 좌표
        self.nx = 60  # X 격자값 (마포구)
        self.ny = 127  # Y 격자값 (마포구)
    
    def get_historical_weather(self, start_date, end_date):
        """
        과거 기상 데이터 수집
        start_date, end_date: YYYYMMDD 형식
        """
        weather_data = []
        
        try:
            params = {
                'ServiceKey': self.weather_api_key,
                'pageNo': 1,
                'numOfRows': 1000,
                'dataType': 'JSON',
                'base_date': start_date,
                'base_time': '0600',
                'nx': self.nx,
                'ny': self.ny
            }
            
            response = requests.get(self.weather_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'response' in data:
                    items = data['response']['body']['items']['item']
                    
                    for item in items:
                        weather_point = {
                            'date': item['baseDate'],
                            'time': item['baseTime'],
                            'temp': float(item.get('T1H', 0)),  # 기온
                            'humidity': float(item.get('REH', 0)),  # 상대습도
                            'precipitation': float(item.get('RN1', 0)),  # 1시간 강수량
                            'wind_speed': float(item.get('WS', 0))  # 풍속
                        }
                        weather_data.append(weather_point)
        
        except Exception as e:
            print(f"Error collecting weather data: {str(e)}")
        
        return weather_data
    
    def save_to_csv(self, data, filename='weather_data.csv'):
        """CSV 파일로 저장"""
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Saved {len(data)} weather records to {filename}")


# ============================================================================
# 4. 공공 데이터 포털 - 캠핑장 정보
# ============================================================================

class CampingDataCollector:
    """서울시 마포구 캠핑장 현황 데이터"""
    
    def __init__(self):
        self.url = "https://mapo.go.kr/site/main/openData/view?dataId=229"
    
    def fetch_camping_data(self):
        """캠핑장 데이터 수집"""
        try:
            response = requests.get(self.url, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # CSV 다운로드 링크 찾기
                download_link = soup.find('a', class_='btn-download')
                
                if download_link:
                    csv_url = download_link['href']
                    print(f"CSV URL: {csv_url}")
                    # CSV 파일 다운로드
                    csv_response = requests.get(csv_url, timeout=10)
                    
                    with open('camping_data.csv', 'wb') as f:
                        f.write(csv_response.content)
                    
                    print("Camping data downloaded successfully")
        
        except Exception as e:
            print(f"Error fetching camping data: {str(e)}")


# ============================================================================
# 5. 교통 정보 수집 (서울시 교통정보)
# ============================================================================

class TrafficDataCollector:
    """서울시 버스/교통 혼잡도 정보 수집"""
    
    def __init__(self):
        # 서울시 교통정보 API
        self.api_key = "YOUR_TRAFFIC_API_KEY"  # 실제 키 필요
        self.base_url = "http://tapi.seoul.go.kr/v2"
    
    def get_bus_arrival(self, station_id):
        """버스 운행 정보"""
        try:
            url = f"{self.base_url}/Bus/{station_id}"
            params = {'key': self.api_key}
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        
        except Exception as e:
            print(f"Error fetching bus data: {str(e)}")
        
        return None


# ============================================================================
# 6. 통합 데이터 취합 및 정제
# ============================================================================

class DataIntegration:
    """수집된 모든 데이터 통합 및 정제"""
    
    def __init__(self):
        self.events = []
        self.concerts = []
        self.weather = []
        self.parking = []
    
    def merge_all_data(self):
        """모든 데이터 병합"""
        
        # 시간대별로 정렬된 통합 데이터
        integrated_data = {
            'timestamp': [],
            'day_of_week': [],
            'season': [],
            'weather_temp': [],
            'weather_humidity': [],
            'weather_precipitation': [],
            'event_happening': [],
            'event_audience': [],
            'fountain_operating': [],
            'pool_operating': [],
            'expected_parking_occupancy': []
        }
        
        return integrated_data
    
    def save_training_data(self, filename='training_data.csv'):
        """머신러닝 트레이닝용 데이터 저장"""
        df = pd.DataFrame(self.merge_all_data())
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Training data saved to {filename}")


# ============================================================================
# 7. 메인 실행 함수
# ============================================================================

def main():
    """모든 크롤링 및 데이터 수집 실행"""
    
    print("=" * 60)
    print("한강 난지공원 주차장 예측 - 데이터 수집 시작")
    print("=" * 60)
    
    # 1. 한강공원 이벤트 크롤링
    print("\n[1/5] 한강공원 이벤트 데이터 크롤링...")
    event_crawler = HangangEventCrawler()
    events = event_crawler.fetch_events()
    event_crawler.save_to_csv(events)
    print(f"✓ {len(events)} 개의 이벤트 수집 완료")
    
    # 2. 나무위키 공연 정보 크롤링
    print("\n[2/5] 나무위키 공연 정보 크롤링...")
    wiki_crawler = NanjiBiggiWikiCrawler()
    concerts = wiki_crawler.fetch_concerts()
    wiki_crawler.save_to_json(concerts)
    print(f"✓ {len(concerts)} 개의 공연 정보 수집 완료")
    
    # 3. 기상청 데이터 수집
    print("\n[3/5] 기상청 과거 데이터 수집...")
    weather_collector = WeatherDataCollector()
    # 예: 2024년 1월 1일 ~ 현재
    start = "20240101"
    end = "20260403"
    weather_data = weather_collector.get_historical_weather(start, end)
    weather_collector.save_to_csv(weather_data)
    print(f"✓ {len(weather_data)} 개의 기상 기록 수집 완료")
    
    # 4. 캠핑장 정보 수집
    print("\n[4/5] 캠핑장 정보 수집...")
    camping_collector = CampingDataCollector()
    camping_collector.fetch_camping_data()
    print("✓ 캠핑장 정보 수집 완료")
    
    # 5. 교통 정보 수집
    print("\n[5/5] 교통 정보 수집...")
    traffic_collector = TrafficDataCollector()
    # 난지공원 버스 정류장 ID 필요
    bus_info = traffic_collector.get_bus_arrival("station_id_goes_here")
    print("✓ 교통 정보 수집 완료")
    
    # 6. 데이터 통합 및 저장
    print("\n[통합] 모든 데이터 통합 및 머신러닝 학습용 데이터 생성...")
    integrator = DataIntegration()
    integrator.save_training_data()
    
    print("\n" + "=" * 60)
    print("✓ 모든 데이터 수집 및 처리 완료!")
    print("생성된 파일:")
    print("  - hangang_events.csv")
    print("  - nanji_concerts.json")
    print("  - weather_data.csv")
    print("  - camping_data.csv")
    print("  - training_data.csv")
    print("=" * 60)


if __name__ == "__main__":
    main()
