from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import get_settings
import logging
import secrets
import math
import time
from typing import Optional, List, Dict
from datetime import datetime, timezone

# Cryptographically secure random for price simulation
_rng = secrets.SystemRandom()

logger = logging.getLogger(__name__)

# Simulated market data for demo mode
DEMO_PAIRS = [
    {"symbol": "BTCUSDT", "base": "BTC", "quote": "USDT", "price": 97500.0},
    {"symbol": "ETHUSDT", "base": "ETH", "quote": "USDT", "price": 3450.0},
    {"symbol": "BNBUSDT", "base": "BNB", "quote": "USDT", "price": 635.0},
    {"symbol": "SOLUSDT", "base": "SOL", "quote": "USDT", "price": 178.0},
    {"symbol": "XRPUSDT", "base": "XRP", "quote": "USDT", "price": 2.35},
    {"symbol": "ADAUSDT", "base": "ADA", "quote": "USDT", "price": 0.72},
    {"symbol": "DOGEUSDT", "base": "DOGE", "quote": "USDT", "price": 0.185},
    {"symbol": "AVAXUSDT", "base": "AVAX", "quote": "USDT", "price": 38.50},
    {"symbol": "DOTUSDT", "base": "DOT", "quote": "USDT", "price": 7.20},
    {"symbol": "LINKUSDT", "base": "LINK", "quote": "USDT", "price": 18.50},
    {"symbol": "MATICUSDT", "base": "MATIC", "quote": "USDT", "price": 0.55},
    {"symbol": "UNIUSDT", "base": "UNI", "quote": "USDT", "price": 12.80},
    {"symbol": "LTCUSDT", "base": "LTC", "quote": "USDT", "price": 95.0},
    {"symbol": "APTUSDT", "base": "APT", "quote": "USDT", "price": 9.50},
    {"symbol": "ARBUSDT", "base": "ARB", "quote": "USDT", "price": 1.05},
    {"symbol": "OPUSDT", "base": "OP", "quote": "USDT", "price": 2.10},
    {"symbol": "SUIUSDT", "base": "SUI", "quote": "USDT", "price": 3.80},
    {"symbol": "SEIUSDT", "base": "SEI", "quote": "USDT", "price": 0.42},
    {"symbol": "TIAUSDT", "base": "TIA", "quote": "USDT", "price": 8.90},
    {"symbol": "JUPUSDT", "base": "JUP", "quote": "USDT", "price": 1.15},
]


def generate_klines(base_price: float, count: int = 200, interval_ms: int = 3600000) -> List:
    """Generate realistic candlestick data"""
    klines = []
    price = base_price * 0.95
    now = int(time.time() * 1000)
    start_time = now - (count * interval_ms)
    
    for i in range(count):
        t = start_time + (i * interval_ms)
        volatility = base_price * 0.008
        
        # Add trend component
        trend = math.sin(i / 20) * volatility * 0.5
        noise = _rng.gauss(0, volatility)
        
        open_p = price
        change = trend + noise
        close_p = open_p + change
        high_p = max(open_p, close_p) + abs(_rng.gauss(0, volatility * 0.5))
        low_p = min(open_p, close_p) - abs(_rng.gauss(0, volatility * 0.5))
        vol = _rng.uniform(100, 5000) * (base_price / 100)
        
        klines.append([
            t,                      # Open time
            str(round(open_p, 8)),  # Open
            str(round(high_p, 8)), # High
            str(round(low_p, 8)),  # Low
            str(round(close_p, 8)), # Close
            str(round(vol, 2)),     # Volume
            t + interval_ms - 1,    # Close time
            str(round(vol * close_p, 2)),  # Quote volume
            _rng.randint(50, 500),  # Number of trades
            str(round(vol * 0.55, 2)),  # Taker buy base
            str(round(vol * close_p * 0.55, 2)),  # Taker buy quote
            "0"
        ])
        price = close_p
    
    return klines


class BinanceSpotClient:
    """Wrapper around Binance Spot API with demo fallback"""
    
    def __init__(self):
        settings = get_settings()
        self.demo_mode = True
        self.authenticated = False
        self._price_cache = {p['symbol']: p['price'] for p in DEMO_PAIRS}
        self._kline_cache = {}
        
        if settings.binance_api_key and settings.binance_api_secret:
            try:
                self.client = Client(
                    settings.binance_api_key,
                    settings.binance_api_secret,
                    testnet=settings.binance_testnet
                )
                # Test connection
                self.client.get_server_time()
                self.demo_mode = False
                self.authenticated = True
                logger.info("Connected to Binance API")
            except Exception as e:
                logger.warning(f"Binance API unavailable, using demo mode: {e}")
                self.client = None
        else:
            try:
                self.client = Client("", "", testnet=settings.binance_testnet)
                self.client.get_server_time()
                self.demo_mode = False
                logger.info("Connected to Binance (public data only)")
            except Exception as e:
                logger.warning(f"Binance API unavailable, using demo mode: {e}")
                self.client = None
    
    def _jitter_price(self, base_price: float) -> float:
        """Add realistic price jitter"""
        return base_price * (1 + _rng.gauss(0, 0.001))
    
    def get_all_tickers(self) -> List[Dict]:
        if not self.demo_mode and self.client:
            try:
                return self.client.get_all_tickers()
            except Exception:
                pass
        
        # Demo data
        tickers = []
        for p in DEMO_PAIRS:
            price = self._jitter_price(self._price_cache.get(p['symbol'], p['price']))
            self._price_cache[p['symbol']] = price
            tickers.append({'symbol': p['symbol'], 'price': str(round(price, 8))})
        return tickers
    
    def get_ticker_24h(self, symbol: Optional[str] = None) -> List[Dict]:
        if not self.demo_mode and self.client:
            try:
                if symbol:
                    return [self.client.get_ticker(symbol=symbol)]
                return self.client.get_ticker()
            except Exception:
                pass
        
        # Demo data
        tickers = []
        pairs = DEMO_PAIRS
        if symbol:
            pairs = [p for p in DEMO_PAIRS if p['symbol'] == symbol]
        
        for p in pairs:
            price = self._jitter_price(self._price_cache.get(p['symbol'], p['price']))
            self._price_cache[p['symbol']] = price
            change = _rng.uniform(-5, 5)
            volume = _rng.uniform(1000, 50000) * (price / 100)
            tickers.append({
                'symbol': p['symbol'],
                'lastPrice': str(round(price, 8)),
                'priceChangePercent': str(round(change, 2)),
                'quoteVolume': str(round(volume * price, 2)),
                'highPrice': str(round(price * (1 + abs(change) / 100), 8)),
                'lowPrice': str(round(price * (1 - abs(change) / 100), 8)),
                'volume': str(round(volume, 2)),
                'openPrice': str(round(price * (1 - change / 100), 8))
            })
        return tickers
    
    def get_exchange_info(self) -> Dict:
        if not self.demo_mode and self.client:
            try:
                return self.client.get_exchange_info()
            except Exception:
                pass
        
        symbols = []
        for p in DEMO_PAIRS:
            symbols.append({
                'symbol': p['symbol'],
                'status': 'TRADING',
                'baseAsset': p['base'],
                'quoteAsset': p['quote']
            })
        return {'symbols': symbols}
    
    def get_symbol_ticker(self, symbol: str) -> Optional[Dict]:
        if not self.demo_mode and self.client:
            try:
                return self.client.get_symbol_ticker(symbol=symbol)
            except Exception:
                pass
        
        base_price = self._price_cache.get(symbol)
        if base_price is None:
            for p in DEMO_PAIRS:
                if p['symbol'] == symbol:
                    base_price = p['price']
                    break
        
        if base_price:
            price = self._jitter_price(base_price)
            self._price_cache[symbol] = price
            return {'symbol': symbol, 'price': str(round(price, 8))}
        return None
    
    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List:
        if not self.demo_mode and self.client:
            try:
                return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
            except Exception:
                pass
        
        # Demo klines
        base_price = self._price_cache.get(symbol, 50000)
        
        interval_ms = {
            '1m': 60000, '3m': 180000, '5m': 300000, '15m': 900000,
            '30m': 1800000, '1h': 3600000, '2h': 7200000, '4h': 14400000,
            '6h': 21600000, '12h': 43200000, '1d': 86400000, '1w': 604800000
        }.get(interval, 3600000)
        
        cache_key = f"{symbol}_{interval}_{limit}"
        if cache_key not in self._kline_cache:
            self._kline_cache[cache_key] = generate_klines(base_price, limit, interval_ms)
        
        # Update last candle with fresh price
        klines = self._kline_cache[cache_key]
        if klines:
            last = klines[-1]
            price = self._jitter_price(float(last[4]))
            last[4] = str(round(price, 8))
            last[2] = str(round(max(float(last[2]), price), 8))
            last[3] = str(round(min(float(last[3]), price), 8))
            self._price_cache[symbol] = price
        
        return klines
    
    def get_account_balance(self) -> Optional[Dict]:
        if not self.demo_mode and self.client and self.authenticated:
            try:
                account = self.client.get_account()
                return {b['asset']: {'free': float(b['free']), 'locked': float(b['locked'])}
                        for b in account['balances'] if float(b['free']) + float(b['locked']) > 0}
            except Exception:
                pass
        return None
    
    def place_order(self, symbol, side, order_type, quantity, price=None) -> Optional[Dict]:
        if not self.demo_mode and self.client and self.authenticated:
            try:
                params = {'symbol': symbol, 'side': side.upper(), 'type': order_type.upper(), 'quantity': quantity}
                if order_type.upper() == 'LIMIT' and price:
                    params['timeInForce'] = 'GTC'
                    params['price'] = price
                return self.client.create_order(**params)
            except Exception as e:
                logger.error(f"Order error: {e}")
        return None
    
    def get_open_orders(self, symbol=None) -> List[Dict]:
        if not self.demo_mode and self.client and self.authenticated:
            try:
                return self.client.get_open_orders(symbol=symbol) if symbol else self.client.get_open_orders()
            except Exception:
                pass
        return []
