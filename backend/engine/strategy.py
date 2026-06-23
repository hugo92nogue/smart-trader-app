"""
Lógica de decisión de trading — función pura, parametrizable y reutilizable.

La usan el motor en vivo (auto_trader), el backtester y el optimizador, para
garantizar que lo que se optimiza/backtestea es EXACTAMENTE lo que se opera.

Dos modos:
  - "momentum": confluencia de 5 indicadores a favor de la tendencia (original).
  - "pullback": reversión a la media DENTRO de la tendencia — comprar retrocesos
    (RSI sobrevendido) en tendencia alcista, vender rebotes en tendencia bajista.
    Tiene mejor ventaja estadística en cripto que perseguir el momentum.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from advanced_indicators import (
    SniperScore, PrecisionSniperConfluence, IchimokuCloud,
    NeuroTrendII, TurtleChannels,
)

MIN_CANDLES = 210    # necesitamos EMA200 para el filtro de tendencia


@dataclass
class StrategyParams:
    mode: str = "pullback"          # "pullback" | "momentum" | "volume"
    ema_fast: int = 50
    ema_slow: int = 200
    rsi_period: int = 14
    rsi_buy: float = 35.0           # pullback: RSI por debajo → comprar el retroceso
    rsi_sell: float = 65.0          # pullback: RSI por encima → vender el rebote
    atr_period: int = 14
    sl_atr: float = 1.5
    tp_atr: float = 3.0
    tp2_atr: float = 5.0
    min_score: int = 4              # momentum: votos netos para abrir
    # modo "volume": detecta entrada de demanda (pico de volumen + dirección + tendencia)
    vol_period: int = 20            # media del volumen
    vol_surge: float = 2.0          # volumen actual > media × este factor
    max_hold: int = 24             # salida forzada tras N velas (24 = 24h en 1h)


def _ema_series(series, period):
    return pd.Series(series).ewm(span=period, adjust=False).mean()


def _rsi_series(series, period=14):
    s = pd.Series(series)
    d = s.diff()
    gain = d.where(d > 0, 0.0)
    loss = -d.where(d < 0, 0.0)
    ag = gain.ewm(com=period - 1, adjust=False).mean()
    al = loss.ewm(com=period - 1, adjust=False).mean()
    return 100 - (100 / (1 + ag / al.replace(0, 1e-9)))


def _atr_series(highs, lows, closes, period=14):
    h, l, c = pd.Series(highs), pd.Series(lows), pd.Series(closes)
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _sma_series(series, period):
    return pd.Series(series).rolling(period).mean()


def _levels(signal: str, price: float, atr: float, p: StrategyParams) -> Dict:
    if signal == "buy":
        sl = price - atr * p.sl_atr
        tp1 = price + atr * p.tp_atr
        tp2 = price + atr * p.tp2_atr
    else:
        sl = price + atr * p.sl_atr
        tp1 = price - atr * p.tp_atr
        tp2 = price - atr * p.tp2_atr
    risk = abs(price - sl)
    reward = abs(tp1 - price)
    return {
        "stop_loss": round(sl, 8),
        "take_profit_1": round(tp1, 8),
        "take_profit_2": round(tp2, 8),
        "rr_ratio": round(reward / risk, 2) if risk > 0 else 0,
    }


def _hold(confidence=0.0):
    return {"signal": "hold", "confidence": confidence, "rr_ratio": 0}


def evaluate_signal(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    volumes: List[float],
    params: Optional[StrategyParams] = None,
) -> Dict:
    """Devuelve: signal ('buy'|'sell'|'hold'), confidence, entry, stop_loss, tp1/2, rr_ratio, atr."""
    p = params or StrategyParams()
    if len(closes) < MIN_CANDLES:
        return _hold()

    price = closes[-1]
    atr = float(_atr_series(highs, lows, closes, p.atr_period).iloc[-1]) or price * 0.01
    ema_fast = float(_ema_series(closes, p.ema_fast).iloc[-1])
    ema_slow = float(_ema_series(closes, p.ema_slow).iloc[-1])
    uptrend = ema_fast > ema_slow

    if p.mode == "volume":
        # Detecta ENTRADA DE DEMANDA: pico de volumen + dirección + a favor de tendencia.
        vol_ma = float(_sma_series(volumes, p.vol_period).iloc[-1]) if len(volumes) >= p.vol_period else 0
        surge = vol_ma > 0 and volumes[-1] > vol_ma * p.vol_surge
        direction_up = closes[-1] > closes[-2]
        if surge and direction_up and uptrend and price > ema_slow:
            signal = "buy"
        elif surge and (not direction_up) and (not uptrend) and price < ema_slow:
            signal = "sell"
        else:
            return _hold()
        confidence = round(min(volumes[-1] / (vol_ma * p.vol_surge), 1.5) / 1.5, 2) if vol_ma else 0.5
    elif p.mode == "pullback":
        rsi = float(_rsi_series(closes, p.rsi_period).iloc[-1])
        # Comprar el retroceso en tendencia alcista; vender el rebote en bajista.
        if uptrend and price > ema_slow and rsi < p.rsi_buy:
            signal = "buy"
        elif (not uptrend) and price < ema_slow and rsi > p.rsi_sell:
            signal = "sell"
        else:
            return _hold()
        confidence = round(min(abs(rsi - 50) / 50, 1.0), 2)
    else:  # momentum (confluencia de 5 indicadores)
        sniper = SniperScore.calculate(closes, highs, lows, volumes)
        confluence = PrecisionSniperConfluence.calculate(closes, highs, lows, volumes)
        ichimoku = IchimokuCloud.calculate(closes, highs, lows)
        neuro = NeuroTrendII.calculate(closes, highs, lows, volumes)
        turtle = TurtleChannels.calculate(closes, highs, lows)
        votes = []
        bias = sniper.get("bias", "NEUTRAL")
        votes.append(1 if "BULL" in bias else -1 if "BEAR" in bias else 0)
        cs = confluence.get("signal", "neutral")
        votes.append(1 if cs == "buy" else -1 if cs == "sell" else 0)
        votes.append(1 if ichimoku.get("above_cloud") else -1 if ichimoku.get("below_cloud") else 0)
        votes.append(1 if neuro.get("trend_direction") == "Bullish" else -1)
        ts = turtle.get("signal", "neutral")
        votes.append(1 if ts == "buy" else -1 if ts == "sell" else 0)
        score = sum(votes)
        confidence = round(abs(score) / len(votes), 2)
        if score >= p.min_score and uptrend:
            signal = "buy"
        elif score <= -p.min_score and not uptrend:
            signal = "sell"
        else:
            return _hold(confidence)

    levels = _levels(signal, price, atr, p)
    return {"signal": signal, "confidence": confidence, "entry": price, "atr": atr, **levels}
