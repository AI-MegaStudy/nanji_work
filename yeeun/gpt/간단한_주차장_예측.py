# 난지공원 주차장 남은 자리 예측 시스템
# 최소 데이터 기반 간단한 예측

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

# ============================================================================
# 1. 기존 데이터 기반 설정
# ============================================================================

class NanjiParkingPredictor:
    """난지공원 주차장 남은 자리 예측"""
    
    def __init__(self):
        # 난지공원 주차 기본 정보 (추정치 기반)
        self.total_parking_spaces = 300  # 총 주차칸 (추정)
        
        # 구역별 배치 (총 300칸 기준)
        self.area_capacity = {
            'camping': 80,      # 캠핑장
            'center': 120,      # 중앙 (공연장)
            'right': 100        # 우측 (거울분수/피크닉)
        }
        
        # 기존 데이터 기반 이용 패턴
        self.base_occupancy_by_hour = {
            0: 5,    # 00시 - 매우 적음
            1: 3,
            2: 2,
            3: 2,
            4: 3,    # 04시 - 최소값
            5: 5,
            6: 8,
            7: 15,   # 07시 - 망원(출퇴근)
            8: 20,
            9: 30,   # 09시 - 광나루(출퇴근)
            10: 35,
            11: 45,
            12: 55,  # 12시 경 증가 시작
            13: 60,  # 13시 
            14: 65,  # 점심시간대
            15: 68,  # 14-16시 지속
            16: 70,  # 16시 - 강서/난지 첨두
            17: 72,  # 17시 여의도 첨두
            18: 70,  # 18시 - 양화/이촌/반포/뚝섬 첨두
            19: 65,
            20: 58,
            21: 45,  # 21시 - 잠실 첨두
            22: 30,
            23: 15   # 23시 - 야간 하강
        }
        
        # 2025년 공연/축제 데이터 (실제 관객수 기반)
        self.events = [
            {'date': '2025-04-26', 'title': 'LOVESOME', 'audience': 10952, 'area': 'center'},
            {'date': '2025-05-24', 'title': 'PEAK FESTIVAL', 'audience': 19256, 'area': 'center'},
            {'date': '2025-09-06', 'title': '렛츠락 페스티벌', 'audience': 17681, 'area': 'center'},
            {'date': '2025-09-13', 'title': 'SOMEDAY FESTIVAL', 'audience': 5375, 'area': 'center'},
            {'date': '2025-09-27', 'title': 'Asia Top Artist Festival', 'audience': 8728, 'area': 'center'},
        ]
        
        # 거울분수 가동 시간 (방문객 증가 요인)
        self.fountain_schedule = {
            5: [12, 17, 18, 19, 20],      # 5월 (비수기)
            6: [12, 17, 18, 19, 20],      # 6월
            7: [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # 7월 (성수기)
            8: [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],  # 8월
            9: [12, 17, 18, 19, 20],      # 9월
            10: [12, 17, 18, 19, 20],     # 10월
        }
    
    # ========================================================================
    # 2. 점유율 계산 함수
    # ========================================================================
    
    def get_base_occupancy(self, hour, weekday):
        """시간대별 기본 점유율 반환"""
        base = self.base_occupancy_by_hour.get(hour, 50)
        
        # 주말 보정 (+10%)
        if weekday >= 5:  # 토요일(5), 일요일(6)
            base = base * 1.1
        
        return min(base, 100)  # 최대 100%
    
    def get_fountain_bonus(self, month, hour):
        """거울분수 가동 시 추가 점유율"""
        if month in self.fountain_schedule:
            if hour in self.fountain_schedule[month]:
                return 15  # 15% 추가 (저녁 방문객 증가)
        return 0
    
    def get_event_bonus(self, predict_date):
        """이벤트 개최 시 추가 점유율"""
        for event in self.events:
            event_date = event['date']
            
            if str(predict_date.date()) == event_date:
                # 이벤트 규모에 따른 점유율 상승
                # 관객수 / 100 을 백분율 증가로 변환
                bonus = min(event['audience'] / 100 * 0.5, 40)  # 최대 40%
                return bonus
        
        return 0
    
    def get_season_factor(self, month):
        """계절 요소"""
        if month in [7, 8]:  # 여름 성수기
            return 1.2  # 20% 증가
        elif month in [6, 9]:  # 여름 전후
            return 1.1  # 10% 증가
        elif month in [12, 1, 2]:  # 겨울
            return 0.7  # 30% 감소
        return 1.0
    
    # ========================================================================
    # 3. 예측 함수
    # ========================================================================
    
    def predict_occupancy(self, target_datetime):
        """
        특정 시간의 주차장 점유율 예측
        
        Args:
            target_datetime: datetime 객체
        
        Returns:
            dict: {
                'occupancy_rate': 점유율 (0-100%),
                'available_spaces': 남은 주차칸,
                'total_spaces': 전체 주차칸,
                'timestamp': 예측 시간
            }
        """
        
        hour = target_datetime.hour
        weekday = target_datetime.weekday()
        month = target_datetime.month
        
        # 기본 점유율
        base = self.get_base_occupancy(hour, weekday)
        
        # 거울분수 영향
        fountain_bonus = self.get_fountain_bonus(month, hour)
        
        # 이벤트 영향
        event_bonus = self.get_event_bonus(target_datetime)
        
        # 계절 요소
        season_factor = self.get_season_factor(month)
        
        # 최종 점유율
        occupancy_rate = (base + fountain_bonus + event_bonus) * season_factor
        occupancy_rate = np.clip(occupancy_rate, 0, 100)  # 0-100% 범위
        
        # 남은 주차칸 계산
        available_spaces = int(self.total_parking_spaces * (100 - occupancy_rate) / 100)
        
        return {
            'timestamp': target_datetime.isoformat(),
            'time_str': target_datetime.strftime('%Y-%m-%d %H:%M'),
            'occupancy_rate': round(occupancy_rate, 1),
            'available_spaces': available_spaces,
            'parked_spaces': int(self.total_parking_spaces - available_spaces),
            'total_spaces': self.total_parking_spaces
        }
    
    def predict_next_hours(self, hours=[1, 2, 3, 4]):
        """
        현재 시간 기준 몇 시간 뒤 예측
        
        Args:
            hours: 예측할 시간 리스트 (예: [1, 2, 3, 4])
        
        Returns:
            list: 예측 결과 리스트
        """
        
        current_time = datetime.now()
        predictions = []
        
        for h in hours:
            future_time = current_time + timedelta(hours=h)
            pred = self.predict_occupancy(future_time)
            predictions.append(pred)
        
        return predictions
    
    def predict_area_occupancy(self, target_datetime):
        """
        구역별 주차 예측
        """
        total_occupancy = self.predict_occupancy(target_datetime)
        occupancy_rate = total_occupancy['occupancy_rate']
        
        # 구역별로 비례 배치
        area_predictions = {}
        for area, capacity in self.area_capacity.items():
            area_occupied = int(capacity * occupancy_rate / 100)
            area_available = capacity - area_occupied
            
            area_predictions[area] = {
                'capacity': capacity,
                'occupied': area_occupied,
                'available': area_available,
                'occupancy_rate': round(occupancy_rate, 1)
            }
        
        return area_predictions


# ============================================================================
# 4. 실행 예제
# ============================================================================

def main():
    print("=" * 70)
    print("난지공원 주차장 남은 자리 수 예측")
    print("=" * 70)
    
    # 예측기 생성
    predictor = NanjiParkingPredictor()
    
    # 현재 시간 기준 향후 4시간 예측
    print("\n[향후 4시간 주차장 예측]\n")
    predictions = predictor.predict_next_hours([1, 2, 3, 4])
    
    for i, pred in enumerate(predictions, 1):
        print(f"📍 {i}시간 뒤 ({pred['time_str']})")
        print(f"   • 점유율: {pred['occupancy_rate']}%")
        print(f"   • 남은 자리: {pred['available_spaces']} 칸")
        print(f"   • 차 있는 자리: {pred['parked_spaces']} 칸")
        print(f"   • 전체 주차칸: {pred['total_spaces']} 칸")
        print()
    
    # 구역별 예측
    print("\n[구역별 예측 (1시간 뒤)]\n")
    current_time = datetime.now()
    future_time = current_time + timedelta(hours=1)
    
    area_pred = predictor.predict_area_occupancy(future_time)
    
    for area, info in area_pred.items():
        print(f"🅿️ {area.upper()}")
        print(f"   • 전체: {info['capacity']} 칸")
        print(f"   • 주차: {info['occupied']} 칸")
        print(f"   • 남은 칸: {info['available']} 칸 ✓")
        print()
    
    # JSON 형식 출력
    print("\n[JSON 형식 결과]\n")
    result = {
        'current_time': datetime.now().isoformat(),
        'predictions': predictions,
        'area_details': area_pred
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
