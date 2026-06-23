import axios from 'axios';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' }
});

export const fetchPairs = () => api.get('/pairs');
export const fetchPrice = (symbol) => api.get(`/pairs/${symbol}/price`);
export const fetchKlines = (symbol, interval = '1h', limit = 200) =>
  api.get(`/pairs/${symbol}/klines?interval=${interval}&limit=${limit}`);
export const fetchIndicators = (symbol, interval = '1h') =>
  api.get(`/pairs/${symbol}/indicators?interval=${interval}`);
export const fetchAIAnalysis = (symbol, interval = '1h') =>
  api.post('/analysis/ai', { symbol, interval });
export const fetchAIHistory = (symbol, limit = 20) =>
  api.get(`/analysis/history?symbol=${symbol}&limit=${limit}`);
export const fetchSignals = (limit = 50) => api.get(`/signals?limit=${limit}`);
export const fetchBalance = () => api.get('/account/balance');
export const placeOrder = (data) => api.post('/orders', data);
export const fetchOrderHistory = (limit = 50) => api.get(`/orders/history?limit=${limit}`);
export const fetchNewListings = () => api.get('/new-listings');
export const fetchSettings = () => api.get('/settings');
export const fetchHealth = () => api.get('/health');
export const toggleAutoTrade = (enabled) => api.post('/settings/auto-trade', { enabled });

// Futures
export const placeFuturesOrder = (data) => api.post('/futures/order', data);
export const fetchFuturesPositions = () => api.get('/futures/positions');
export const fetchFuturesBalance = () => api.get('/futures/balance');
export const fetchFuturesHistory = (limit = 50) => api.get(`/futures/history?limit=${limit}`);

// Exchanges
export const fetchExchanges = () => api.get('/exchanges');
export const setActiveExchange = (name) => api.post('/exchanges/active', { name });

// Auto-trade Engine
export const fetchEngineStatus = () => api.get('/engine/status');
export const startEngine = () => api.post('/engine/start');
export const stopEngine = () => api.post('/engine/stop');
export const closeAllPositions = () => api.post('/engine/close-all');
export const updateEngineConfig = (config) => api.post('/engine/config', config);

// Backtesting
export const runBacktest = (params) => api.post('/backtest/run', params);

// Stocks / mercados tradicionales
export const fetchStocksList = () => api.get('/stocks/list');
export const fetchStockKlines = (symbol, interval = '1d', limit = 500) =>
  api.get(`/stocks/${symbol}/klines?interval=${interval}&limit=${limit}`);

// Arbitrage (cross-exchange)
export const fetchArbitrageStatus = () => api.get('/arbitrage/status');
export const startArbitrage = () => api.post('/arbitrage/start');
export const stopArbitrage = () => api.post('/arbitrage/stop');
export const updateArbitrageConfig = (config) => api.post('/arbitrage/config', config);

// Arbitrage (triangular, single exchange)
export const fetchTriangularStatus = () => api.get('/arbitrage/triangular/status');
export const startTriangular = () => api.post('/arbitrage/triangular/start');
export const stopTriangular = () => api.post('/arbitrage/triangular/stop');

// WebSocket
export const createPriceWebSocket = (onMessage) => {
  const wsUrl = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://');
  const ws = new WebSocket(`${wsUrl}/ws/prices`);
  ws.onmessage = (event) => {
    try {
      onMessage(JSON.parse(event.data));
    } catch (err) {
      console.error('WS parse error:', err);
    }
  };
  ws.onerror = (e) => console.error('WS error:', e);
  return ws;
};

export default api;
