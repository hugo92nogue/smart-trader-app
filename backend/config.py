from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Literal
import os
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

class Settings(BaseSettings):
    """Application configuration loaded from environment variables"""
    app_name: str = "Smart Trader Bot"
    
    # MongoDB
    mongo_url: str = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name: str = os.environ.get('DB_NAME', 'smart_trader_db')
    
    # Binance API
    binance_api_key: str = os.environ.get('BINANCE_API_KEY', '')
    binance_api_secret: str = os.environ.get('BINANCE_API_SECRET', '')
    binance_testnet: bool = os.environ.get('BINANCE_TESTNET', 'true').lower() == 'true'
    
    # Binance Futures
    binance_futures_key: str = os.environ.get('BINANCE_FUTURES_KEY', '')
    binance_futures_secret: str = os.environ.get('BINANCE_FUTURES_SECRET', '')

    # ✅ Anthropic API directo (reemplaza Emergent)
    anthropic_api_key: str = os.environ.get('ANTHROPIC_API_KEY', '')
    
    # Trading Mode
    trading_mode: Literal["auto", "semi_auto", "signals_only"] = os.environ.get('TRADING_MODE', 'semi_auto')
    auto_trade_enabled: bool = os.environ.get('AUTO_TRADE_ENABLED', 'false').lower() == 'true'
    
    cors_origins: str = os.environ.get('CORS_ORIGINS', '*')
    
    model_config = SettingsConfigDict(env_file=".env")
    
    @property
    def binance_base_url(self) -> str:
        return "https://testnet.binance.vision" if self.binance_testnet else "https://api.binance.com"
    
    @property
    def binance_websocket_url(self) -> str:
        if self.binance_testnet:
            return "wss://testnet.binance.vision/ws"
        return "wss://stream.binance.com:9443/ws"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
