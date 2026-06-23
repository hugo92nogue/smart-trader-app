import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from .base import ExchangeAdapter, Candle, OrderResult, Side

logger = logging.getLogger(__name__)


class BinanceAdapter(ExchangeAdapter):
    """Adaptador async para BinanceSpotClient (cliente síncrono existente)."""

    def __init__(self, spot_client):
        self._client = spot_client

    @property
    def name(self) -> str:
        return "Binance"

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def _run(self, fn, *args):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fn, *args)

    async def get_price(self, symbol: str) -> float:
        ticker = await self._run(self._client.get_symbol_ticker, symbol)
        return float(ticker["price"])

    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]:
        klines = await self._run(self._client.get_klines, symbol, interval, limit)
        return [
            Candle(
                time=float(k[0]) / 1000,
                open=float(k[1]),
                high=float(k[2]),
                low=float(k[3]),
                close=float(k[4]),
                volume=float(k[5]),
            )
            for k in klines
        ]

    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult:
        now = datetime.now(timezone.utc).isoformat()

        async def _demo_fill() -> OrderResult:
            price = await self.get_price(symbol)
            return OrderResult(
                order_id=f"DEMO_{int(datetime.now(timezone.utc).timestamp()*1000)}",
                symbol=symbol, side=side, quantity=quantity, price=price,
                status="DEMO_FILLED", exchange=self.name, timestamp=now,
            )

        if not self._client.authenticated:
            return await _demo_fill()

        binance_side = "BUY" if side == Side.BUY else "SELL"
        result = await self._run(
            lambda: self._client.place_order(symbol, binance_side, "market", quantity, None)
        )
        # Sin ejecución real (sin keys de cuenta o error) → fill demo (paper trading).
        if not result:
            return await _demo_fill()

        price = float(result.get("price", 0)) or await self.get_price(symbol)
        return OrderResult(
            order_id=str(result.get("orderId", "")),
            symbol=symbol, side=side, quantity=quantity, price=price,
            status=result.get("status", "FILLED"), exchange=self.name, timestamp=now,
        )

    async def get_usdt_balance(self) -> float:
        if not self._client.authenticated:
            return 10_000.0
        balance = await self._run(self._client.get_account_balance)
        if not balance:
            # Autenticado pero sin saldo de cuenta accesible → balance demo.
            return 10_000.0
        usdt = balance.get("USDT", {})
        return float(usdt.get("free", 0))

    async def get_all_prices(self) -> dict:
        """Bid/ask de TODOS los pares USDT en UNA llamada (book ticker). Evita congelar."""
        tickers = await self._run(self._client.get_book_tickers)
        out = {}
        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT"):
                continue
            try:
                bid = float(t["bidPrice"]); ask = float(t["askPrice"])
                if bid > 0 and ask > 0:
                    out[sym] = (bid, ask)
            except (KeyError, ValueError):
                continue
        return out

    # Stablecoins: operar par stable/USDT no tiene sentido (volatilidad nula).
    _STABLES = {"USDC", "USD1", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "PYUSD", "EUR", "AEUR"}

    async def get_top_symbols(self, n: int = 20) -> List[str]:
        tickers = await self._run(self._client.get_ticker_24h)
        usdt = [
            t for t in tickers
            if t.get("symbol", "").endswith("USDT")
            and t.get("symbol", "")[:-4] not in self._STABLES
            and float(t.get("quoteVolume", 0)) > 5_000_000
        ]
        usdt.sort(key=lambda x: float(x.get("quoteVolume", 0)), reverse=True)
        return [t["symbol"] for t in usdt[:n]]
