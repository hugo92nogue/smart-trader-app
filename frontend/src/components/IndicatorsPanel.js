import React from 'react';
import { TrendUp, TrendDown, Minus, Lightning } from '@phosphor-icons/react';

const INDICATOR_BADGES = [
  { key: 'rsi', label: 'RSI', color: '#007AFF' },
  { key: 'macd', label: 'MACD', color: '#A855F7' },
  { key: 'bollinger', label: 'BBANDS', color: '#F5A623' },
  { key: 'ema_20', label: 'EMA(20)', color: '#34C759' },
  { key: 'sma_50', label: 'SMA(50)', color: '#FF3B30' },
  { key: 'stochastic', label: 'STOCH', color: '#06b6d4' },
  { key: 'atr', label: 'ATR', color: '#ec4899' },
];

function SignalIcon({ signal }) {
  if (signal === 'buy') return <TrendUp size={14} weight="bold" className="text-emerald-400" />;
  if (signal === 'sell') return <TrendDown size={14} weight="bold" className="text-red-400" />;
  return <Minus size={14} className="text-zinc-500" />;
}

export default function IndicatorsPanel({ data, activeIndicators, onToggle }) {
  if (!data) return (
    <div data-testid="indicators-panel" className="p-3 space-y-2">
      <h3 className="font-heading font-bold text-xs uppercase tracking-[0.2em] text-zinc-500">Indicadores</h3>
      <p className="text-zinc-600 text-xs font-mono">Selecciona un par...</p>
    </div>
  );

  const basic = data.basic || {};
  const sniper = data.sniper_score || {};
  const confluence = data.confluence_score || {};
  const lr = data.linear_regression || {};

  return (
    <div data-testid="indicators-panel" className="p-3 space-y-3 overflow-y-auto max-h-full">
      <h3 className="font-heading font-bold text-xs uppercase tracking-[0.2em] text-zinc-500 pb-1">
        Indicadores Tecnicoss
      </h3>

      {/* Toggle badges */}
      <div className="flex flex-wrap gap-1">
        {INDICATOR_BADGES.map(ind => (
          <button
            key={ind.key}
            data-testid={`indicator-toggle-${ind.key}`}
            onClick={() => onToggle && onToggle(ind.key)}
            className={`px-2 py-1 text-[10px] font-mono border transition-colors duration-150 ${
              activeIndicators?.includes(ind.key)
                ? 'bg-zinc-800 text-white border-zinc-600'
                : 'bg-transparent text-zinc-500 border-zinc-800'
            }`}
          >
            {ind.label}
          </button>
        ))}
      </div>

      {/* Basic indicators values */}
      <div className="space-y-1">
        {basic.rsi !== undefined && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">RSI(14)</span>
            <span className={basic.rsi > 70 ? 'text-red-400' : basic.rsi < 30 ? 'text-emerald-400' : 'text-white'}>
              {basic.rsi?.toFixed(2)}
            </span>
          </div>
        )}
        {basic.macd && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">MACD</span>
            <span className={basic.macd.histogram > 0 ? 'text-emerald-400' : 'text-red-400'}>
              {basic.macd.histogram?.toFixed(6)}
            </span>
          </div>
        )}
        {basic.bollinger && (
          <div className="text-xs font-mono space-y-0.5">
            <div className="flex justify-between"><span className="text-zinc-500">BB Upper</span><span className="text-zinc-300">{basic.bollinger.upper?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">BB Middle</span><span className="text-zinc-300">{basic.bollinger.middle?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">BB Lower</span><span className="text-zinc-300">{basic.bollinger.lower?.toFixed(2)}</span></div>
          </div>
        )}
        {basic.stochastic && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">Stoch K/D</span>
            <span className="text-white">{basic.stochastic.k?.toFixed(1)} / {basic.stochastic.d?.toFixed(1)}</span>
          </div>
        )}
        {basic.atr !== undefined && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">ATR(14)</span>
            <span className="text-white">{basic.atr?.toFixed(4)}</span>
          </div>
        )}
        {basic.ema_20 !== undefined && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">EMA(20)</span>
            <span className="text-white">{basic.ema_20?.toFixed(2)}</span>
          </div>
        )}
        {basic.sma_50 !== undefined && (
          <div className="flex justify-between items-center text-xs font-mono">
            <span className="text-zinc-400">SMA(50)</span>
            <span className="text-white">{basic.sma_50?.toFixed(2)}</span>
          </div>
        )}
      </div>

      {/* Sniper Score */}
      <div className="border border-zinc-800 p-2 space-y-1">
        <div className="flex items-center gap-1 text-xs font-mono">
          <Lightning size={12} className="text-yellow-400" weight="fill" />
          <span className="text-zinc-400 uppercase tracking-widest text-[10px]">Sniper Score</span>
        </div>
        <div className="flex justify-between text-xs font-mono">
          <span className="text-emerald-400">Bull: {sniper.bull_score || 0}/7</span>
          <span className="text-red-400">Bear: {sniper.bear_score || 0}/7</span>
        </div>
        <div className={`text-center text-xs font-bold font-mono ${
          sniper.bias?.includes('BULL') ? 'text-emerald-400' : sniper.bias?.includes('BEAR') ? 'text-red-400' : 'text-zinc-400'
        }`}>
          {sniper.bias || 'NEUTRAL'}
        </div>
        {/* Progress bars */}
        <div className="flex gap-1 h-1">
          <div className="flex-1 bg-zinc-800 overflow-hidden">
            <div className="h-full bg-emerald-500 transition-all" style={{ width: `${sniper.bull_pct || 0}%` }} />
          </div>
          <div className="flex-1 bg-zinc-800 overflow-hidden">
            <div className="h-full bg-red-500 transition-all float-right" style={{ width: `${sniper.bear_pct || 0}%` }} />
          </div>
        </div>
      </div>

      {/* Confluence Score */}
      <div className="border border-zinc-800 p-2 space-y-1">
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Precision Sniper</div>
        <div className="flex justify-between text-xs font-mono">
          <span className="text-emerald-400">Bull: {confluence.bull_score?.toFixed(1) || 0}/10</span>
          <span className="text-red-400">Bear: {confluence.bear_score?.toFixed(1) || 0}/10</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-zinc-500 font-mono">Grade:</span>
          <span className={`text-xs font-bold font-mono ${
            confluence.grade === 'A+' || confluence.grade === 'A' ? 'text-emerald-400' :
            confluence.grade === 'B' ? 'text-yellow-400' : 'text-red-400'
          }`}>{confluence.grade || 'N/A'}</span>
        </div>
      </div>

      {/* Linear Regression */}
      {lr.line > 0 && (
        <div className="border border-zinc-800 p-2 space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Reg. Lineal</div>
          <div className="text-xs font-mono space-y-0.5">
            <div className="flex justify-between"><span className="text-zinc-400">LR</span><span>{lr.line?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Banda+</span><span>{lr.upper?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Banda-</span><span>{lr.lower?.toFixed(2)}</span></div>
          </div>
        </div>
      )}

      {/* Combined signal */}
      <div className={`border p-2 text-center ${
        data.combined_signal === 'buy' ? 'border-emerald-500/50 bg-emerald-500/10' :
        data.combined_signal === 'sell' ? 'border-red-500/50 bg-red-500/10' :
        'border-zinc-700 bg-zinc-900'
      }`}>
        <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono mb-1">Signal Combinada</div>
        <div className={`text-sm font-bold font-heading uppercase ${
          data.combined_signal === 'buy' ? 'text-emerald-400' :
          data.combined_signal === 'sell' ? 'text-red-400' : 'text-zinc-400'
        }`}>
          <SignalIcon signal={data.combined_signal} />
          {' '}{data.combined_signal?.toUpperCase() || 'NEUTRAL'}
        </div>
        <div className="text-[10px] text-zinc-500 font-mono">
          Fuerza: {((data.signal_strength || 0) * 100).toFixed(0)}%
        </div>
      </div>

      {/* Ichimoku */}
      {data.ichimoku && (
        <div className="border border-zinc-800 p-2 space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Ichimoku</div>
          <div className="text-xs font-mono space-y-0.5">
            <div className="flex justify-between"><span className="text-zinc-400">Tenkan</span><span>{data.ichimoku.tenkan?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Kijun</span><span>{data.ichimoku.kijun?.toFixed(2)}</span></div>
            <div className="flex justify-between">
              <span className="text-zinc-400">Cloud</span>
              <span className={data.ichimoku.above_cloud ? 'text-emerald-400' : data.ichimoku.below_cloud ? 'text-red-400' : 'text-yellow-400'}>
                {data.ichimoku.above_cloud ? 'ABOVE' : data.ichimoku.below_cloud ? 'BELOW' : 'INSIDE'}
              </span>
            </div>
          </div>
          {(data.ichimoku.tk_cross_bull || data.ichimoku.tk_cross_bear) && (
            <div className={`text-[10px] font-mono font-bold ${data.ichimoku.tk_cross_bull ? 'text-emerald-400' : 'text-red-400'}`}>
              TK Cross: {data.ichimoku.tk_cross_bull ? 'BULLISH' : 'BEARISH'}
            </div>
          )}
        </div>
      )}

      {/* NeuroTrend */}
      {data.neurotrend && (
        <div className="border border-zinc-800 p-2 space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">NeuroTrend II</div>
          <div className={`text-xs font-mono font-bold ${
            data.neurotrend.trend_direction === 'Bullish' ? 'text-emerald-400' : 'text-red-400'
          }`}>{data.neurotrend.trend_direction} - {data.neurotrend.phase}</div>
          <div className="flex justify-between text-[10px] font-mono">
            <span className="text-zinc-400">Confianza</span>
            <span className="text-white">{data.neurotrend.confidence}%</span>
          </div>
          <div className="flex justify-between text-[10px] font-mono">
            <span className="text-zinc-400">Slope Power</span>
            <span className={data.neurotrend.slope_power > 0 ? 'text-emerald-400' : 'text-red-400'}>{data.neurotrend.slope_power}</span>
          </div>
        </div>
      )}

      {/* SuperTrend RSI */}
      {data.supertrend_rsi && (
        <div className="border border-zinc-800 p-2 space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">SuperTrend RSI</div>
          <div className="flex justify-between text-xs font-mono">
            <span className="text-zinc-400">RSI</span>
            <span className={data.supertrend_rsi.overbought ? 'text-red-400' : data.supertrend_rsi.oversold ? 'text-emerald-400' : 'text-white'}>
              {data.supertrend_rsi.rsi}
            </span>
          </div>
          <div className={`text-[10px] font-mono font-bold ${
            data.supertrend_rsi.trend === 'bullish' ? 'text-emerald-400' : 'text-red-400'
          }`}>{data.supertrend_rsi.trend?.toUpperCase()}</div>
        </div>
      )}

      {/* Turtle Channels */}
      {data.turtle_channels && (
        <div className="border border-zinc-800 p-2 space-y-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-mono">Turtle Channels</div>
          <div className="text-xs font-mono space-y-0.5">
            <div className="flex justify-between"><span className="text-zinc-400">Upper</span><span>{data.turtle_channels.upper_channel?.toFixed(2)}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Lower</span><span>{data.turtle_channels.lower_channel?.toFixed(2)}</span></div>
          </div>
          {data.turtle_channels.signal !== 'neutral' && (
            <div className={`text-[10px] font-mono font-bold ${
              data.turtle_channels.signal === 'buy' ? 'text-emerald-400' : 'text-red-400'
            }`}>Signal: {data.turtle_channels.signal?.toUpperCase()}</div>
          )}
        </div>
      )}
    </div>
  );
}
