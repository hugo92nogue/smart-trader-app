"""
Motor de backtesting — replay de la estrategia sobre datos históricos.

Camina la serie vela a vela, abre/cierra trades con la MISMA lógica que el motor
en vivo (engine.strategy), aplica SL/TP y trailing stop, y reporta métricas
profesionales: win rate, PnL, drawdown máximo, Sharpe, profit factor.
"""
import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from engine.strategy import evaluate_signal, MIN_CANDLES, StrategyParams

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    side: str
    entry_index: int
    entry_price: float
    atr: float = 0.0
    exit_index: int = 0
    exit_price: float = 0.0
    reason: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class BacktestConfig:
    initial_balance: float = 10_000.0
    risk_per_trade_pct: float = 0.02
    commission_rate: float = 0.001
    use_trailing_stop: bool = True
    trailing_atr_mult: float = 2.0       # distancia del trailing en múltiplos de ATR
    trailing_activation_atr: float = 1.0  # solo trailing tras +1×ATR de beneficio
    warmup: int = MIN_CANDLES


class Backtester:
    def __init__(self, config: BacktestConfig = None, params: StrategyParams = None):
        self.config = config or BacktestConfig()
        self.params = params or StrategyParams()

    def run(self, candles: List[Dict], symbol: str = "") -> Dict:
        """
        candles: lista de dicts {time, open, high, low, close, volume}.
        Devuelve métricas + curva de equity + lista de trades.
        """
        c = self.config
        closes = [float(k["close"]) for k in candles]
        highs = [float(k["high"]) for k in candles]
        lows = [float(k["low"]) for k in candles]
        volumes = [float(k.get("volume", 0)) for k in candles]
        n = len(closes)

        if n < c.warmup + 10:
            return {"error": f"Datos insuficientes: {n} velas (mínimo {c.warmup + 10})"}

        balance = c.initial_balance
        equity_curve = [balance]
        trades: List[BacktestTrade] = []
        open_trade: Optional[BacktestTrade] = None
        qty = 0.0
        stop_loss = take_profit = trail = 0.0

        for i in range(c.warmup, n):
            price = closes[i]
            high_i = highs[i]
            low_i = lows[i]

            # ── Gestión de posición abierta ──
            if open_trade is not None:
                exit_price = None
                reason = ""

                atr_t = open_trade.atr
                if open_trade.side == "buy":
                    # Trailing solo tras estar +activation×ATR en beneficio (deja respirar al trade).
                    if c.use_trailing_stop and high_i >= open_trade.entry_price + atr_t * c.trailing_activation_atr:
                        new_stop = high_i - atr_t * c.trailing_atr_mult
                        stop_loss = max(stop_loss, new_stop)
                    if low_i <= stop_loss:
                        exit_price, reason = stop_loss, "SL"
                    elif high_i >= take_profit:
                        exit_price, reason = take_profit, "TP"
                else:  # sell
                    if c.use_trailing_stop and low_i <= open_trade.entry_price - atr_t * c.trailing_activation_atr:
                        new_stop = low_i + atr_t * c.trailing_atr_mult
                        stop_loss = min(stop_loss, new_stop)
                    if high_i >= stop_loss:
                        exit_price, reason = stop_loss, "SL"
                    elif low_i <= take_profit:
                        exit_price, reason = take_profit, "TP"

                # Salida por tiempo máximo (p.ej. 24 velas = 24h en 1h).
                if exit_price is None and self.params.max_hold > 0 and (i - open_trade.entry_index) >= self.params.max_hold:
                    exit_price, reason = price, "TIME"

                if exit_price is not None:
                    gross = (exit_price - open_trade.entry_price) * qty
                    if open_trade.side == "sell":
                        gross = -gross
                    commission = (open_trade.entry_price + exit_price) * qty * c.commission_rate
                    pnl = gross - commission
                    balance += pnl
                    open_trade.exit_index = i
                    open_trade.exit_price = exit_price
                    open_trade.reason = reason
                    open_trade.pnl = round(pnl, 4)
                    open_trade.pnl_pct = round((pnl / c.initial_balance) * 100, 4)
                    trades.append(open_trade)
                    open_trade = None

            # ── Buscar nueva entrada ──
            if open_trade is None:
                window_c = closes[: i + 1]
                window_h = highs[: i + 1]
                window_l = lows[: i + 1]
                window_v = volumes[: i + 1]
                decision = evaluate_signal(window_c, window_h, window_l, window_v, self.params)
                if decision["signal"] in ("buy", "sell"):
                    entry = decision["entry"]
                    stop_loss = decision["stop_loss"]
                    take_profit = decision["take_profit_1"]
                    atr = decision.get("atr", entry * 0.01)
                    risk_per_unit = abs(entry - stop_loss)
                    if risk_per_unit > 0:
                        risk_amount = balance * c.risk_per_trade_pct
                        qty = risk_amount / risk_per_unit
                        trail = 0.0
                        open_trade = BacktestTrade(
                            side=decision["signal"], entry_index=i, entry_price=entry, atr=atr,
                        )

            equity_curve.append(balance)

        return self._metrics(trades, equity_curve, balance, symbol)

    def _metrics(self, trades: List[BacktestTrade], equity: List[float],
                 final_balance: float, symbol: str) -> Dict:
        c = self.config
        closed = len(trades)
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))

        # Drawdown máximo sobre la curva de equity
        peak = equity[0]
        max_dd = 0.0
        for v in equity:
            peak = max(peak, v)
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Sharpe (simplificado) sobre retornos por trade
        returns = [t.pnl / c.initial_balance for t in trades]
        sharpe = 0.0
        if len(returns) > 1:
            mean = sum(returns) / len(returns)
            var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
            std = math.sqrt(var)
            if std > 0:
                sharpe = (mean / std) * math.sqrt(len(returns))

        total_return_pct = ((final_balance - c.initial_balance) / c.initial_balance) * 100

        return {
            "symbol": symbol,
            "initial_balance": c.initial_balance,
            "final_balance": round(final_balance, 2),
            "total_return_pct": round(total_return_pct, 2),
            "total_trades": closed,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / closed * 100, 1) if closed else 0,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else (gross_profit if gross_profit else 0),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "sharpe": round(sharpe, 2),
            "avg_win": round(gross_profit / len(wins), 2) if wins else 0,
            "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0,
            "best_trade": round(max((t.pnl for t in trades), default=0), 2),
            "worst_trade": round(min((t.pnl for t in trades), default=0), 2),
            "equity_curve": [round(v, 2) for v in equity[::max(1, len(equity) // 200)]],
            "trades": [
                {
                    "side": t.side, "entry_price": round(t.entry_price, 6),
                    "exit_price": round(t.exit_price, 6), "reason": t.reason,
                    "pnl": t.pnl, "pnl_pct": t.pnl_pct,
                }
                for t in trades[-50:]
            ],
        }
