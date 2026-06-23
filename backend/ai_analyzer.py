import asyncio
import json
import logging
from typing import Dict

import anthropic
from config import get_settings

logger = logging.getLogger(__name__)

_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "recommendation": {"type": "string", "enum": ["buy", "sell", "hold"]},
        "confidence": {"type": "number", "description": "Confianza de 0 a 100"},
        "risk_reward_ratio": {"type": "number", "description": "Ratio riesgo/beneficio"},
        "entry_price": {"type": "number"},
        "stop_loss": {"type": "number"},
        "take_profit_1": {"type": "number"},
        "take_profit_2": {"type": "number"},
        "estimated_commission": {"type": "number", "description": "Comisión estimada ida y vuelta"},
        "estimated_net_profit": {"type": "number", "description": "Profit neto estimado tras comisiones"},
        "analysis": {"type": "string", "description": "Análisis detallado en 3-5 líneas, en español"},
    },
    "required": [
        "recommendation", "confidence", "risk_reward_ratio", "entry_price",
        "stop_loss", "take_profit_1", "take_profit_2", "estimated_commission",
        "estimated_net_profit", "analysis",
    ],
    "additionalProperties": False,
}

_SYSTEM_MESSAGE = """Eres un analista experto de trading de criptomonedas de alta frecuencia.
Tu trabajo es analizar indicadores técnicos avanzados y dar recomendaciones precisas y accionables.

INDICADORES DISPONIBLES:
- Básicos: RSI(14), MACD, Bollinger Bands, EMA(20), EMA(50), SMA(50), Estocástico, ATR(14)
- Sniper Score: confluencia de 7 señales (bull_score/7, bear_score/7, bias, EMA cross)
- Precision Sniper: confluencia ponderada (bull/bear /10, grade A+/A/B/C, ADX, signal)
- Ichimoku Cloud: Tenkan, Kijun, posición respecto a la nube, TK Cross
- NeuroTrend II: dirección (Bullish/Bearish), fase (Expansion/Contraction), confianza %, slope power
- Linear Regression Channel: línea central, banda superior/inferior (±2σ), ángulo de tendencia
- Swing Profile: tendencia dominante (UPTREND/DOWNTREND), máximo y mínimo de las últimas 20 velas
- Fair Value Gaps (FVG): zonas de desequilibrio BULLISH/BEARISH como soporte/resistencia

REGLAS:
1. Siempre considera las comisiones del exchange. El profit potencial DEBE superar 3x las comisiones.
2. Busca confluencia: Ichimoku sobre la nube + NeuroTrend Bullish + Sniper Score bull > 5 = señal fuerte.
3. Usa los FVG como niveles de entrada/stop loss cuando el precio los respeta.
4. El ángulo del Linear Regression indica la fuerza de la tendencia (>10° fuerte, <5° lateral).
5. Confirma la tendencia con Swing Profile antes de recomendar contra-tendencia.
6. Calcula ratio R/R y propón entrada, stop loss y dos take profits concretos.
7. `confidence` es un número de 0 a 100. `analysis` va en español, 3-5 líneas.
Devuelve únicamente los campos del esquema estructurado solicitado."""

_MAX_RETRIES = 2
_RETRY_BASE_DELAY = 2.0


class AITradingAnalyzer:
    """Análisis de trading con Claude vía la API de Anthropic (cliente asíncrono + salida estructurada)."""

    def __init__(self):
        settings = get_settings()
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.anthropic_model

    async def analyze_market(self, symbol: str, indicators: Dict, commission_rate: float = 0.001) -> Dict:
        """Analiza las condiciones de mercado usando Claude y devuelve una recomendación estructurada."""
        indicators_text = self._format_indicators(indicators, commission_rate)
        prompt = f"""Analiza {symbol} para operación de alta frecuencia:

Comisión del exchange: {commission_rate * 100}% por operación (ida y vuelta: {commission_rate * 2 * 100}%)

{indicators_text}

¿Vale la pena entrar considerando comisiones? Da tu análisis."""

        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                message = await self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    thinking={"type": "adaptive"},
                    system=_SYSTEM_MESSAGE,
                    output_config={"format": {"type": "json_schema", "schema": _ANALYSIS_SCHEMA}},
                    messages=[{"role": "user", "content": prompt}],
                )

                if message.stop_reason == "refusal":
                    raise RuntimeError("La solicitud fue rechazada por los clasificadores de seguridad")

                usage = message.usage
                logger.info(
                    "Claude tokens — input: %d, output: %d, cache_read: %d",
                    usage.input_tokens,
                    usage.output_tokens,
                    getattr(usage, "cache_read_input_tokens", 0),
                )

                # Con adaptive thinking puede haber bloques 'thinking' antes del texto.
                raw = next((b.text for b in message.content if b.type == "text"), None)
                if not raw:
                    raise RuntimeError("Respuesta vacía del modelo")
                data = json.loads(raw)

                return {
                    "analysis": data.get("analysis", ""),
                    "recommendation": data.get("recommendation", "hold"),
                    # Frontend espera confidence en rango 0-1.
                    "confidence": float(data.get("confidence", 0)) / 100.0,
                    "risk_reward_ratio": data.get("risk_reward_ratio"),
                    "entry_price": data.get("entry_price"),
                    "stop_loss": data.get("stop_loss"),
                    "take_profit_1": data.get("take_profit_1"),
                    "take_profit_2": data.get("take_profit_2"),
                    "estimated_commission": data.get("estimated_commission"),
                    "estimated_net_profit": data.get("estimated_net_profit"),
                    "commission_rate": commission_rate,
                    "indicators_summary": indicators,
                }

            except (anthropic.RateLimitError, anthropic.APIConnectionError) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Transient error (%s), retry %d/%d in %.1fs",
                        type(e).__name__, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries reached after %s: %s", type(e).__name__, e)

            except anthropic.APIStatusError as e:
                if e.status_code >= 500 and attempt < _MAX_RETRIES:
                    last_error = e
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Server error %d, retry %d/%d in %.1fs",
                        e.status_code, attempt + 1, _MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error("API status error %d: %s", e.status_code, e)
                    last_error = e
                    break

            except anthropic.BadRequestError as e:
                logger.error("Bad request (non-retryable): %s", e)
                last_error = e
                break

            except Exception as e:
                logger.error("Unexpected error in AI analysis: %s", e)
                last_error = e
                break

        return self._error_response(
            str(last_error) if last_error else "Error desconocido",
            commission_rate,
            indicators,
        )

    def _error_response(self, msg: str, commission_rate: float, indicators: Dict) -> Dict:
        return {
            "analysis": f"Error en análisis con Claude: {msg}",
            "recommendation": "hold",
            "confidence": 0.0,
            "risk_reward_ratio": None,
            "entry_price": None,
            "stop_loss": None,
            "take_profit_1": None,
            "take_profit_2": None,
            "estimated_commission": None,
            "estimated_net_profit": None,
            "commission_rate": commission_rate,
            "indicators_summary": indicators,
        }

    def _format_indicators(self, indicators: Dict, commission_rate: float) -> str:
        lines = []

        # ── Indicadores básicos ──────────────────────────────────────────────
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            zone = "SOBRECOMPRA" if rsi > 70 else "SOBREVENTA" if rsi < 30 else "NEUTRAL"
            lines.append(f"RSI(14): {rsi:.2f} [{zone}]")
        if 'macd' in indicators:
            m = indicators['macd']
            trend = "ALCISTA" if m['histogram'] > 0 else "BAJISTA"
            lines.append(
                f"MACD: Línea={m['macd']:.6f}, Señal={m['signal']:.6f}, "
                f"Hist={m['histogram']:.6f} [{trend}]"
            )
        if 'bollinger' in indicators:
            bb = indicators['bollinger']
            lines.append(
                f"Bollinger: Superior={bb['upper']:.4f}, Medio={bb['middle']:.4f}, "
                f"Inferior={bb['lower']:.4f}"
            )
        if 'ema_20' in indicators:
            lines.append(f"EMA(20): {indicators['ema_20']:.4f}")
        if 'ema_50' in indicators:
            lines.append(f"EMA(50): {indicators['ema_50']:.4f}")
        if 'sma_50' in indicators:
            lines.append(f"SMA(50): {indicators['sma_50']:.4f}")
        if 'stochastic' in indicators:
            s = indicators['stochastic']
            zone = "SOBRECOMPRA" if s['k'] > 80 else "SOBREVENTA" if s['k'] < 20 else "NEUTRAL"
            lines.append(f"Estocástico: K={s['k']:.2f}, D={s['d']:.2f} [{zone}]")
        if 'atr' in indicators:
            lines.append(f"ATR(14): {indicators['atr']:.6f}")

        # ── Sniper Score ─────────────────────────────────────────────────────
        if 'sniper_score' in indicators:
            ss = indicators['sniper_score']
            lines.append("\n--- SNIPER SCORE ---")
            lines.append(
                f"Bull: {ss.get('bull_score', 0)}/7 | Bear: {ss.get('bear_score', 0)}/7 | "
                f"Bias: {ss.get('bias', 'NEUTRAL')} | "
                f"Bull%: {ss.get('bull_pct', 0):.0f} | Bear%: {ss.get('bear_pct', 0):.0f}"
            )
            if ss.get('ema_cross_buy'):
                lines.append("EMA Cross BUY detectado")
            elif ss.get('ema_cross_sell'):
                lines.append("EMA Cross SELL detectado")

        # ── Precision Sniper Confluence ──────────────────────────────────────
        if 'confluence_score' in indicators:
            cs = indicators['confluence_score']
            lines.append("\n--- PRECISION SNIPER ---")
            lines.append(
                f"Bull: {cs.get('bull_score', 0):.1f}/10 | Bear: {cs.get('bear_score', 0):.1f}/10 | "
                f"Grade: {cs.get('grade', 'N/A')} | ADX: {cs.get('adx', 0):.1f} | "
                f"Signal: {cs.get('signal', 'neutral')}"
            )

        # ── Ichimoku Cloud ───────────────────────────────────────────────────
        if 'ichimoku' in indicators:
            ich = indicators['ichimoku']
            if ich.get('above_cloud'):
                cloud_pos = "SOBRE la nube (alcista)"
            elif ich.get('below_cloud'):
                cloud_pos = "BAJO la nube (bajista)"
            else:
                cloud_pos = "DENTRO de la nube (neutral)"
            lines.append("\n--- ICHIMOKU ---")
            lines.append(
                f"Tenkan={ich.get('tenkan', 0):.4f}, Kijun={ich.get('kijun', 0):.4f} | {cloud_pos}"
            )
            if ich.get('tk_cross_bull'):
                lines.append("TK Cross ALCISTA")
            elif ich.get('tk_cross_bear'):
                lines.append("TK Cross BAJISTA")

        # ── NeuroTrend II ────────────────────────────────────────────────────
        if 'neurotrend' in indicators:
            nt = indicators['neurotrend']
            lines.append("\n--- NEUROTREND II ---")
            lines.append(
                f"Dirección: {nt.get('trend_direction', '?')} | "
                f"Fase: {nt.get('phase', '?')} | "
                f"Confianza: {nt.get('confidence', 0)}% | "
                f"Slope Power: {nt.get('slope_power', 0):.2f}"
            )

        # ── Linear Regression Channel ────────────────────────────────────────
        if 'linear_regression' in indicators:
            lr = indicators['linear_regression']
            pos = "sobre la línea" if lr.get('above_line') else "bajo la línea"
            lines.append("\n--- REGRESIÓN LINEAL ---")
            lines.append(
                f"LR={lr.get('line', 0):.4f} | Banda+={lr.get('upper', 0):.4f} | "
                f"Banda-={lr.get('lower', 0):.4f} | Precio {pos} | "
                f"Ángulo: {lr.get('angle', 0):.1f}°"
            )

        # ── Swing Profile ────────────────────────────────────────────────────
        if 'swing_profile' in indicators:
            sw = indicators['swing_profile']
            lines.append("\n--- SWING PROFILE ---")
            lines.append(
                f"Tendencia: {sw.get('trend', '?')} | "
                f"Max(20): {sw.get('last_high', 0):.4f} | "
                f"Min(20): {sw.get('last_low', 0):.4f}"
            )

        # ── Fair Value Gaps ──────────────────────────────────────────────────
        if 'fvg' in indicators:
            gaps = indicators['fvg'].get('gaps', [])
            if gaps:
                lines.append("\n--- FAIR VALUE GAPS ---")
                for gap in gaps:
                    lines.append(
                        f"FVG {gap['type']}: {gap['low']:.4f} - {gap['high']:.4f} "
                        f"(mid={gap.get('mid', 0):.4f})"
                    )

        # ── Precio y volumen ─────────────────────────────────────────────────
        if 'current_price' in indicators:
            lines.append(f"\nPrecio Actual: ${indicators['current_price']:.4f}")
            lines.append(f"Volumen: {indicators.get('volume', 0):.2f}")

        return "\n".join(lines)
