import React from 'react';
import { ArrowUp, ArrowDown } from '@phosphor-icons/react';

export default function TradeHistory({ trades }) {
  if (!trades || trades.length === 0) {
    return (
      <div data-testid="trade-history" className="p-3">
        <h3 className="cs-title pb-2">
          Historial de Operaciones
        </h3>
        <p className="text-zinc-600 text-xs font-mono text-center py-4">Sin operaciones registradas</p>
      </div>
    );
  }

  return (
    <div data-testid="trade-history" className="p-3">
      <h3 className="cs-title pb-2">
        Historial de Operaciones
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-mono">
              <th className="text-left pb-2 pr-3">Par</th>
              <th className="text-left pb-2 pr-3">Lado</th>
              <th className="text-left pb-2 pr-3">Tipo</th>
              <th className="text-right pb-2 pr-3">Cantidad</th>
              <th className="text-right pb-2 pr-3">Precio</th>
              <th className="text-right pb-2 pr-3">Total</th>
              <th className="text-left pb-2 pr-3">Estado</th>
              <th className="text-left pb-2 pr-3">Modo</th>
              <th className="text-right pb-2">Fecha</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade, i) => {
              const total = (trade.quantity * (trade.executed_price || trade.price || 0)).toFixed(2);
              const date = trade.timestamp ? new Date(trade.timestamp).toLocaleString('es-ES', {
                month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
              }) : '';
              
              return (
                <tr key={trade.id || `${trade.symbol}-${trade.timestamp}-${i}`} data-testid={`trade-row-${i}`} className="border-t border-zinc-800/50 hover:bg-zinc-900/50 transition-colors">
                  <td className="py-1.5 pr-3 text-xs font-mono font-bold text-white">{trade.symbol}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`inline-flex items-center gap-0.5 text-[10px] font-mono font-bold uppercase ${
                      trade.side === 'buy' ? 'text-emerald-400' : 'text-red-400'
                    }`}>
                      {trade.side === 'buy' ? <ArrowUp size={10} weight="bold" /> : <ArrowDown size={10} weight="bold" />}
                      {trade.side}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-[10px] font-mono text-zinc-400 uppercase">{trade.order_type}</td>
                  <td className="py-1.5 pr-3 text-xs font-mono text-right text-zinc-300">{trade.quantity?.toFixed(6)}</td>
                  <td className="py-1.5 pr-3 text-xs font-mono text-right text-white">${(trade.executed_price || trade.price || 0).toFixed(2)}</td>
                  <td className="py-1.5 pr-3 text-xs font-mono text-right text-zinc-300">${total}</td>
                  <td className="py-1.5 pr-3">
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 ${
                      trade.status?.includes('FILLED') ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' :
                      trade.status === 'CANCELED' ? 'bg-red-500/10 text-red-400 border border-red-500/30' :
                      'bg-zinc-800 text-zinc-400 border border-zinc-700'
                    }`}>
                      {trade.status}
                    </span>
                  </td>
                  <td className="py-1.5 pr-3 text-[10px] font-mono text-zinc-500 uppercase">{trade.mode}</td>
                  <td className="py-1.5 text-[10px] font-mono text-right text-zinc-500">{date}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
