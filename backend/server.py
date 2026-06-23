from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
from pathlib import Path
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import asyncio
import json
import time
import numpy as np

from config import get_settings
from binance_client import BinanceSpotClient
from indicators import TechnicalIndicators
from advanced_indicators import (
    SniperScore, PrecisionSniperConfluence, LinearRegressionChannel,
    SwingProfile, FairValueGaps, CommissionAwareSignalEngine,
    IchimokuCloud, NeuroTrendII, SuperTrendedRSI, TurtleChannels,
    VWAP, OBV, ADXIndicator, CVD, MFI
)
from ai_analyzer import AITradingAnalyzer
from futures_client import BinanceFuturesClient
from exchanges.exchange_manager import ExchangeManager
from exchanges.binance_adapter import BinanceAdapter
from exchanges.bybit_adapter import BybitAdapter
from exchanges.okx_adapter import OKXAdapter
from exchanges.kraken_adapter import KrakenAdapter
from exchanges.simulated_adapter import SimulatedExchangeAdapter
from exchanges.stock_adapter import StockExchangeAdapter
from engine.risk_manager import RiskManager, RiskConfig
from engine.auto_trader import AutoTrader
from engine.arbitrage import ArbitrageScanner
from engine.triangular import TriangularArbitrage
from engine.backtester import Backtester, BacktestConfig
import market_data

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

settings = get_settings()
mongo_url = settings.mongo_url
client = None
db = None  # se inicializa en startup

# Almacenamiento en memoria como fallback
_mem_trades = []
_mem_signals = []
_mem_analyses = []
_mem_listings = []
_mem_futures = []
_mem_autotrade_log = []
_mem_open_positions = []

class _MemCollection:
    def __init__(self, store): self._store = store; self._lim = 50; self._query = {}
    async def insert_one(self, doc):
        doc.pop('_id', None); self._store.append(dict(doc)); return doc
    async def delete_one(self, q):
        for i, d in enumerate(self._store):
            if all(d.get(k) == v for k, v in q.items()):
                del self._store[i]; return
    def find(self, q=None, proj=None): self._query = q or {}; return self
    def sort(self, *a): return self
    def limit(self, n): self._lim = n; return self
    async def to_list(self, n):
        # Respeta el filtro pasado a find() (antes lo ignoraba y devolvía todo).
        items = [d for d in self._store if all(d.get(k) == v for k, v in self._query.items())]
        return list(reversed(items))[:n]

class _MemDB:
    def __init__(self):
        self.trades = _MemCollection(_mem_trades)
        self.signals = _MemCollection(_mem_signals)
        self.ai_analyses = _MemCollection(_mem_analyses)
        self.new_listings = _MemCollection(_mem_listings)
        self.futures_trades = _MemCollection(_mem_futures)
        self.auto_trade_log = _MemCollection(_mem_autotrade_log)
        self.open_positions = _MemCollection(_mem_open_positions)



binance_client = BinanceSpotClient()
futures_client = BinanceFuturesClient()
ai_analyzer = AITradingAnalyzer()
signal_engine = CommissionAwareSignalEngine()

# ── Multi-exchange + motor de auto-trading ──
exchange_manager = ExchangeManager()
_binance_adapter = BinanceAdapter(binance_client)
exchange_manager.register(_binance_adapter, set_active=True)
exchange_manager.register(BybitAdapter(settings.bybit_api_key, settings.bybit_api_secret))
exchange_manager.register(OKXAdapter(settings.okx_api_key, settings.okx_api_secret, settings.okx_passphrase))
# Kraken vía API pública: precios REALES para arbitraje cross-exchange (sin key para leer).
exchange_manager.register(KrakenAdapter(settings.kraken_api_key, settings.kraken_api_secret))
# Acciones/ETFs de EEUU (Yahoo): selecciónalo como exchange activo para que el motor
# opere acciones (operaciones largas, velas diarias). Datos públicos, ejecución paper.
exchange_manager.register(StockExchangeAdapter())
# Exchange simulado (opcional): solo si se pide explícitamente para demos.
if settings.arbitrage_simulate:
    exchange_manager.register(SimulatedExchangeAdapter(_binance_adapter, name="SimEx", max_spread=0.012))

risk_manager = RiskManager(RiskConfig(min_confidence=0.6, max_open_positions=10))
auto_trader = AutoTrader(
    exchange_manager=exchange_manager,
    risk_manager=risk_manager,
    ai_analyzer=ai_analyzer,
    scan_interval=settings.engine_scan_interval,
    commission_rate=settings.commission_rate,
)
auto_trader.use_ai = settings.engine_use_ai

arbitrage_scanner = ArbitrageScanner(
    exchange_manager=exchange_manager,
    commission_rate=settings.commission_rate,
)
# Arbitraje triangular: un solo exchange (Binance), sin segundas keys.
triangular_arb = TriangularArbitrage(
    binance_client,
    commission_rate=settings.commission_rate,
)

# Auto-trade state
auto_trade_enabled = os.environ.get('AUTO_TRADE_ENABLED', 'false').lower() == 'true'

def sanitize(obj):
    """Convert numpy types to Python native types for JSON serialization"""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(v) for v in obj]
    elif isinstance(obj, (np.integer,)):
        return int(obj)
    elif isinstance(obj, (np.floating,)):
        return float(obj)
    elif isinstance(obj, (np.bool_,)):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──
    global known_symbols, client, db
    logger.info("Starting Crypto Trading Bot")

    # Inicializar MongoDB (con fallback en memoria)
    try:
        client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=3000)
        await client.admin.command('ping')
        db = client[settings.db_name]
        logger.info(f"MongoDB conectado: {mongo_url}")
    except Exception as e:
        logger.warning(f"MongoDB no disponible, usando memoria: {e}")
        client = None
        db = _MemDB()
        logger.info("Usando almacenamiento en memoria")

    # Inyecta la DB en el motor y restaura posiciones abiertas (sobreviven reinicios).
    auto_trader.db = db
    await auto_trader.restore_positions()

    try:
        info = binance_client.get_exchange_info()
        if 'symbols' in info:
            known_symbols = {s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING'}
            logger.info(f"Loaded {len(known_symbols)} trading pairs")
    except Exception as e:
        logger.error(f"Startup error: {e}")

    listings_task = asyncio.create_task(monitor_new_listings())

    yield

    # ── shutdown ──
    auto_trader.stop()
    arbitrage_scanner.stop()
    triangular_arb.stop()
    listings_task.cancel()
    if client is not None:
        client.close()  # antes crasheaba en modo memoria (client era None)


app = FastAPI(title="Crypto Trading Bot", version="1.0.0", lifespan=lifespan)
api_router = APIRouter(prefix="/api")

# logging moved to top

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    async def broadcast(self, message: dict):
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()
known_symbols = set()

# ─── Validación / Cache / Rate-limit ───
_VALID_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"}
_INDICATORS_CACHE_TTL = 30   # segundos
_AI_COOLDOWN_TTL = 60        # segundos por símbolo

_indicators_cache: dict = {}  # (symbol, interval) -> (data, expiry)
_ai_last_call: dict = {}      # symbol -> timestamp

# ─── HEALTH & ROOT ───
@api_router.get("/")
async def root():
    return {"message": "Crypto Trading Bot API", "status": "running"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "binance_connected": binance_client.authenticated, "timestamp": datetime.now(timezone.utc).isoformat()}

# ─── PAIRS ───
@api_router.get("/pairs")
async def get_trading_pairs():
    try:
        tickers = await asyncio.to_thread(binance_client.get_ticker_24h)
        pairs = []
        for t in tickers:
            sym = t.get('symbol', '')
            if any(sym.endswith(q) for q in ['USDT', 'BTC', 'ETH', 'BNB']) and t.get('status', '') != 'BREAK':
                pairs.append({
                    'symbol': sym,
                    'price': float(t.get('lastPrice', 0)),
                    'change_24h': float(t.get('priceChangePercent', 0)),
                    'volume_24h': float(t.get('quoteVolume', 0)),
                    'high_24h': float(t.get('highPrice', 0)),
                    'low_24h': float(t.get('lowPrice', 0))
                })
        pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
        return {"success": True, "data": pairs[:100]}
    except Exception as e:
        logger.error(f"Error getting pairs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pairs/{symbol}/price")
async def get_symbol_price(symbol: str):
    try:
        ticker = binance_client.get_symbol_ticker(symbol.upper())
        if not ticker:
            raise HTTPException(status_code=404, detail="Symbol not found")
        return {"success": True, "data": {"symbol": ticker['symbol'], "price": float(ticker['price'])}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/pairs/{symbol}/klines")
async def get_klines(symbol: str, interval: str = "1h", limit: int = 200):
    try:
        sym = symbol.upper()
        # Acciones/ETFs → Yahoo Finance; cripto → Binance. Mismo formato de salida.
        if market_data.is_stock(sym):
            klines = await asyncio.to_thread(market_data.get_stock_klines, sym, interval, limit)
        else:
            # to_thread: no bloquea el event loop (el gráfico se actualiza aunque el motor opere).
            klines = await asyncio.to_thread(binance_client.get_klines, sym, interval, limit)
        data = [{"time": k[0] / 1000, "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in klines]
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── INDICATORS (Basic + Advanced) ───
@api_router.get("/pairs/{symbol}/indicators")
async def get_indicators(symbol: str, interval: str = "1h"):
    sym = symbol.upper()
    is_stock_sym = market_data.is_stock(sym)
    # Validaciones de cripto solo aplican a cripto (las acciones van por Yahoo).
    if not is_stock_sym:
        if interval not in _VALID_INTERVALS:
            raise HTTPException(status_code=400, detail=f"Intervalo inválido '{interval}'. Válidos: {sorted(_VALID_INTERVALS)}")
        if known_symbols and sym not in known_symbols:
            raise HTTPException(status_code=400, detail=f"Símbolo desconocido: {sym}")

    cache_key = (sym, interval)
    now = time.monotonic()
    if cache_key in _indicators_cache:
        cached_data, expiry = _indicators_cache[cache_key]
        if now < expiry:
            return {"success": True, "data": cached_data}

    try:
        if is_stock_sym:
            klines = await asyncio.to_thread(market_data.get_stock_klines, sym, interval, 250)
        else:
            klines = await asyncio.to_thread(binance_client.get_klines, sym, interval, 200)
        if not klines or len(klines) < 50:
            raise HTTPException(status_code=404, detail="Insufficient data")
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        
        # Basic indicators
        basic = TechnicalIndicators.get_all_indicators(klines)
        basic_signal = TechnicalIndicators.analyze_indicators(basic)
        
        # Advanced indicators
        sniper = SniperScore.calculate(closes, highs, lows, volumes)
        confluence = PrecisionSniperConfluence.calculate(closes, highs, lows, volumes)
        lr = LinearRegressionChannel.calculate(closes, highs, lows)
        swing = SwingProfile.calculate(closes, highs, lows, volumes)
        fvg = FairValueGaps.calculate(closes, highs, lows)
        ichimoku = IchimokuCloud.calculate(closes, highs, lows)
        neurotrend = NeuroTrendII.calculate(closes, highs, lows, volumes)
        st_rsi = SuperTrendedRSI.calculate(closes, highs, lows)
        turtle = TurtleChannels.calculate(closes, highs, lows)

        # Indicadores profesionales adicionales
        opens = [float(k[1]) for k in klines]
        pro = {
            'vwap':  VWAP.calculate(closes, highs, lows, volumes),
            'obv':   OBV.calculate(closes, volumes),
            'adx':   ADXIndicator.calculate(closes, highs, lows),
            'cvd':   CVD.calculate(closes, opens, volumes),
            'mfi':   MFI.calculate(closes, highs, lows, volumes),
        }
        
        # Commission-aware viability
        price = closes[-1]
        atr_risk = sniper.get('atr_risk', 0)
        if atr_risk > 0:
            viability = CommissionAwareSignalEngine.evaluate_trade_viability(
                entry_price=price,
                stop_loss=price - atr_risk,
                take_profit=price + atr_risk * 2,
                commission_rate=settings.commission_rate,
            )
        else:
            viability = {'viable': False, 'rr_ratio': 0}
        
        # Combined signal
        signals = []
        if basic_signal == 'buy': signals.append(1)
        elif basic_signal == 'sell': signals.append(-1)
        else: signals.append(0)
        
        if 'BULL' in sniper.get('bias', ''): signals.append(1)
        elif 'BEAR' in sniper.get('bias', ''): signals.append(-1)
        else: signals.append(0)
        
        if confluence.get('signal') == 'buy': signals.append(1)
        elif confluence.get('signal') == 'sell': signals.append(-1)
        else: signals.append(0)
        
        if lr.get('buy_signal'): signals.append(1)
        else: signals.append(0)
        
        # New indicators
        ich_sig = ichimoku.get('signal', 'neutral')
        if 'buy' in ich_sig: signals.append(1)
        elif 'sell' in ich_sig: signals.append(-1)
        else: signals.append(0)
        
        if neurotrend.get('buy_signal'): signals.append(1)
        elif neurotrend.get('sell_signal'): signals.append(-1)
        else: signals.append(0)
        
        st_rsi_sig = st_rsi.get('signal', 'neutral')
        if st_rsi_sig == 'buy': signals.append(1)
        elif st_rsi_sig == 'sell': signals.append(-1)
        else: signals.append(0)
        
        turtle_sig = turtle.get('signal', 'neutral')
        if turtle_sig == 'buy': signals.append(1)
        elif turtle_sig == 'sell': signals.append(-1)
        else: signals.append(0)
        
        avg_signal = sum(signals) / len(signals)
        if avg_signal > 0.3:
            combined_signal = "buy"
        elif avg_signal < -0.3:
            combined_signal = "sell"
        else:
            combined_signal = "neutral"
        
        result = {
            'symbol': symbol.upper(),
            'interval': interval,
            'basic': basic,
            'basic_signal': basic_signal,
            'sniper_score': sniper,
            'confluence_score': confluence,
            'linear_regression': lr,
            'swing_profile': swing,
            'fvg': fvg,
            'ichimoku': ichimoku,
            'neurotrend': neurotrend,
            'supertrend_rsi': st_rsi,
            'turtle_channels': turtle,
            'pro': pro,
            'viability': viability,
            'combined_signal': combined_signal,
            'signal_strength': abs(avg_signal),
            'auto_trade_enabled': auto_trade_enabled,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        sanitized = sanitize(result)
        _indicators_cache[cache_key] = (sanitized, time.monotonic() + _INDICATORS_CACHE_TTL)
        return {"success": True, "data": sanitized}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── AI ANALYSIS ───
class AIAnalysisRequest(BaseModel):
    symbol: str
    interval: str = "1h"

@api_router.post("/analysis/ai")
async def get_ai_analysis(req: AIAnalysisRequest):
    if req.interval not in _VALID_INTERVALS:
        raise HTTPException(status_code=400, detail=f"Intervalo inválido '{req.interval}'. Válidos: {sorted(_VALID_INTERVALS)}")
    sym = req.symbol.upper()
    if known_symbols and sym not in known_symbols:
        raise HTTPException(status_code=400, detail=f"Símbolo desconocido: {sym}")

    now = time.monotonic()
    last_call = _ai_last_call.get(sym, 0)
    if now - last_call < _AI_COOLDOWN_TTL:
        remaining = int(_AI_COOLDOWN_TTL - (now - last_call))
        raise HTTPException(status_code=429, detail=f"Rate limit: espera {remaining}s antes del siguiente análisis de {sym}")

    try:
        klines = await asyncio.to_thread(binance_client.get_klines, sym, req.interval, 200)
        if not klines or len(klines) < 50:
            raise HTTPException(status_code=404, detail="Insufficient data")
        
        closes = [float(k[4]) for k in klines]
        highs = [float(k[2]) for k in klines]
        lows = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]

        # Calculate all indicators
        basic = TechnicalIndicators.get_all_indicators(klines)
        sniper = SniperScore.calculate(closes, highs, lows, volumes)
        confluence = PrecisionSniperConfluence.calculate(closes, highs, lows, volumes)
        lr = LinearRegressionChannel.calculate(closes, highs, lows)
        swing = SwingProfile.calculate(closes, highs, lows, volumes)
        fvg = FairValueGaps.calculate(closes, highs, lows)
        ichimoku = IchimokuCloud.calculate(closes, highs, lows)
        neurotrend = NeuroTrendII.calculate(closes, highs, lows, volumes)

        # Combine all indicators for AI
        all_indicators = {**basic, 'sniper_score': sniper, 'confluence_score': confluence,
                          'linear_regression': lr, 'swing_profile': swing, 'fvg': fvg,
                          'ichimoku': ichimoku, 'neurotrend': neurotrend}

        analysis = await ai_analyzer.analyze_market(sym, all_indicators, commission_rate=settings.commission_rate)
        _ai_last_call[sym] = time.monotonic()
        
        # Save to DB
        doc = {
            'symbol': req.symbol.upper(),
            'analysis': analysis['analysis'],
            'recommendation': analysis['recommendation'],
            'confidence': float(analysis['confidence']) if analysis['confidence'] else 0.0,
            'entry_price': analysis.get('entry_price'),
            'stop_loss': analysis.get('stop_loss'),
            'take_profit_1': analysis.get('take_profit_1'),
            'take_profit_2': analysis.get('take_profit_2'),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        await db.ai_analyses.insert_one(doc)
        
        return {"success": True, "data": sanitize(analysis)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/analysis/history")
async def get_ai_history(symbol: Optional[str] = None, limit: int = 20):
    try:
        query = {'symbol': symbol.upper()} if symbol else {}
        analyses = await db.ai_analyses.find(query, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"success": True, "data": analyses}
    except Exception as e:
        return {"success": True, "data": []}

# ─── SIGNALS ───
@api_router.get("/signals")
async def get_signals(limit: int = 50):
    try:
        signals = await db.signals.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"success": True, "data": signals}
    except Exception as e:
        return {"success": True, "data": []}

# ─── ACCOUNT ───
@api_router.get("/account/balance")
async def get_balance():
    try:
        if not binance_client.authenticated:
            return {"success": True, "data": {
                "mode": "demo",
                "balances": {"USDT": {"free": 10000.0, "locked": 0.0}, "BTC": {"free": 0.5, "locked": 0.0}}
            }}
        balance = binance_client.get_account_balance()
        return {"success": True, "data": {"mode": "live", "balances": balance}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── ORDERS ───
class OrderRequest(BaseModel):
    symbol: str
    side: str
    order_type: str = "market"
    quantity: float
    price: Optional[float] = None
    mode: str = "manual"

@api_router.post("/orders")
async def place_order(order: OrderRequest):
    try:
        doc = {
            'id': str(id(order)) + str(datetime.now(timezone.utc).timestamp()),
            'symbol': order.symbol.upper(),
            'side': order.side,
            'order_type': order.order_type,
            'quantity': order.quantity,
            'price': order.price,
            'executed_price': order.price,
            'status': 'DEMO_FILLED' if not binance_client.authenticated else 'PENDING',
            'mode': order.mode,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        if binance_client.authenticated:
            result = binance_client.place_order(order.symbol, order.side, order.order_type, order.quantity, order.price)
            if result:
                doc['order_id'] = result.get('orderId')
                doc['status'] = result.get('status', 'FILLED')
                doc['executed_price'] = float(result.get('price', 0)) or order.price
        
        await db.trades.insert_one(doc)
        doc.pop('_id', None)
        return {"success": True, "data": doc}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/orders/history")
async def get_order_history(limit: int = 50):
    try:
        trades = await db.trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"success": True, "data": trades}
    except Exception as e:
        return {"success": True, "data": []}

# ─── NEW LISTINGS ───
@api_router.get("/new-listings")
async def get_new_listings():
    try:
        listings = await db.new_listings.find({}, {"_id": 0}).sort("detected_at", -1).limit(20).to_list(20)
        return {"success": True, "data": listings}
    except Exception as e:
        return {"success": True, "data": []}

# ─── SETTINGS ───
@api_router.get("/settings")
async def get_settings_api():
    return {"success": True, "data": {
        "trading_mode": settings.trading_mode,
        "binance_connected": binance_client.authenticated,
        "binance_testnet": settings.binance_testnet,
        "commission_rate": settings.commission_rate,
        "auto_trade_enabled": auto_trade_enabled,
        "available_intervals": ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "12h", "1d", "1w"]
    }}

class AutoTradeToggle(BaseModel):
    enabled: bool

@api_router.post("/settings/auto-trade")
async def toggle_auto_trade(data: AutoTradeToggle):
    global auto_trade_enabled
    auto_trade_enabled = data.enabled
    logger.info(f"Auto-trade {'ENABLED' if auto_trade_enabled else 'DISABLED'}")
    
    # Log toggle event
    await db.auto_trade_log.insert_one({
        'action': 'enabled' if auto_trade_enabled else 'disabled',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "auto_trade_enabled": auto_trade_enabled}

# ─── FUTURES ───
class FuturesOrderRequest(BaseModel):
    symbol: str
    side: str  # "long" or "short"
    action: str  # "open" or "close"
    quantity: float
    leverage: int = 5

@api_router.post("/futures/order")
async def futures_order(req: FuturesOrderRequest):
    try:
        result = None
        if req.action == "open" and req.side == "long":
            result = futures_client.open_long(req.symbol.upper(), req.quantity, req.leverage)
        elif req.action == "close" and req.side == "long":
            result = futures_client.close_long(req.symbol.upper(), req.quantity)
        elif req.action == "open" and req.side == "short":
            result = futures_client.open_short(req.symbol.upper(), req.quantity, req.leverage)
        elif req.action == "close" and req.side == "short":
            result = futures_client.close_short(req.symbol.upper(), req.quantity)
        
        if result is None:
            raise HTTPException(status_code=400, detail="Order failed")
        
        doc = {
            'symbol': req.symbol.upper(),
            'market': 'futures',
            'side': req.side,
            'action': req.action,
            'quantity': req.quantity,
            'leverage': req.leverage,
            'status': result.get('status', 'DEMO_FILLED'),
            'order_id': str(result.get('orderId', '')),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        await db.futures_trades.insert_one(doc)
        doc.pop('_id', None)
        return {"success": True, "data": doc}
    except Exception as e:
        logger.error(f"Futures order error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/futures/positions")
async def get_futures_positions():
    try:
        positions = futures_client.get_positions()
        clean = []
        for p in positions:
            clean.append({
                'symbol': p.get('symbol'),
                'positionAmt': float(p.get('positionAmt', 0)),
                'entryPrice': float(p.get('entryPrice', 0)),
                'markPrice': float(p.get('markPrice', 0)),
                'unRealizedProfit': float(p.get('unRealizedProfit', 0)),
                'leverage': int(p.get('leverage', 1)),
                'positionSide': p.get('positionSide', 'BOTH')
            })
        return {"success": True, "data": clean}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/futures/balance")
async def get_futures_balance():
    try:
        balances = futures_client.get_account_balance()
        clean = []
        for b in balances:
            bal = float(b.get('balance', 0))
            avail = float(b.get('availableBalance', b.get('balance', 0)))
            if bal > 0:
                clean.append({'asset': b.get('asset'), 'balance': bal, 'available': avail})
        return {"success": True, "data": clean, "futures_connected": futures_client.authenticated}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/futures/history")
async def get_futures_history(limit: int = 50):
    try:
        trades = await db.futures_trades.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"success": True, "data": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── EXCHANGES ───
@api_router.get("/exchanges")
async def list_exchanges():
    return {"success": True, "data": exchange_manager.list_status()}

class SetExchangeRequest(BaseModel):
    name: str

@api_router.post("/exchanges/active")
async def set_active_exchange(req: SetExchangeRequest):
    if exchange_manager.set_active(req.name):
        return {"success": True, "active": req.name}
    raise HTTPException(status_code=400, detail=f"Exchange '{req.name}' no disponible o sin conexión")

# ─── AUTO-TRADE ENGINE ───
@api_router.get("/engine/status")
async def engine_status():
    return {"success": True, "data": auto_trader.snapshot()}

@api_router.post("/engine/start")
async def engine_start():
    auto_trader.start()
    return {"success": True, "running": auto_trader.running}

@api_router.post("/engine/stop")
async def engine_stop():
    auto_trader.stop()
    return {"success": True, "running": auto_trader.running}

@api_router.post("/engine/close-all")
async def engine_close_all():
    """PÁNICO: detiene el motor y cierra todas las posiciones abiertas."""
    closed = await auto_trader.close_all()
    return {"success": True, "closed": closed, "running": auto_trader.running}

class EngineConfigRequest(BaseModel):
    scan_interval: Optional[float] = None
    use_ai: Optional[bool] = None
    mode: Optional[str] = None              # 'paper' | 'live'
    strategy_mode: Optional[str] = None     # 'momentum' | 'pullback' | 'volume'
    use_trailing_stop: Optional[bool] = None
    use_leverage: Optional[bool] = None
    leverage: Optional[int] = None
    risk_per_trade_pct: Optional[float] = None
    max_open_positions: Optional[int] = None
    max_daily_loss_pct: Optional[float] = None
    min_confidence: Optional[float] = None
    min_rr_ratio: Optional[float] = None

@api_router.post("/engine/config")
async def engine_config(req: EngineConfigRequest):
    if req.scan_interval is not None:
        auto_trader.scan_interval = max(5.0, req.scan_interval)
    if req.use_ai is not None:
        auto_trader.use_ai = req.use_ai
    if req.mode is not None:
        if req.mode not in ("paper", "live"):
            raise HTTPException(status_code=400, detail="mode debe ser 'paper' o 'live'")
        auto_trader.mode = req.mode
    if req.strategy_mode is not None:
        if req.strategy_mode not in ("momentum", "pullback", "volume"):
            raise HTTPException(status_code=400, detail="strategy_mode inválido")
        auto_trader.params.mode = req.strategy_mode
    if req.use_trailing_stop is not None:
        auto_trader.use_trailing_stop = req.use_trailing_stop
    if req.use_leverage is not None:
        auto_trader.use_leverage = req.use_leverage
    if req.leverage is not None:
        auto_trader.leverage = max(1, min(int(req.leverage), 20))
    rc = risk_manager.config
    if req.risk_per_trade_pct is not None:
        rc.risk_per_trade_pct = req.risk_per_trade_pct
    if req.max_open_positions is not None:
        rc.max_open_positions = req.max_open_positions
    if req.max_daily_loss_pct is not None:
        rc.max_daily_loss_pct = req.max_daily_loss_pct
    if req.min_confidence is not None:
        rc.min_confidence = req.min_confidence
    if req.min_rr_ratio is not None:
        rc.min_rr_ratio = req.min_rr_ratio
    return {"success": True, "data": auto_trader.snapshot()}

# ─── STOCKS / MERCADOS TRADICIONALES (acciones, ETFs de EEUU) ───
@api_router.get("/stocks/list")
async def stocks_list():
    return {"success": True, "data": market_data.list_stocks()}

@api_router.get("/stocks/{symbol}/klines")
async def stocks_klines(symbol: str, interval: str = "1d", limit: int = 500):
    klines = await asyncio.to_thread(market_data.get_stock_klines, symbol.upper(), interval, limit)
    if not klines:
        raise HTTPException(status_code=404, detail=f"Sin datos para {symbol}")
    data = [{"time": k[0] / 1000, "open": k[1], "high": k[2], "low": k[3], "close": k[4], "volume": k[5]} for k in klines]
    return {"success": True, "data": data}

# ─── BACKTESTING ───
class BacktestRequest(BaseModel):
    symbol: str
    interval: str = "15m"
    limit: int = 1000
    initial_balance: float = 10000.0
    risk_per_trade_pct: float = 0.02
    use_trailing_stop: bool = True
    market: str = "crypto"   # 'crypto' (Binance) | 'stocks' (Yahoo Finance)

@api_router.post("/backtest/run")
async def backtest_run(req: BacktestRequest):
    sym = req.symbol.upper()
    if req.market == "stocks":
        # Acciones: velas diarias por defecto (operaciones largas, menor volatilidad).
        stock_interval = req.interval if req.interval in ("1d", "1wk", "1mo") else "1d"
        klines = await asyncio.to_thread(market_data.get_stock_klines, sym, stock_interval, min(max(req.limit, 250), 1500))
    else:
        if req.interval not in _VALID_INTERVALS:
            raise HTTPException(status_code=400, detail=f"Intervalo inválido '{req.interval}'")
        klines = await asyncio.to_thread(binance_client.get_klines, sym, req.interval, min(max(req.limit, 250), 1500))
    if not klines or len(klines) < 250:
        raise HTTPException(status_code=404, detail="Datos históricos insuficientes")
    candles = [
        {"time": k[0], "open": float(k[1]), "high": float(k[2]),
         "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])}
        for k in klines
    ]
    config = BacktestConfig(
        initial_balance=req.initial_balance,
        risk_per_trade_pct=req.risk_per_trade_pct,
        commission_rate=settings.commission_rate,
        use_trailing_stop=req.use_trailing_stop,
    )
    result = Backtester(config).run(candles, sym)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"success": True, "data": sanitize(result)}

# ─── ARBITRAJE ───
@api_router.get("/arbitrage/status")
async def arbitrage_status():
    return {"success": True, "data": arbitrage_scanner.snapshot()}

@api_router.post("/arbitrage/start")
async def arbitrage_start():
    arbitrage_scanner.start()
    return {"success": True, "running": arbitrage_scanner.running}

@api_router.post("/arbitrage/stop")
async def arbitrage_stop():
    arbitrage_scanner.stop()
    return {"success": True, "running": arbitrage_scanner.running}

class ArbitrageConfigRequest(BaseModel):
    execute: Optional[bool] = None
    min_net_spread_pct: Optional[float] = None
    scan_interval: Optional[float] = None

@api_router.post("/arbitrage/config")
async def arbitrage_config(req: ArbitrageConfigRequest):
    if req.execute is not None:
        arbitrage_scanner.execute = req.execute
    if req.min_net_spread_pct is not None:
        arbitrage_scanner.min_net_spread_pct = req.min_net_spread_pct
    if req.scan_interval is not None:
        arbitrage_scanner.scan_interval = max(2.0, req.scan_interval)
    return {"success": True, "data": arbitrage_scanner.snapshot()}

# ─── ARBITRAJE TRIANGULAR (un solo exchange) ───
@api_router.get("/arbitrage/triangular/status")
async def triangular_status():
    return {"success": True, "data": triangular_arb.snapshot()}

@api_router.post("/arbitrage/triangular/start")
async def triangular_start():
    triangular_arb.start()
    return {"success": True, "running": triangular_arb.running}

@api_router.post("/arbitrage/triangular/stop")
async def triangular_stop():
    triangular_arb.stop()
    return {"success": True, "running": triangular_arb.running}

# ─── WebSocket for real-time prices ───
@app.websocket("/ws/prices")
async def websocket_prices(websocket: WebSocket):
    await manager.connect(websocket)
    subscribed_symbols = set()
    try:
        # Start with default
        subscribed_symbols.add("BTCUSDT")
        
        async def price_sender():
            while True:
                for symbol in list(subscribed_symbols):
                    ticker = await asyncio.to_thread(binance_client.get_symbol_ticker, symbol)
                    if ticker:
                        await websocket.send_json({
                            "type": "price_update",
                            "symbol": symbol,
                            "price": float(ticker['price']),
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                await asyncio.sleep(1.5)
        
        sender_task = asyncio.create_task(price_sender())
        
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("action") == "subscribe":
                sym = msg.get("symbol", "BTCUSDT").upper()
                subscribed_symbols.add(sym)
            elif msg.get("action") == "unsubscribe":
                sym = msg.get("symbol", "").upper()
                subscribed_symbols.discard(sym)
            elif msg.get("action") == "set_symbol":
                subscribed_symbols.clear()
                subscribed_symbols.add(msg.get("symbol", "BTCUSDT").upper())
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
    finally:
        if 'sender_task' in dir():
            sender_task.cancel()

# ─── Background Tasks ───
async def monitor_new_listings():
    global known_symbols
    while True:
        try:
            exchange_info = binance_client.get_exchange_info()
            if 'symbols' in exchange_info:
                current = {s['symbol'] for s in exchange_info['symbols'] if s['status'] == 'TRADING'}
                if known_symbols:
                    new = current - known_symbols
                    for sym in new:
                        info = next((s for s in exchange_info['symbols'] if s['symbol'] == sym), None)
                        if info:
                            doc = {'symbol': sym, 'base_asset': info['baseAsset'], 'quote_asset': info['quoteAsset'],
                                   'detected_at': datetime.now(timezone.utc).isoformat()}
                            await db.new_listings.insert_one(doc)
                            logger.info(f"New listing: {sym}")
                            await manager.broadcast({"type": "new_listing", "data": {"symbol": sym}})
                known_symbols = current
        except Exception as e:
            logger.error(f"Listings monitor error: {e}")
        await asyncio.sleep(120)

app.include_router(api_router)

# CORS desde config (CORS_ORIGINS="*" o lista separada por comas)
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["*"]
app.add_middleware(CORSMiddleware, allow_credentials=False,
                   allow_origins=_cors_origins,
                   allow_methods=["*"], allow_headers=["*"])


# Punto de entrada para el ejecutable empaquetado (PyInstaller).
# Electron lo lanza directamente; lee el puerto de la variable PORT.
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
