# Manual — Crypto Sniper Pro v2

Plataforma de análisis y trading automático de criptomonedas con backtesting, arbitraje
multi-exchange y confirmación opcional con la IA de Claude. App instalable en Windows.

---

## 1. Qué es y qué NO es

**Es:** una plataforma completa para analizar mercados cripto, probar estrategias contra
datos históricos (backtesting riguroso), detectar oportunidades de arbitraje entre
exchanges, y operar de forma automática en modo simulación (paper) o real (live).

**No es:** una máquina de hacer dinero. Las pruebas walk-forward demuestran que las
estrategias de indicadores **no tienen ventaja consistente** tras comisiones. El valor real
es aprender, validar ideas sin riesgo y operar con control de riesgo estricto. El modo por
defecto es **PAPER** (simulado) precisamente por esto.

---

## 2. Instalación y arranque

### App instalada (recomendado)
1. Ejecuta `release\Crypto Sniper Pro Setup 2.0.0.exe`
2. Sigue el asistente → crea acceso directo
3. Ábrela; el backend arranca solo dentro de la app

> Windows SmartScreen mostrará "Editor desconocido" (la app no está firmada). 
> Pulsa "Más información" → "Ejecutar de todos modos".

### Modo desarrollo (para cambios)
- Backend: `start_backend.bat` (puerto 8001)
- Frontend: `start_frontend.bat` (puerto 3000) → abre `http://localhost:3000`

### Configuración (`backend\.env`)
Copia `backend\.env.example` a `backend\.env`. Claves importantes:
- `ANTHROPIC_API_KEY` — tu key de Claude (para la reconfirmación con IA)
- `BINANCE_API_KEY` / `SECRET` — para operar real en Binance (opcional; los precios son públicos)
- `KRAKEN_API_KEY` / `SECRET` — solo para EJECUTAR en Kraken (los precios son públicos, no necesita key)
- `COMMISSION_RATE=0.001` — comisión del exchange (0.1%)
- `ENGINE_USE_AI=false` — pon `true` para que Claude confirme cada señal

---

## 3. La interfaz

```
┌──────────────────────── BARRA SUPERIOR ────────────────────────┐
│ Par | Precio | Intervalos (1m..1d) | AUTO | Refrescar | Estado │
├──────────────┬────────────────────────────┬───────────────────┤
│ IZQUIERDA    │         CENTRO             │     DERECHA       │
│ • Motor      │   Gráfico de velas         │ • Indicadores     │
│   Auto-Trade │   (líneas entrada/SL/TP)   │   técnicos        │
│ • Señales    │                            │ • Panel de        │
│ • Listados   │   Pestañas:                │   trading manual  │
│   nuevos     │   IA / Backtest / Arbitraje│                   │
├──────────────┴────────────────────────────┴───────────────────┤
│              HISTORIAL DE OPERACIONES (abajo)                  │
└────────────────────────────────────────────────────────────────┘
```

- **Cambiar de par:** clic en el selector arriba a la izquierda → busca y elige.
  El gráfico, indicadores y posiciones se actualizan al instante.
- **Líneas en el gráfico:** cuando hay posiciones abiertas en el activo que estás viendo,
  se dibujan líneas de ENTRADA (verde/rojo según long/short), STOP LOSS (ámbar) y
  TAKE PROFIT (cian).

---

## 4. El motor de auto-trading (lo central)

Panel **Motor Auto-Trade** (columna izquierda).

### Cómo funciona, paso a paso
1. **Escanea** los 20 pares más líquidos cada 30 segundos.
2. **Evalúa** cada par con la confluencia de 5 indicadores avanzados (modo *momentum*):
   Sniper Score, Precision Sniper, Ichimoku, NeuroTrend II, Turtle Channels.
3. Si ≥4 de 5 coinciden **a favor de la tendencia** (EMA50 vs EMA200) → señal (largo o corto).
4. **Claude reconfirma** (si está activado): solo opera si la IA coincide en dirección.
5. **Control de riesgo:** confianza mínima, ratio R/R ≥ 1.5, máximo 10 posiciones,
   corte diario si la pérdida llega al -6%.
6. **Tamaño de posición:** arriesga 2% del balance por operación (tope 20% por posición).
7. **Ejecuta** (orden de mercado real en live, o simulada en paper).
8. **Monitorea y cierra** cada posición por:
   - Stop Loss / Take Profit (basados en ATR)
   - **Trailing stop** (persigue el precio tras +1×ATR de beneficio)
   - **Señal contraria** de los indicadores ("indicadores de venta")
   - **Tiempo máximo:** 3 días (operación normal)

### Controles del panel
- **INICIAR / DETENER** — arranca o para el escaneo
- **CERRAR TODO (n)** — pánico: cierra todas las posiciones y detiene el motor
- **🧪 PAPER / 🔴 LIVE** — simulación (sin órdenes reales) vs real
- **Señal: momentum** — la estrategia activa
- **🤖 Claude: ON/OFF** — activa la reconfirmación con IA (requiere API key)
- **Exchanges** — elige el exchange activo (Binance conectado)

### Por qué "abre 10 y parece parar"
Es el límite de riesgo: máximo **10 posiciones a la vez**. Cuando una cierra (SL/TP/tiempo/
reverso), se libera el hueco y abre otra si hay señal. En mercado tranquilo, los cierres
tardan, así que parece pausado. No está roto — está respetando el riesgo.

---

## 5. Indicadores (17 en total)

### Básicos (8)
RSI(14), MACD, Bandas de Bollinger, EMA(20), EMA(50), SMA(50), Estocástico, ATR(14)

### Avanzados (9)
- **Sniper Score** — confluencia de 7 señales (EMA cross, RSI, MACD, ADX, volumen)
- **Precision Sniper** — confluencia ponderada con grado A+/A/B/C
- **Linear Regression Channel** — canal de regresión con bandas ±2σ
- **Swing Profile** — tendencia dominante y máximos/mínimos
- **Fair Value Gaps** — zonas de desequilibrio (soporte/resistencia)
- **Ichimoku Cloud** — Tenkan, Kijun, nube, TK Cross
- **NeuroTrend II** — dirección, fase, confianza, slope power
- **SuperTrend RSI** — RSI con bandas ATR
- **Turtle Channels** — canales de Donchian (rupturas)

El motor usa 5 avanzados en confluencia. Los 17 se muestran en el panel derecho.

---

## 6. Backtesting

Pestaña **Backtest** (centro). Prueba la estrategia contra ~1000 velas históricas y reporta:
- Retorno %, Win Rate, Profit Factor, Max Drawdown, Sharpe, curva de equity, últimos trades.

Optimizador avanzado (terminal): `cd backend && py -3.11 optimize_strategy.py 1h`
Hace grid search con validación **walk-forward** sobre 5000 velas y 6 símbolos.

> Realidad comprobada: ninguna configuración supera el equilibrio fuera de muestra.

---

## 7. Arbitraje

Pestaña **Arbitraje** (centro). Dos modos:

- **Cross-exchange** (Binance ↔ Kraken): compara precios reales de 45 monedas. Compra al
  ask más bajo, vende al bid más alto. Muestra el mejor spread neto tras comisiones.
- **Triangular** (un solo exchange): ciclos USDT→BTC→ETH→USDT con bid/ask reales.

> Realidad: los spreads (~0.01-0.02%) son menores que las comisiones (~0.2%). Sin maker
> fees bajos o picos de volatilidad, no es rentable desde retail. El detector cuantifica
> exactamente cuándo y cuánto aparece.

---

## 8. Claude (IA)

Dos usos:
1. **Análisis bajo demanda** — pestaña *Terminal IA*: análisis del par actual.
2. **Reconfirmación en el motor** — botón 🤖 Claude: ON. Cada señal mecánica debe ser
   confirmada por Claude antes de operar; si la IA discrepa, veta.

Requiere `ANTHROPIC_API_KEY` real en `.env`. Honestidad: Claude sobre los mismos
indicadores de precio no añade ventaja predictiva; es una capa de filtro/confirmación.

---

## 9. Seguridad y riesgo

- **Empieza siempre en PAPER.** Verifica el comportamiento sin arriesgar dinero.
- El control de riesgo limita pérdidas: 2% por trade, 10 posiciones máx, corte diario -6%.
- **CERRAR TODO** es tu freno de emergencia.
- Pasar a LIVE envía órdenes reales con tu saldo. Hazlo solo si entiendes el riesgo.

---

## 10. Solución de problemas

| Problema | Solución |
|---|---|
| El gráfico no cambia de par | Recarga (Ctrl+R). Corregido en la última versión. |
| No opera | Revisa que esté INICIADO y en modo `momentum`; con Claude ON necesita API key. |
| Historial vacío | Corregido: las operaciones del motor se registran automáticamente. |
| Backend no arranca | Falta `backend\.env`; cópialo de `.env.example`. |
| Puerto 8001 ocupado | Otro proceso lo usa; ciérralo o cambia el puerto. |
