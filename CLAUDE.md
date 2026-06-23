# Crypto Sniper Pro — Memoria de desarrollo

> Documento maestro del proyecto. Resume TODO lo construido hasta hoy para que cualquier
> sesión de Claude (o cualquier desarrollador) retome el contexto sin perder nada.
> Última actualización: 2026-06-22.

## Qué es

App de **trading automático multi-mercado** (cripto + acciones EEUU) con tablero en tiempo real,
22 indicadores técnicos, motor de auto-trading, backtesting walk-forward y detección de arbitraje.
Empaquetable como **instalador `.exe` de Windows** (Electron). Autor: hugo92nogue.
Repo: https://github.com/hugo92nogue/smart-trader-app (rama `main`).

## Stack

- **Backend**: FastAPI (Python **3.11**) — puerto **8001**
- **Frontend**: React 18 + Vite — puerto **3000**
- **Escritorio**: Electron + electron-builder (NSIS) → `.exe` instalable
- **Empaquetado backend**: PyInstaller (`backend/crypto_sniper_backend.spec`)
- **Datos**: Binance API pública (cripto), Yahoo Finance (acciones), Kraken API pública (arbitraje)
- **Persistencia**: MongoDB si está disponible; si no, cae a almacenamiento **en memoria** (esperado, no es error)
- **IA**: Anthropic Claude (opcional, capa de confirmación — requiere `ANTHROPIC_API_KEY`)

## Cómo arrancar

### Desarrollo (dos procesos, desde la raíz del proyecto)
```
# Backend
cd backend && py -3.11 -m uvicorn server:app --host 127.0.0.1 --port 8001
# Frontend
cd frontend && npm start          # Vite en :3000
```
Entrar en **http://localhost:3000**.

**Gotchas de arranque (causaron "no me anda"):**
- El backend usa **8001, NO 8000** porque el usuario tiene OTRO proyecto Python permanente en el 8000.
- El frontend usa Axios con `VITE_BACKEND_URL` (en `frontend/src/api.js`), que va DIRECTO a esa URL e **ignora el proxy de Vite**. Sin `frontend/.env` con `VITE_BACKEND_URL=http://localhost:8001`, cae al default 8000 (el otro proyecto). **Vite debe reiniciarse** tras tocar `.env`.
- `backend/.env` se copia de `backend/.env.example`. Sin `ANTHROPIC_API_KEY` la app funciona igual; solo falla el botón de análisis con IA.

### Build del instalador
```
npm run dist        # = build:frontend (vite) + build:backend (PyInstaller) + electron-builder
```
- Frontend → `frontend/dist`
- Backend → `backend/dist/crypto_sniper_backend/crypto_sniper_backend.exe`
- Instalador → `release/Crypto Sniper Pro Setup 2.0.0.exe` (~137 MB)
- **Workaround winCodeSign**: electron-builder falla creando symlinks de dylibs macOS sin permisos admin ("El cliente no dispone de un privilegio requerido"). Se pre-extrae `winCodeSign-2.6.0` excluyendo la carpeta `darwin` (`7za x ... -x'!darwin'`). Ya aplicado en la caché de electron-builder.
- El instalador **no está firmado** (sin certificado) → Windows mostrará "Editor desconocido" → Más información → Ejecutar de todas formas. Normal.
- **El `.exe` es autónomo** (trae backend + frontend dentro); no necesita Python/Node instalados.
- **Instalador actual entregado**: `Crypto Sniper Pro 2.0.0 (acciones+graficos).exe` en la raíz del proyecto.

## Arquitectura del backend

```
backend/
  server.py              # FastAPI: todos los endpoints + instancias globales
  config.py              # Settings (pydantic): keys de exchanges, comisiones, flags del motor
  market_data.py         # Acciones/ETFs vía Yahoo Finance (is_stock, get_stock_klines, get_stock_price)
  indicators.py          # TechnicalIndicators (8 básicos)
  advanced_indicators.py # 9 avanzados + 5 PRO (VWAP, OBV, ADX, CVD, MFI)
  ai_analyzer.py         # Claude (capa de confirmación, opcional)
  exchanges/
    base.py              # ExchangeAdapter (interfaz unificada) + Candle/OrderResult/Position/Side
    exchange_manager.py  # Registro y exchange activo
    binance_adapter.py   # ACTIVO (cripto, datos reales)
    kraken_adapter.py    # API pública (precios reales para arbitraje)
    stock_adapter.py     # Yahoo "exchange" → el motor opera ACCIONES (is_stock_market=True)
    bybit_adapter.py / okx_adapter.py   # stubs (necesitan keys)
    simulated_adapter.py # SimEx (off por defecto)
  engine/
    strategy.py          # evaluate_signal() — lógica compartida motor+backtester (StrategyParams)
    auto_trader.py       # AutoTrader async: escanear→señal→riesgo→(Claude)→ejecutar→monitorear
    risk_manager.py      # position sizing, topes, corte diario
    backtester.py        # replay vela a vela
    arbitrage.py         # cross-exchange (Binance vs Kraken)
    triangular.py        # arbitraje triangular en un exchange
  optimize_strategy.py   # grid search WALK-FORWARD (validación honesta)
```

### Cómo funciona el motor (auto_trader)
Ciclo cada `scan_interval` (30s): escanear N símbolos del exchange activo → `evaluate_signal` (confluencia de indicadores, filtro tendencia EMA50/EMA200) → control de riesgo → **(opcional) Claude reconfirma/veta** → ejecutar → monitorear salidas (SL / TP / trailing stop / tiempo máx / señal contraria).
- Modos de señal: `momentum` (default del motor, confluencia 5 indicadores), `pullback`, `volume`.
- Modo `paper` (default, NO envía órdenes reales) | `live`.
- **Posiciones**: 1–10 simultáneas, largo Y corto.
- **Apalancamiento** (solo cripto): solo en entradas de confianza ≥80%, máx 24h. Spot normal: máx 72h (3 días).
- **Acciones**: seleccionar exchange "Yahoo" → opera las 20 acciones, velas diarias, retención ~45 días, sin apalancamiento. Todo paper.
- **Botón pánico** `/engine/close-all`: detiene el motor y cierra todo.

## Funcionalidades (resumen por rondas)

- **v2** — Multi-exchange (ExchangeAdapter/Manager), motor auto-trade, empaquetado Electron, endpoints `/exchanges` y `/engine/*`, EnginePanel.
- **v3** — Estrategia compartida motor/backtester, backtesting + métricas + curva equity, trailing stop, modo paper/live, persistencia de posiciones, arbitraje cross-exchange y triangular, optimizador walk-forward.
- **v4** — Kraken real (precios públicos), arbitraje Binance/Kraken con precios ejecutables, fix del **congelamiento** (llamadas síncronas bloqueaban asyncio → `get_all_prices()` por lote + `asyncio.to_thread`), Claude cableado como capa de confirmación en el motor.
- **v5** — **Acciones EEUU** (Yahoo), **5 indicadores PRO** (total 22), **apalancamiento**, rediseño UI "Claude design" (acento coral #d97757, clases `cs-*` en `index.css`). Fix gráfico al cambiar par (`Promise.allSettled`). Líneas entrada/SL/TP en el gráfico.
- **v5+ (2026-06-22, "HAZLO TODO")** — Acciones integradas en el **gráfico principal + selector de pares** (toggle ₿ Cripto / 📈 Acciones) Y en el **motor** (exchange "Yahoo"). Endpoints `/pairs/{sym}/klines` e `/indicators` rutean por símbolo (`is_stock`). Instalador reconstruido.

## Indicadores (22 total)
- **8 básicos** (`indicators.py`): RSI, MACD, Bollinger, EMA, SMA, Estocástico, ATR, volumen.
- **9 avanzados** (`advanced_indicators.py`): SniperScore, PrecisionSniperConfluence, LinearRegressionChannel, SwingProfile, FairValueGaps, IchimokuCloud, NeuroTrendII, SuperTrendedRSI, TurtleChannels.
- **5 PRO** (los de las grandes mesas): VWAP, OBV, ADX, CVD (cumulative volume delta), MFI.

## ⚠️ VEREDICTO DE RENTABILIDAD (CRÍTICO — mantener honestidad)

Validado rigurosamente en 5 rondas con walk-forward sobre 5000 velas:
- **Ninguna estrategia mecánica tiene ventaja robusta**. Todo lo rentable in-sample colapsa out-of-sample (es sobre-ajuste; la validación OOS lo caza). Momentum PF~0.27, pullback/volume PF~0.46, todas pierden OOS.
- **Largos Y cortos ambos pierden** (demostrado: largos -4598, cortos -1969 USDT).
- **Arbitraje no rentable desde retail**: cross-exchange Binance/Kraken **-0.18% neto**, triangular **-0.28% neto** (los spreads brutos ~0.02% << comisiones). Mercados eficientes.
- **Claude NO añade ventaja predictiva** sobre los mismos indicadores de precio (ve datos públicos y tardíos). Es capa de **confirmación**, no de predicción.
- **Acciones**: menor volatilidad y útiles para analizar/backtestear, pero no cambian el veredicto.

**Valor real de la app**: plataforma de aprendizaje + paper trading + backtester honesto + tablero. **NO afirmar nunca que alguna estrategia gana dinero.** El default del motor es **PAPER**. El usuario ordenó operar igual ("por más que sea en pérdidas, yo me hago cargo") — se respeta, pero siempre con la advertencia honesta.

## Directivas del usuario (recordar)
- "Despues usaremos la api de claude por el momento no" → la app funciona SIN key de Claude.
- Operar automáticamente aunque sea en pérdidas; él se hace cargo. Default paper por seguridad.
- Quiere generar beneficios reales — pero la estructura del mercado lo impide a nivel retail. Honestidad ante todo.
- Idioma: español.

## Pendiente / diferido
- **Ejecución real de futuros** (apalancamiento real): hoy solo paper/infraestructura. Necesita `futures_client` cableado + keys de futuros del usuario.
- **Ejecución real de acciones**: no hay bróker conectado (solo paper vía Yahoo).
- Activar Bybit/OKX (stubs) requiere API keys.

## Memoria persistente complementaria
Carpeta `~/.claude/projects/.../memory/` (auto-cargada): `project_v2..v5`, `setup_puertos_arranque`,
`reference_github`. Este `CLAUDE.md` es el consolidado legible y versionado en git.
