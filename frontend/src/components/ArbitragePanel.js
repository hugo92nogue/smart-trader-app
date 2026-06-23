import React, { useState, useEffect, useCallback } from 'react';
import { ArrowsLeftRight, Play, Stop, Triangle } from '@phosphor-icons/react';
import {
  fetchArbitrageStatus, startArbitrage, stopArbitrage, updateArbitrageConfig,
  fetchTriangularStatus, startTriangular, stopTriangular,
} from '../api';

export default function ArbitragePanel() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetchArbitrageStatus();
      setStatus(res.data.data);
    } catch (e) {
      console.error('Arbitrage status error:', e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const handleToggle = async () => {
    setBusy(true);
    try {
      if (status?.running) await stopArbitrage();
      else await startArbitrage();
      await refresh();
    } catch (e) {
      console.error('Arbitrage toggle error:', e);
    }
    setBusy(false);
  };

  const handleExecuteToggle = async () => {
    try {
      await updateArbitrageConfig({ execute: !status?.execute });
      await refresh();
    } catch (e) {
      console.error('Arbitrage config error:', e);
    }
  };

  const running = status?.running;
  const opps = status?.opportunities || [];
  const stats = status?.stats || {};
  const exchanges = status?.connected_exchanges || [];
  const enoughExchanges = exchanges.length >= 2;

  return (
    <div data-testid="arbitrage-panel" className="p-3 space-y-3 overflow-y-auto max-h-full">
      <div className="flex items-center justify-between">
        <h3 className="cs-title flex items-center gap-1.5">
          <ArrowsLeftRight size={14} weight="bold" className={running ? 'text-violet-400' : 'text-zinc-600'} />
          Arbitraje
        </h3>
        <button
          data-testid="arbitrage-toggle"
          onClick={handleToggle}
          disabled={busy || !enoughExchanges}
          className={`flex items-center gap-1.5 px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all ${
            running ? 'bg-red-500/20 text-red-400 border-red-500/50' : 'bg-violet-500/20 text-violet-400 border-violet-500/50'
          } ${(busy || !enoughExchanges) ? 'opacity-50' : ''}`}
        >
          {running ? <Stop size={11} weight="fill" /> : <Play size={11} weight="fill" />}
          {running ? 'DETENER' : 'INICIAR'}
        </button>
      </div>

      {!enoughExchanges && (
        <div className="border border-yellow-500/40 bg-yellow-500/10 p-2 text-[9px] font-mono text-yellow-400 leading-tight">
          Requiere ≥2 exchanges conectados. Conectados: {exchanges.join(', ') || 'ninguno'}.
        </div>
      )}

      {/* Exchanges + ejecución */}
      <div className="flex items-center justify-between text-[10px] font-mono">
        <span className="text-zinc-500">{exchanges.join(' ↔ ')}</span>
        <button
          onClick={handleExecuteToggle}
          className={`px-2 py-0.5 border text-[9px] uppercase tracking-wider ${
            status?.execute ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50' : 'bg-zinc-900 text-zinc-500 border-zinc-700'
          }`}
        >
          {status?.execute ? 'Ejecutar: ON' : 'Ejecutar: OFF'}
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-1">
        <Stat label="Pares" value={stats.pairs_compared ?? 0} />
        <Stat label="Detectadas" value={stats.detected ?? 0} />
        <Stat
          label="Mejor neto"
          value={stats.best_net_pct != null ? `${stats.best_net_pct}%` : '—'}
          cls={(stats.best_net_pct ?? -1) >= 0 ? 'text-emerald-400' : 'text-red-400'}
        />
      </div>
      {stats.best_net_pct != null && stats.best_net_pct < 0 && (
        <div className="text-[9px] font-mono text-zinc-600 leading-tight">
          Mejor oportunidad ({stats.best_symbol}) sigue negativa tras comisiones: spreads reales &lt; costes.
        </div>
      )}

      {/* Oportunidades */}
      <div className="space-y-1">
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">
          Oportunidades ({opps.length})
        </div>
        {opps.length === 0 ? (
          <p className="text-zinc-600 text-[10px] font-mono">{running ? 'Escaneando mercados...' : 'Scanner detenido'}</p>
        ) : (
          opps.map((o) => (
            <div key={o.symbol} className="border border-violet-500/30 bg-violet-500/5 p-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold text-white">{o.symbol}</span>
                <span className="text-[11px] font-mono font-bold text-emerald-400">+{o.net_pct}%</span>
              </div>
              <div className="text-[9px] font-mono text-zinc-500 mt-0.5 leading-tight">
                <span className="text-emerald-400">COMPRA</span> {o.buy_exchange} @ {o.buy_price}
              </div>
              <div className="text-[9px] font-mono text-zinc-500 leading-tight">
                <span className="text-red-400">VENDE</span> {o.sell_exchange} @ {o.sell_price}
              </div>
            </div>
          ))
        )}
      </div>

      {/* ── Arbitraje triangular (un solo exchange) ── */}
      <TriangularSection />
    </div>
  );
}

function TriangularSection() {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await fetchTriangularStatus();
      setStatus(res.data.data);
    } catch (e) {
      console.error('Triangular status error:', e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const timer = window.setInterval(refresh, 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const handleToggle = async () => {
    setBusy(true);
    try {
      if (status?.running) await stopTriangular();
      else await startTriangular();
      await refresh();
    } catch (e) {
      console.error('Triangular toggle error:', e);
    }
    setBusy(false);
  };

  const running = status?.running;
  const opps = status?.opportunities || [];
  const best = status?.stats?.best_pct;

  return (
    <div className="pt-2 mt-1 border-t border-zinc-800 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="font-heading font-bold text-[10px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-1.5">
          <Triangle size={12} weight="bold" className={running ? 'text-amber-400' : 'text-zinc-600'} />
          Triangular (Binance)
        </h4>
        <button
          data-testid="triangular-toggle"
          onClick={handleToggle}
          disabled={busy}
          className={`flex items-center gap-1 px-2 py-0.5 text-[9px] font-mono font-bold uppercase border ${
            running ? 'bg-red-500/20 text-red-400 border-red-500/50' : 'bg-amber-500/20 text-amber-400 border-amber-500/50'
          } ${busy ? 'opacity-50' : ''}`}
        >
          {running ? <Stop size={9} weight="fill" /> : <Play size={9} weight="fill" />}
          {running ? 'STOP' : 'SCAN'}
        </button>
      </div>

      {best !== undefined && best !== null && (
        <div className="text-[9px] font-mono text-zinc-500">
          Mejor spread neto: <span className={best >= 0 ? 'text-emerald-400' : 'text-red-400'}>{best}%</span>
          <span className="text-zinc-600"> (tras 3 comisiones)</span>
        </div>
      )}

      {opps.length === 0 ? (
        <p className="text-zinc-600 text-[9px] font-mono leading-tight">
          {running
            ? 'Escaneando triángulos... (en Binance las oportunidades netas suelen ser negativas: mercado eficiente)'
            : 'Detector de ciclos USDT→X→Y→USDT. Solo detección — ejecutar requiere infra HFT.'}
        </p>
      ) : (
        opps.map((o) => (
          <div key={o.triangle} className="border border-amber-500/30 bg-amber-500/5 p-1.5">
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-mono text-white">{o.route}</span>
              <span className="text-[10px] font-mono font-bold text-emerald-400">+{o.net_pct}%</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function Stat({ label, value, cls = 'text-white' }) {
  return (
    <div className="border border-zinc-800 p-1.5 text-center">
      <div className="text-[8px] text-zinc-500 uppercase tracking-widest font-mono">{label}</div>
      <div className={`text-xs font-mono font-bold ${cls}`}>{value}</div>
    </div>
  );
}
