import asyncio
import random
from datetime import datetime, timezone
from typing import List

from .base import ExchangeAdapter, Candle, OrderResult, Side


class SimulatedExchangeAdapter(ExchangeAdapter):
    """
    Exchange simulado para DEMOSTRAR arbitraje sin segundas API keys.

    Refleja los precios de un exchange real (source) aplicando un pequeño spread
    aleatorio (±0.05%–0.4%), imitando la diferencia de precios entre exchanges que
    el arbitraje explota. NO es trading real: sirve para ver el scanner funcionando.
    """

    def __init__(self, source_adapter: ExchangeAdapter, name: str = "SimEx", max_spread: float = 0.004):
        self._source = source_adapter
        self._name = name
        self._max_spread = max_spread

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_connected(self) -> bool:
        return True  # simulado → siempre "conectado"

    def _spread_factor(self) -> float:
        # Diferencia de precio respecto al exchange real, en ambas direcciones.
        return 1.0 + random.uniform(-self._max_spread, self._max_spread)

    async def get_price(self, symbol: str) -> float:
        base = await self._source.get_price(symbol)
        return round(base * self._spread_factor(), 8)

    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]:
        return await self._source.get_candles(symbol, interval, limit)

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        price = await self.get_price(symbol)
        return OrderResult(
            order_id=f"SIM_{int(datetime.now(timezone.utc).timestamp()*1000)}",
            symbol=symbol, side=side, quantity=quantity, price=price,
            status="SIM_FILLED", exchange=self.name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    async def get_usdt_balance(self) -> float:
        return 10_000.0

    async def get_top_symbols(self, n: int = 20) -> List[str]:
        return await self._source.get_top_symbols(n)
