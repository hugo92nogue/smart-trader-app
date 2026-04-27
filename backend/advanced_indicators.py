import numpy as np
import talib
from typing import Dict, List, Optional, Literal
import logging

logger = logging.getLogger(__name__)


class SniperScore:
    """Sniper Entry-Exit scoring system (from KhanSaab V.02)
    Dual bull/bear scoring based on multiple indicator confluence."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  volumes: List[float]) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            v = np.array(volumes, dtype=float)
            
            # Indicators
            ema9 = talib.EMA(c, timeperiod=9)
            ema21 = talib.EMA(c, timeperiod=21)
            rsi = talib.RSI(c, timeperiod=14)
            macd, macd_signal, _ = talib.MACD(c)
            adx = talib.ADX(h, l, c, timeperiod=14)
            vol_avg = talib.SMA(v, timeperiod=20)
            
            # VWAP approximation (typical price * volume / cumulative volume)
            tp = (h + l + c) / 3
            cum_vol = np.cumsum(v)
            cum_tp_vol = np.cumsum(tp * v)
            vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, c)
            
            idx = -1
            price = c[idx]
            
            # Bull score
            bull_score = 0
            if price > vwap[idx]: bull_score += 1
            if not np.isnan(rsi[idx]) and rsi[idx] > 50: bull_score += 1
            if not np.isnan(macd[idx]) and not np.isnan(macd_signal[idx]) and macd[idx] > macd_signal[idx]: bull_score += 1
            if not np.isnan(ema9[idx]) and not np.isnan(ema21[idx]) and ema9[idx] > ema21[idx]: bull_score += 1
            if not np.isnan(adx[idx]) and adx[idx] > 25 and price > ema9[idx]: bull_score += 1
            if not np.isnan(vol_avg[idx]) and v[idx] > vol_avg[idx] and price > c[idx - 1]: bull_score += 1
            # Additional: price above ema9
            if not np.isnan(ema9[idx]) and price > ema9[idx]: bull_score += 1
            
            # Bear score
            bear_score = 0
            if price < vwap[idx]: bear_score += 1
            if not np.isnan(rsi[idx]) and rsi[idx] < 50: bear_score += 1
            if not np.isnan(macd[idx]) and not np.isnan(macd_signal[idx]) and macd[idx] < macd_signal[idx]: bear_score += 1
            if not np.isnan(ema9[idx]) and not np.isnan(ema21[idx]) and ema9[idx] < ema21[idx]: bear_score += 1
            if not np.isnan(adx[idx]) and adx[idx] > 25 and price < ema9[idx]: bear_score += 1
            if not np.isnan(vol_avg[idx]) and v[idx] > vol_avg[idx] and price < c[idx - 1]: bear_score += 1
            if not np.isnan(ema9[idx]) and price < ema9[idx]: bear_score += 1
            
            bull_pct = (bull_score / 7) * 100
            bear_pct = (bear_score / 7) * 100
            
            diff = bull_pct - bear_pct
            if diff >= 40:
                bias = "STRONG BULL"
            elif diff <= -40:
                bias = "STRONG BEAR"
            elif bull_pct > bear_pct:
                bias = "MILD BULL"
            else:
                bias = "MILD BEAR"
            
            # EMA crossover signals
            ema_cross_buy = not np.isnan(ema9[idx]) and not np.isnan(ema21[idx]) and \
                            not np.isnan(ema9[idx-1]) and not np.isnan(ema21[idx-1]) and \
                            ema9[idx] > ema21[idx] and ema9[idx-1] <= ema21[idx-1]
            ema_cross_sell = not np.isnan(ema9[idx]) and not np.isnan(ema21[idx]) and \
                             not np.isnan(ema9[idx-1]) and not np.isnan(ema21[idx-1]) and \
                             ema9[idx] < ema21[idx] and ema9[idx-1] >= ema21[idx-1]
            
            # ATR-based SL/TP
            atr = talib.ATR(h, l, c, timeperiod=14)
            atr_val = float(atr[idx]) if not np.isnan(atr[idx]) else 0
            risk = atr_val * 1.5
            
            return {
                'bull_score': bull_score,
                'bear_score': bear_score,
                'bull_pct': bull_pct,
                'bear_pct': bear_pct,
                'bias': bias,
                'ema_cross_buy': ema_cross_buy,
                'ema_cross_sell': ema_cross_sell,
                'atr_risk': risk,
                'stop_loss_distance': risk,
                'tp1_distance': risk,
                'tp2_distance': risk * 2,
                'tp3_distance': risk * 3
            }
        except Exception as e:
            logger.error(f"SniperScore error: {e}")
            return {'bull_score': 0, 'bear_score': 0, 'bull_pct': 0, 'bear_pct': 0, 'bias': 'NEUTRAL'}


class PrecisionSniperConfluence:
    """Precision Sniper confluence scoring engine (from WillyAlgoTrader).
    Weights multiple indicators to determine signal grade."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  volumes: List[float]) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            v = np.array(volumes, dtype=float)
            
            ema_fast = talib.EMA(c, timeperiod=9)
            ema_slow = talib.EMA(c, timeperiod=21)
            ema_trend = talib.EMA(c, timeperiod=50)
            rsi = talib.RSI(c, timeperiod=14)
            macd, macd_signal, macd_hist = talib.MACD(c)
            adx = talib.ADX(h, l, c, timeperiod=14)
            plus_di = talib.PLUS_DI(h, l, c, timeperiod=14)
            minus_di = talib.MINUS_DI(h, l, c, timeperiod=14)
            vol_sma = talib.SMA(v, timeperiod=20)
            
            # VWAP approximation
            tp = (h + l + c) / 3
            cum_vol = np.cumsum(v)
            cum_tp_vol = np.cumsum(tp * v)
            vwap = np.where(cum_vol > 0, cum_tp_vol / cum_vol, c)
            
            idx = -1
            price = c[idx]
            
            def safe(arr, i=-1):
                return float(arr[i]) if not np.isnan(arr[i]) else 0
            
            # Bull confluence score (max ~10)
            bull_score = 0.0
            if safe(ema_fast) > safe(ema_slow): bull_score += 1.0
            if price > safe(ema_trend): bull_score += 1.0
            if 50 < safe(rsi) < 75: bull_score += 1.0
            if safe(macd_hist) > 0: bull_score += 1.0
            if safe(macd) > safe(macd_signal): bull_score += 1.0
            if price > safe(vwap): bull_score += 1.0
            if safe(vol_sma) > 0 and v[idx] > safe(vol_sma) * 1.2: bull_score += 1.0
            if safe(adx) > 25 and safe(plus_di) > safe(minus_di): bull_score += 1.0
            if price > safe(ema_fast): bull_score += 0.5
            
            # Bear confluence score
            bear_score = 0.0
            if safe(ema_fast) < safe(ema_slow): bear_score += 1.0
            if price < safe(ema_trend): bear_score += 1.0
            if 25 < safe(rsi) < 50: bear_score += 1.0
            if safe(macd_hist) < 0: bear_score += 1.0
            if safe(macd) < safe(macd_signal): bear_score += 1.0
            if price < safe(vwap): bear_score += 1.0
            if safe(vol_sma) > 0 and v[idx] > safe(vol_sma) * 1.2: bear_score += 1.0
            if safe(adx) > 25 and safe(minus_di) > safe(plus_di): bear_score += 1.0
            if price < safe(ema_fast): bear_score += 0.5
            
            # Grade
            max_score = max(bull_score, bear_score)
            if max_score >= 7.5:
                grade = "A+"
            elif max_score >= 6.5:
                grade = "A"
            elif max_score >= 5.5:
                grade = "B"
            elif max_score >= 4.5:
                grade = "C"
            else:
                grade = "D"
            
            # EMA cross signals
            ema_bull_cross = safe(ema_fast) > safe(ema_slow) and safe(ema_fast, -2) <= safe(ema_slow, -2)
            ema_bear_cross = safe(ema_fast) < safe(ema_slow) and safe(ema_fast, -2) >= safe(ema_slow, -2)
            
            # Signal generation
            signal = "neutral"
            if bull_score >= 5.5 and ema_bull_cross and 50 < safe(rsi) < 75:
                signal = "buy"
            elif bear_score >= 5.5 and ema_bear_cross and 25 < safe(rsi) < 50:
                signal = "sell"
            
            return {
                'bull_score': bull_score,
                'bear_score': bear_score,
                'grade': grade,
                'signal': signal,
                'adx': safe(adx),
                'trend_strength': 'STRONG' if safe(adx) > 25 else 'WEAK'
            }
        except Exception as e:
            logger.error(f"PrecisionSniper error: {e}")
            return {'bull_score': 0, 'bear_score': 0, 'grade': 'N/A', 'signal': 'neutral'}


class LinearRegressionChannel:
    """Fedra Algotrading LR indicator.
    Linear regression with deviation bands + SuperTrend filter."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  length: int = 10, dev_mult: float = 2.0) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            
            lr = talib.LINEARREG(c, timeperiod=length)
            lr_angle = talib.LINEARREG_ANGLE(c, timeperiod=length)
            stddev = talib.STDDEV(c, timeperiod=length)
            
            idx = -1
            lr_val = float(lr[idx]) if not np.isnan(lr[idx]) else c[idx]
            std_val = float(stddev[idx]) if not np.isnan(stddev[idx]) else 0
            angle = float(lr_angle[idx]) if not np.isnan(lr_angle[idx]) else 0
            
            upper = lr_val + std_val * dev_mult
            lower = lr_val - std_val * dev_mult
            
            price = c[idx]
            
            # EMAs for trend filter
            ema20 = talib.EMA(c, timeperiod=20)
            ema100 = talib.EMA(c, timeperiod=min(100, len(c) - 1))
            
            ema_filter = False
            if not np.isnan(ema20[idx]) and not np.isnan(ema100[idx]):
                ema_filter = ema20[idx] > ema100[idx]
            
            # SuperTrend approximation
            atr = talib.ATR(h, l, c, timeperiod=10)
            atr_val = float(atr[idx]) if not np.isnan(atr[idx]) else 0
            hl2 = (h + l) / 2
            st_upper = hl2[idx] + 3.0 * atr_val
            st_lower = hl2[idx] - 3.0 * atr_val
            supertrend_bullish = price > st_lower
            
            # Buy signal: price crosses below lower LR band + EMA filter bullish
            buy_signal = price <= lower and ema_filter
            
            return {
                'line': lr_val,
                'upper': upper,
                'lower': lower,
                'angle': angle,
                'above_line': price > lr_val,
                'ema_filter_bullish': ema_filter,
                'supertrend_bullish': supertrend_bullish,
                'supertrend_upper': st_upper,
                'supertrend_lower': st_lower,
                'buy_signal': buy_signal,
                'current_price': price
            }
        except Exception as e:
            logger.error(f"LinearRegression error: {e}")
            return {'line': 0, 'upper': 0, 'lower': 0, 'above_line': False}


class SwingProfile:
    """Swing Profile (from BigBeluga).
    Detects swing highs/lows and volume profiles at swing points."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  volumes: List[float], swing_len: int = 10) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            v = np.array(volumes, dtype=float)
            
            # Find swing highs and lows
            swing_highs = []
            swing_lows = []
            
            for i in range(swing_len, len(c) - swing_len):
                # Swing high: highest in window
                if h[i] == np.max(h[i - swing_len:i + swing_len + 1]):
                    swing_highs.append({'index': i, 'price': float(h[i]), 'volume': float(v[i])})
                # Swing low: lowest in window
                if l[i] == np.min(l[i - swing_len:i + swing_len + 1]):
                    swing_lows.append({'index': i, 'price': float(l[i]), 'volume': float(v[i])})
            
            # Determine trend
            last_high = swing_highs[-1]['price'] if swing_highs else 0
            last_low = swing_lows[-1]['price'] if swing_lows else 0
            prev_high = swing_highs[-2]['price'] if len(swing_highs) > 1 else 0
            prev_low = swing_lows[-2]['price'] if len(swing_lows) > 1 else 0
            
            if last_high > prev_high and last_low > prev_low:
                trend = "UPTREND"
            elif last_high < prev_high and last_low < prev_low:
                trend = "DOWNTREND"
            else:
                trend = "RANGING"
            
            # Volume profile at last swing
            total_volume = float(np.sum(v[-swing_len:]))
            buy_volume = float(np.sum(v[-swing_len:][c[-swing_len:] > c[-swing_len - 1:-1]]))
            sell_volume = total_volume - buy_volume
            delta = ((buy_volume - sell_volume) / total_volume * 100) if total_volume > 0 else 0
            
            return {
                'trend': trend,
                'last_high': last_high,
                'last_low': last_low,
                'prev_high': prev_high,
                'prev_low': prev_low,
                'swing_count': len(swing_highs) + len(swing_lows),
                'volume_delta': delta,
                'buy_volume_pct': (buy_volume / total_volume * 100) if total_volume > 0 else 50,
                'recent_swing_highs': swing_highs[-3:] if swing_highs else [],
                'recent_swing_lows': swing_lows[-3:] if swing_lows else []
            }
        except Exception as e:
            logger.error(f"SwingProfile error: {e}")
            return {'trend': 'UNKNOWN', 'last_high': 0, 'last_low': 0}


class FairValueGaps:
    """FVG Multi-Timeframe detector.
    Identifies Fair Value Gaps (price imbalances)."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  min_gap_pct: float = 0.001) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            
            gaps = []
            
            for i in range(2, len(c)):
                # Bullish FVG: gap between candle[i-2] high and candle[i] low
                if l[i] > h[i - 2]:
                    gap_size = (l[i] - h[i - 2]) / c[i]
                    if gap_size >= min_gap_pct:
                        mid = (l[i] + h[i - 2]) / 2
                        mitigated = c[-1] <= h[i - 2] if i < len(c) - 1 else False
                        gaps.append({
                            'type': 'BULLISH',
                            'low': float(h[i - 2]),
                            'high': float(l[i]),
                            'mid': float(mid),
                            'size_pct': float(gap_size * 100),
                            'mitigated': mitigated,
                            'bar_index': i
                        })
                
                # Bearish FVG: gap between candle[i] high and candle[i-2] low
                if h[i] < l[i - 2]:
                    gap_size = (l[i - 2] - h[i]) / c[i]
                    if gap_size >= min_gap_pct:
                        mid = (h[i] + l[i - 2]) / 2
                        mitigated = c[-1] >= l[i - 2] if i < len(c) - 1 else False
                        gaps.append({
                            'type': 'BEARISH',
                            'low': float(h[i]),
                            'high': float(l[i - 2]),
                            'mid': float(mid),
                            'size_pct': float(gap_size * 100),
                            'mitigated': mitigated,
                            'bar_index': i
                        })
            
            # Return only recent unmitigated gaps
            active_gaps = [g for g in gaps if not g['mitigated']][-5:]
            
            # Nearest support/resistance from FVGs
            current_price = c[-1]
            nearest_support = None
            nearest_resistance = None
            
            for g in active_gaps:
                if g['type'] == 'BULLISH' and g['mid'] < current_price:
                    if nearest_support is None or g['mid'] > nearest_support:
                        nearest_support = g['mid']
                if g['type'] == 'BEARISH' and g['mid'] > current_price:
                    if nearest_resistance is None or g['mid'] < nearest_resistance:
                        nearest_resistance = g['mid']
            
            return {
                'gaps': active_gaps,
                'total_bullish': len([g for g in active_gaps if g['type'] == 'BULLISH']),
                'total_bearish': len([g for g in active_gaps if g['type'] == 'BEARISH']),
                'nearest_fvg_support': nearest_support,
                'nearest_fvg_resistance': nearest_resistance
            }
        except Exception as e:
            logger.error(f"FVG error: {e}")
            return {'gaps': [], 'total_bullish': 0, 'total_bearish': 0}


class CommissionAwareSignalEngine:
    """Signal engine that considers exchange commissions for high-frequency trading."""
    
    @staticmethod
    def evaluate_trade_viability(
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        commission_rate: float = 0.001,  # 0.1% per trade (Binance default)
        min_rr_ratio: float = 2.0
    ) -> Dict:
        """Evaluate if a trade is viable after commissions."""
        
        # Total commission (entry + exit)
        total_commission_pct = commission_rate * 2
        total_commission = entry_price * total_commission_pct
        
        # Potential profit/loss
        potential_profit = abs(take_profit - entry_price)
        potential_loss = abs(entry_price - stop_loss)
        
        # Net profit after commissions
        net_profit = potential_profit - total_commission
        net_loss = potential_loss + total_commission
        
        # Risk/Reward ratio (net)
        rr_ratio = net_profit / net_loss if net_loss > 0 else 0
        
        # Is it viable?
        viable = net_profit > 0 and rr_ratio >= min_rr_ratio
        
        # Profit factor
        profit_pct = (net_profit / entry_price) * 100
        
        return {
            'viable': viable,
            'rr_ratio': round(rr_ratio, 2),
            'net_profit': round(net_profit, 8),
            'net_loss': round(net_loss, 8),
            'total_commission': round(total_commission, 8),
            'profit_pct': round(profit_pct, 4),
            'commission_impact_pct': round(total_commission_pct * 100, 3),
            'min_move_to_profit': round(total_commission, 8)
        }


class IchimokuCloud:
    """Ichimoku Kinko Hyo - Apicode implementation.
    Tenkan, Kijun, Senkou Span A/B, Chikou."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  tenkan_period: int = 9, kijun_period: int = 26, senkou_b_period: int = 52) -> Dict:
        try:
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            c = np.array(closes, dtype=float)
            
            def midline(high_arr, low_arr, period):
                vals = []
                for i in range(len(high_arr)):
                    if i < period - 1:
                        vals.append(float('nan'))
                    else:
                        hh = np.max(high_arr[i - period + 1:i + 1])
                        ll = np.min(low_arr[i - period + 1:i + 1])
                        vals.append((hh + ll) / 2)
                return np.array(vals)
            
            tenkan = midline(h, l, tenkan_period)
            kijun = midline(h, l, kijun_period)
            senkou_a = (tenkan + kijun) / 2
            senkou_b = midline(h, l, senkou_b_period)
            
            idx = -1
            price = c[idx]
            tenkan_val = float(tenkan[idx]) if not np.isnan(tenkan[idx]) else 0
            kijun_val = float(kijun[idx]) if not np.isnan(kijun[idx]) else 0
            span_a = float(senkou_a[idx]) if not np.isnan(senkou_a[idx]) else 0
            span_b = float(senkou_b[idx]) if not np.isnan(senkou_b[idx]) else 0
            
            # TK Cross signals
            tk_cross_bull = (not np.isnan(tenkan[idx]) and not np.isnan(kijun[idx]) and
                            not np.isnan(tenkan[idx-1]) and not np.isnan(kijun[idx-1]) and
                            tenkan[idx] > kijun[idx] and tenkan[idx-1] <= kijun[idx-1])
            tk_cross_bear = (not np.isnan(tenkan[idx]) and not np.isnan(kijun[idx]) and
                            not np.isnan(tenkan[idx-1]) and not np.isnan(kijun[idx-1]) and
                            tenkan[idx] < kijun[idx] and tenkan[idx-1] >= kijun[idx-1])
            
            above_cloud = price > max(span_a, span_b)
            below_cloud = price < min(span_a, span_b)
            cloud_bullish = span_a > span_b
            
            signal = "neutral"
            if tk_cross_bull and above_cloud:
                signal = "strong_buy"
            elif tk_cross_bull:
                signal = "buy"
            elif tk_cross_bear and below_cloud:
                signal = "strong_sell"
            elif tk_cross_bear:
                signal = "sell"
            
            return {
                'tenkan': tenkan_val, 'kijun': kijun_val,
                'senkou_a': span_a, 'senkou_b': span_b,
                'above_cloud': bool(above_cloud), 'below_cloud': bool(below_cloud),
                'cloud_bullish': bool(cloud_bullish),
                'tk_cross_bull': bool(tk_cross_bull), 'tk_cross_bear': bool(tk_cross_bear),
                'signal': signal
            }
        except Exception as e:
            logger.error(f"Ichimoku error: {e}")
            return {'tenkan': 0, 'kijun': 0, 'signal': 'neutral'}


class NeuroTrendII:
    """NeuroTrend II - Adaptive AI Trend Engine (from Apicode).
    Adaptive EMAs, slope forecasting, confidence scoring, reversal detection."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  volumes: List[float], base_fast: int = 12, base_slow: int = 24) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            
            atr = talib.ATR(h, l, c, timeperiod=14)
            rsi = talib.RSI(c, timeperiod=14)
            adx = talib.ADX(h, l, c, timeperiod=14)
            plus_di = talib.PLUS_DI(h, l, c, timeperiod=14)
            minus_di = talib.MINUS_DI(h, l, c, timeperiod=14)
            
            idx = -1
            atr_val = float(atr[idx]) if not np.isnan(atr[idx]) else 0
            rsi_val = float(rsi[idx]) if not np.isnan(rsi[idx]) else 50
            adx_val = float(adx[idx]) if not np.isnan(adx[idx]) else 0
            
            # Adaptive EMA
            vol_factor = atr_val / c[idx] if c[idx] > 0 else 0
            momentum_factor = (rsi_val - 50) / 100
            
            fast_len = max(2, base_fast - vol_factor * 5 + momentum_factor * 5)
            slow_len = max(3, base_slow + vol_factor * 5 - momentum_factor * 5)
            
            ema_fast = talib.EMA(c, timeperiod=int(fast_len))
            ema_slow = talib.EMA(c, timeperiod=int(slow_len))
            
            ef = float(ema_fast[idx]) if not np.isnan(ema_fast[idx]) else c[idx]
            es = float(ema_slow[idx]) if not np.isnan(ema_slow[idx]) else c[idx]
            
            # Slope metrics
            slope_norm = (ef - es) / atr_val if atr_val > 0 else 0
            slope_deg = np.arctan(slope_norm) * 180 / np.pi
            slope_power = slope_deg * (1 + vol_factor + momentum_factor)
            
            # Trend classifier
            is_impulse = abs(slope_power) > 20
            is_cooling = 10 < abs(slope_power) <= 20
            is_reversal = rsi_val < 40 or (len(c) > 2 and abs(slope_deg - np.arctan((float(ema_fast[idx-1] or 0) - float(ema_slow[idx-1] or 0)) / max(float(atr[idx-1] or 1), 0.0001)) * 180 / np.pi) > 30)
            
            trend_dir = "Bullish" if slope_power > 0 else "Bearish"
            
            phase = "Impulse" if is_impulse else "Cooling" if is_cooling else "Reversal" if is_reversal else "Neutral"
            
            # Confidence score
            safe_di_plus = float(plus_di[idx]) if not np.isnan(plus_di[idx]) else 0
            safe_di_minus = float(minus_di[idx]) if not np.isnan(minus_di[idx]) else 0
            trend_strength = min(adx_val, 50) / 50
            direction_bias = abs(safe_di_plus - safe_di_minus) / 100
            vol_ratio = min(atr_val / max(abs(ef - es), 0.0001), 3.0) / 3.0
            
            confidence_raw = (trend_strength + direction_bias + abs(slope_norm) + (1 - vol_ratio)) / 4
            confidence = min(round(confidence_raw * 100), 100)
            
            # Buy/Sell signals
            buy_signal = slope_deg > 0 and (len(c) > 2 and np.arctan((float(ema_fast[idx-1] or 0) - float(ema_slow[idx-1] or 0)) / max(float(atr[idx-1] or 1), 0.0001)) * 180 / np.pi <= 0)
            sell_signal = slope_deg < 0 and (len(c) > 2 and np.arctan((float(ema_fast[idx-1] or 0) - float(ema_slow[idx-1] or 0)) / max(float(atr[idx-1] or 1), 0.0001)) * 180 / np.pi >= 0)
            
            return {
                'trend_direction': trend_dir,
                'phase': phase,
                'slope_power': round(float(slope_power), 2),
                'confidence': int(confidence),
                'is_impulse': bool(is_impulse),
                'is_reversal': bool(is_reversal),
                'buy_signal': bool(buy_signal),
                'sell_signal': bool(sell_signal),
                'adx': round(adx_val, 2),
                'rsi': round(rsi_val, 2)
            }
        except Exception as e:
            logger.error(f"NeuroTrend error: {e}")
            return {'trend_direction': 'Neutral', 'phase': 'Unknown', 'confidence': 0}


class SuperTrendedRSI:
    """SuperTrend applied to RSI values (from Apicode).
    Detects overbought/oversold reversals."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  rsi_period: int = 14, st_factor: float = 0.8, st_atr_period: int = 10) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            
            rsi = talib.RSI(c, timeperiod=rsi_period)
            rsi_vals = rsi[~np.isnan(rsi)]
            
            if len(rsi_vals) < st_atr_period + 2:
                return {'rsi': 50, 'signal': 'neutral', 'trend': 'neutral'}
            
            # SuperTrend on RSI
            rsi_clean = rsi_vals
            rsi_high = np.array([max(rsi_clean[max(0, i - st_atr_period):i + 1]) for i in range(len(rsi_clean))])
            rsi_low = np.array([min(rsi_clean[max(0, i - st_atr_period):i + 1]) for i in range(len(rsi_clean))])
            rsi_tr = rsi_high - rsi_low
            rsi_atr = np.convolve(rsi_tr, np.ones(st_atr_period) / st_atr_period, mode='same')
            
            upper = rsi_clean + st_factor * rsi_atr
            lower = rsi_clean - st_factor * rsi_atr
            
            trend = np.ones(len(rsi_clean))
            st = np.zeros(len(rsi_clean))
            
            for i in range(1, len(rsi_clean)):
                if rsi_clean[i] > upper[i - 1]:
                    trend[i] = -1
                elif rsi_clean[i] < lower[i - 1]:
                    trend[i] = 1
                else:
                    trend[i] = trend[i - 1]
                
                st[i] = lower[i] if trend[i] == -1 else upper[i]
            
            last_rsi = float(rsi_clean[-1])
            last_trend = int(trend[-1])
            
            # Cross signals
            cross_down = last_trend == 1 and trend[-2] == -1 and last_rsi > 70
            cross_up = last_trend == -1 and trend[-2] == 1 and last_rsi < 30
            
            signal = "sell" if cross_down else "buy" if cross_up else "neutral"
            
            return {
                'rsi': round(last_rsi, 2),
                'supertrend_value': round(float(st[-1]), 2),
                'trend': 'bullish' if last_trend == -1 else 'bearish',
                'overbought': bool(last_rsi > 70),
                'oversold': bool(last_rsi < 30),
                'signal': signal,
                'cross_down': bool(cross_down),
                'cross_up': bool(cross_up)
            }
        except Exception as e:
            logger.error(f"SuperTrendedRSI error: {e}")
            return {'rsi': 50, 'signal': 'neutral', 'trend': 'neutral'}


class TurtleChannels:
    """Turtle Channels (Apicode version).
    Breakout-based entry/exit system."""
    
    @staticmethod
    def calculate(closes: List[float], highs: List[float], lows: List[float],
                  entry_length: int = 25, exit_length: int = 20) -> Dict:
        try:
            c = np.array(closes, dtype=float)
            h = np.array(highs, dtype=float)
            l = np.array(lows, dtype=float)
            
            if len(c) < max(entry_length, exit_length) + 2:
                return {'signal': 'neutral', 'upper': 0, 'lower': 0}
            
            # Channel calculation
            upper_channel = np.array([np.max(h[max(0, i - entry_length + 1):i + 1]) for i in range(len(h))])
            lower_channel = np.array([np.min(l[max(0, i - entry_length + 1):i + 1]) for i in range(len(l))])
            
            exit_upper = np.array([np.max(h[max(0, i - exit_length + 1):i + 1]) for i in range(len(h))])
            exit_lower = np.array([np.min(l[max(0, i - exit_length + 1):i + 1]) for i in range(len(l))])
            
            idx = -1
            
            # Entry signals
            buy_entry = h[idx] >= upper_channel[idx - 1]
            sell_entry = l[idx] <= lower_channel[idx - 1]
            
            # Exit signals
            buy_exit = l[idx] <= exit_lower[idx - 1]
            sell_exit = h[idx] >= exit_upper[idx - 1]
            
            signal = "neutral"
            if buy_entry:
                signal = "buy"
            elif sell_entry:
                signal = "sell"
            elif buy_exit:
                signal = "exit_long"
            elif sell_exit:
                signal = "exit_short"
            
            return {
                'upper_channel': round(float(upper_channel[idx]), 2),
                'lower_channel': round(float(lower_channel[idx]), 2),
                'exit_upper': round(float(exit_upper[idx]), 2),
                'exit_lower': round(float(exit_lower[idx]), 2),
                'buy_entry': bool(buy_entry),
                'sell_entry': bool(sell_entry),
                'buy_exit': bool(buy_exit),
                'sell_exit': bool(sell_exit),
                'signal': signal,
                'channel_width_pct': round(float((upper_channel[idx] - lower_channel[idx]) / c[idx] * 100), 2)
            }
        except Exception as e:
            logger.error(f"TurtleChannels error: {e}")
            return {'signal': 'neutral', 'upper': 0, 'lower': 0}
