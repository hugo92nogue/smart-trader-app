import React from 'react';
import { Clock, ArrowUp, ArrowDown, Target } from '@phosphor-icons/react';

export default function SignalsPanel({ signals, indicators }) {
  // Generate signals from indicators
  const generateSignals = () => {
    if (!indicators) return [];
    
    const sigs = [];
    const now = new Date().toISOString();
    
    // Sniper Score signal
    const sniper = indicators.sniper_score;
    if (sniper) {
      if (sniper.ema_cross_buy) {
        sigs.push({
          type: 'entry', action: 'buy', source: 'Sniper EMA Cross',
          confidence: sniper.bull_pct, timestamp: now,
          detail: `Bull ${sniper.bull_pct?.toFixed(0)}% | ${sniper.bias}`
        });
      }
      if (sniper.ema_cross_sell) {
        sigs.push({
          type: 'exit', action: 'sell', source: 'Sniper EMA Cross',
          confidence: sniper.bear_pct, timestamp: now,
          detail: `Bear ${sniper.bear_pct?.toFixed(0)}% | ${sniper.bias}`
        });
      }
    }
    
    // Confluence signal
    const conf = indicators.confluence_score;
    if (conf?.signal && conf.signal !== 'neutral') {
      sigs.push({
        type: conf.signal === 'buy' ? 'entry' : 'exit',
        action: conf.signal,
        source: 'Precision Sniper',
        confidence: (Math.max(conf.bull_score, conf.bear_score) / 10) * 100,
        timestamp: now,
        detail: `Grade ${conf.grade} | ADX ${conf.adx?.toFixed(1)}`
      });
    }
    
    // Combined signal
    if (indicators.combined_signal && indicators.combined_signal !== 'neutral') {
      sigs.push({
        type: indicators.combined_signal === 'buy' ? 'entry' : 'exit',
        action: indicators.combined_signal,
        source: 'Confluencia Total',
        confidence: (indicators.signal_strength || 0) * 100,
        timestamp: now,
        detail: `Fuerza: ${((indicators.signal_strength || 0) * 100).toFixed(0)}%`
      });
    }

    // Viability signal
    const viability = indicators.viability;
    if (viability && viability.viable) {
      sigs.push({
        type: 'entry', action: indicators.combined_signal || 'neutral',
        source: 'Comisiones OK',
        confidence: viability.rr_ratio * 25,
        timestamp: now,
        detail: `R/R: ${viability.rr_ratio} | Net: ${viability.profit_pct?.toFixed(3)}%`
      });
    }

    return sigs;
  };

  const allSignals = [...generateSignals(), ...(signals || [])];

  return (
    <div data-testid="signals-panel" className="p-3 space-y-2 overflow-y-auto max-h-full">
      <h3 className="cs-title pb-1">
        Señales de Trading
      </h3>

      {allSignals.length === 0 ? (
        <p className="text-zinc-600 text-xs font-mono">Sin señales activas</p>
      ) : (
        <div className="space-y-1">
          {allSignals.map((sig, i) => {
            const signalKey = `${sig.source}-${sig.action}-${sig.type}-${i}`;
            const borderClass = sig.action === 'buy'
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : sig.action === 'sell'
              ? 'border-red-500/30 bg-red-500/5'
              : 'border-zinc-800 bg-zinc-950';
            const textClass = sig.action === 'buy' ? 'text-emerald-400' : sig.action === 'sell' ? 'text-red-400' : 'text-zinc-400';

            function renderIcon() {
              if (sig.action === 'buy') return <ArrowUp size={10} weight="bold" className="text-emerald-400" />;
              if (sig.action === 'sell') return <ArrowDown size={10} weight="bold" className="text-red-400" />;
              return <Target size={10} className="text-zinc-400" />;
            }

            return (
            <div
              key={signalKey}
              data-testid={`signal-${i}`}
              className={`border p-2 transition-all duration-150 ${borderClass}`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1">
                  {renderIcon()}
                  <span className={`text-[10px] font-mono font-bold uppercase ${textClass}`}>
                    {sig.type === 'entry' ? 'ENTRADA' : 'SALIDA'} {sig.action?.toUpperCase()}
                  </span>
                </div>
                <span className="text-[9px] font-mono text-zinc-600">
                  {sig.confidence?.toFixed(0)}%
                </span>
              </div>
              <div className="text-[10px] font-mono text-zinc-500 mt-0.5">{sig.source}</div>
              {sig.detail && <div className="text-[9px] font-mono text-zinc-600 mt-0.5">{sig.detail}</div>}
            </div>
            );
          })}
        </div>
      )}

      {/* FVG Levels */}
      {indicators?.fvg?.gaps?.length > 0 && (
        <div className="cs-card p-2 mt-2">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono mb-1">Fair Value Gaps</div>
          {indicators.fvg.gaps.slice(0, 3).map((gap) => (
            <div key={`${gap.type}-${gap.low}-${gap.high}`} className="flex justify-between text-[10px] font-mono py-0.5">
              <span className={gap.type === 'BULLISH' ? 'text-emerald-400' : 'text-red-400'}>{gap.type}</span>
              <span className="text-zinc-400">{gap.low?.toFixed(2)} - {gap.high?.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Swing Profile */}
      {indicators?.swing_profile?.trend && (
        <div className="cs-card p-2">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono mb-1">Swing Profile</div>
          <div className={`text-xs font-mono font-bold ${
            indicators.swing_profile.trend === 'UPTREND' ? 'text-emerald-400' :
            indicators.swing_profile.trend === 'DOWNTREND' ? 'text-red-400' : 'text-yellow-400'
          }`}>{indicators.swing_profile.trend}</div>
          <div className="text-[10px] font-mono text-zinc-500 mt-0.5">
            Delta Vol: {indicators.swing_profile.volume_delta?.toFixed(1)}%
          </div>
        </div>
      )}
    </div>
  );
}
