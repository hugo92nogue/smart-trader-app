import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional

from exchanges.base import Position, Side
from exchanges.exchange_manager import ExchangeManager
from engine.risk_manager import RiskManager
from engine.strategy import evaluate_signal, StrategyParams

logger = logging.getLogger(__name__)


class AutoTrader:
    """
    Motor de trading automático multi-exchange.

    Ciclo: escanear mercados → señal por confluencia de indicadores → control de riesgo
    → ejecutar → monitorear SL/TP. La IA de Claude es opcional (use_ai); por defecto
    decide solo con indicadores técnicos, así funciona sin API key.
    """

    def __init__(
        self,
        exchange_manager: ExchangeManager,
        risk_manager: RiskManager,
        ai_analyzer=None,
        scan_interval: float = 30.0,
        commission_rate: float = 0.001,
    ):
        self.exchanges = exchange_manager
        self.risk = risk_manager
        self.ai_analyzer = ai_analyzer
        self.scan_interval = scan_interval
        self.commission_rate = commission_rate

        self.running = False
        self.use_ai = False              # se activa cuando haya API key de Claude
        # Estrategia del motor: 'momentum' = confluencia de los 5 indicadores cargados.
        self.params = StrategyParams(mode="momentum")
        self.mode = "paper"              # 'paper' (simulado, sin órdenes reales) | 'live'
        self.use_trailing_stop = True
        self.trailing_atr_mult = 2.0
        self.trailing_activation_atr = 1.0
        self.max_hold_hours = 72.0       # 3 días (operación normal spot cripto)
        # Acciones/ETFs (mercado tradicional): horizonte LARGO (semanas a meses).
        self.stock_max_hold_hours = 24.0 * 45   # ~45 días
        # Apalancamiento: solo en entradas MUY seguras (confianza alta), retención máx 24h.
        self.use_leverage = False
        self.leverage = 3
        self.leverage_min_confidence = 0.8   # umbral para considerar "entrada segura"
        self.leverage_max_hold_hours = 24.0
        self._task: Optional[asyncio.Task] = None
        self.positions: Dict[str, Position] = {}     # key: f"{exchange}:{symbol}"
        self.db = None                   # se inyecta desde server.py para persistencia
        self.log: deque = deque(maxlen=200)
        self.stats = {"trades_opened": 0, "trades_closed": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}

    # ─── logging interno ───
    def _emit(self, level: str, msg: str) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg}
        self.log.appendleft(entry)
        getattr(logger, level if level in ("info", "warning", "error") else "info")(msg)

    # ─── control ───
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        self._emit("info", "Motor de auto-trading INICIADO")

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
        self._emit("warning", "Motor de auto-trading DETENIDO")

    # ─── bucle principal ───
    async def _loop(self) -> None:
        while self.running:
            try:
                await self._scan_and_trade()
                await self._monitor_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error en ciclo del motor")
                self._emit("error", f"Error en ciclo: {e}")
            await asyncio.sleep(self.scan_interval)

    async def _scan_and_trade(self) -> None:
        exchange = self.exchanges.active
        if exchange is None:
            self._emit("warning", "Sin exchange activo conectado")
            return

        balance = await exchange.get_usdt_balance()
        self.risk.roll_day_if_needed(balance)

        if self.risk.state.halted:
            return

        symbols = await exchange.get_top_symbols(20)
        self._emit("info", f"Escaneando {len(symbols)} pares en {exchange.name}")

        for symbol in symbols:
            key = f"{exchange.name.lower()}:{symbol}"
            if key in self.positions:
                continue
            try:
                decision = await self._evaluate(exchange, symbol)
                if decision["signal"] == "hold":
                    continue

                ok, reason = self.risk.can_open(
                    open_positions=len(self.positions),
                    confidence=decision["confidence"],
                    rr_ratio=decision["rr_ratio"],
                )
                if not ok:
                    self._emit("info", f"{symbol}: señal {decision['signal']} descartada ({reason})")
                    continue

                # Confirmación de Claude (complemento): la IA debe estar de acuerdo.
                if self.use_ai:
                    confirmed = await self._ai_confirms(symbol, decision)
                    if not confirmed:
                        self._emit("info", f"{symbol}: señal {decision['signal']} VETADA por Claude")
                        continue

                qty = self.risk.position_size(balance, decision["entry"], decision["stop_loss"])
                if qty <= 0:
                    continue

                await self._open_position(exchange, symbol, decision, qty)
            except Exception as e:
                self._emit("error", f"{symbol}: {e}")

    async def _ai_confirms(self, symbol: str, decision: Dict) -> bool:
        """Pregunta a Claude si confirma la señal mecánica. Capa de complemento, no de predicción."""
        if self.ai_analyzer is None:
            return True
        indicators = {
            "current_price": decision["entry"],
            "signal_mecanico": decision["signal"],
            "entry_price": decision["entry"],
            "stop_loss": decision["stop_loss"],
            "take_profit_1": decision["take_profit_1"],
            "confidence": decision["confidence"],
            "rr_ratio": decision["rr_ratio"],
        }
        try:
            result = await self.ai_analyzer.analyze_market(symbol, indicators, self.commission_rate)
            rec = (result.get("recommendation") or "hold").lower()
            conf = float(result.get("confidence") or 0)
            # La IA confirma si coincide con la dirección y tiene confianza mínima.
            agree = (decision["signal"] == "buy" and rec == "buy") or \
                    (decision["signal"] == "sell" and rec == "sell")
            return agree and conf >= 0.5
        except Exception as e:
            # Si la IA está activada pero falla (sin key, error API), NO operamos a ciegas.
            self._emit("warning", f"{symbol}: Claude no disponible ({e}) — señal omitida")
            return False

    async def _evaluate(self, exchange, symbol: str) -> Dict:
        """Devuelve dict: signal, confidence(0-1), entry, stop_loss, take_profit_1/2, rr_ratio."""
        # 250 velas: la estrategia necesita EMA200 (>=210) para el filtro de tendencia.
        candles = await exchange.get_candles(symbol, "15m", 250)
        if len(candles) < 210:
            return {"signal": "hold", "confidence": 0, "rr_ratio": 0}

        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]
        # Misma lógica que usa el backtester (engine.strategy) → coherencia in-vivo / backtest.
        return evaluate_signal(closes, highs, lows, volumes, self.params)

    async def _open_position(self, exchange, symbol: str, decision: Dict, qty: float) -> None:
        side = Side.BUY if decision["signal"] == "buy" else Side.SELL
        is_stock = getattr(exchange, "is_stock_market", False)

        # Apalancamiento solo si está activo Y la entrada es muy segura (confianza alta).
        # En ACCIONES no aplicamos apalancamiento: horizonte largo, menor volatilidad.
        leverage = 1
        max_hold = self.stock_max_hold_hours if is_stock else self.max_hold_hours
        if not is_stock and self.use_leverage and decision.get("confidence", 0) >= self.leverage_min_confidence:
            leverage = self.leverage
            qty = round(qty * leverage, 8)       # amplifica tamaño (y riesgo) ×leverage
            max_hold = self.leverage_max_hold_hours   # apalancado → máx 24h

        # En modo paper NO se envía ninguna orden real: fill al precio de mercado.
        if self.mode == "live":
            order = await exchange.place_market_order(symbol, side, qty)
            fill_price, order_id = order.price, order.order_id
            opened_at = order.timestamp
        else:
            fill_price = await exchange.get_price(symbol)
            order_id = f"PAPER_{int(datetime.now(timezone.utc).timestamp()*1000)}"
            opened_at = datetime.now(timezone.utc).isoformat()

        key = f"{exchange.name.lower()}:{symbol}"
        pos = Position(
            symbol=symbol, side=side, quantity=qty, entry_price=fill_price,
            stop_loss=decision["stop_loss"], take_profit_1=decision["take_profit_1"],
            take_profit_2=decision["take_profit_2"], exchange=exchange.name,
            opened_at=opened_at, atr=decision.get("atr", 0.0), mode=self.mode, order_id=order_id,
            leverage=leverage, max_hold_hours=max_hold,
        )
        self.positions[key] = pos
        self.stats["trades_opened"] += 1
        await self._persist_position(key, pos)
        await self._record_trade({
            "id": order_id, "symbol": symbol, "side": side, "order_type": "market",
            "quantity": round(qty, 8), "price": fill_price, "executed_price": fill_price,
            "status": "FILLED" if self.mode == "live" else "PAPER_FILLED",
            "mode": self.mode, "source": "auto", "event": "open",
            "timestamp": opened_at,
        })
        self._emit(
            "info",
            f"[{self.mode.upper()}] ABIERTA {side.upper()} {symbol} qty={qty} @ {fill_price:.6f} "
            f"SL={decision['stop_loss']:.6f} TP1={decision['take_profit_1']:.6f} "
            f"(conf {decision['confidence']:.0%}, R/R {decision['rr_ratio']})",
        )

    async def _monitor_positions(self) -> None:
        for key in list(self.positions.keys()):
            pos = self.positions[key]
            exchange = self.exchanges.get(pos.exchange.lower())
            if exchange is None:
                continue
            try:
                price = await exchange.get_price(pos.symbol)
            except Exception:
                continue

            # Trailing stop: tras +activation×ATR de beneficio, persigue el precio.
            if self.use_trailing_stop and pos.atr > 0:
                if pos.side == Side.BUY and price >= pos.entry_price + pos.atr * self.trailing_activation_atr:
                    new_stop = price - pos.atr * self.trailing_atr_mult
                    if new_stop > pos.stop_loss:
                        pos.stop_loss = new_stop
                elif pos.side == Side.SELL and price <= pos.entry_price - pos.atr * self.trailing_activation_atr:
                    new_stop = price + pos.atr * self.trailing_atr_mult
                    if new_stop < pos.stop_loss:
                        pos.stop_loss = new_stop

            hit_sl = (pos.side == Side.BUY and price <= pos.stop_loss) or \
                     (pos.side == Side.SELL and price >= pos.stop_loss)
            hit_tp = (pos.side == Side.BUY and price >= pos.take_profit_1) or \
                     (pos.side == Side.SELL and price <= pos.take_profit_1)

            if hit_sl or hit_tp:
                await self._close_position(exchange, key, price, "TP" if hit_tp else "SL")
                continue

            # Salida por TIEMPO máximo por posición (apalancada 24h / normal 3 días).
            age_h = self._age_hours(pos.opened_at)
            if age_h >= pos.max_hold_hours:
                await self._close_position(exchange, key, price, "TIME")
                continue

            # Salida por SEÑAL CONTRARIA de los indicadores (los "indicadores de venta").
            try:
                rev = await self._evaluate(exchange, pos.symbol)
                opposite = (pos.side == Side.BUY and rev["signal"] == "sell") or \
                           (pos.side == Side.SELL and rev["signal"] == "buy")
                if opposite:
                    await self._close_position(exchange, key, price, "REVERSO")
            except Exception:
                pass

    def _age_hours(self, opened_at: str) -> float:
        try:
            t0 = datetime.fromisoformat(opened_at)
            if t0.tzinfo is None:
                t0 = t0.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - t0).total_seconds() / 3600.0
        except Exception:
            return 0.0

    async def _close_position(self, exchange, key: str, price: float, reason: str) -> None:
        pos = self.positions.pop(key, None)
        if pos is None:
            return
        if pos.mode == "live":
            close_side = Side.SELL if pos.side == Side.BUY else Side.BUY
            await exchange.place_market_order(pos.symbol, close_side, pos.quantity)

        gross = (price - pos.entry_price) * pos.quantity
        if pos.side == Side.SELL:
            gross = -gross
        commission = (pos.entry_price + price) * pos.quantity * self.commission_rate
        pnl = round(gross - commission, 6)

        self.stats["trades_closed"] += 1
        self.stats["total_pnl"] = round(self.stats["total_pnl"] + pnl, 6)
        if pnl >= 0:
            self.stats["wins"] += 1
        else:
            self.stats["losses"] += 1

        balance = await exchange.get_usdt_balance()
        self.risk.register_close(pnl, balance)
        await self._unpersist_position(key)
        # Lado opuesto al de apertura: registra el cierre en el historial.
        close_side = Side.SELL if pos.side == Side.BUY else Side.BUY
        await self._record_trade({
            "id": f"CLOSE_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            "symbol": pos.symbol, "side": close_side, "order_type": "market",
            "quantity": round(pos.quantity, 8), "price": price, "executed_price": price,
            "status": f"CLOSED_{reason}", "mode": pos.mode, "source": "auto", "event": "close",
            "pnl": pnl, "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        self._emit(
            "info" if pnl >= 0 else "warning",
            f"[{pos.mode.upper()}] CERRADA [{reason}] {pos.symbol} @ {price:.6f} PnL={pnl:+.4f} USDT",
        )

    async def _record_trade(self, doc: dict) -> None:
        """Guarda la operación del motor en el historial (db.trades)."""
        if self.db is None:
            return
        try:
            await self.db.trades.insert_one(dict(doc))
        except Exception as e:
            logger.warning(f"No se pudo registrar la operación en el historial: {e}")

    async def close_all(self) -> int:
        """PÁNICO: detiene el motor y cierra TODAS las posiciones abiertas al precio de mercado."""
        self.stop()
        count = 0
        for key in list(self.positions.keys()):
            pos = self.positions.get(key)
            if pos is None:
                continue
            exchange = self.exchanges.get(pos.exchange.lower())
            if exchange is None:
                self.positions.pop(key, None)
                continue
            try:
                price = await exchange.get_price(pos.symbol)
                await self._close_position(exchange, key, price, "MANUAL")
                count += 1
            except Exception as e:
                self._emit("error", f"No se pudo cerrar {pos.symbol}: {e}")
                self.positions.pop(key, None)
                await self._unpersist_position(key)
        self._emit("warning", f"CIERRE TOTAL: {count} posiciones cerradas manualmente")
        return count

    # ─── persistencia (sobrevive reinicios) ───
    async def _persist_position(self, key: str, pos: Position) -> None:
        if self.db is None:
            return
        try:
            doc = {"_key": key, **pos.__dict__}
            await self.db.open_positions.insert_one(doc)
        except Exception as e:
            logger.warning(f"No se pudo persistir posición {key}: {e}")

    async def _unpersist_position(self, key: str) -> None:
        if self.db is None:
            return
        try:
            await self.db.open_positions.delete_one({"_key": key})
        except Exception as e:
            logger.warning(f"No se pudo borrar posición persistida {key}: {e}")

    async def restore_positions(self) -> None:
        """Carga posiciones abiertas desde la DB al arrancar (sobreviven reinicios)."""
        if self.db is None:
            return
        try:
            docs = await self.db.open_positions.find({}, {"_id": 0}).to_list(100)
        except Exception as e:
            logger.warning(f"No se pudieron restaurar posiciones: {e}")
            return
        for doc in docs:
            key = doc.pop("_key", None)
            if not key:
                continue
            doc.pop("_id", None)
            try:
                self.positions[key] = Position(**{k: v for k, v in doc.items() if k in Position.__dataclass_fields__})
            except Exception as e:
                logger.warning(f"Posición corrupta en DB {key}: {e}")
        if self.positions:
            self._emit("info", f"Restauradas {len(self.positions)} posiciones desde la DB")

    # ─── estado para la API ───
    def snapshot(self) -> dict:
        win_rate = (self.stats["wins"] / self.stats["trades_closed"] * 100) if self.stats["trades_closed"] else 0
        return {
            "running": self.running,
            "use_ai": self.use_ai,
            "mode": self.mode,
            "strategy_mode": self.params.mode,
            "use_trailing_stop": self.use_trailing_stop,
            "use_leverage": self.use_leverage,
            "leverage": self.leverage,
            "scan_interval": self.scan_interval,
            "open_positions": [
                {
                    "symbol": p.symbol, "side": p.side, "quantity": p.quantity,
                    "entry_price": p.entry_price, "stop_loss": p.stop_loss,
                    "take_profit_1": p.take_profit_1, "exchange": p.exchange,
                    "opened_at": p.opened_at, "mode": p.mode,
                }
                for p in self.positions.values()
            ],
            "stats": {**self.stats, "win_rate": round(win_rate, 1)},
            "risk": self.risk.snapshot(),
            "log": list(self.log)[:50],
        }
