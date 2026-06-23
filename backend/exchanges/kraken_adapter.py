import asyncio
import logging
import time
from typing import Dict, List, Tuple

import requests

from .base import ExchangeAdapter, Candle, OrderResult

logger = logging.getLogger(__name__)

KRAKEN_URL = "https://api.kraken.com/0/public"

# Kraken usa "XBT" para Bitcoin; el resto de tickers coincide con Binance.
def _to_binance_symbol(altname: str) -> str:
    base = altname[:-4]  # quita "USDT"
    if base == "XBT":
        base = "BTC"
    return f"{base}USDT"


class KrakenAdapter(ExchangeAdapter):
    """
    Kraken vía API PÚBLICA (precios reales, sin API key necesaria para leer).

    Descubre dinámicamente los pares USDT disponibles (AssetPairs) y consulta sus
    precios bid/ask en una sola llamada. Para arbitraje cross-exchange real con
    Binance. La EJECUCIÓN requeriría api_key/secret y saldo en Kraken.
    """

    def __init__(self, api_key: str = "", api_secret: str = "", price_ttl: float = 4.0):
        self._api_key = api_key
        self._api_secret = api_secret
        self._ttl = price_ttl
        self._cache: Dict[str, Tuple[float, float]] = {}
        self._cache_at = 0.0
        self._pairs: Dict[str, str] = {}   # altname Kraken → símbolo Binance
        self._pairs_at = 0.0

    @property
    def name(self) -> str:
        return "Kraken"

    @property
    def is_connected(self) -> bool:
        return True  # lectura pública siempre disponible

    async def _run(self, fn, *args):
        return await asyncio.get_event_loop().run_in_executor(None, fn, *args)

    def _discover_pairs(self) -> Dict[str, str]:
        """Pares USDT online en Kraken → {altname: símbolo_binance}."""
        try:
            r = requests.get(f"{KRAKEN_URL}/AssetPairs", timeout=8)
            result = r.json().get("result", {})
        except Exception as e:
            logger.warning(f"Kraken AssetPairs error: {e}")
            return {}
        pairs = {}
        for v in result.values():
            alt = v.get("altname", "")
            if v.get("quote") == "USDT" and v.get("status") == "online" and alt.endswith("USDT"):
                pairs[alt] = _to_binance_symbol(alt)
        return pairs

    def _fetch_all(self) -> Dict[str, Tuple[float, float]]:
        if not self._pairs or (time.monotonic() - self._pairs_at > 3600):
            self._pairs = self._discover_pairs()
            self._pairs_at = time.monotonic()
        if not self._pairs:
            return {}
        try:
            r = requests.get(f"{KRAKEN_URL}/Ticker",
                             params={"pair": ",".join(self._pairs.keys())}, timeout=10)
            data = r.json()
            if data.get("error"):
                logger.warning(f"Kraken Ticker error: {data['error']}")
            result = data.get("result", {})
        except Exception as e:
            logger.warning(f"Kraken fetch error: {e}")
            return {}

        out: Dict[str, Tuple[float, float]] = {}
        for kpair, vals in result.items():
            binance_sym = self._pairs.get(kpair) or (_to_binance_symbol(kpair) if kpair.endswith("USDT") else None)
            if not binance_sym:
                continue
            try:
                bid = float(vals["b"][0]); ask = float(vals["a"][0])
                if bid > 0 and ask > 0:
                    out[binance_sym] = (bid, ask)
            except (KeyError, ValueError, IndexError):
                continue
        return out

    async def get_all_prices(self) -> Dict[str, Tuple[float, float]]:
        now = time.monotonic()
        if now - self._cache_at > self._ttl or not self._cache:
            self._cache = await self._run(self._fetch_all)
            self._cache_at = now
        return self._cache

    async def get_price(self, symbol: str) -> float:
        prices = await self.get_all_prices()
        if symbol not in prices:
            raise ValueError(f"Kraken no lista {symbol}")
        bid, ask = prices[symbol]
        return (bid + ask) / 2

    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]:
        raise NotImplementedError("Kraken: velas no implementadas (solo precios para arbitraje)")

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        raise NotImplementedError("Kraken: ejecución real requiere api_key/secret y saldo")

    async def get_usdt_balance(self) -> float:
        return 10_000.0  # demo (lectura pública no expone saldo)

    async def get_top_symbols(self, n: int = 20) -> List[str]:
        prices = await self.get_all_prices()
        return list(prices.keys())[:n]
