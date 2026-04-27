"""Binance Futures client for Long/Short operations on Testnet."""
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import get_settings
import logging
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """Wrapper for Binance USDⓈ-M Futures Testnet API."""

    def __init__(self):
        settings = get_settings()
        self.authenticated = False
        self.client = None

        if settings.binance_futures_key and settings.binance_futures_secret:
            try:
                self.client = Client(
                    settings.binance_futures_key,
                    settings.binance_futures_secret,
                    testnet=True
                )
                self.client.futures_ping()
                self.authenticated = True
                logger.info("Connected to Binance Futures Testnet")
            except Exception as e:
                logger.warning(f"Futures Testnet unavailable: {e}")
                self.client = None
        else:
            logger.info("Futures keys not configured")

    # ── account ──
    def get_account_balance(self) -> List[Dict]:
        if not self.authenticated:
            return [{"asset": "USDT", "balance": "10000.00", "availableBalance": "10000.00"}]
        try:
            return self.client.futures_account_balance()
        except BinanceAPIException as e:
            logger.error(f"Futures balance error: {e}")
            return []

    def get_positions(self) -> List[Dict]:
        if not self.authenticated:
            return []
        try:
            positions = self.client.futures_position_information()
            return [p for p in positions if float(p.get("positionAmt", 0)) != 0]
        except BinanceAPIException as e:
            logger.error(f"Futures positions error: {e}")
            return []

    def get_exchange_info(self) -> Dict:
        if not self.authenticated:
            return {}
        try:
            return self.client.futures_exchange_info()
        except Exception as e:
            logger.error(f"Futures exchange info error: {e}")
            return {}

    # ── orders ──
    def open_long(self, symbol: str, quantity: float, leverage: int = 5) -> Optional[Dict]:
        """Open a LONG position (buy)."""
        if not self.authenticated:
            return {"orderId": "DEMO", "status": "DEMO_FILLED", "side": "BUY", "type": "MARKET"}
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            order = self.client.futures_create_order(
                symbol=symbol, side="BUY", type="MARKET", quantity=quantity
            )
            logger.info(f"LONG opened: {symbol} qty={quantity} lev={leverage}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Open LONG error: {e}")
            return None

    def close_long(self, symbol: str, quantity: float) -> Optional[Dict]:
        """Close a LONG position (sell)."""
        if not self.authenticated:
            return {"orderId": "DEMO", "status": "DEMO_FILLED", "side": "SELL", "type": "MARKET"}
        try:
            order = self.client.futures_create_order(
                symbol=symbol, side="SELL", type="MARKET", quantity=quantity, reduceOnly=True
            )
            logger.info(f"LONG closed: {symbol} qty={quantity}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Close LONG error: {e}")
            return None

    def open_short(self, symbol: str, quantity: float, leverage: int = 5) -> Optional[Dict]:
        """Open a SHORT position (sell)."""
        if not self.authenticated:
            return {"orderId": "DEMO", "status": "DEMO_FILLED", "side": "SELL", "type": "MARKET"}
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            order = self.client.futures_create_order(
                symbol=symbol, side="SELL", type="MARKET", quantity=quantity
            )
            logger.info(f"SHORT opened: {symbol} qty={quantity} lev={leverage}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Open SHORT error: {e}")
            return None

    def close_short(self, symbol: str, quantity: float) -> Optional[Dict]:
        """Close a SHORT position (buy)."""
        if not self.authenticated:
            return {"orderId": "DEMO", "status": "DEMO_FILLED", "side": "BUY", "type": "MARKET"}
        try:
            order = self.client.futures_create_order(
                symbol=symbol, side="BUY", type="MARKET", quantity=quantity, reduceOnly=True
            )
            logger.info(f"SHORT closed: {symbol} qty={quantity}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Close SHORT error: {e}")
            return None

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List:
        if not self.authenticated:
            return []
        try:
            return self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        except BinanceAPIException as e:
            logger.error(f"Futures klines error: {e}")
            return []

    def get_mark_price(self, symbol: str) -> Optional[Dict]:
        if not self.authenticated:
            return None
        try:
            return self.client.futures_mark_price(symbol=symbol)
        except BinanceAPIException as e:
            logger.error(f"Mark price error: {e}")
            return None
