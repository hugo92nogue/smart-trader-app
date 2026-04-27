import React, { useState, useEffect, useRef } from 'react';
import { Brain, CircleNotch } from '@phosphor-icons/react';
import { fetchAIAnalysis } from '../api';

export default function AITerminal({ symbol, interval }) {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [displayText, setDisplayText] = useState('');
  const [error, setError] = useState(null);
  const textRef = useRef(null);

  const requestAnalysis = async () => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    setDisplayText('');
    try {
      const res = await fetchAIAnalysis(symbol, interval);
      setAnalysis(res.data.data);
      // Typewriter effect
      const text = res.data.data.analysis || '';
      let i = 0;
      const timer = setInterval(() => {
        if (i < text.length) {
          setDisplayText(prev => prev + text[i]);
          i++;
        } else {
          clearInterval(timer);
        }
      }, 8);
      return () => clearInterval(timer);
    } catch (e) {
      setError(e.response?.data?.detail || 'Error en análisis IA');
    }
    setLoading(false);
  };

  useEffect(() => {
    if (textRef.current) {
      textRef.current.scrollTop = textRef.current.scrollHeight;
    }
  }, [displayText, textRef]);

  const recColor = analysis?.recommendation === 'buy' ? 'text-emerald-400' :
                    analysis?.recommendation === 'sell' ? 'text-red-400' : 'text-yellow-400';

  return (
    <div data-testid="ai-terminal" className="border border-zinc-800 bg-zinc-950 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <Brain size={14} className="text-purple-400" weight="fill" />
          <span className="text-[10px] font-mono uppercase tracking-widest text-zinc-400">
            Claude AI Analysis
          </span>
        </div>
        <button
          data-testid="ai-analyze-btn"
          onClick={requestAnalysis}
          disabled={loading || !symbol}
          className="px-2 py-1 text-[10px] font-mono uppercase bg-purple-500/10 text-purple-400 border border-purple-500/30 hover:bg-purple-500/20 transition-colors disabled:opacity-30"
        >
          {loading ? <CircleNotch size={12} className="animate-spin" /> : 'ANALIZAR'}
        </button>
      </div>

      {/* Terminal body */}
      <div ref={textRef} className="flex-1 p-3 overflow-y-auto text-xs font-mono leading-relaxed" style={{ minHeight: '120px', maxHeight: '250px' }}>
        {!analysis && !loading && !error && (
          <div className="text-zinc-600">
            <p className="text-cyan-400/60">&gt; Sistema de Análisis IA listo</p>
            <p className="text-zinc-600">&gt; Selecciona un par y presiona ANALIZAR</p>
            <p className="text-zinc-700">&gt; Claude evaluará indicadores + comisiones_</p>
          </div>
        )}

        {loading && (
          <div className="text-cyan-400">
            <p>&gt; Analizando {symbol}...</p>
            <p>&gt; Procesando indicadores técnicos...</p>
            <p>&gt; Evaluando confluencia de señales...</p>
            <p className="ai-cursor">&gt; Calculando viabilidad con comisiones</p>
          </div>
        )}

        {error && (
          <div className="text-red-400">
            <p>&gt; ERROR: {error}</p>
            <p className="text-zinc-600">&gt; Intenta de nuevo_</p>
          </div>
        )}

        {displayText && (
          <div className="space-y-1">
            {/* Recommendation badge */}
            {analysis && (
              <div className="flex items-center gap-2 mb-2 pb-2 border-b border-zinc-800">
                <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                  analysis.recommendation === 'buy' ? 'border-emerald-500/50 bg-emerald-500/10 text-emerald-400' :
                  analysis.recommendation === 'sell' ? 'border-red-500/50 bg-red-500/10 text-red-400' :
                  'border-yellow-500/50 bg-yellow-500/10 text-yellow-400'
                }`}>
                  {analysis.recommendation?.toUpperCase()}
                </span>
                <span className="text-zinc-500">
                  Confianza: <span className={recColor}>{((analysis.confidence || 0) * 100).toFixed(0)}%</span>
                </span>
              </div>
            )}
            <p className="text-cyan-400/80 whitespace-pre-wrap">{displayText}<span className="ai-cursor" /></p>
          </div>
        )}
      </div>
    </div>
  );
}
