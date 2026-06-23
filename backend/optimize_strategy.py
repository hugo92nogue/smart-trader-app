"""
Optimizador de estrategia — grid search con validación train/test.

Precomputa indicadores (vectorizado) para que el grid sea rápido, prueba cientos
de combinaciones de parámetros sobre VARIOS símbolos, y valida los mejores en datos
OUT-OF-SAMPLE (que no se usaron para optimizar) para evitar sobre-ajuste.

Uso:  cd backend && py -3.11 optimize_strategy.py
"""
import itertools
import logging
import math
import sys
from dataclasses import dataclass, replace
from typing import Dict, List

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from binance_client import BinanceSpotClient
from engine.strategy import StrategyParams, _ema_series, _rsi_series, _atr_series, _sma_series

logging.disable(logging.WARNING)

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT"]
INTERVAL = sys.argv[1] if len(sys.argv) > 1 else "15m"  # py optimize_strategy.py 1h
CANDLES = 5000   # paginado (>1000) para validación walk-forward seria
WARMUP = 210
# Walk-forward: ventana de entrenamiento, ventana de validación, paso
WF_TRAIN = 1500
WF_TEST = 750
WF_STEP = 750
COMMISSION = 0.001
RISK_PER_TRADE = 0.02
TRAIL_ACT_ATR = 1.0
TRAIL_DIST_ATR = 2.0


@dataclass
class Series:
    close: np.ndarray
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray


def fetch(symbol: str) -> Series:
    bc = BinanceSpotClient()
    k = bc.get_klines_paginated(symbol, INTERVAL, CANDLES)
    return Series(
        close=np.array([float(x[4]) for x in k]),
        high=np.array([float(x[2]) for x in k]),
        low=np.array([float(x[3]) for x in k]),
        volume=np.array([float(x[5]) for x in k]),
    )


def precompute(s: Series, p: StrategyParams):
    ema_fast = _ema_series(s.close, p.ema_fast).to_numpy()
    ema_slow = _ema_series(s.close, p.ema_slow).to_numpy()
    rsi = _rsi_series(s.close, p.rsi_period).to_numpy()
    atr = _atr_series(s.high, s.low, s.close, p.atr_period).to_numpy()
    vol_ma = _sma_series(s.volume, p.vol_period).to_numpy()
    return ema_fast, ema_slow, rsi, atr, vol_ma


def _entry_signal(p, i, price, ema_fast, ema_slow, rsi, vol_ma, s):
    """Devuelve 'buy'|'sell'|None según el modo de la estrategia."""
    uptrend = ema_fast[i] > ema_slow[i]
    if p.mode == "volume":
        if np.isnan(vol_ma[i]) or vol_ma[i] <= 0:
            return None
        surge = s.volume[i] > vol_ma[i] * p.vol_surge
        direction_up = s.close[i] > s.close[i - 1]
        if surge and direction_up and uptrend and price > ema_slow[i]:
            return "buy"
        if surge and (not direction_up) and (not uptrend) and price < ema_slow[i]:
            return "sell"
        return None
    if p.mode == "volume_fade":
        # Contrario: un pico de volumen marca AGOTAMIENTO → desvanecerlo.
        if np.isnan(vol_ma[i]) or vol_ma[i] <= 0:
            return None
        surge = s.volume[i] > vol_ma[i] * p.vol_surge
        direction_up = s.close[i] > s.close[i - 1]
        if surge and direction_up:       # pico de compra → esperar reversión a la baja
            return "sell"
        if surge and (not direction_up):  # pico de venta → esperar rebote
            return "buy"
        return None
    # pullback
    if np.isnan(rsi[i]):
        return None
    if uptrend and price > ema_slow[i] and rsi[i] < p.rsi_buy:
        return "buy"
    if (not uptrend) and price < ema_slow[i] and rsi[i] > p.rsi_sell:
        return "sell"
    return None


def backtest_fast(s: Series, p: StrategyParams, start: int, end: int,
                  use_trailing: bool = True) -> Dict:
    """Backtest vectorizado (modos pullback y volume) con salida por tiempo máximo."""
    ema_fast, ema_slow, rsi, atr, vol_ma = precompute(s, p)
    balance = 10_000.0
    initial = balance
    equity = [balance]
    pnls: List[float] = []

    in_pos = False
    side = ""
    entry = sl = tp = qty = atr_e = 0.0
    entry_i = 0

    end = min(end, len(s.close))
    for i in range(max(start, WARMUP), end):
        price = s.close[i]
        hi, lo = s.high[i], s.low[i]

        if in_pos:
            exit_price = None
            if side == "buy":
                if use_trailing and hi >= entry + atr_e * TRAIL_ACT_ATR:
                    sl = max(sl, hi - atr_e * TRAIL_DIST_ATR)
                if lo <= sl:
                    exit_price = sl
                elif hi >= tp:
                    exit_price = tp
            else:
                if use_trailing and lo <= entry - atr_e * TRAIL_ACT_ATR:
                    sl = min(sl, lo + atr_e * TRAIL_DIST_ATR)
                if hi >= sl:
                    exit_price = sl
                elif lo <= tp:
                    exit_price = tp
            # Salida por tiempo máximo (24 velas = 24h en 1h)
            if exit_price is None and p.max_hold > 0 and (i - entry_i) >= p.max_hold:
                exit_price = price
            if exit_price is not None:
                gross = (exit_price - entry) * qty
                if side == "sell":
                    gross = -gross
                commission = (entry + exit_price) * qty * COMMISSION
                pnl = gross - commission
                balance += pnl
                pnls.append(pnl)
                equity.append(balance)
                in_pos = False
                continue

        if not in_pos:
            if np.isnan(ema_slow[i]) or np.isnan(atr[i]):
                continue
            sig = _entry_signal(p, i, price, ema_fast, ema_slow, rsi, vol_ma, s)
            if sig:
                entry = price
                atr_e = atr[i]
                entry_i = i
                if sig == "buy":
                    sl = entry - atr_e * p.sl_atr
                    tp = entry + atr_e * p.tp_atr
                else:
                    sl = entry + atr_e * p.sl_atr
                    tp = entry - atr_e * p.tp_atr
                risk_unit = abs(entry - sl)
                if risk_unit <= 0:
                    continue
                qty = (balance * RISK_PER_TRADE) / risk_unit
                side = sig
                in_pos = True

    return _metrics(pnls, equity, balance, initial)


def _metrics(pnls, equity, balance, initial) -> Dict:
    n = len(pnls)
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x <= 0]
    gp = sum(wins)
    gl = abs(sum(losses))
    peak, max_dd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak if peak > 0 else 0)
    rets = [x / initial for x in pnls]
    sharpe = 0.0
    if len(rets) > 1:
        mean = sum(rets) / len(rets)
        std = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1))
        if std > 0:
            sharpe = (mean / std) * math.sqrt(len(rets))
    return {
        "trades": n,
        "win_rate": round(len(wins) / n * 100, 1) if n else 0,
        "return_pct": round((balance - initial) / initial * 100, 2),
        "profit_factor": round(gp / gl, 3) if gl > 0 else (gp if gp else 0),
        "gross_profit": gp,
        "gross_loss": gl,
        "max_dd": round(max_dd * 100, 2),
        "sharpe": round(sharpe, 2),
    }


def aggregate(results: List[Dict]) -> Dict:
    """Agrupa TODOS los trades de los símbolos (PF y retorno reales, no promedios engañosos)."""
    total_trades = sum(r["trades"] for r in results)
    if total_trades == 0:
        return {"trades": 0, "avg_return": 0, "pooled_pf": 0, "avg_win": 0, "avg_dd": 0}
    # PF agrupado = suma de ganancias brutas / suma de pérdidas brutas (honesto)
    total_gp = sum(r["gross_profit"] for r in results)
    total_gl = sum(r["gross_loss"] for r in results)
    pooled_pf = round(total_gp / total_gl, 3) if total_gl > 0 else (round(total_gp, 2) if total_gp else 0)
    avg_return = sum(r["return_pct"] for r in results) / len(results)
    avg_win = sum(r["win_rate"] * r["trades"] for r in results) / total_trades
    avg_dd = sum(r["max_dd"] for r in results) / len(results)
    return {
        "trades": total_trades,
        "avg_return": round(avg_return, 2),
        "pooled_pf": pooled_pf,
        "avg_win": round(avg_win, 1),
        "avg_dd": round(avg_dd, 2),
    }


MODE = sys.argv[2] if len(sys.argv) > 2 else "volume"  # py optimize_strategy.py 1h volume

GRIDS = {
    "pullback": {
        "rsi_buy": [25, 30, 35, 40],
        "rsi_sell": [60, 65, 70, 75],
        "sl_atr": [1.0, 1.5, 2.0],
        "tp_atr": [2.0, 3.0, 4.0],
    },
    "volume": {
        "vol_surge": [1.5, 2.0, 2.5, 3.0],
        "sl_atr": [1.0, 1.5, 2.0],
        "tp_atr": [2.0, 3.0, 4.0],
        "max_hold": [12, 24],   # horas máximas de retención (en velas de 1h)
    },
    "volume_fade": {
        "vol_surge": [2.0, 2.5, 3.0, 4.0],
        "sl_atr": [1.0, 1.5, 2.0],
        "tp_atr": [1.5, 2.0, 3.0],
        "max_hold": [6, 12, 24],
    },
}
GRID = GRIDS[MODE]


def optimize_window(data, train_start, train_end):
    """Grid search en [train_start, train_end). Devuelve los mejores params por PF agrupado."""
    keys = list(GRID.keys())
    best = None
    for combo in itertools.product(*GRID.values()):
        params = dict(zip(keys, combo))
        p = StrategyParams(mode=MODE, **params)
        res = [backtest_fast(data[sym], p, train_start, train_end) for sym in SYMBOLS]
        agg = aggregate(res)
        score = agg["pooled_pf"] if agg["trades"] >= 15 else 0
        if best is None or score > best[0]:
            best = (score, agg, params)
    return best


def main():
    print(f"MODO: {MODE} | TIMEFRAME: {INTERVAL}")
    print(f"Descargando {len(SYMBOLS)} símbolos (~{CANDLES} velas {INTERVAL}, paginado)...")
    data = {sym: fetch(sym) for sym in SYMBOLS}
    n = min(len(s.close) for s in data.values())
    print(f"Velas reales por símbolo: {n}\n")

    # ── WALK-FORWARD: optimiza en train, valida en el test SIGUIENTE, avanza ──
    print(f"=== WALK-FORWARD (train={WF_TRAIN}, test={WF_TEST}, step={WF_STEP}) ===")
    print("Cada fold optimiza en datos pasados y valida en datos futuros que NO vio.\n")

    fold = 0
    oos_all = []   # resultados out-of-sample agregados de todos los folds
    start = WARMUP
    while start + WF_TRAIN + WF_TEST <= n:
        train_start = start
        train_end = start + WF_TRAIN
        test_end = min(train_end + WF_TEST, n)
        fold += 1

        score, agg_is, params = optimize_window(data, train_start, train_end)
        # Validar los params ganadores en el tramo de test (futuro no visto)
        res_oos = [backtest_fast(data[sym], StrategyParams(mode=MODE, **params), train_end, test_end)
                   for sym in SYMBOLS]
        agg_oos = aggregate(res_oos)
        oos_all.extend(res_oos)

        v = "[OK]" if agg_oos["pooled_pf"] >= 1.0 else "[X]"
        print(f"Fold {fold}: best={params}")
        print(f"   train: PF={agg_is['pooled_pf']} ret={agg_is['avg_return']}%  ->  "
              f"test(OOS): PF={agg_oos['pooled_pf']} ret={agg_oos['avg_return']}% "
              f"win={agg_oos['avg_win']}% trades={agg_oos['trades']} {v}")
        start += WF_STEP

    # ── Veredicto agregado de TODA la validación walk-forward ──
    final = aggregate(oos_all)
    print("\n=== VEREDICTO WALK-FORWARD (agregado de todos los folds OOS) ===")
    print(f"   PF agrupado: {final['pooled_pf']}")
    print(f"   Retorno medio por fold/símbolo: {final['avg_return']}%")
    print(f"   Win rate: {final['avg_win']}%   Trades totales: {final['trades']}")
    if final["pooled_pf"] >= 1.05 and final["trades"] >= 50:
        print("   >>> La estrategia muestra ventaja ROBUSTA fuera de muestra.")
    else:
        print("   >>> SIN ventaja robusta. PF≈1 o <1 en datos no vistos = no rentable tras costes.")


if __name__ == "__main__":
    main()
