import React from 'react';
import { MagnifyingGlass, CaretDown, TrendUp, TrendDown } from '@phosphor-icons/react';

export default function PairSelector({ pairs, selectedPair, onSelect, searchQuery, onSearchChange }) {
  const filteredPairs = (pairs || []).filter(p =>
    p.symbol?.toLowerCase().includes((searchQuery || '').toLowerCase())
  );

  return (
    <div data-testid="pair-selector" className="border border-zinc-800 bg-zinc-950">
      {/* Search */}
      <div className="flex items-center border-b border-zinc-800 px-2">
        <MagnifyingGlass size={12} className="text-zinc-500" />
        <input
          data-testid="pair-search-input"
          type="text"
          placeholder="Buscar par..."
          value={searchQuery || ''}
          onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
          className="w-full bg-transparent text-xs font-mono text-white px-2 py-2 focus:outline-none placeholder:text-zinc-600"
        />
      </div>

      {/* Pairs list */}
      <div className="overflow-y-auto max-h-[300px]">
        {filteredPairs.slice(0, 30).map(pair => (
          <button
            key={pair.symbol}
            data-testid={`pair-${pair.symbol}`}
            onClick={() => onSelect && onSelect(pair.symbol)}
            className={`w-full flex items-center justify-between px-2 py-1.5 border-b border-zinc-800/30 transition-colors hover:bg-zinc-900 ${
              selectedPair === pair.symbol ? 'bg-zinc-800/50' : ''
            }`}
          >
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono font-bold text-white">{pair.symbol?.replace('USDT', '')}</span>
              <span className="text-[9px] text-zinc-600 font-mono">/USDT</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-zinc-300">${pair.price?.toFixed(pair.price < 1 ? 4 : 2)}</span>
              <span className={`text-[10px] font-mono flex items-center gap-0.5 ${
                pair.change_24h >= 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {pair.change_24h >= 0 ? <TrendUp size={10} /> : <TrendDown size={10} />}
                {pair.change_24h >= 0 ? '+' : ''}{pair.change_24h?.toFixed(2)}%
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
