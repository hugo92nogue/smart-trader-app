import React, { useState, useEffect, useCallback, useRef } from 'react';
import "@/App.css";
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import {
  WifiHigh, WifiX, ChartLine, ArrowsClockwise,
  CaretDown, Lightning
} from '@phosphor-icons/react';
import PriceChart from './components/PriceChart';
import IndicatorsPanel from './components/IndicatorsPanel';
import TradingPanel from './components/TradingPanel';
import AITerminal from './components/AITerminal';
import SignalsPanel from './components/SignalsPanel';
import TradeHistory from './components/TradeHistory';
import PairSelector from './components/PairSelector';
import NewListingsPanel from './components/NewListingsPanel';
import {
  fetchPairs, fetchKlines, fetchIndicators, fetchBalance,
  fetchOrderHistory, fetchNewListings, fetchHealth, fetchSignals,
  toggleAutoTrade, createPriceWebSocket
} from './api';

const INTERVALS = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];

// ── Custom hook: WebSocket price stream ──
function usePriceWebSocket(selectedPair) {
  const [wsConnected, setWsConnected] = useState(false);
  const [livePrice, setLivePrice] = useState(null);
  const wsRef = useRef(null);
  const selectedPairRef = useRef(selectedPair);

  // Keep ref in sync
  useEffect(() => {
    selectedPairRef.current = selectedPair;
  }, [selectedPair]);

  // Connect once on mount
  useEffect(() => {
    const ws = createPriceWebSocket((msg) => {
      if (msg.type === 'price_update' && msg.symbol === selectedPairRef.current) {
        setLivePrice(msg.price);
      }
    });

    ws.onopen = () => {
      setWsConnected(true);
      ws.send(JSON.stringify({ action: 'set_symbol', symbol: selectedPairRef.current }));
    };
    ws.onclose = () => setWsConnected(false);
    wsRef.current = ws;

    return () => {
      if (ws.readyState === WebSocket.OPEN) ws.close();
    };
  }, []);

  // Re-subscribe when pair changes
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'set_symbol', symbol: selectedPair }));
    }
  }, [selectedPair]);

  return { wsConnected, livePrice };
}

// ── Custom hook: initial data ──
function useInitialData() {
  const [pairs, setPairs] = useState([]);
  const [balance, setBalance] = useState(null);
  const [newListings, setNewListings] = useState([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        const healthRes = await fetchHealth();
        setConnected(healthRes.data.status === 'healthy');
      } catch {
        setConnected(false);
      }
      try {
        const pairsRes = await fetchPairs();
        setPairs(pairsRes.data.data || []);
      } catch (e) {
        console.error('Error loading pairs:', e);
      }
      try {
        const balRes = await fetchBalance();
        setBalance(balRes.data.data?.balances || balRes.data.data?.demo_balance);
      } catch (e) {
        console.error('Error loading balance:', e);
      }
      try {
        const listingsRes = await fetchNewListings();
        setNewListings(listingsRes.data.data || []);
      } catch (e) {
        console.error('Error loading listings:', e);
      }
    }
    init();
  }, []);

  return { pairs, balance, newListings, connected };
}

// ── Dashboard ──
function Dashboard() {
  const [selectedPair, setSelectedPair] = useState('BTCUSDT');
  const [interval, setInterval_] = useState('1h');
  const [klines, setKlines] = useState([]);
  const [indicators, setIndicators] = useState(null);
  const [trades, setTrades] = useState([]);
  const [signals, setSignals] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showPairSelector, setShowPairSelector] = useState(false);
  const [pairSearch, setPairSearch] = useState('');
  const [activeIndicators, setActiveIndicators] = useState(['rsi', 'macd', 'bollinger', 'ema_20', 'stochastic']);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [priceChange, setPriceChange] = useState(null);
  const [autoTradeEnabled, setAutoTradeEnabled] = useState(false);

  const { pairs, balance, newListings, connected } = useInitialData();
  const { wsConnected, livePrice } = usePriceWebSocket(selectedPair);

  // Apply live WS price
  useEffect(() => {
    if (livePrice !== null) {
      setCurrentPrice(livePrice);
    }
  }, [livePrice]);

  // Load data for selected pair
  const loadPairData = useCallback(async () => {
    if (!selectedPair) return;
    setLoading(true);
    try {
      const [klinesRes, indRes, tradesRes, signalsRes] = await Promise.all([
        fetchKlines(selectedPair, interval, 200),
        fetchIndicators(selectedPair, interval),
        fetchOrderHistory(50),
        fetchSignals(50)
      ]);

      setKlines(klinesRes.data.data || []);
      setIndicators(indRes.data.data || null);
      setTrades(tradesRes.data.data || []);
      setSignals(signalsRes.data.data || []);

      const lastKline = klinesRes.data.data?.slice(-1)[0];
      if (lastKline) {
        setCurrentPrice(lastKline.close);
        const firstKline = klinesRes.data.data?.[0];
        if (firstKline) {
          setPriceChange(((lastKline.close - firstKline.open) / firstKline.open * 100));
        }
      }
    } catch (e) {
      console.error('Error loading pair data:', e);
    }
    setLoading(false);
  }, [selectedPair, interval]);

  useEffect(() => {
    loadPairData();
    const timer = window.setInterval(loadPairData, 10000);
    return () => window.clearInterval(timer);
  }, [loadPairData]);

  const handlePairSelect = useCallback((symbol) => {
    setSelectedPair(symbol);
    setShowPairSelector(false);
    setPairSearch('');
  }, []);

  const handleToggleIndicator = useCallback((key) => {
    setActiveIndicators(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  }, []);

  const handleToggleAutoTrade = useCallback(async () => {
    try {
      const newState = !autoTradeEnabled;
      await toggleAutoTrade(newState);
      setAutoTradeEnabled(newState);
    } catch (e) {
      console.error('Error toggling auto-trade:', e);
    }
  }, [autoTradeEnabled]);

  function formatPrice(price) {
    if (price == null) return '---';
    return price < 1 ? price.toFixed(4) : price.toFixed(2);
  }

  function getPriceChangeClass() {
    if (priceChange === null) return '';
    return priceChange >= 0 ? 'text-emerald-400' : 'text-red-400';
  }

  return (
    <div data-testid="trading-dashboard" className="h-screen flex flex-col bg-[#09090b] overflow-hidden">
      {/* ═══ TOP TOOLBAR ═══ */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <ChartLine size={18} weight="bold" className="text-[#007AFF]" />
            <span className="font-heading font-bold text-sm text-white tracking-tight">CRYPTO SNIPER</span>
          </div>

          <div className="relative">
            <button
              data-testid="pair-selector-btn"
              onClick={() => setShowPairSelector(!showPairSelector)}
              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 border border-zinc-800 hover:border-zinc-600 transition-colors"
            >
              <span className="font-mono font-bold text-sm text-white">{selectedPair?.replace('USDT', '')}</span>
              <span className="text-[10px] text-zinc-500 font-mono">/USDT</span>
              <CaretDown size={10} className="text-zinc-500" />
            </button>
            {showPairSelector && (
              <div className="absolute top-full left-0 mt-1 z-50 w-80">
                <PairSelector pairs={pairs} selectedPair={selectedPair} onSelect={handlePairSelect} searchQuery={pairSearch} onSearchChange={setPairSearch} />
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-white">${formatPrice(currentPrice)}</span>
            {priceChange !== null && (
              <span className={`text-xs font-mono font-bold ${getPriceChangeClass()}`}>
                {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)}%
              </span>
            )}
          </div>

          <div className="flex gap-0.5">
            {INTERVALS.map(int => (
              <button key={int} data-testid={`interval-${int}`} onClick={() => setInterval_(int)}
                className={`px-2 py-1 text-[10px] font-mono uppercase transition-colors ${
                  interval === int ? 'bg-zinc-800 text-white border border-zinc-600' : 'text-zinc-500 hover:text-zinc-300 border border-transparent'
                }`}>{int}</button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button data-testid="auto-trade-toggle" onClick={handleToggleAutoTrade}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all duration-150 ${
              autoTradeEnabled ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50 pulse-buy' : 'bg-zinc-900 text-zinc-500 border-zinc-700 hover:border-zinc-500'
            }`}>
            <Lightning size={12} weight={autoTradeEnabled ? "fill" : "regular"} />
            {autoTradeEnabled ? 'AUTO: ON' : 'AUTO: OFF'}
          </button>

          <button data-testid="refresh-btn" onClick={loadPairData} className="p-1.5 text-zinc-500 hover:text-white transition-colors">
            <ArrowsClockwise size={14} className={loading ? 'animate-spin' : ''} />
          </button>

          <ConnectionStatus connected={connected} wsConnected={wsConnected} />
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div className="flex-1 grid grid-cols-12 gap-0 overflow-hidden">
        <div className="col-span-2 border-r border-zinc-800 overflow-y-auto flex flex-col">
          <div className="flex-1 border-b border-zinc-800"><SignalsPanel signals={signals} indicators={indicators} /></div>
          <div><NewListingsPanel listings={newListings} /></div>
        </div>

        <div className="col-span-7 flex flex-col overflow-hidden">
          <div className="flex-1 border-b border-zinc-800" style={{ minHeight: '400px' }}>
            <PriceChart klines={klines} symbol={selectedPair} interval={interval} />
          </div>
          <div style={{ height: '220px' }}><AITerminal symbol={selectedPair} interval={interval} /></div>
        </div>

        <div className="col-span-3 border-l border-zinc-800 overflow-y-auto flex flex-col">
          <div className="flex-1 border-b border-zinc-800 overflow-y-auto">
            <IndicatorsPanel data={indicators} activeIndicators={activeIndicators} onToggle={handleToggleIndicator} />
          </div>
          <div className="border-b border-zinc-800">
            <TradingPanel symbol={selectedPair} price={currentPrice} balance={balance} onOrderPlaced={loadPairData} />
          </div>
        </div>
      </div>

      <div className="border-t border-zinc-800 overflow-y-auto" style={{ maxHeight: '200px' }}>
        <TradeHistory trades={trades} />
      </div>

      {showPairSelector && <div className="fixed inset-0 z-30" onClick={() => setShowPairSelector(false)} />}
    </div>
  );
}

// ── Extracted component: Connection Status ──
function ConnectionStatus({ connected, wsConnected }) {
  if (connected) {
    return (
      <div data-testid="connection-status" className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800">
        <WifiHigh size={12} className="text-emerald-400" />
        <span className="text-[10px] font-mono text-emerald-400">TESTNET</span>
        {wsConnected && <span className="text-[9px] font-mono text-cyan-400 ml-1">WS</span>}
      </div>
    );
  }
  return (
    <div data-testid="connection-status" className="flex items-center gap-1.5 px-2 py-1 border border-zinc-800">
      <WifiX size={12} className="text-red-400" />
      <span className="text-[10px] font-mono text-red-400">OFFLINE</span>
    </div>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
