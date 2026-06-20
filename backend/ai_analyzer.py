import anthropic
from config import get_settings
import logging
from typing import Dict, Literal
import re

logger = logging.getLogger(__name__)

class AITradingAnalyzer:
    """AI-powered trading analysis usando Anthropic API directo (sin Emergent)"""
    
    def __init__(self):
        settings = get_settings()
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        
    async def analyze_market(self, symbol: str, indicators: Dict, commission_rate: float = 0.001) -> Dict:
        """Analyze market conditions using Claude AI"""
        try:
            system_message = """Eres un analista experto de trading de criptomonedas de alta frecuencia.
Tu trabajo es analizar indicadores técnicos avanzados y dar recomendaciones precisas.

REGLAS:
1. Siempre considera las comisiones del exchange al evaluar si una entrada vale la pena
2. Para operaciones de alta frecuencia, el profit potencial DEBE superar al menos 3x las comisiones
3. Evalúa la confluencia de TODOS los indicadores antes de recomendar
4. Calcula el Risk/Reward ratio
5. Proporciona niveles específicos de entrada, stop loss y take profit

FORMATO DE RESPUESTA (usa exactamente este formato):
RECOMENDACION: [BUY/SELL/HOLD]
CONFIANZA: [0-100]%
RIESGO/BENEFICIO: [ratio]
ENTRADA: [precio]
STOP LOSS: [precio]
TAKE PROFIT 1: [precio]
TAKE PROFIT 2: [precio]
COMISION ESTIMADA: [valor]
PROFIT NETO ESTIMADO: [valor después de comisiones]
ANALISIS: [análisis detallado en 3-5 líneas]"""
            
            indicators_text = self._format_indicators(indicators, commission_rate)
            prompt = f"""Analiza {symbol} para operación de alta frecuencia:

Comisión del exchange: {commission_rate * 100}% por operación (ida y vuelta: {commission_rate * 2 * 100}%)

{indicators_text}

¿Vale la pena entrar considerando comisiones? Da tu análisis."""

            # Llamada directa a Anthropic API
            message = self.client.messages.create(
                model="claude-sonnet-4-5",
                max_tokens=1024,
                system=system_message,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response = message.content[0].text
            
            return {
                'analysis': response,
                'recommendation': self._parse_recommendation(response),
                'confidence': self._parse_confidence(response),
                'entry_price': self._parse_price(response, "ENTRADA"),
                'stop_loss': self._parse_price(response, "STOP LOSS"),
                'take_profit_1': self._parse_price(response, "TAKE PROFIT 1"),
                'take_profit_2': self._parse_price(response, "TAKE PROFIT 2"),
                'commission_rate': commission_rate,
                'indicators_summary': indicators
            }
            
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            return {
                'analysis': f"Error en análisis con Claude: {str(e)}",
                'recommendation': 'hold',
                'confidence': 0.0,
                'entry_price': None,
                'stop_loss': None,
                'take_profit_1': None,
                'take_profit_2': None,
                'commission_rate': commission_rate,
                'indicators_summary': indicators
            }
    
    def _format_indicators(self, indicators: Dict, commission_rate: float) -> str:
        lines = []
        if 'rsi' in indicators:
            rsi = indicators['rsi']
            zone = "SOBRECOMPRA" if rsi > 70 else "SOBREVENTA" if rsi < 30 else "NEUTRAL"
            lines.append(f"RSI(14): {rsi:.2f} [{zone}]")
        if 'macd' in indicators:
            m = indicators['macd']
            trend = "ALCISTA" if m['histogram'] > 0 else "BAJISTA"
            lines.append(f"MACD: Línea={m['macd']:.6f}, Señal={m['signal']:.6f}, Hist={m['histogram']:.6f} [{trend}]")
        if 'bollinger' in indicators:
            bb = indicators['bollinger']
            lines.append(f"Bollinger: Superior={bb['upper']:.2f}, Medio={bb['middle']:.2f}, Inferior={bb['lower']:.2f}")
        if 'ema_20' in indicators:
            lines.append(f"EMA(20): {indicators['ema_20']:.2f}")
        if 'ema_50' in indicators:
            lines.append(f"EMA(50): {indicators['ema_50']:.2f}")
        if 'stochastic' in indicators:
            s = indicators['stochastic']
            zone = "SOBRECOMPRA" if s['k'] > 80 else "SOBREVENTA" if s['k'] < 20 else "NEUTRAL"
            lines.append(f"Estocástico: K={s['k']:.2f}, D={s['d']:.2f} [{zone}]")
        if 'atr' in indicators:
            lines.append(f"ATR(14): {indicators['atr']:.6f}")
        if 'sniper_score' in indicators:
            ss = indicators['sniper_score']
            lines.append(f"\n--- SNIPER SCORE ---")
            lines.append(f"Bull Score: {ss.get('bull_score',0)}/7 | Bear Score: {ss.get('bear_score',0)}/7")
            lines.append(f"Bias: {ss.get('bias','NEUTRAL')}")
        if 'confluence_score' in indicators:
            cs = indicators['confluence_score']
            lines.append(f"\n--- CONFLUENCE ---")
            lines.append(f"Bull: {cs.get('bull_score',0):.1f}/10 | Bear: {cs.get('bear_score',0):.1f}/10 | Grade: {cs.get('grade','N/A')}")
        if 'fvg' in indicators:
            fvg = indicators['fvg']
            for gap in fvg.get('gaps', []):
                lines.append(f"FVG {gap['type']}: {gap['low']:.2f} - {gap['high']:.2f}")
        if 'current_price' in indicators:
            lines.append(f"\nPrecio Actual: ${indicators['current_price']:.2f}")
            lines.append(f"Volumen: {indicators.get('volume', 0):.2f}")
        return "\n".join(lines)
    
    def _parse_recommendation(self, text: str) -> Literal["buy", "sell", "hold"]:
        text_lower = text.lower()
        rec_match = re.search(r'recomendacion:\s*(buy|sell|hold|compra|venta|mantener)', text_lower)
        if rec_match:
            val = rec_match.group(1)
            if val in ('buy', 'compra'): return 'buy'
            elif val in ('sell', 'venta'): return 'sell'
            return 'hold'
        if 'buy' in text_lower or 'compra' in text_lower: return 'buy'
        elif 'sell' in text_lower or 'venta' in text_lower: return 'sell'
        return 'hold'
    
    def _parse_confidence(self, text: str) -> float:
        match = re.search(r'confianza:\s*(\d+)', text, re.IGNORECASE)
        if match: return float(match.group(1)) / 100.0
        matches = re.findall(r'(\d+)%', text)
        if matches: return float(matches[0]) / 100.0
        return 0.5
    
    def _parse_price(self, text: str, label: str) -> float:
        match = re.search(rf'{label}:\s*\$?([\d,]+\.?\d*)', text, re.IGNORECASE)
        if match: return float(match.group(1).replace(',', ''))
        return None
