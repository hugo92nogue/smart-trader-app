from typing import List
from .base import ExchangeAdapter, Candle, OrderResult


class BybitAdapter(ExchangeAdapter):
    """Bybit — stub. Agrega api_key y api_secret al .env para activar."""

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self._api_key = api_key
        self._api_secret = api_secret

    @property
    def name(self) -> str:
        return "Bybit"

    @property
    def is_connected(self) -> bool:
        return bool(self._api_key and self._api_secret)

    async def get_price(self, symbol: str) -> float:
        raise NotImplementedError("Bybit: conecta la API key para activar")

    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]:
        raise NotImplementedError("Bybit: conecta la API key para activar")

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        raise NotImplementedError("Bybit: conecta la API key para activar")

    async def get_usdt_balance(self) -> float:
        raise NotImplementedError("Bybit: conecta la API key para activar")

    async def get_top_symbols(self, n: int = 20) -> List[str]:
        raise NotImplementedError("Bybit: conecta la API key para activar")
