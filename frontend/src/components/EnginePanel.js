import React, { useState, useEffect, useCallback } from 'react';
import { Lightning, Play, Stop, Warning, TrendUp, TrendDown, XCircle } from '@phosphor-icons/react';
import {
  fetchEngineStatus, startEngine, stopEngine, closeAllPositions,
  fetchExchanges, setActiveExchange, updateEngineConfig,
} from '../api';

export default function EnginePanel() {
  const [status, setStatus] = useState(null);
  const [exchanges, setExchanges] = useState([]);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [statusRes, exRes] = await Promise.all([fetchEngineStatus(), fetchExchanges()]);
      setStatus(statusRes.data.data);
      setExchanges(exRes.data.data || []);
    } catch (e) {
      console.error('Engine status error:', e);
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
      if (status?.running) await stopEngine();
      else await startEngine();
      await refresh();
    } catch (e) {
      console.error('Engine toggle error:', e);
    }
    setBusy(false);
  };

  const handleExchange = async (name) => {
    try {
      await setActiveExchange(name);
      await refresh();
    } catch (e) {
      console.error('Set exchange error:', e);
    }
  };

  const handleModeToggle = async () => {
    try {
      await updateEngineConfig({ mode: status?.mode === 'live' ? 'paper' : 'live' });
      await refresh();
    } catch (e) {
      console.error('Set mode error:', e);
    }
  };

  const handleAiToggle = async () => {
    try {
      await updateEngineConfig({ use_ai: !status?.use_ai });
      await refresh();
    } catch (e) {
      console.error('Set AI error:', e);
    }
  };

  const handleLeverageToggle = async () => {
    try {
      await updateEngineConfig({ use_leverage: !status?.use_leverage });
      await refresh();
    } catch (e) {
      console.error('Set leverage error:', e);
    }
  };

  const handleCloseAll = async () => {
    const n = status?.open_positions?.length || 0;
    if (!window.confirm(`¿Cerrar TODAS las ${n} posiciones abiertas y detener el motor?`)) return;
    setBusy(true);
    try {
      await closeAllPositions();
      await refresh();
    } catch (e) {
      console.error('Close all error:', e);
    }
    setBusy(false);
  };

  const running = status?.running;
  const mode = status?.mode || 'paper';
  const useAi = status?.use_ai;
  const strategyMode = status?.strategy_mode || 'momentum';
  const stats = status?.stats || {};
  const risk = status?.risk || {};
  const positions = status?.open_positions || [];
  const log = status?.log || [];

  return (
    <div data-testid="engine-panel" className="p-3 space-y-3 overflow-y-auto max-h-full">
      <div className="flex items-center justify-between">
        <h3 className="cs-title">
          <Lightning size={14} weight="fill" className={running ? 'text-emerald-400' : 'text-zinc-600'} />
          Motor Auto-Trade
        </h3>
        <button
          data-testid="engine-toggle"
          onClick={handleToggle}
          disabled={busy}
          className={`flex items-center gap-1.5 px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all duration-150 ${
            running
              ? 'bg-red-500/20 text-red-400 border-red-500/50'
              : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50'
          } ${busy ? 'opacity-50' : ''}`}
        >
          {running ? <Stop size={11} weight="fill" /> : <Play size={11} weight="fill" />}
          {running ? 'DETENER' : 'INICIAR'}
        </button>
      </div>

      {/* PÁNICO: cerrar todas las posiciones y detener el motor */}
      <button
        data-testid="engine-close-all"
        onClick={handleCloseAll}
        disabled={busy || (status?.open_positions?.length || 0) === 0}
        className={`w-full flex items-center justify-center gap-1.5 px-2 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all ${
          (status?.open_positions?.length || 0) > 0
            ? 'bg-red-600/30 text-red-300 border-red-500/60 hover:bg-red-600/50'
            : 'bg-zinc-900 text-zinc-600 border-zinc-800 cursor-not-allowed'
        }`}
      >
        <XCircle size={13} weight="fill" />
        CERRAR TODO ({status?.open_positions?.length || 0})
      </button>

      {/* Modo PAPER / LIVE — seguridad: distingue simulación de real */}
      <button
        data-testid="engine-mode-toggle"
        onClick={handleModeToggle}
        className={`w-full flex items-center justify-center gap-1.5 px-2 py-1 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all ${
          mode === 'live'
            ? 'bg-red-500/20 text-red-400 border-red-500/50'
            : 'bg-sky-500/15 text-sky-400 border-sky-500/40'
        }`}
      >
        {mode === 'live' ? '🔴 MODO REAL (LIVE)' : '🧪 MODO SIMULACIÓN (PAPER)'}
        <span className="text-zinc-500 normal-case">— clic para cambiar</span>
      </button>

      {/* Estrategia + confirmación IA (Claude) */}
      <div className="flex gap-1">
        <div className="flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[10px] font-mono cs-card text-zinc-400">
          <span className="text-zinc-600 uppercase">Señal:</span> {strategyMode}
        </div>
        <button
          data-testid="engine-ai-toggle"
          onClick={handleAiToggle}
          className={`flex-1 flex items-center justify-center gap-1 px-2 py-1 text-[10px] font-mono font-bold uppercase border transition-all ${
            useAi ? 'bg-violet-500/20 text-violet-400 border-violet-500/50' : 'bg-zinc-900 text-zinc-500 border-zinc-700'
          }`}
        >
          {useAi ? '🤖 Claude: ON' : 'Claude: OFF'}
        </button>
      </div>
      {useAi && (
        <div className="text-[9px] font-mono text-zinc-600 leading-tight">
          Claude reconfirma cada señal de los indicadores antes de operar. Requiere API key en .env.
        </div>
      )}

      {/* Apalancamiento (solo entradas seguras, máx 24h) */}
      <button
        data-testid="engine-leverage-toggle"
        onClick={handleLeverageToggle}
        className={`w-full flex items-center justify-center gap-1.5 px-2 py-1 text-[10px] font-mono font-bold uppercase tracking-wider border transition-all ${
          status?.use_leverage
            ? 'bg-amber-500/20 text-amber-400 border-amber-500/50'
            : 'bg-zinc-900 text-zinc-500 border-zinc-700'
        }`}
      >
        {status?.use_leverage ? `⚡ Apalancamiento ${status?.leverage}× (entradas seguras, 24h)` : 'Apalancamiento: OFF'}
      </button>
      {status?.use_leverage && (
        <div className="text-[9px] font-mono text-amber-600/80 leading-tight">
          Solo en entradas de confianza ≥80%. Amplifica ganancias Y pérdidas ×{status?.leverage}. Cierre máx 24h.
        </div>
      )}

      {/* Halt warning */}
      {risk.halted && (
        <div className="flex items-start gap-1.5 border border-red-500/40 bg-red-500/10 p-2">
          <Warning size={12} className="text-red-400 mt-0.5 shrink-0" />
          <span className="text-[10px] font-mono text-red-400">{risk.halt_reason}</span>
        </div>
      )}

      {/* Exchange selector */}
      <div className="space-y-1">
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Exchanges</div>
        <div className="flex gap-1">
          {exchanges.map((ex) => (
            <button
              key={ex.name}
              data-testid={`exchange-${ex.name}`}
              onClick={() => ex.connected && handleExchange(ex.name)}
              disabled={!ex.connected}
              className={`flex-1 px-2 py-1.5 text-[10px] font-mono border transition-colors ${
                ex.active
                  ? 'bg-zinc-800 text-white border-zinc-600'
                  : ex.connected
                  ? 'bg-transparent text-zinc-400 border-zinc-800 hover:border-zinc-600'
                  : 'bg-transparent text-zinc-700 border-zinc-900 cursor-not-allowed'
              }`}
            >
              <div className="flex items-center justify-center gap-1">
                <span className={`w-1.5 h-1.5 rounded-full ${ex.connected ? 'bg-emerald-400' : 'bg-zinc-700'}`} />
                {ex.name}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-1">
        <StatBox label="Trades" value={stats.trades_closed ?? 0} />
        <StatBox label="Win Rate" value={`${stats.win_rate ?? 0}%`} accent={stats.win_rate >= 50 ? 'emerald' : 'red'} />
        <StatBox
          label="PnL Total"
          value={`${(stats.total_pnl ?? 0) >= 0 ? '+' : ''}${(stats.total_pnl ?? 0).toFixed(2)}`}
          accent={(stats.total_pnl ?? 0) >= 0 ? 'emerald' : 'red'}
        />
        <StatBox
          label="PnL Hoy"
          value={`${(risk.daily_pnl ?? 0) >= 0 ? '+' : ''}${(risk.daily_pnl ?? 0).toFixed(2)}`}
          accent={(risk.daily_pnl ?? 0) >= 0 ? 'emerald' : 'red'}
        />
      </div>

      {/* Open positions */}
      <div className="space-y-1">
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">
          Posiciones ({positions.length})
        </div>
        {positions.length === 0 ? (
          <p className="text-zinc-600 text-[10px] font-mono">Sin posiciones abiertas</p>
        ) : (
          positions.map((p) => (
            <div key={`${p.exchange}-${p.symbol}`} className={`border p-1.5 ${
              p.side === 'buy' ? 'border-emerald-500/30 bg-emerald-500/5' : 'border-red-500/30 bg-red-500/5'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-mono font-bold text-white flex items-center gap-1">
                  {p.side === 'buy' ? <TrendUp size={10} className="text-emerald-400" /> : <TrendDown size={10} className="text-red-400" />}
                  {p.symbol}
                </span>
                <span className="text-[9px] font-mono text-zinc-500">{p.exchange}</span>
              </div>
              <div className="text-[9px] font-mono text-zinc-500 mt-0.5">
                {p.quantity} @ {p.entry_price?.toFixed(6)} | SL {p.stop_loss?.toFixed(6)}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Live log */}
      <div className="space-y-1">
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Actividad</div>
        <div className="space-y-0.5 max-h-40 overflow-y-auto">
          {log.length === 0 ? (
            <p className="text-zinc-600 text-[10px] font-mono">Motor inactivo</p>
          ) : (
            log.map((entry, i) => (
              <div key={`${entry.ts}-${i}`} className="text-[9px] font-mono leading-tight">
                <span className={
                  entry.level === 'error' ? 'text-red-400' :
                  entry.level === 'warning' ? 'text-yellow-400' : 'text-zinc-500'
                }>
                  {entry.msg}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function StatBox({ label, value, accent }) {
  const colorClass = accent === 'emerald' ? 'text-emerald-400' : accent === 'red' ? 'text-red-400' : 'text-white';
  return (
    <div className="cs-card p-1.5">
      <div className="text-[9px] text-zinc-500 uppercase tracking-widest font-mono">{label}</div>
      <div className={`text-sm font-mono font-bold ${colorClass}`}>{value}</div>
    </div>
  );
}
