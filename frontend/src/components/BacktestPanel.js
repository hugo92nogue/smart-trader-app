import React, { useState, useEffect } from 'react';
import { ChartBar, Play, Spinner } from '@phosphor-icons/react';
import { runBacktest, fetchStocksList } from '../api';

export default function BacktestPanel({ symbol, interval }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [trailing, setTrailing] = useState(true);
  const [market, setMarket] = useState('crypto');     // 'crypto' | 'stocks'
  const [stocks, setStocks] = useState([]);
  const [stockSymbol, setStockSymbol] = useState('SPY');

  useEffect(() => {
    if (market === 'stocks' && stocks.length === 0) {
      fetchStocksList().then(r => setStocks(r.data.data || [])).catch(() => {});
    }
  }, [market, stocks.length]);

  const activeSymbol = market === 'stocks' ? stockSymbol : symbol;
  const activeInterval = market === 'stocks' ? '1d' : interval;

  const handleRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await runBacktest({
        symbol: activeSymbol,
        interval: activeInterval,
        limit: 1000,
        use_trailing_stop: trailing,
        market,
      });
      setResult(res.data.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Error al ejecutar backtest');
    }
    setLoading(false);
  };

  const positive = (v) => (v >= 0 ? 'text-emerald-400' : 'text-red-400');

  return (
    <div data-testid="backtest-panel" className="p-3 space-y-3 overflow-y-auto max-h-full">
      <div className="flex items-center justify-between">
        <h3 className="cs-title flex items-center gap-1.5">
          <ChartBar size={14} weight="bold" className="text-cyan-400" />
          Backtest — {activeSymbol} {activeInterval}
        </h3>
        <button
          data-testid="backtest-run"
          onClick={handleRun}
          disabled={loading}
          className="flex items-center gap-1.5 px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-wider border bg-cyan-500/20 text-cyan-400 border-cyan-500/50 disabled:opacity-50"
        >
          {loading ? <Spinner size={11} className="animate-spin" /> : <Play size={11} weight="fill" />}
          {loading ? 'Corriendo' : 'Ejecutar'}
        </button>
      </div>

      {/* Selector de mercado: Cripto vs Acciones EEUU */}
      <div className="flex gap-1">
        {['crypto', 'stocks'].map(m => (
          <button
            key={m}
            onClick={() => setMarket(m)}
            className={`flex-1 px-2 py-1 text-[10px] font-mono font-bold uppercase border transition-colors ${
              market === m ? 'bg-cyan-500/20 text-cyan-400 border-cyan-500/50' : 'bg-transparent text-zinc-500 border-zinc-800'
            }`}
          >
            {m === 'crypto' ? '₿ Cripto' : '📈 Acciones EEUU'}
          </button>
        ))}
      </div>

      {market === 'stocks' && (
        <select
          value={stockSymbol}
          onChange={(e) => setStockSymbol(e.target.value)}
          className="w-full bg-zinc-900 border border-zinc-700 text-zinc-200 text-[11px] font-mono px-2 py-1 rounded"
        >
          {stocks.map(s => (
            <option key={s.symbol} value={s.symbol}>{s.symbol} — {s.name}</option>
          ))}
        </select>
      )}

      <label className="flex items-center gap-2 text-[10px] font-mono text-zinc-400 cursor-pointer">
        <input type="checkbox" checked={trailing} onChange={(e) => setTrailing(e.target.checked)} className="accent-cyan-500" />
        Trailing stop activado
      </label>

      {error && (
        <div className="border border-red-500/40 bg-red-500/10 p-2 text-[10px] font-mono text-red-400">{error}</div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 gap-1">
            <Metric label="Retorno" value={`${result.total_return_pct >= 0 ? '+' : ''}${result.total_return_pct}%`} cls={positive(result.total_return_pct)} />
            <Metric label="Win Rate" value={`${result.win_rate}%`} cls={result.win_rate >= 50 ? 'text-emerald-400' : 'text-yellow-400'} />
            <Metric label="Trades" value={result.total_trades} />
            <Metric label="Profit Factor" value={result.profit_factor} cls={result.profit_factor >= 1 ? 'text-emerald-400' : 'text-red-400'} />
            <Metric label="Max Drawdown" value={`-${result.max_drawdown_pct}%`} cls="text-red-400" />
            <Metric label="Sharpe" value={result.sharpe} cls={positive(result.sharpe)} />
            <Metric label="Balance Final" value={`$${result.final_balance}`} cls={positive(result.total_return_pct)} />
            <Metric label="Wins / Losses" value={`${result.wins} / ${result.losses}`} />
          </div>

          {result.profit_factor < 1 && (
            <div className="border border-yellow-500/40 bg-yellow-500/10 p-2 text-[9px] font-mono text-yellow-400 leading-tight">
              ⚠ Estrategia no rentable en este periodo (PF &lt; 1). Ajusta parámetros antes de operar en real.
            </div>
          )}

          <EquityCurve curve={result.equity_curve} initial={result.initial_balance} />

          <div className="space-y-0.5">
            <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Últimos trades</div>
            <div className="max-h-32 overflow-y-auto space-y-0.5">
              {result.trades?.slice().reverse().map((t, i) => (
                <div key={i} className="flex justify-between text-[9px] font-mono">
                  <span className={t.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}>
                    {t.side.toUpperCase()} [{t.reason}]
                  </span>
                  <span className={positive(t.pnl)}>{t.pnl >= 0 ? '+' : ''}{t.pnl}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!result && !loading && !error && (
        <p className="text-zinc-600 text-[10px] font-mono">Ejecuta un backtest para ver el rendimiento histórico de la estrategia.</p>
      )}
    </div>
  );
}

function Metric({ label, value, cls = 'text-white' }) {
  return (
    <div className="border border-zinc-800 p-1.5">
      <div className="text-[9px] text-zinc-500 uppercase tracking-widest font-mono">{label}</div>
      <div className={`text-xs font-mono font-bold ${cls}`}>{value}</div>
    </div>
  );
}

function EquityCurve({ curve, initial }) {
  if (!curve || curve.length < 2) return null;
  const w = 240, h = 50;
  const min = Math.min(...curve), max = Math.max(...curve);
  const range = max - min || 1;
  const pts = curve.map((v, i) => {
    const x = (i / (curve.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  const up = curve[curve.length - 1] >= initial;
  return (
    <div className="border border-zinc-800 p-1.5">
      <div className="text-[9px] text-zinc-500 uppercase tracking-widest font-mono mb-1">Curva de Equity</div>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="block">
        <polyline points={pts} fill="none" stroke={up ? '#34C759' : '#FF3B30'} strokeWidth="1.5" />
      </svg>
    </div>
  );
}
