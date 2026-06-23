import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.02       # 2% del balance arriesgado por operación
    max_open_positions: int = 5
    max_daily_loss_pct: float = 0.06       # corta el día tras -6% del balance
    min_confidence: float = 0.65           # confianza mínima (0-1) para entrar
    min_rr_ratio: float = 1.5              # ratio riesgo/beneficio mínimo
    max_position_pct: float = 0.20         # ninguna posición supera el 20% del balance


@dataclass
class RiskState:
    daily_pnl: float = 0.0
    daily_start_balance: float = 0.0
    day: str = ""
    halted: bool = False
    halt_reason: str = ""


class RiskManager:
    """Controla el tamaño de posición y los límites de pérdida. El corazón de 'pérdidas muy pequeñas'."""

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()
        self.state = RiskState()

    def _today(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def roll_day_if_needed(self, balance: float) -> None:
        today = self._today()
        if self.state.day != today:
            self.state.day = today
            self.state.daily_pnl = 0.0
            self.state.daily_start_balance = balance
            self.state.halted = False
            self.state.halt_reason = ""
            logger.info(f"Nuevo día de trading. Balance inicial: ${balance:.2f}")

    def can_open(self, open_positions: int, confidence: float, rr_ratio: float) -> tuple[bool, str]:
        c = self.config
        if self.state.halted:
            return False, f"Trading detenido: {self.state.halt_reason}"
        if open_positions >= c.max_open_positions:
            return False, f"Máximo de posiciones abiertas ({c.max_open_positions})"
        if confidence < c.min_confidence:
            return False, f"Confianza {confidence:.0%} < mínimo {c.min_confidence:.0%}"
        if rr_ratio is not None and rr_ratio < c.min_rr_ratio:
            return False, f"R/R {rr_ratio:.2f} < mínimo {c.min_rr_ratio}"
        return True, "OK"

    def position_size(self, balance: float, entry_price: float, stop_loss: float) -> float:
        """Tamaño basado en riesgo: arriesga risk_per_trade_pct y limita por max_position_pct."""
        c = self.config
        risk_per_unit = abs(entry_price - stop_loss)
        if risk_per_unit <= 0 or entry_price <= 0:
            return 0.0
        risk_amount = balance * c.risk_per_trade_pct
        qty = risk_amount / risk_per_unit
        # Tope absoluto por exposición
        max_qty = (balance * c.max_position_pct) / entry_price
        return round(min(qty, max_qty), 6)

    def register_close(self, pnl: float, balance: float) -> None:
        self.state.daily_pnl += pnl
        start = self.state.daily_start_balance or balance
        if start > 0 and self.state.daily_pnl <= -(start * self.config.max_daily_loss_pct):
            self.state.halted = True
            self.state.halt_reason = (
                f"Pérdida diaria {self.state.daily_pnl:.2f} alcanzó el límite "
                f"({self.config.max_daily_loss_pct:.0%})"
            )
            logger.warning(self.state.halt_reason)

    def snapshot(self) -> dict:
        return {
            "daily_pnl": round(self.state.daily_pnl, 4),
            "daily_start_balance": round(self.state.daily_start_balance, 2),
            "day": self.state.day,
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
            "config": {
                "risk_per_trade_pct": self.config.risk_per_trade_pct,
                "max_open_positions": self.config.max_open_positions,
                "max_daily_loss_pct": self.config.max_daily_loss_pct,
                "min_confidence": self.config.min_confidence,
                "min_rr_ratio": self.config.min_rr_ratio,
                "max_position_pct": self.config.max_position_pct,
            },
        }
