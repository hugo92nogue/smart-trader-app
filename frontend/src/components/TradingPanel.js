import React, { useState } from 'react';
import { ArrowUp, ArrowDown, Robot, Rocket } from '@phosphor-icons/react';
import { placeOrder, placeFuturesOrder } from '../api';

export default function TradingPanel({ symbol, price, balance, onOrderPlaced }) {
  const [side, setSide] = useState('buy');
  const [orderType, setOrderType] = useState('market');
  const [market, setMarket] = useState('spot'); // spot | futures
  const [futuresSide, setFuturesSide] = useState('long'); // long | short
  const [quantity, setQuantity] = useState('');
  const [limitPrice, setLimitPrice] = useState('');
  const [leverage, setLeverage] = useState(5);
  const [mode, setMode] = useState('semi_auto');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!quantity || parseFloat(quantity) <= 0) return;
    setLoading(true);
    try {
      if (market === 'futures') {
        await placeFuturesOrder({
          symbol, side: futuresSide, action: 'open',
          quantity: parseFloat(quantity), leverage
        });
      } else {
        await placeOrder({
          symbol, side, order_type: orderType,
          quantity: parseFloat(quantity),
          price: orderType === 'limit' ? parseFloat(limitPrice) : price,
          mode
        });
      }
      if (onOrderPlaced) onOrderPlaced();
      setQuantity('');
    } catch (e) {
      console.error('Order error:', e);
    }
    setLoading(false);
  };

  const estimatedTotal = price && quantity ? (price * parseFloat(quantity || 0)).toFixed(2) : '0.00';
  const commission = price && quantity ? (price * parseFloat(quantity || 0) * 0.001).toFixed(4) : '0.00';

  return (
    <div data-testid="trading-panel" className="p-3 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="font-heading font-bold text-xs uppercase tracking-[0.2em] text-zinc-500">Trading</h3>
        <div className="flex items-center gap-1">
          <Robot size={12} className="text-purple-400" />
          <select data-testid="trading-mode-select" value={mode} onChange={(e) => setMode(e.target.value)}
            className="bg-zinc-900 border border-zinc-800 text-zinc-300 text-[10px] font-mono px-1 py-0.5 focus:outline-none focus:border-zinc-600">
            <option value="auto">AUTO</option>
            <option value="semi_auto">SEMI-AUTO</option>
            <option value="manual">MANUAL</option>
          </select>
        </div>
      </div>

      {/* Market type: Spot / Futures */}
      <div className="grid grid-cols-2 gap-1">
        <button data-testid="market-spot" onClick={() => setMarket('spot')}
          className={`py-1.5 text-[10px] font-mono uppercase tracking-wider border transition-colors ${
            market === 'spot' ? 'bg-[#007AFF]/20 text-[#007AFF] border-[#007AFF]/50' : 'bg-zinc-900 text-zinc-500 border-zinc-800'
          }`}>SPOT</button>
        <button data-testid="market-futures" onClick={() => setMarket('futures')}
          className={`py-1.5 text-[10px] font-mono uppercase tracking-wider border transition-colors flex items-center justify-center gap-1 ${
            market === 'futures' ? 'bg-purple-500/20 text-purple-400 border-purple-500/50' : 'bg-zinc-900 text-zinc-500 border-zinc-800'
          }`}><Rocket size={10} /> FUTUROS</button>
      </div>

      {/* Buy/Sell or Long/Short */}
      {market === 'spot' ? (
        <div className="grid grid-cols-2 gap-1">
          <button data-testid="buy-button" onClick={() => setSide('buy')}
            className={`py-2 text-xs font-bold font-mono uppercase tracking-wider transition-colors ${
              side === 'buy' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-zinc-900 text-zinc-500 border border-zinc-800 hover:bg-zinc-800'
            }`}><ArrowUp size={12} weight="bold" className="inline mr-1" />BUY</button>
          <button data-testid="sell-button" onClick={() => setSide('sell')}
            className={`py-2 text-xs font-bold font-mono uppercase tracking-wider transition-colors ${
              side === 'sell' ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-zinc-900 text-zinc-500 border border-zinc-800 hover:bg-zinc-800'
            }`}><ArrowDown size={12} weight="bold" className="inline mr-1" />SELL</button>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-1">
          <button data-testid="long-button" onClick={() => setFuturesSide('long')}
            className={`py-2 text-xs font-bold font-mono uppercase tracking-wider transition-colors ${
              futuresSide === 'long' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50' : 'bg-zinc-900 text-zinc-500 border border-zinc-800'
            }`}><ArrowUp size={12} weight="bold" className="inline mr-1" />LONG</button>
          <button data-testid="short-button" onClick={() => setFuturesSide('short')}
            className={`py-2 text-xs font-bold font-mono uppercase tracking-wider transition-colors ${
              futuresSide === 'short' ? 'bg-red-500/20 text-red-400 border border-red-500/50' : 'bg-zinc-900 text-zinc-500 border border-zinc-800'
            }`}><ArrowDown size={12} weight="bold" className="inline mr-1" />SHORT</button>
        </div>
      )}

      {/* Leverage (futures only) */}
      {market === 'futures' && (
        <div>
          <label className="text-[10px] text-zinc-500 font-mono uppercase">Apalancamiento: {leverage}x</label>
          <div className="flex gap-1 mt-1">
            {[1, 2, 5, 10, 20, 50].map(lev => (
              <button key={lev} data-testid={`leverage-${lev}`} onClick={() => setLeverage(lev)}
                className={`flex-1 py-1 text-[9px] font-mono border transition-colors ${
                  leverage === lev ? 'bg-purple-500/20 text-purple-400 border-purple-500/50' : 'text-zinc-500 border-zinc-800 hover:bg-zinc-800'
                }`}>{lev}x</button>
            ))}
          </div>
        </div>
      )}

      {/* Order Type (spot only) */}
      {market === 'spot' && (
        <div className="flex gap-1">
          {['market', 'limit'].map(t => (
            <button key={t} data-testid={`order-type-${t}`} onClick={() => setOrderType(t)}
              className={`flex-1 py-1 text-[10px] font-mono uppercase tracking-wider border transition-colors ${
                orderType === t ? 'bg-zinc-800 text-white border-zinc-600' : 'bg-transparent text-zinc-500 border-zinc-800'
              }`}>{t}</button>
          ))}
        </div>
      )}

      {/* Price */}
      <div className="bg-zinc-950 border border-zinc-800 p-2">
        <div className="text-[10px] text-zinc-500 font-mono uppercase">Precio</div>
        <div className="text-sm font-mono font-bold text-white">${price?.toFixed(2) || '---'}</div>
      </div>

      {/* Limit Price */}
      {market === 'spot' && orderType === 'limit' && (
        <div>
          <label className="text-[10px] text-zinc-500 font-mono uppercase">Precio Limite</label>
          <input data-testid="limit-price-input" type="number" value={limitPrice} onChange={(e) => setLimitPrice(e.target.value)}
            placeholder="0.00" className="w-full bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-zinc-600" />
        </div>
      )}

      {/* Quantity */}
      <div>
        <label className="text-[10px] text-zinc-500 font-mono uppercase">Cantidad</label>
        <input data-testid="quantity-input" type="number" value={quantity} onChange={(e) => setQuantity(e.target.value)}
          placeholder="0.00" className="w-full bg-zinc-950 border border-zinc-800 px-2 py-1.5 text-xs font-mono text-white focus:outline-none focus:border-zinc-600" />
        <div className="flex gap-1 mt-1">
          {[25, 50, 75, 100].map(pct => (
            <button key={pct} data-testid={`qty-${pct}-btn`}
              onClick={() => {
                if (balance && price) {
                  const usdtBal = balance?.USDT?.free || 10000;
                  const effectiveBal = market === 'futures' ? usdtBal * leverage : usdtBal;
                  setQuantity(((effectiveBal * pct / 100) / price).toFixed(6));
                }
              }}
              className="flex-1 py-0.5 text-[9px] font-mono text-zinc-500 border border-zinc-800 hover:bg-zinc-800 transition-colors"
            >{pct}%</button>
          ))}
        </div>
      </div>

      {/* Totals */}
      <div className="space-y-1 text-[10px] font-mono">
        <div className="flex justify-between text-zinc-400">
          <span>Total Estimado</span>
          <span className="text-white">${estimatedTotal}</span>
        </div>
        {market === 'futures' && (
          <div className="flex justify-between text-zinc-400">
            <span>Margen Requerido</span>
            <span className="text-purple-400">${(parseFloat(estimatedTotal) / leverage).toFixed(2)}</span>
          </div>
        )}
        <div className="flex justify-between text-zinc-500">
          <span>Comision (0.1%)</span>
          <span className="text-yellow-400">${commission}</span>
        </div>
      </div>

      {/* Submit */}
      <button data-testid="place-order-btn" onClick={handleSubmit} disabled={loading || !quantity}
        className={`w-full py-2.5 text-xs font-bold font-mono uppercase tracking-wider transition-colors disabled:opacity-30 ${
          market === 'futures'
            ? futuresSide === 'long'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30'
            : side === 'buy'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 hover:bg-emerald-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/50 hover:bg-red-500/30'
        }`}>
        {loading ? 'PROCESANDO...' : market === 'futures'
          ? `${futuresSide === 'long' ? 'ABRIR LONG' : 'ABRIR SHORT'} ${leverage}x ${symbol?.replace('USDT','') || ''}`
          : `${side === 'buy' ? 'COMPRAR' : 'VENDER'} ${symbol?.replace('USDT','') || ''}`
        }
      </button>

      {/* Balance */}
      <div className="border border-zinc-800 p-2 space-y-1">
        <div className="text-[10px] text-zinc-500 font-mono uppercase tracking-widest">Balance {market === 'futures' ? '(Futuros)' : '(Spot)'}</div>
        <div className="flex justify-between text-xs font-mono">
          <span className="text-zinc-400">USDT</span>
          <span className="text-white">{(balance?.USDT?.free || 10000).toFixed(2)}</span>
        </div>
        <div className="flex justify-between text-xs font-mono">
          <span className="text-zinc-400">BTC</span>
          <span className="text-white">{(balance?.BTC?.free || 0.5).toFixed(6)}</span>
        </div>
      </div>
    </div>
  );
}
