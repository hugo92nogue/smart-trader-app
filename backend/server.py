from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timezone
import asyncio
import json
import numpy as np

from config import get_settings
from binance_client import BinanceSpotClient
from indicators import TechnicalIndicators
from advanced_indicators import (
    SniperScore, PrecisionSniperConfluence, LinearRegressionChannel,
    SwingProfile, FairValueGaps, CommissionAwareSignalEngine,
    IchimokuCloud, NeuroTrendII, SuperTrendedRSI, TurtleChannels
)
from ai_analyzer import AITradingAnalyzer
from futures_client import BinanceFuturesClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

settings = get_settings()
mongo_url = settings.mongo_url
client = AsyncIOMotorClient(mongo_url)
db = client[settings.db_name]

binance_client = BinanceSpotClient()
futures_client = BinanceFuturesClient()
ai_analyzer = AITradingAnalyzer()
signal_engine = CommissionAwareSignalEngine()

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

app = FastAPI(title="Crypto Trading Bot", version="1.0.0")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        tickers = binance_client.get_ticker_24h()
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
        klines = binance_client.get_klines(symbol.upper(), interval, limit)
        data = [{"time": k[0] / 1000, "open": float(k[1]), "high": float(k[2]), "low": float(k[3]), "close": float(k[4]), "volume": float(k[5])} for k in klines]
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── INDICATORS (Basic + Advanced) ───
@api_router.get("/pairs/{symbol}/indicators")
async def get_indicators(symbol: str, interval: str = "1h"):
    try:
        klines = binance_client.get_klines(symbol.upper(), interval, 200)
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
        
        # Commission-aware viability
        price = closes[-1]
        atr_risk = sniper.get('atr_risk', 0)
        if atr_risk > 0:
            viability = CommissionAwareSignalEngine.evaluate_trade_viability(
                entry_price=price,
                stop_loss=price - atr_risk,
                take_profit=price + atr_risk * 2,
                commission_rate=0.001
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
            'viability': viability,
            'combined_signal': combined_signal,
            'signal_strength': abs(avg_signal),
            'auto_trade_enabled': auto_trade_enabled,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        return {"success": True, "data": sanitize(result)}
    except Exception as e:
        logger.error(f"Error calculating indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ─── AI ANALYSIS ───
class AIAnalysisRequest(BaseModel):
    symbol: str
    interval: str = "1h"

@api_router.post("/analysis/ai")
async def get_ai_analysis(req: AIAnalysisRequest):
    try:
        klines = binance_client.get_klines(req.symbol.upper(), req.interval, 200)
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
        
        analysis = await ai_analyzer.analyze_market(req.symbol.upper(), all_indicators, commission_rate=0.001)
        
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
        raise HTTPException(status_code=500, detail=str(e))

# ─── SIGNALS ───
@api_router.get("/signals")
async def get_signals(limit: int = 50):
    try:
        signals = await db.signals.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        return {"success": True, "data": signals}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        raise HTTPException(status_code=500, detail=str(e))

# ─── NEW LISTINGS ───
@api_router.get("/new-listings")
async def get_new_listings():
    try:
        listings = await db.new_listings.find({}, {"_id": 0}).sort("detected_at", -1).limit(20).to_list(20)
        return {"success": True, "data": listings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── SETTINGS ───
@api_router.get("/settings")
async def get_settings_api():
    return {"success": True, "data": {
        "trading_mode": settings.trading_mode,
        "binance_connected": binance_client.authenticated,
        "binance_testnet": settings.binance_testnet,
        "commission_rate": 0.001,
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
                    ticker = binance_client.get_symbol_ticker(symbol)
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

app.add_middleware(CORSMiddleware, allow_credentials=True,
                   allow_origins=settings.cors_origins.split(','),
                   allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
async def startup_event():
    global known_symbols
    logger.info("Starting Crypto Trading Bot")
    try:
        info = binance_client.get_exchange_info()
        if 'symbols' in info:
            known_symbols = {s['symbol'] for s in info['symbols'] if s['status'] == 'TRADING'}
            logger.info(f"Loaded {len(known_symbols)} trading pairs")
    except Exception as e:
        logger.error(f"Startup error: {e}")
    asyncio.create_task(monitor_new_listings())

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
