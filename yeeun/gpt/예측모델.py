#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한강 난지공원 주차장 공간 예측 모델
시계열 데이터 기반 몇 시간 뒤의 주차장 점유율 예측
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import pickle
import json
from datetime import datetime, timedelta

# ============================================================================
# 1. 데이터 전처리
# ============================================================================

class DataPreprocessor:
    """주차장 예측용 데이터 전처리"""
    
    def __init__(self):
        self.scaler = MinMaxScaler()
        self.feature_names = []
    
    def add_time_features(self, df):
        """시간 기반 피처 추가"""
        df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
        df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
        df['month'] = pd.to_datetime(df['timestamp']).dt.month
        df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
        
        # 사인/코사인 변환 (주기성 반영)
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        df['month_sin'] = np.sin(2 * np.pi * df['month'] / 12)
        df['month_cos'] = np.cos(2 * np.pi * df['month'] / 12)
        
        return df
    
    def add_season_features(self, df):
        """계절 피처 추가"""
        def get_season(month):
            if month in [12, 1, 2]:
                return 0  # 겨울
            elif month in [3, 4, 5]:
                return 1  # 봄
            elif month in [6, 7, 8]:
                return 2  # 여름
            else:
                return 3  # 가을
        
        df['season'] = df['month'].apply(get_season)
        return df
    
    def add_facility_features(self, df):
        """시설 운영 피처 추가"""
        
        # 거울분수 운영 여부
        def fountain_operating(row):
            month = row['month']
            hour = row['hour']
            if month not in [5, 6, 9, 10, 7, 8]:  # 운영 월만
                return 0
            
            operating_hours = {
                7: [12, 17, 18, 19, 20],
                8: [12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
                5: [12, 17, 18, 19, 20],
                6: [12, 17, 18, 19, 20],
                9: [12, 17, 18, 19, 20],
                10: [12, 17, 18, 19, 20]
            }
            
            return 1 if hour in operating_hours.get(month, []) else 0
        
        df['fountain_operating'] = df.apply(fountain_operating, axis=1)
        
        # 물놀이장 운영 여부 (6-8월)
        df['pool_operating'] = ((df['month'].isin([6, 7, 8])) & 
                                 (df['hour'] >= 10) & (df['hour'] <= 19)).astype(int)
        
        # 캠핑장 체크인/아웃 피크 (14:00 ~ 11:00 다음날)
        df['camping_peak'] = ((df['hour'] >= 14) | (df['hour'] <= 11)).astype(int)
        
        return df
    
    def add_event_features(self, df, events_data):
        """이벤트 기반 피처 추가"""
        df['event_happening'] = 0
        df['event_audience'] = 0
        
        for idx, row in df.iterrows():
            timestamp = pd.to_datetime(row['timestamp'])
            
            for event in events_data:
                event_date = pd.to_datetime(event['date'], format='%Y/%m/%d', errors='coerce')
                
                if pd.notna(event_date) and timestamp.date() == event_date.date():
                    df.at[idx, 'event_happening'] = 1
                    df.at[idx, 'event_audience'] = int(event.get('audience', 5000))
        
        return df
    
    def add_lag_features(self, df, target_col='parking_occupancy', lags=[1, 2, 24, 168]):
        """시차 피처 추가 (과거 데이터 기반)"""
        
        for lag in lags:
            df[f'{target_col}_lag_{lag}'] = df[target_col].shift(lag)
        
        return df.fillna(method='bfill').fillna(method='ffill')
    
    def prepare_features(self, df, events_data=None, target_col='parking_occupancy'):
        """모든 피처 준비"""
        
        df = self.add_time_features(df)
        df = self.add_season_features(df)
        df = self.add_facility_features(df)
        
        if events_data:
            df = self.add_event_features(df, events_data)
        
        if target_col in df.columns:
            df = self.add_lag_features(df, target_col)
        
        # 결측값 처리
        df = df.fillna(method='bfill').fillna(method='ffill')
        
        return df


# ============================================================================
# 2. LSTM 기반 시계열 예측 모델
# ============================================================================

class LSTMParkingPredictor:
    """LSTM 기반 주차장 점유율 예측 모델"""
    
    def __init__(self, lookback=24):
        """
        lookback: 과거 몇 시간의 데이터를 사용할지 결정
        """
        self.lookback = lookback
        self.model = None
        self.scaler = MinMaxScaler()
    
    def create_sequences(self, data, lookback):
        """시간 시퀀스 생성"""
        X, y = [], []
        
        for i in range(len(data) - lookback):
            X.append(data[i:(i + lookback)])
            y.append(data[i + lookback])
        
        return np.array(X), np.array(y)
    
    def build_model(self, input_shape):
        """LSTM 모델 구축"""
        
        model = keras.Sequential([
            layers.LSTM(128, activation='relu', input_shape=input_shape, return_sequences=True),
            layers.Dropout(0.2),
            layers.LSTM(64, activation='relu', return_sequences=False),
            layers.Dropout(0.2),
            layers.Dense(32, activation='relu'),
            layers.Dense(1)  # 점유율 예측
        ])
        
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.001),
            loss='mse',
            metrics=['mae']
        )
        
        return model
    
    def train(self, X_train, y_train, X_val, y_val, epochs=50, batch_size=32):
        """모델 학습"""
        
        self.model = self.build_model((X_train.shape[1], X_train.shape[2]))
        
        early_stop = keras.callbacks.EarlyStopping(
            monitor='val_loss',
            patience=10,
            restore_best_weights=True
        )
        
        history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=epochs,
            batch_size=batch_size,
            callbacks=[early_stop],
            verbose=1
        )
        
        return history
    
    def predict(self, X):
        """예측"""
        return self.model.predict(X, verbose=0)
    
    def save_model(self, filename='lstm_model.h5'):
        """모델 저장"""
        self.model.save(filename)
        print(f"Model saved to {filename}")
    
    def load_model(self, filename='lstm_model.h5'):
        """모델 로드"""
        self.model = keras.models.load_model(filename)
        print(f"Model loaded from {filename}")


# ============================================================================
# 3. 앙상블 예측 모델 (GradientBoosting + RandomForest)
# ============================================================================

class EnsembleParkingPredictor:
    """앙상블 기반 주차장 예측 모델"""
    
    def __init__(self):
        self.gb_model = GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.1,
            max_depth=7,
            random_state=42
        )
        
        self.rf_model = RandomForestRegressor(
            n_estimators=200,
            max_depth=15,
            random_state=42,
            n_jobs=-1
        )
        
        self.lr_model = LinearRegression()
        
        self.feature_importance = {}
    
    def train(self, X_train, y_train, X_val, y_val):
        """모델 학습"""
        
        print("Training Gradient Boosting...")
        self.gb_model.fit(X_train, y_train)
        gb_val_score = self.gb_model.score(X_val, y_val)
        print(f"GB R² Score: {gb_val_score:.4f}")
        
        print("Training Random Forest...")
        self.rf_model.fit(X_train, y_train)
        rf_val_score = self.rf_model.score(X_val, y_val)
        print(f"RF R² Score: {rf_val_score:.4f}")
        
        # 메타 레이어: 두 모델의 예측값을 이용한 선형 회귀
        gb_pred_train = self.gb_model.predict(X_train)
        rf_pred_train = self.rf_model.predict(X_train)
        
        meta_X_train = np.column_stack([gb_pred_train, rf_pred_train])
        meta_X_val = np.column_stack([
            self.gb_model.predict(X_val),
            self.rf_model.predict(X_val)
        ])
        
        self.lr_model.fit(meta_X_train, y_train)
        lr_val_score = self.lr_model.score(meta_X_val, y_val)
        print(f"Meta LR R² Score: {lr_val_score:.4f}")
        
        # 특성 중요도
        self.feature_importance['gb_importance'] = self.gb_model.feature_importances_
        self.feature_importance['rf_importance'] = self.rf_model.feature_importances_
    
    def predict(self, X):
        """예측"""
        gb_pred = self.gb_model.predict(X)
        rf_pred = self.rf_model.predict(X)
        
        meta_X = np.column_stack([gb_pred, rf_pred])
        final_pred = self.lr_model.predict(meta_X)
        
        return np.clip(final_pred, 0, 100)  # 0-100% 범위 내
    
    def get_feature_importance(self, feature_names):
        """특성 중요도 반환"""
        importance_df = pd.DataFrame({
            'feature': feature_names,
            'gb_importance': self.feature_importance['gb_importance'],
            'rf_importance': self.feature_importance['rf_importance']
        })
        
        importance_df['avg_importance'] = (
            importance_df['gb_importance'] + importance_df['rf_importance']
        ) / 2
        
        return importance_df.sort_values('avg_importance', ascending=False)
    
    def save_model(self, filename='ensemble_model.pkl'):
        """모델 저장"""
        with open(filename, 'wb') as f:
            pickle.dump({
                'gb_model': self.gb_model,
                'rf_model': self.rf_model,
                'lr_model': self.lr_model
            }, f)
        print(f"Ensemble model saved to {filename}")
    
    def load_model(self, filename='ensemble_model.pkl'):
        """모델 로드"""
        with open(filename, 'rb') as f:
            models = pickle.load(f)
            self.gb_model = models['gb_model']
            self.rf_model = models['rf_model']
            self.lr_model = models['lr_model']
        print(f"Ensemble model loaded from {filename}")


# ============================================================================
# 4. 예측 결과 처리 및 API
# ============================================================================

class PredictionAPI:
    """예측 결과 처리 및 API"""
    
    def __init__(self, model):
        self.model = model
        self.last_prediction = {}
    
    def predict_next_hours(self, current_data, hours_ahead=[1, 2, 3, 4]):
        """
        현재 시간 기준 몇 시간 뒤 주차장 점유율 예측
        
        Args:
            current_data: 현재 시간의 피처 데이터
            hours_ahead: 예측할 시간 (예: [1, 2, 3, 4]는 1시간 후, 2시간 후, ...)
        
        Returns:
            dict: 각 시간대별 예측 점유율
        """
        
        predictions = {}
        
        current_time = datetime.now()
        
        for hours in hours_ahead:
            future_time = current_time + timedelta(hours=hours)
            
            # 미래 시간 피처 업데이트
            future_data = current_data.copy()
            future_data['hour'] = future_time.hour
            future_data['day_of_week'] = future_time.weekday()
            future_data['month'] = future_time.month
            
            # 예측
            pred_occupancy = self.model.predict(future_data.values.reshape(1, -1))[0]
            
            predictions[f'{hours}hour_later'] = {
                'time': future_time.isoformat(),
                'predicted_occupancy': float(np.clip(pred_occupancy, 0, 100)),
                'available_spaces': int((100 - pred_occupancy) * total_parking_spaces / 100),
                'confidence': float(np.random.uniform(0.75, 0.95))  # 임시 신뢰도
            }
        
        self.last_prediction = predictions
        return predictions
    
    def get_prediction_json(self):
        """JSON 형식의 예측 결과 반환"""
        return json.dumps(self.last_prediction, indent=2, ensure_ascii=False)
    
    def get_area_specific_prediction(self, area, occupancy):
        """구역별 예측"""
        
        # 구역별 용량 (설정 필요)
        area_capacity = {
            'camping': 50,      # 캠핑장
            'center': 100,      # 중앙
            'right': 80         # 우측 (거울분수)
        }
        
        if area in area_capacity:
            available = int(area_capacity[area] * (100 - occupancy) / 100)
            
            return {
                'area': area,
                'occupancy_rate': float(occupancy),
                'available_spaces': available,
                'total_capacity': area_capacity[area]
            }
        
        return None


# ============================================================================
# 5. 모델 평가
# ============================================================================

class ModelEvaluator:
    """예측 모델 평가"""
    
    @staticmethod
    def evaluate(y_true, y_pred):
        """모델 성능 평가"""
        
        mape = mean_absolute_percentage_error(y_true, y_pred)
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        mae = np.mean(np.abs(y_true - y_pred))
        
        return {
            'MAPE': float(mape),
            'RMSE': float(rmse),
            'MAE': float(mae)
        }
    
    @staticmethod
    def print_evaluation(metrics):
        """평가 결과 출력"""
        print("\n" + "=" * 50)
        print("모델 성능 평가")
        print("=" * 50)
        print(f"MAPE (평균 절대 백분율 오차): {metrics['MAPE']:.2%}")
        print(f"RMSE (제곱 평균 제곱근 오차): {metrics['RMSE']:.2f}")
        print(f"MAE (평균 절대 오차): {metrics['MAE']:.2f}")
        print("=" * 50)


# ============================================================================
# 6. 메인 실행 예제
# ============================================================================

def main():
    print("=" * 60)
    print("한강 난지공원 주차장 공간 예측 모델")
    print("=" * 60)
    
    # 1. 데이터 로드
    print("\n[1] 데이터 로드...")
    df = pd.read_csv('training_data.csv')
    
    # 2. 데이터 전처리
    print("\n[2] 데이터 전처리...")
    preprocessor = DataPreprocessor()
    df = preprocessor.prepare_features(df)
    
    # 3. 학습/검증 데이터 분할
    print("\n[3] 데이터 분할...")
    train_size = int(len(df) * 0.7)
    val_size = int(len(df) * 0.15)
    
    X_train = df.iloc[:train_size, :-1]
    y_train = df.iloc[:train_size, -1]
    X_val = df.iloc[train_size:train_size+val_size, :-1]
    y_val = df.iloc[train_size:train_size+val_size, -1]
    X_test = df.iloc[train_size+val_size:, :-1]
    y_test = df.iloc[train_size+val_size:, -1]
    
    # 4. 모델 학습
    print("\n[4] 앙상블 모델 학습...")
    model = EnsembleParkingPredictor()
    model.train(X_train.values, y_train.values, X_val.values, y_val.values)
    
    # 5. 모델 평가
    print("\n[5] 모델 평가...")
    y_pred = model.predict(X_test.values)
    metrics = ModelEvaluator.evaluate(y_test.values, y_pred)
    ModelEvaluator.print_evaluation(metrics)
    
    # 6. 예측
    print("\n[6] 미래 예측...")
    current_data = X_test.iloc[-1]
    api = PredictionAPI(model)
    predictions = api.predict_next_hours(current_data, hours_ahead=[1, 2, 3, 4])
    print(api.get_prediction_json())
    
    # 7. 모델 저장
    print("\n[7] 모델 저장...")
    model.save_model('parking_predictor.pkl')


if __name__ == "__main__":
    main()
