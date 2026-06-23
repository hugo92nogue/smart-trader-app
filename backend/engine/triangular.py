"""
Arbitraje triangular en UN solo exchange (Binance).

Explota desajustes momentáneos entre tres pares que forman un ciclo, p.ej.:
  USDT → BTC → ETH → USDT
usando los pares BTCUSDT, ETHBTC y ETHUSDT. Si el producto de las conversiones
(restando comisiones de las 3 operaciones) supera 1, hay beneficio sin riesgo de
mercado y sin necesitar un segundo exchange ni transferencias.

Usa bid/ask REALES del order book (no el último precio). Honestidad: en Binance
estas oportunidades son diminutas y duran milisegundos — la EJECUCIÓN rentable
requiere infraestructura HFT (colocation, latencia ~µs). Este scanner DETECTA y
cuantifica las oportunidades; sirve para entender y medir el edge, no para competir
con bots HFT desde un PC doméstico.
"""
import asyncio
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Monedas puente típicas (alta liquidez). Triángulo: USDT → BRIDGE → ALT → USDT.
BRIDGES = ["BTC", "ETH", "BNB"]
QUOTE = "USDT"
_OPP_TTL = 20


class TriangularArbitrage:
    def __init__(self, binance_client, commission_rate: float = 0.001,
                 min_net_pct: float = 0.05, scan_interval: float = 5.0):
        self.client = binance_client
        self.commission_rate = commission_rate
        self.min_net_pct = min_net_pct          # % neto mínimo tras 3 comisiones
        self.scan_interval = scan_interval

        self.running = False
        self._task: Optional[asyncio.Task] = None
        self._triangles: List[tuple] = []        # (alt, bridge): cache de ciclos válidos
        self._recent: Dict[str, Dict] = {}
        self.log: deque = deque(maxlen=200)
        self.stats = {"detected": 0, "best_pct": 0.0, "scans": 0}

    def _emit(self, level: str, msg: str) -> None:
        self.log.appendleft({"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg})
        getattr(logger, level if level in ("info", "warning", "error") else "info")(msg)

    @property
    def opportunities(self) -> List[Dict]:
        now = time.monotonic()
        live = [v["opp"] for v in self._recent.values() if v["expires"] > now]
        live.sort(key=lambda x: x["net_pct"], reverse=True)
        return live[:20]

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        self._emit("info", "Arbitraje triangular INICIADO")

    def stop(self) -> None:
        self.running = False
        if self._task:
            self._task.cancel()
        self._emit("warning", "Arbitraje triangular DETENIDO")

    async def _run(self, fn, *args):
        return await asyncio.get_event_loop().run_in_executor(None, fn, *args)

    async def _build_triangles(self, symbols: set) -> None:
        """Encuentra ciclos válidos: ALT con pares ALTUSDT y ALT{BRIDGE} existentes."""
        triangles = []
        for sym in symbols:
            for bridge in BRIDGES:
                if sym.endswith(bridge) and sym != f"{bridge}{QUOTE}":
                    alt = sym[: -len(bridge)]
                    if f"{alt}{QUOTE}" in symbols and f"{bridge}{QUOTE}" in symbols:
                        triangles.append((alt, bridge))
        self._triangles = triangles
        self._emit("info", f"{len(triangles)} triángulos válidos detectados")

    async def _loop(self) -> None:
        while self.running:
            try:
                await self._scan()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Error en arbitraje triangular")
                self._emit("error", f"Error: {e}")
            await asyncio.sleep(self.scan_interval)

    async def _scan(self) -> None:
        tickers = await self._run(self.client.get_book_tickers)
        if not tickers:
            self._emit("warning", "Sin datos de order book")
            return

        book = {
            t["symbol"]: (float(t["bidPrice"]), float(t["askPrice"]))
            for t in tickers
            if float(t.get("bidPrice", 0)) > 0 and float(t.get("askPrice", 0)) > 0
        }
        if not self._triangles:
            await self._build_triangles(set(book.keys()))

        fee = 1.0 - self.commission_rate
        best = -999.0
        for alt, bridge in self._triangles:
            s_bridge = f"{bridge}{QUOTE}"   # p.ej. BTCUSDT
            s_alt_bridge = f"{alt}{bridge}"  # p.ej. ETHBTC
            s_alt = f"{alt}{QUOTE}"          # p.ej. ETHUSDT
            if s_bridge not in book or s_alt_bridge not in book or s_alt not in book:
                continue

            bridge_bid, bridge_ask = book[s_bridge]
            ab_bid, ab_ask = book[s_alt_bridge]
            alt_bid, alt_ask = book[s_alt]
            if bridge_ask <= 0 or ab_ask <= 0 or alt_ask <= 0:
                continue

            # Ruta directa: USDT → BRIDGE → ALT → USDT
            #  1 USDT compra 1/bridge_ask BRIDGE; compra ALT con BRIDGE (1/ab_ask);
            #  vende ALT por USDT (alt_bid). Comisión en cada paso.
            forward = (1.0 / bridge_ask) * fee * (1.0 / ab_ask) * fee * alt_bid * fee
            # Ruta inversa: USDT → ALT → BRIDGE → USDT
            backward = (1.0 / alt_ask) * fee * ab_bid * fee * bridge_bid * fee

            net = max(forward, backward) - 1.0
            net_pct = net * 100
            if net_pct > best:
                best = net_pct

            if net_pct >= self.min_net_pct:
                route = (f"USDT→{bridge}→{alt}→USDT" if forward >= backward
                         else f"USDT→{alt}→{bridge}→USDT")
                opp = {
                    "triangle": f"{alt}/{bridge}",
                    "route": route,
                    "net_pct": round(net_pct, 4),
                    "pairs": [s_bridge, s_alt_bridge, s_alt],
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
                key = f"{alt}-{bridge}"
                self._recent[key] = {"opp": opp, "expires": time.monotonic() + _OPP_TTL}
                self.stats["detected"] += 1
                self._emit("info", f"TRIANGULAR {route}: +{net_pct:.4f}% neto")

        self.stats["scans"] += 1
        self.stats["best_pct"] = round(best, 4)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "min_net_pct": self.min_net_pct,
            "scan_interval": self.scan_interval,
            "triangles_count": len(self._triangles),
            "opportunities": self.opportunities,
            "stats": self.stats,
            "log": list(self.log)[:50],
        }
