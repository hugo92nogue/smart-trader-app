import logging
from typing import Dict, List, Optional

from .base import ExchangeAdapter

logger = logging.getLogger(__name__)


class ExchangeManager:
    """Registro central de exchanges. Permite operar varios mercados con una API unificada."""

    def __init__(self):
        self._exchanges: Dict[str, ExchangeAdapter] = {}
        self._active: Optional[str] = None

    def register(self, adapter: ExchangeAdapter, set_active: bool = False) -> None:
        key = adapter.name.lower()
        self._exchanges[key] = adapter
        status = "conectado" if adapter.is_connected else "stub (sin API key)"
        logger.info(f"Exchange registrado: {adapter.name} [{status}]")
        if set_active or self._active is None:
            if adapter.is_connected:
                self._active = key

    def get(self, name: str) -> Optional[ExchangeAdapter]:
        return self._exchanges.get(name.lower())

    @property
    def active(self) -> Optional[ExchangeAdapter]:
        if self._active:
            return self._exchanges.get(self._active)
        # Fallback: primer exchange conectado
        for adapter in self._exchanges.values():
            if adapter.is_connected:
                return adapter
        return None

    def set_active(self, name: str) -> bool:
        key = name.lower()
        if key in self._exchanges and self._exchanges[key].is_connected:
            self._active = key
            logger.info(f"Exchange activo: {self._exchanges[key].name}")
            return True
        return False

    def list_status(self) -> List[Dict]:
        return [
            {
                "name": adapter.name,
                "connected": adapter.is_connected,
                "active": key == self._active,
            }
            for key, adapter in self._exchanges.items()
        ]

    @property
    def connected_exchanges(self) -> List[ExchangeAdapter]:
        return [a for a in self._exchanges.values() if a.is_connected]
