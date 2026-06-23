from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Candle:
    time: float
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str        # 'buy' | 'sell'
    quantity: float
    price: float
    status: str
    exchange: str
    timestamp: str


@dataclass
class Position:
    symbol: str
    side: str
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    exchange: str
    opened_at: str
    unrealized_pnl: float = 0.0
    atr: float = 0.0           # para el trailing stop
    mode: str = "paper"        # 'paper' (simulado) | 'live' (real)
    order_id: str = ""
    leverage: int = 1          # 1 = spot normal; >1 = apalancado
    max_hold_hours: float = 72.0  # 3 días normal; 24h si apalancado


class Side:
    BUY = "buy"
    SELL = "sell"


class ExchangeAdapter(ABC):
    """Interfaz unificada para todos los exchanges soportados."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    async def get_price(self, symbol: str) -> float: ...

    @abstractmethod
    async def get_candles(self, symbol: str, interval: str, limit: int = 200) -> List[Candle]: ...

    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, quantity: float) -> OrderResult: ...

    @abstractmethod
    async def get_usdt_balance(self) -> float: ...

    @abstractmethod
    async def get_top_symbols(self, n: int = 20) -> List[str]: ...

    async def get_all_prices(self) -> Dict[str, tuple]:
        """{symbol: (bid, ask)} de todos los pares USDT en UNA llamada (para arbitraje).
        Vacío por defecto; los adapters que lo soporten lo sobreescriben."""
        return {}
