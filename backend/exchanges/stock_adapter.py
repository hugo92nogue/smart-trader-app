import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import market_data
from .base import ExchangeAdapter, Candle, OrderResult

logger = logging.getLogger(__name__)


class StockExchangeAdapter(ExchangeAdapter):
    """
    Mercado de ACCIONES/ETFs de EEUU vía Yahoo Finance (datos públicos, sin API key).

    Implementa la misma interfaz que los exchanges de cripto para que el MOTOR
    auto-trade pueda operar acciones igual que pares cripto. Pensado para
    operaciones LARGAS (velas diarias, posiciones de semanas a meses) y menor
    volatilidad que cripto.

    Marca `is_stock_market = True` para que el motor ajuste el horizonte temporal
    (retención larga) y desactive el apalancamiento. La ejecución es siempre
    SIMULADA (paper): no hay broker conectado.
    """

    is_stock_market = True   # bandera que lee el motor (auto_trader)

    def __init__(self, candle_ttl: float = 120.0):
        self._symbols = [s["symbol"] for s in market_data.STOCK_UNIVERSE]
        # Caché de velas diarias: el motor escanea 20 símbolos cada ciclo y Yahoo
        # limita peticiones. Las velas diarias apenas cambian intradía → TTL amplio.
        self._candle_ttl = candle_ttl
        self._candle_cache: Dict[str, Tuple[float, List[Candle]]] = {}

    @property
    def name(self) -> str:
        return "Yahoo"

    @property
    def is_connected(self) -> bool:
        return True  # datos públicos siempre disponibles

    async def get_price(self, symbol: str) -> float:
        price = await asyncio.to_thread(market_data.get_stock_price, symbol)
        if price is None:
            raise ValueError(f"Sin precio para {symbol}")
        return float(price)

    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]:
        # Acciones = horizonte largo: usamos velas DIARIAS sea cual sea el intervalo pedido.
        sym = symbol.upper()
        now = time.monotonic()
        cached = self._candle_cache.get(sym)
        if cached and now - cached[0] < self._candle_ttl and len(cached[1]) >= limit:
            return cached[1][-limit:]
        klines = await asyncio.to_thread(market_data.get_stock_klines, sym, "1d", max(limit, 500))
        candles = [
            Candle(time=k[0] / 1000, open=k[1], high=k[2], low=k[3], close=k[4], volume=k[5])
            for k in klines
        ]
        if candles:
            self._candle_cache[sym] = (now, candles)
        return candles[-limit:]

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        # Paper: rellenamos al último precio. No hay broker real conectado.
        price = await self.get_price(symbol)
        return OrderResult(
            order_id=f"STOCK_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            symbol=symbol, side=side, quantity=quantity, price=price,
            status="PAPER_FILLED", exchange=self.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def get_usdt_balance(self) -> float:
        return 100_000.0  # saldo demo (cuenta de papel para acciones)

    async def get_top_symbols(self, n: int = 20) -> List[str]:
        return self._symbols[:n]
