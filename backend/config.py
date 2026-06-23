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

    # Bybit (multi-exchange — opcional, stub hasta conectar API)
    bybit_api_key: str = os.environ.get('BYBIT_API_KEY', '')
    bybit_api_secret: str = os.environ.get('BYBIT_API_SECRET', '')

    # OKX (multi-exchange — opcional, stub hasta conectar API)
    okx_api_key: str = os.environ.get('OKX_API_KEY', '')
    okx_api_secret: str = os.environ.get('OKX_API_SECRET', '')
    okx_passphrase: str = os.environ.get('OKX_PASSPHRASE', '')

    # Kraken — lectura de precios es pública (no requiere key). Key solo para ejecutar.
    kraken_api_key: str = os.environ.get('KRAKEN_API_KEY', '')
    kraken_api_secret: str = os.environ.get('KRAKEN_API_SECRET', '')

    # Auto-trade engine
    engine_scan_interval: float = float(os.environ.get('ENGINE_SCAN_INTERVAL', '30'))
    engine_use_ai: bool = os.environ.get('ENGINE_USE_AI', 'false').lower() == 'true'

    # Arbitraje: exchange simulado adicional (ya hay Kraken real, por defecto off)
    arbitrage_simulate: bool = os.environ.get('ARBITRAGE_SIMULATE', 'false').lower() == 'true'

    # ✅ Anthropic API directo (reemplaza Emergent)
    anthropic_api_key: str = os.environ.get('ANTHROPIC_API_KEY', '')
    # Modelo de Claude (ajustable sin tocar código: claude-opus-4-8, claude-sonnet-4-6, claude-haiku-4-5...)
    anthropic_model: str = os.environ.get('ANTHROPIC_MODEL', 'claude-opus-4-8')
    
    # Commission rate (Binance maker/taker: 0.001 = 0.1%)
    commission_rate: float = float(os.environ.get('COMMISSION_RATE', '0.001'))

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
