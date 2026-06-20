# 🤖 Smart Trader App — AI-Powered Crypto Trading Bot

Aplicación de trading de criptomonedas con análisis de mercado impulsado por **Claude AI (Anthropic)**, integrado con **Binance** (Spot y Futures).

---

## 🚀 Características

- 📊 **Análisis técnico avanzado** — RSI, MACD, Bollinger Bands, EMA, y más
- 🤖 **IA con Claude** — Recomendaciones de BUY/SELL/HOLD con niveles de entrada, Stop Loss y Take Profit
- 📈 **Binance Spot & Futures** — Conexión en tiempo real vía WebSocket
- 🔔 **Panel de señales** — Señales de trading con confianza y ratio riesgo/beneficio
- 📋 **Historial de trades** — Registro completo de operaciones
- 🆕 **Nuevos listados** — Detección de pares recientes en Binance
- 💻 **Terminal AI** — Chat directo con el analizador de IA

---

## 🛠️ Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | React, TailwindCSS, Shadcn/UI |
| Backend | Python, FastAPI, Motor (MongoDB) |
| AI | Claude (Anthropic) vía Emergent LLM |
| Exchange | Binance API (python-binance) + Futures |
| Base de datos | MongoDB |
| Indicadores | TA-Lib, pandas |

---

## ⚙️ Instalación

### Requisitos
- Node.js 18+
- Python 3.11+
- MongoDB
- Cuenta Binance (API Key + Secret)
- API Key de Claude (Anthropic)

### Backend

```bash
cd backend
pip install -r requirements.txt

# Crear archivo .env
cp .env.example .env
# Editar .env con tus credenciales
```

### Frontend

```bash
cd frontend
npm install
npm start
```

---

## 🔑 Variables de Entorno

Crear `backend/.env` con:

```env
# MongoDB
MONGO_URL=mongodb://localhost:27017
DB_NAME=smart_trader_db

# Binance
BINANCE_API_KEY=tu_api_key
BINANCE_API_SECRET=tu_api_secret
BINANCE_TESTNET=true

# Binance Futures (opcional)
BINANCE_FUTURES_KEY=tu_futures_key
BINANCE_FUTURES_SECRET=tu_futures_secret

# AI - Claude via Emergent
EMERGENT_LLM_KEY=tu_emergent_key

# Trading Mode: auto | semi_auto | signals_only
TRADING_MODE=semi_auto
AUTO_TRADE_ENABLED=false

# CORS
CORS_ORIGINS=*
```

> ⚠️ **NUNCA subas tu `.env` a GitHub.** Está incluido en `.gitignore`.

---

## 🎮 Modos de Trading

| Modo | Descripción |
|------|-------------|
| `signals_only` | Solo muestra señales, sin ejecutar órdenes |
| `semi_auto` | Sugiere operaciones, el usuario confirma |
| `auto` | Ejecuta operaciones automáticamente |

---

## 📁 Estructura del Proyecto

```
smart-trader-app/
├── backend/
│   ├── server.py              # API FastAPI principal
│   ├── ai_analyzer.py         # Análisis con Claude AI
│   ├── binance_client.py      # Cliente Binance Spot
│   ├── futures_client.py      # Cliente Binance Futures
│   ├── indicators.py          # Indicadores técnicos básicos
│   ├── advanced_indicators.py # Indicadores avanzados
│   ├── models.py              # Modelos de datos
│   ├── config.py              # Configuración
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js
│   │   ├── api.js
│   │   └── components/
│   │       ├── AITerminal.js      # Chat con IA
│   │       ├── TradingPanel.js    # Panel principal
│   │       ├── SignalsPanel.js    # Señales de trading
│   │       ├── IndicatorsPanel.js # Indicadores técnicos
│   │       ├── PriceChart.js      # Gráfico de precios
│   │       ├── PairSelector.js    # Selector de pares
│   │       ├── TradeHistory.js    # Historial
│   │       └── NewListingsPanel.js
│   └── package.json
└── README.md
```

---

## ⚠️ Descargo de Responsabilidad

Este software es para **fines educativos y de investigación**. El trading de criptomonedas implica riesgo de pérdida de capital. No es asesoramiento financiero. Usa en testnet primero.

---

## 📄 Licencia

MIT License — Libre para uso personal y comercial.
