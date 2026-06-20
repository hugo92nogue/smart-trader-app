import numpy as np
import pandas as pd
from typing import Dict, List, Literal
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    """Calculate technical indicators - pure numpy/pandas (sin talib)"""
    
    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        try:
            prices_array = np.array(prices, dtype=float)
            delta = np.diff(prices_array)
            gain = np.where(delta > 0, delta, 0)
            loss = np.where(delta < 0, -delta, 0)
            avg_gain = np.mean(gain[:period])
            avg_loss = np.mean(loss[:period])
            for i in range(period, len(gain)):
                avg_gain = (avg_gain * (period - 1) + gain[i]) / period
                avg_loss = (avg_loss * (period - 1) + loss[i]) / period
            if avg_loss == 0:
                return 100.0
            rs = avg_gain / avg_loss
            return float(100 - (100 / (1 + rs)))
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return 50.0

    @staticmethod
    def calculate_macd(prices: List[float]) -> Dict[str, float]:
        try:
            s = pd.Series(prices, dtype=float)
            ema12 = s.ewm(span=12, adjust=False).mean()
            ema26 = s.ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line
            return {
                'macd': float(macd_line.iloc[-1]),
                'signal': float(signal_line.iloc[-1]),
                'histogram': float(histogram.iloc[-1])
            }
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            return {'macd': 0.0, 'signal': 0.0, 'histogram': 0.0}

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20) -> Dict[str, float]:
        try:
            s = pd.Series(prices, dtype=float)
            middle = s.rolling(window=period).mean().iloc[-1]
            std = s.rolling(window=period).std().iloc[-1]
            return {
                'upper': float(middle + 2 * std),
                'middle': float(middle),
                'lower': float(middle - 2 * std)
            }
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            return {'upper': 0.0, 'middle': 0.0, 'lower': 0.0}

    @staticmethod
    def calculate_ema(prices: List[float], period: int = 20) -> float:
        try:
            s = pd.Series(prices, dtype=float)
            return float(s.ewm(span=period, adjust=False).mean().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating EMA: {e}")
            return 0.0

    @staticmethod
    def calculate_sma(prices: List[float], period: int = 20) -> float:
        try:
            s = pd.Series(prices, dtype=float)
            return float(s.rolling(window=period).mean().iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating SMA: {e}")
            return 0.0

    @staticmethod
    def calculate_stochastic(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Dict[str, float]:
        try:
            h = pd.Series(highs, dtype=float)
            l = pd.Series(lows, dtype=float)
            c = pd.Series(closes, dtype=float)
            lowest_low = l.rolling(window=period).min()
            highest_high = h.rolling(window=period).max()
            k = 100 * (c - lowest_low) / (highest_high - lowest_low)
            d = k.rolling(window=3).mean()
            return {
                'k': float(k.iloc[-1]) if not np.isnan(k.iloc[-1]) else 50.0,
                'd': float(d.iloc[-1]) if not np.isnan(d.iloc[-1]) else 50.0
            }
        except Exception as e:
            logger.error(f"Error calculating Stochastic: {e}")
            return {'k': 50.0, 'd': 50.0}

    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
        try:
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            c = np.array(closes, dtype=float)
            prev_close = np.roll(c, 1)
            prev_close[0] = c[0]
            tr = np.maximum(h - l, np.maximum(np.abs(h - prev_close), np.abs(l - prev_close)))
            atr = pd.Series(tr).ewm(span=period, adjust=False).mean()
            return float(atr.iloc[-1])
        except Exception as e:
            logger.error(f"Error calculating ATR: {e}")
            return 0.0

    @staticmethod
    def analyze_indicators(indicators: Dict) -> Literal["buy", "sell", "neutral"]:
        buy_signals = 0
        sell_signals = 0
        if 'rsi' in indicators:
            if indicators['rsi'] < 30:
                buy_signals += 2
            elif indicators['rsi'] > 70:
                sell_signals += 2
        if 'macd' in indicators:
            if indicators['macd']['histogram'] > 0:
                buy_signals += 1
            elif indicators['macd']['histogram'] < 0:
                sell_signals += 1
        if 'bollinger' in indicators and 'current_price' in indicators:
            price = indicators['current_price']
            if price < indicators['bollinger']['lower']:
                buy_signals += 1
            elif price > indicators['bollinger']['upper']:
                sell_signals += 1
        if 'ema_20' in indicators and 'sma_50' in indicators:
            if indicators['ema_20'] > indicators['sma_50']:
                buy_signals += 1
            elif indicators['ema_20'] < indicators['sma_50']:
                sell_signals += 1
        if 'stochastic' in indicators:
            if indicators['stochastic']['k'] < 20:
                buy_signals += 1
            elif indicators['stochastic']['k'] > 80:
                sell_signals += 1
        if buy_signals > sell_signals:
            return "buy"
        elif sell_signals > buy_signals:
            return "sell"
        return "neutral"

    @classmethod
    def get_all_indicators(cls, klines: List) -> Dict:
        if not klines or len(klines) < 50:
            return {}
        closes = [float(k[4]) for k in klines]
        highs  = [float(k[2]) for k in klines]
        lows   = [float(k[3]) for k in klines]
        volumes= [float(k[5]) for k in klines]
        return {
            'rsi':          cls.calculate_rsi(closes),
            'macd':         cls.calculate_macd(closes),
            'bollinger':    cls.calculate_bollinger_bands(closes),
            'ema_20':       cls.calculate_ema(closes, 20),
            'ema_50':       cls.calculate_ema(closes, 50),
            'sma_20':       cls.calculate_sma(closes, 20),
            'sma_50':       cls.calculate_sma(closes, 50),
            'stochastic':   cls.calculate_stochastic(highs, lows, closes),
            'atr':          cls.calculate_atr(highs, lows, closes),
            'current_price': closes[-1],
            'volume':        volumes[-1]
        }
