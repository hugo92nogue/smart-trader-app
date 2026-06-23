import React, { useState } from 'react';
import { MagnifyingGlass, TrendUp, TrendDown } from '@phosphor-icons/react';

export default function PairSelector({ pairs, stocks, market = 'crypto', selectedPair, onSelect, searchQuery, onSearchChange }) {
  // Pestaña local de navegación: arranca en el mercado activo pero permite explorar
  // el otro sin cambiar el gráfico hasta que el usuario elige un símbolo.
  const [tab, setTab] = useState(market);
  const isStocks = tab === 'stocks';
  const q = (searchQuery || '').toLowerCase();

  const filteredPairs = (pairs || []).filter(p => p.symbol?.toLowerCase().includes(q));
  const filteredStocks = (stocks || []).filter(s =>
    s.symbol?.toLowerCase().includes(q) || s.name?.toLowerCase().includes(q)
  );

  return (
    <div data-testid="pair-selector" className="border border-zinc-800 bg-zinc-950">
      {/* Toggle de mercado: Cripto / Acciones EEUU */}
      <div className="flex border-b border-zinc-800">
        {[
          { id: 'crypto', label: '₿ Cripto' },
          { id: 'stocks', label: '📈 Acciones EEUU' },
        ].map(m => (
          <button
            key={m.id}
            data-testid={`market-${m.id}`}
            onClick={() => setTab(m.id)}
            className={`flex-1 px-2 py-1.5 text-[10px] font-mono font-bold uppercase tracking-wider transition-colors ${
              tab === m.id ? 'bg-zinc-800 text-cyan-400' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="flex items-center border-b border-zinc-800 px-2">
        <MagnifyingGlass size={12} className="text-zinc-500" />
        <input
          data-testid="pair-search-input"
          type="text"
          placeholder={isStocks ? 'Buscar acción...' : 'Buscar par...'}
          value={searchQuery || ''}
          onChange={(e) => onSearchChange && onSearchChange(e.target.value)}
          className="w-full bg-transparent text-xs font-mono text-white px-2 py-2 focus:outline-none placeholder:text-zinc-600"
        />
      </div>

      {/* Lista */}
      <div className="overflow-y-auto max-h-[300px]">
        {isStocks ? (
          filteredStocks.map(stock => (
            <button
              key={stock.symbol}
              data-testid={`stock-${stock.symbol}`}
              onClick={() => onSelect && onSelect(stock.symbol, 'stocks')}
              className={`w-full flex items-center justify-between px-2 py-1.5 border-b border-zinc-800/30 transition-colors hover:bg-zinc-900 ${
                selectedPair === stock.symbol ? 'bg-zinc-800/50' : ''
              }`}
            >
              <span className="text-xs font-mono font-bold text-white">{stock.symbol}</span>
              <span className="text-[10px] font-mono text-zinc-500 truncate ml-2">{stock.name}</span>
            </button>
          ))
        ) : (
          filteredPairs.slice(0, 30).map(pair => (
            <button
              key={pair.symbol}
              data-testid={`pair-${pair.symbol}`}
              onClick={() => onSelect && onSelect(pair.symbol, 'crypto')}
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
          ))
        )}
      </div>
    </div>
  );
}
