# PRD - Crypto Sniper Trading Application

## Problem Statement
Crear una aplicación de trading para realizar operaciones en tiempos cortos o largos, con indicadores técnicos avanzados, interfaz estilo TradingView, integración con Binance API, análisis con IA (Claude), y detección de nuevos lanzamientos.

## Architecture
- **Frontend**: React + TailwindCSS + lightweight-charts v5 (TradingView) + Phosphor Icons
- **Backend**: FastAPI + MongoDB + python-binance + TA-Lib + Emergent LLM (Claude)
- **Database**: MongoDB (trades, signals, ai_analyses, new_listings)

## User Personas
- Trader de criptomonedas que busca automatizar decisiones con indicadores técnicos
- Usuario que necesita señales de entrada/salida con análisis de IA
- Trader de alta frecuencia que necesita considerar comisiones

## Core Requirements
1. Gráfico de velas estilo TradingView
2. Indicadores técnicos: RSI, MACD, Bollinger Bands, EMA/SMA, Stochastic, ATR
3. Indicadores avanzados: Sniper Score, Precision Sniper Confluence, Linear Regression, Swing Profile, FVG
4. Análisis con IA (Claude) considerando comisiones
5. Panel de trading (auto/semi-auto/manual)
6. Historial de operaciones
7. Detección de nuevos lanzamientos
8. Señales de entrada/salida

## What's Been Implemented (April 2026)
- [x] Backend completo con 13+ endpoints API
- [x] Motor de indicadores técnicos (7 indicadores básicos: RSI, MACD, BB, EMA/SMA, Stochastic, ATR)
- [x] Motor de indicadores avanzados (9 estrategias integradas):
  - Sniper Score (KhanSaab V.02) - Sistema de puntuación dual bull/bear
  - Precision Sniper Confluence (WillyAlgoTrader) - Motor de confluencia con grading
  - Linear Regression Channel (Fedra Algotrading) - LR con SuperTrend filter
  - Swing Profile (BigBeluga) - Detección de swings + perfil de volumen
  - Fair Value Gaps (FVG Multi-Timeframe) - Gaps de precio
  - Ichimoku Cloud (Apicode) - Tenkan/Kijun/Cloud analysis
  - NeuroTrend II (Apicode) - Adaptive AI Trend Engine con slope forecasting
  - SuperTrend RSI (Apicode) - SuperTrend aplicado a RSI
  - Turtle Channels (Apicode) - Breakout-based entry/exit system
- [x] Sistema de señales combinadas (combina todos los indicadores)
- [x] Análisis con Claude AI considerando comisiones de exchange
- [x] Toggle AUTO-TRADE ON/OFF (activar/desactivar ejecuciones automáticas)
- [x] **WebSocket tiempo real** para precios (actualización cada 1.5s)
- [x] **Futuros (Long/Short)** con API Testnet de Binance Futures
- [x] Selector de apalancamiento (1x, 2x, 5x, 10x, 20x, 50x)
- [x] SPOT / FUTUROS toggle en panel de trading
- [x] Detección de nuevos listings (background task)
- [x] Modo demo con datos simulados (Binance geo-restricted)
- [x] Binance Testnet API keys configuradas
- [x] Frontend dashboard estilo TradingView oscuro profesional
- [x] Gráfico de velas con lightweight-charts v5
- [x] Panel de indicadores con todos los toggles
- [x] Panel de señales con FVG y Swing Profile
- [x] Panel de trading con BUY/SELL
- [x] Terminal de IA Claude con efecto typewriter
- [x] Selector de pares de trading (20 pares)
- [x] Historial de operaciones
- [x] Panel de nuevos lanzamientos

## Backlog
### P0 (Critical)
- [ ] Conectar con Binance API real cuando hay keys disponibles
- [ ] WebSocket para precios en tiempo real (actualmente polling cada 10s)

### P1 (High)
- [ ] Trading automático real (ejecutar órdenes basadas en señales)
- [ ] Stop Loss / Take Profit automáticos basados en ATR
- [ ] Alertas de señales por notificación

### P2 (Medium)
- [ ] Backtesting de estrategias con datos históricos
- [ ] Más indicadores de los archivos del usuario (indicadores completos)
- [ ] Multi-timeframe analysis integrado
- [ ] Portfolio tracking con PnL

## Next Tasks
1. Integrar API keys de Binance del usuario para trading real
2. Implementar WebSocket para precios en tiempo real
3. Auto-trading: ejecutar órdenes automáticamente basadas en confluencia + IA
4. Sistema de alertas cuando se detecten señales fuertes
