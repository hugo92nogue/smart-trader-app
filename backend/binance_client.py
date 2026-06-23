from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import get_settings
import logging
import secrets
import math
import time
import requests
from typing import Optional, List, Dict
from datetime import datetime, timezone

_rng = secrets.SystemRandom()
logger = logging.getLogger(__name__)

# Demo fallback data
DEMO_PAIRS = [
    {"symbol": "BTCUSDT",  "base": "BTC",  "quote": "USDT", "price": 97500.0},
    {"symbol": "ETHUSDT",  "base": "ETH",  "quote": "USDT", "price": 3450.0},
    {"symbol": "BNBUSDT",  "base": "BNB",  "quote": "USDT", "price": 635.0},
    {"symbol": "SOLUSDT",  "base": "SOL",  "quote": "USDT", "price": 178.0},
    {"symbol": "XRPUSDT",  "base": "XRP",  "quote": "USDT", "price": 2.35},
    {"symbol": "ADAUSDT",  "base": "ADA",  "quote": "USDT", "price": 0.72},
    {"symbol": "DOGEUSDT", "base": "DOGE", "quote": "USDT", "price": 0.185},
    {"symbol": "AVAXUSDT", "base": "AVAX", "quote": "USDT", "price": 38.50},
    {"symbol": "DOTUSDT",  "base": "DOT",  "quote": "USDT", "price": 7.20},
    {"symbol": "LINKUSDT", "base": "LINK", "quote": "USDT", "price": 18.50},
    {"symbol": "MATICUSDT","base": "MATIC","quote": "USDT", "price": 0.55},
    {"symbol": "UNIUSDT",  "base": "UNI",  "quote": "USDT", "price": 12.80},
    {"symbol": "LTCUSDT",  "base": "LTC",  "quote": "USDT", "price": 95.0},
    {"symbol": "APTUSDT",  "base": "APT",  "quote": "USDT", "price": 9.50},
    {"symbol": "ARBUSDT",  "base": "ARB",  "quote": "USDT", "price": 1.05},
    {"symbol": "OPUSDT",   "base": "OP",   "quote": "USDT", "price": 2.10},
    {"symbol": "SUIUSDT",  "base": "SUI",  "quote": "USDT", "price": 3.80},
    {"symbol": "SEIUSDT",  "base": "SEI",  "quote": "USDT", "price": 0.42},
    {"symbol": "TIAUSDT",  "base": "TIA",  "quote": "USDT", "price": 8.90},
    {"symbol": "JUPUSDT",  "base": "JUP",  "quote": "USDT", "price": 1.15},
]

BINANCE_PUBLIC_URL = "https://api.binance.com/api/v3"

def _public_get(endpoint: str, params: dict = None, timeout: int = 10):
    """Llamada directa a Binance API pública (sin auth, datos reales)"""
    try:
        r = requests.get(f"{BINANCE_PUBLIC_URL}/{endpoint}", params=params, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logger.warning(f"Public API error: {e}")
    return None

def generate_klines(base_price: float, count: int = 200, interval_ms: int = 3600000) -> List:
    klines = []
    price = base_price * 0.95
    now = int(time.time() * 1000)
    start_time = now - (count * interval_ms)
    for i in range(count):
        t = start_time + (i * interval_ms)
        volatility = base_price * 0.008
        trend = math.sin(i / 20) * volatility * 0.5
        noise = _rng.gauss(0, volatility)
        open_p = price
        close_p = open_p + trend + noise
        high_p = max(open_p, close_p) + abs(_rng.gauss(0, volatility * 0.5))
        low_p  = min(open_p, close_p) - abs(_rng.gauss(0, volatility * 0.5))
        vol = _rng.uniform(100, 5000) * (base_price / 100)
        klines.append([
            t, str(round(open_p, 8)), str(round(high_p, 8)),
            str(round(low_p, 8)), str(round(close_p, 8)),
            str(round(vol, 2)), t + interval_ms - 1,
            str(round(vol * close_p, 2)), _rng.randint(50, 500),
            str(round(vol * 0.55, 2)), str(round(vol * close_p * 0.55, 2)), "0"
        ])
        price = close_p
    return klines


class BinanceSpotClient:
    def __init__(self):
        settings = get_settings()
        self.demo_mode = True
        self.authenticated = False
        self._price_cache = {p['symbol']: p['price'] for p in DEMO_PAIRS}
        self._kline_cache = {}

        # Intentar conectar con keys si existen
        if settings.binance_api_key and settings.binance_api_secret:
            try:
                self.client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=settings.binance_testnet
                )
                self.client.get_server_time()
                self.authenticated = True
                logger.info(f"Connected to Binance {'Testnet' if settings.binance_testnet else 'Live'}")
            except Exception as e:
                logger.warning(f"Binance auth failed: {e}")
                self.client = None
        else:
            self.client = None

        # Siempre intentar datos públicos reales
        test = _public_get("ping")
        if test is not None:
            self.demo_mode = False
            logger.info("Using Binance public API (real market data)")
        else:
            logger.warning("Binance public API unavailable, using demo data")

    def _jitter_price(self, base_price: float) -> float:
        return base_price * (1 + _rng.gauss(0, 0.001))

    def get_ticker_24h(self, symbol: Optional[str] = None) -> List[Dict]:
        # Intentar API pública real primero
        params = {"symbol": symbol} if symbol else {}
        data = _public_get("ticker/24hr", params)
        if data:
            if isinstance(data, list):
                return data
            return [data]

        # Autenticado con keys
        if self.authenticated and self.client:
            try:
                if symbol:
                    return [self.client.get_ticker(symbol=symbol)]
                return self.client.get_ticker()
            except Exception:
                pass

        # Demo fallback
        tickers = []
        pairs = DEMO_PAIRS if not symbol else [p for p in DEMO_PAIRS if p['symbol'] == symbol]
        for p in pairs:
            price = self._jitter_price(self._price_cache.get(p['symbol'], p['price']))
            self._price_cache[p['symbol']] = price
            change = _rng.uniform(-5, 5)
            volume = _rng.uniform(1000, 50000) * (price / 100)
            tickers.append({
                'symbol': p['symbol'], 'lastPrice': str(round(price, 8)),
                'priceChangePercent': str(round(change, 2)),
                'quoteVolume': str(round(volume * price, 2)),
                'highPrice': str(round(price * 1.05, 8)),
                'lowPrice': str(round(price * 0.95, 8)),
                'volume': str(round(volume, 2)),
                'status': 'TRADING'
            })
        return tickers

    def get_exchange_info(self) -> Dict:
        data = _public_get("exchangeInfo")
        if data:
            return data
        if self.authenticated and self.client:
            try:
                return self.client.get_exchange_info()
            except Exception:
                pass
        symbols = [{'symbol': p['symbol'], 'status': 'TRADING',
                    'baseAsset': p['base'], 'quoteAsset': p['quote']} for p in DEMO_PAIRS]
        return {'symbols': symbols}

    def get_symbol_ticker(self, symbol: str) -> Optional[Dict]:
        data = _public_get("ticker/price", {"symbol": symbol})
        if data:
            price = float(data['price'])
            self._price_cache[symbol] = price
            return data
        if self.authenticated and self.client:
            try:
                return self.client.get_symbol_ticker(symbol=symbol)
            except Exception:
                pass
        base_price = self._price_cache.get(symbol, 50000)
        price = self._jitter_price(base_price)
        self._price_cache[symbol] = price
        return {'symbol': symbol, 'price': str(round(price, 8))}

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List:
        # Datos reales de Binance público
        data = _public_get("klines", {"symbol": symbol, "interval": interval, "limit": limit})
        if data:
            return data

        # Autenticado
        if self.authenticated and self.client:
            try:
                return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            except Exception:
                pass

        # Demo
        base_price = self._price_cache.get(symbol, 50000)
        interval_ms = {
            '1m':60000,'3m':180000,'5m':300000,'15m':900000,
            '30m':1800000,'1h':3600000,'2h':7200000,'4h':14400000,
            '6h':21600000,'12h':43200000,'1d':86400000,'1w':604800000
        }.get(interval, 3600000)
        cache_key = f"{symbol}_{interval}_{limit}"
        if cache_key not in self._kline_cache:
            self._kline_cache[cache_key] = generate_klines(base_price, limit, interval_ms)
        klines = self._kline_cache[cache_key]
        if klines:
            last = klines[-1]
            price = self._jitter_price(float(last[4]))
            last[4] = str(round(price, 8))
            self._price_cache[symbol] = price
        return klines

    def get_klines_paginated(self, symbol: str, interval: str, total: int = 5000) -> List:
        """Descarga >1000 velas encadenando peticiones hacia atrás con endTime."""
        out: List = []
        end_time = None
        while len(out) < total:
            params = {"symbol": symbol, "interval": interval, "limit": 1000}
            if end_time is not None:
                params["endTime"] = end_time
            batch = _public_get("klines", params)
            if not batch:
                break
            out = batch + out
            end_time = batch[0][0] - 1  # justo antes de la primera vela del lote
            if len(batch) < 1000:
                break  # no hay más historia disponible
            time.sleep(0.15)  # respeta el rate limit
        return out[-total:]

    def get_all_tickers(self) -> List[Dict]:
        data = _public_get("ticker/price")
        if data:
            return data
        return [{'symbol': p['symbol'], 'price': str(p['price'])} for p in DEMO_PAIRS]

    def get_book_tickers(self) -> List[Dict]:
        """Mejor bid/ask de TODOS los símbolos (para arbitraje triangular)."""
        data = _public_get("ticker/bookTicker")
        if data and isinstance(data, list):
            return data
        return []

    def get_account_balance(self) -> Optional[Dict]:
        if self.authenticated and self.client:
            try:
                account = self.client.get_account()
                return {b['asset']: {'free': float(b['free']), 'locked': float(b['locked'])}
                        for b in account['balances'] if float(b['free']) + float(b['locked']) > 0}
            except Exception:
                pass
        return None

    def place_order(self, symbol, side, order_type, quantity, price=None) -> Optional[Dict]:
        if self.authenticated and self.client:
            try:
                params = {'symbol': symbol, 'side': side.upper(),
                          'type': order_type.upper(), 'quantity': quantity}
                if order_type.upper() == 'LIMIT' and price:
                    params['timeInForce'] = 'GTC'
                    params['price'] = price
                return self.client.create_order(**params)
            except Exception as e:
                logger.error(f"Order error: {e}")
        return None

    def get_open_orders(self, symbol=None) -> List[Dict]:
        if self.authenticated and self.client:
            try:
                return self.client.get_open_orders(symbol=symbol) if symbol else self.client.get_open_orders()
            except Exception:
                pass
        return []
