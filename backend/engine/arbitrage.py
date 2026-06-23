"""
Scanner de arbitraje cross-exchange.

Compara el precio del MISMO activo en dos o más exchanges. Cuando la diferencia
neta (tras comisiones de ambos lados) supera un umbral, registra/ejecuta la
operación: vender en el caro + comprar en el barato simultáneamente.

Estrategia de inventario pre-posicionado (no transfiere cripto por trade): asume
saldo en ambos exchanges. Por defecto corre en modo simulación (no envía órdenes).
"""
import asyncio
import logging
import time
from collections import deque, Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

_OPP_TTL = 30  # segundos que una oportunidad permanece visible tras detectarse
_STABLES = {"USDC", "USD1", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "PYUSD", "EUR", "AEUR"}

from exchanges.exchange_manager import ExchangeManager

logger = logging.getLogger(__name__)


class ArbitrageScanner:
    def __init__(
        self,
        exchange_manager: ExchangeManager,
        commission_rate: float = 0.001,
        min_net_spread_pct: float = 0.2,   # % neto mínimo para considerar la oportunidad
        scan_interval: float = 5.0,
        top_symbols: int = 15,
    ):
        self.exchanges = exchange_manager
        self.commission_rate = commission_rate
        self.min_net_spread_pct = min_net_spread_pct
        self.scan_interval = scan_interval
        self.top_symbols = top_symbols

        self.running = False
        self.execute = False               # False = solo detectar; True = ejecutar (simulado)
        self._task: Optional[asyncio.Task] = None
        self._recent: Dict[str, Dict] = {}  # symbol -> (opp, expira_en) para no parpadear
        self.log: deque = deque(maxlen=200)
        self.stats = {"detected": 0, "executed": 0, "sim_profit": 0.0,
                      "scans": 0, "best_net_pct": None, "best_symbol": "", "pairs_compared": 0}

    @property
    def opportunities(self) -> List[Dict]:
        now = time.monotonic()
        live = [v["opp"] for v in self._recent.values() if v["expires"] > now]
        live.sort(key=lambda x: x["net_pct"], reverse=True)
        return live[:20]

    def _emit(self, level: str, msg: str) -> None:
        self.log.appendleft({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})
        getattr(logger, level if level in ("info", "warning", "error") else "info")(msg)

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        self._emit("info", "Scanner de arbitraje INICIADO")

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
        self._emit("warning", "Scanner de arbitraje DETENIDO")

    async def _loop(self) -> None:
        while self.running:
            try:
                await self._scan()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error en scanner de arbitraje")
                self._emit("error", f"Error: {e}")
            await asyncio.sleep(self.scan_interval)

    async def _scan(self) -> None:
        connected = self.exchanges.connected_exchanges
        if len(connected) < 2:
            self._emit("warning", "Arbitraje requiere ≥2 exchanges conectados")
            return

        # UNA llamada por exchange (bid/ask de todos los pares) — concurrente, no congela.
        results = await asyncio.gather(
            *[self._safe_all_prices(ex) for ex in connected],
            return_exceptions=True,
        )
        books: Dict[str, Dict[str, tuple]] = {}
        for ex, res in zip(connected, results):
            if isinstance(res, dict) and res:
                books[ex.name] = res
        if len(books) < 2:
            self._emit("warning", "Menos de 2 exchanges devolvieron precios")
            return

        # Símbolos comunes a ≥2 exchanges
        counts = Counter()
        for book in books.values():
            counts.update(book.keys())
        common = [s for s, c in counts.items() if c >= 2 and s[:-4] not in _STABLES]

        fee_pct = self.commission_rate * 2 * 100
        best_net = -999.0
        best_sym = ""
        for symbol in common:
            # Comprar al ASK más bajo, vender al BID más alto (precios ejecutables reales).
            best_ask = None  # (exchange, ask)
            best_bid = None  # (exchange, bid)
            for ex_name, book in books.items():
                if symbol not in book:
                    continue
                bid, ask = book[symbol]
                if best_ask is None or ask < best_ask[1]:
                    best_ask = (ex_name, ask)
                if best_bid is None or bid > best_bid[1]:
                    best_bid = (ex_name, bid)
            if not best_ask or not best_bid or best_ask[0] == best_bid[0]:
                continue

            buy_ex, buy_price = best_ask     # compras al ask del barato
            sell_ex, sell_price = best_bid   # vendes al bid del caro
            if buy_price <= 0:
                continue
            gross_pct = (sell_price - buy_price) / buy_price * 100
            net_pct = gross_pct - fee_pct
            if net_pct > best_net:
                best_net = net_pct
                best_sym = symbol

            if net_pct >= self.min_net_spread_pct:
                opp = {
                    "symbol": symbol,
                    "buy_exchange": buy_ex, "buy_price": round(buy_price, 8),
                    "sell_exchange": sell_ex, "sell_price": round(sell_price, 8),
                    "gross_pct": round(gross_pct, 4),
                    "net_pct": round(net_pct, 4),
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                self.stats["detected"] += 1
                self._recent[symbol] = {"opp": opp, "expires": time.monotonic() + _OPP_TTL}
                self._emit(
                    "info",
                    f"ARBITRAJE {symbol}: comprar {buy_ex} @ {buy_price:.6f} → "
                    f"vender {sell_ex} @ {sell_price:.6f} = +{net_pct:.3f}% neto",
                )
                if self.execute:
                    await self._execute(opp)

        self.stats["scans"] = self.stats.get("scans", 0) + 1
        self.stats["best_net_pct"] = round(best_net, 4) if best_net > -999 else None
        self.stats["best_symbol"] = best_sym
        self.stats["pairs_compared"] = len(common)

    async def _safe_all_prices(self, exchange) -> dict:
        try:
            return await exchange.get_all_prices()
        except Exception as e:
            logger.warning(f"get_all_prices {exchange.name}: {e}")
            return {}

    async def _execute(self, opp: Dict) -> None:
        """Ejecuta el par de órdenes (simulado: usa un nominal fijo)."""
        buy_ex = self.exchanges.get(opp["buy_exchange"].lower())
        sell_ex = self.exchanges.get(opp["sell_exchange"].lower())
        if not buy_ex or not sell_ex:
            return
        notional = 1000.0  # USDT por operación (simulado)
        qty = notional / opp["buy_price"]
        try:
            await asyncio.gather(
                buy_ex.place_market_order(opp["symbol"], "buy", qty),
                sell_ex.place_market_order(opp["symbol"], "sell", qty),
            )
            profit = notional * opp["net_pct"] / 100
            self.stats["executed"] += 1
            self.stats["sim_profit"] = round(self.stats["sim_profit"] + profit, 4)
            self._emit("info", f"EJECUTADO {opp['symbol']}: +{profit:.2f} USDT (simulado)")
        except Exception as e:
            self._emit("error", f"Fallo ejecutando {opp['symbol']}: {e}")

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "execute": self.execute,
            "min_net_spread_pct": self.min_net_spread_pct,
            "scan_interval": self.scan_interval,
            "connected_exchanges": [e.name for e in self.exchanges.connected_exchanges],
            "opportunities": self.opportunities,
            "stats": self.stats,
            "log": list(self.log)[:50],
        }
