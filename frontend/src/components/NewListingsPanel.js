import React from 'react';
import { Rocket, Star } from '@phosphor-icons/react';

export default function NewListingsPanel({ listings }) {
  return (
    <div data-testid="new-listings-panel" className="p-3 space-y-2">
      <div className="flex items-center gap-2">
        <Rocket size={14} className="text-cyan-400" weight="fill" />
        <h3 className="cs-title">
          Nuevos Lanzamientos
        </h3>
      </div>
      
      {(!listings || listings.length === 0) ? (
        <div className="text-center py-4">
          <Star size={20} className="text-zinc-700 mx-auto mb-2" />
          <p className="text-zinc-600 text-[10px] font-mono">Monitoreando nuevos listings...</p>
          <p className="text-zinc-700 text-[9px] font-mono mt-1">Se notificara cuando se detecten</p>
        </div>
      ) : (
        <div className="space-y-1">
          {listings.map((listing) => (
            <div key={listing.symbol || listing.id} data-testid={`listing-${listing.symbol}`} className="border border-cyan-500/20 bg-cyan-500/5 p-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-cyan-400">{listing.symbol}</span>
                <span className="text-[9px] font-mono text-zinc-500">
                  {listing.detected_at ? new Date(listing.detected_at).toLocaleTimeString() : ''}
                </span>
              </div>
              <div className="text-[10px] font-mono text-zinc-500 mt-0.5">
                {listing.base_asset}/{listing.quote_asset}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
