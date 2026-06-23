"""
Proveedor de datos de mercados tradicionales (acciones / ETFs de EEUU) vía Yahoo Finance.

Devuelve velas en el MISMO formato que Binance: [time_ms, open, high, low, close, volume],
para reutilizar todos los indicadores, el backtester y el gráfico sin cambios.

Mercados tradicionales = menor volatilidad que cripto → operaciones más largas (1d/1wk/1mo,
posiciones de semanas a meses). Datos públicos, sin API key.
"""
import logging
import time
import requests
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart"
_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Universo curado de acciones/ETFs líquidos de EEUU (bajo riesgo relativo, alto volumen).
STOCK_UNIVERSE = [
    {"symbol": "SPY",  "name": "S&P 500 ETF"},
    {"symbol": "QQQ",  "name": "Nasdaq 100 ETF"},
    {"symbol": "DIA",  "name": "Dow Jones ETF"},
    {"symbol": "IWM",  "name": "Russell 2000 ETF"},
    {"symbol": "AAPL", "name": "Apple"},
    {"symbol": "MSFT", "name": "Microsoft"},
    {"symbol": "GOOGL","name": "Alphabet"},
    {"symbol": "AMZN", "name": "Amazon"},
    {"symbol": "NVDA", "name": "NVIDIA"},
    {"symbol": "META", "name": "Meta"},
    {"symbol": "TSLA", "name": "Tesla"},
    {"symbol": "JPM",  "name": "JPMorgan"},
    {"symbol": "V",    "name": "Visa"},
    {"symbol": "JNJ",  "name": "Johnson & Johnson"},
    {"symbol": "WMT",  "name": "Walmart"},
    {"symbol": "PG",   "name": "Procter & Gamble"},
    {"symbol": "KO",   "name": "Coca-Cola"},
    {"symbol": "GLD",  "name": "Oro (ETF)"},
    {"symbol": "TLT",  "name": "Bonos USA 20+ años"},
    {"symbol": "VTI",  "name": "Total Market ETF"},
]

# Conjunto de símbolos para detección rápida (¿es acción o cripto?).
STOCK_SYMBOLS = {s["symbol"] for s in STOCK_UNIVERSE}

# Intervalos válidos de Yahoo y rango por defecto para tener histórico suficiente.
_RANGE_FOR = {
    "1mo": "max", "1wk": "5y", "1d": "2y",
    "1h": "3mo", "30m": "1mo", "15m": "1mo", "5m": "5d", "1m": "5d",
}

# Cripto usa intervalos que Yahoo no tiene (4h). Mapeo al más cercano soportado.
_YAHOO_INTERVAL = {
    "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "4h": "1h", "1d": "1d", "1wk": "1wk", "1mo": "1mo",
}


def is_stock(symbol: str) -> bool:
    """True si el símbolo pertenece al universo de acciones/ETFs (no cripto)."""
    return symbol.upper() in STOCK_SYMBOLS


def to_yahoo_interval(interval: str) -> str:
    """Traduce un intervalo de cripto al equivalente soportado por Yahoo Finance."""
    return _YAHOO_INTERVAL.get(interval, "1d")


def list_stocks() -> List[Dict]:
    return STOCK_UNIVERSE


def get_stock_klines(symbol: str, interval: str = "1d", limit: int = 500) -> List:
    """Velas de una acción/ETF en formato Binance: [t_ms, o, h, l, c, v]."""
    interval = to_yahoo_interval(interval)
    rng = _RANGE_FOR.get(interval, "2y")
    url = f"{YAHOO_CHART}/{symbol.upper()}"
    try:
        r = requests.get(url, params={"interval": interval, "range": rng},
                         headers=_HEADERS, timeout=10)
        data = r.json()
        result = data.get("chart", {}).get("result")
        if not result:
            return []
        res = result[0]
        ts = res.get("timestamp", [])
        q = res.get("indicators", {}).get("quote", [{}])[0]
        opens, highs, lows, closes, vols = (
            q.get("open", []), q.get("high", []), q.get("low", []),
            q.get("close", []), q.get("volume", []),
        )
        klines = []
        for i in range(len(ts)):
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
            if None in (o, h, l, c):   # Yahoo deja huecos en festivos/datos faltantes
                continue
            v = vols[i] if i < len(vols) and vols[i] is not None else 0
            klines.append([ts[i] * 1000, float(o), float(h), float(l), float(c), float(v)])
        return klines[-limit:]
    except Exception as e:
        logger.warning(f"Yahoo Finance error {symbol}: {e}")
        return []


# Caché de precio en vivo (Yahoo no da WebSocket; refrescamos cada _PRICE_TTL s).
_PRICE_TTL = 15.0
_price_cache: Dict[str, tuple] = {}   # symbol -> (price, ts)


def get_stock_price(symbol: str) -> Optional[float]:
    """Último precio de una acción/ETF (close más reciente), con caché corta."""
    sym = symbol.upper()
    now = time.monotonic()
    cached = _price_cache.get(sym)
    if cached and now - cached[1] < _PRICE_TTL:
        return cached[0]
    try:
        r = requests.get(f"{YAHOO_CHART}/{sym}",
                         params={"interval": "1m", "range": "1d"},
                         headers=_HEADERS, timeout=8)
        res = r.json().get("chart", {}).get("result")
        if not res:
            return cached[0] if cached else None
        meta = res[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        if price is None:
            closes = res[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]
            price = closes[-1] if closes else None
        if price is not None:
            price = float(price)
            _price_cache[sym] = (price, now)
            return price
    except Exception as e:
        logger.warning(f"Yahoo price error {sym}: {e}")
    return cached[0] if cached else None


def get_stock_ticker(symbol: str) -> Dict:
    """Resumen para el selector de pares: precio + cambio % de la sesión."""
    sym = symbol.upper()
    name = next((s["name"] for s in STOCK_UNIVERSE if s["symbol"] == sym), sym)
    out = {"symbol": sym, "name": name, "price": 0.0, "change_24h": 0.0}
    try:
        r = requests.get(f"{YAHOO_CHART}/{sym}",
                         params={"interval": "1d", "range": "5d"},
                         headers=_HEADERS, timeout=8)
        res = r.json().get("chart", {}).get("result")
        if not res:
            return out
        meta = res[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is not None:
            out["price"] = float(price)
        if price is not None and prev:
            out["change_24h"] = round((float(price) - float(prev)) / float(prev) * 100, 2)
    except Exception as e:
        logger.warning(f"Yahoo ticker error {sym}: {e}")
    return out
