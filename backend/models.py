from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
from datetime import datetime
import uuid

class TradingPair(BaseModel):
    model_config = ConfigDict(extra="ignore")
    symbol: str
    base_asset: str
    quote_asset: str
    status: str
    price: Optional[float] = None
    change_24h: Optional[float] = None
    volume_24h: Optional[float] = None
    is_new: bool = False

class Indicator(BaseModel):
    name: str
    value: float
    signal: Literal["buy", "sell", "neutral"]
    timestamp: datetime

class TradingSignal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    signal_type: Literal["entry", "exit"]
    action: Literal["buy", "sell"]
    price: float
    indicators: List[Indicator]
    confidence: float
    ai_analysis: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["active", "executed", "expired"] = "active"

class Trade(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    order_id: Optional[int] = None
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: float
    price: Optional[float] = None
    executed_price: Optional[float] = None
    status: str
    mode: Literal["auto", "semi_auto", "manual"]
    signal_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    pnl: Optional[float] = None

class AIAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    analysis: str
    recommendation: Literal["buy", "sell", "hold"]
    confidence: float
    indicators_summary: dict
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class NewListing(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    base_asset: str
    quote_asset: str
    listing_time: datetime
    initial_price: Optional[float] = None
    current_price: Optional[float] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    notified: bool = False
