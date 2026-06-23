import React, { useEffect, useRef, useCallback } from 'react';
import { createChart, CandlestickSeries, HistogramSeries } from 'lightweight-charts';

const CHART_OPTIONS = {
  layout: {
    background: { color: '#09090b' },
    textColor: '#a1a1aa',
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: 11,
  },
  grid: {
    vertLines: { color: '#1f1f22' },
    horzLines: { color: '#1f1f22' },
  },
  crosshair: {
    mode: 0,
    vertLine: { color: '#007AFF', width: 1, style: 2, labelBackgroundColor: '#007AFF' },
    horzLine: { color: '#007AFF', width: 1, style: 2, labelBackgroundColor: '#007AFF' },
  },
  rightPriceScale: {
    borderColor: '#27272a',
    scaleMargins: { top: 0.1, bottom: 0.25 },
  },
  timeScale: {
    borderColor: '#27272a',
    timeVisible: true,
    secondsVisible: false,
    tickMarkFormatter: (time) => {
      const date = new Date(time * 1000);
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const mins = String(date.getMinutes()).padStart(2, '0');
      return `${month}/${day} ${hours}:${mins}`;
    },
  },
  handleScroll: { vertTouchDrag: false },
  localization: {
    timeFormatter: (time) => {
      const date = new Date(time * 1000);
      return date.toISOString().replace('T', ' ').substring(0, 16);
    },
  },
};

const CANDLE_OPTIONS = {
  upColor: '#34C759',
  downColor: '#FF3B30',
  borderDownColor: '#FF3B30',
  borderUpColor: '#34C759',
  wickDownColor: '#FF3B30',
  wickUpColor: '#34C759',
};

function formatKlineData(klines) {
  const candleData = klines.map(k => ({
    time: typeof k.time === 'number' ? Math.floor(k.time) : k.time,
    open: k.open,
    high: k.high,
    low: k.low,
    close: k.close,
  }));

  const volumeData = klines.map(k => ({
    time: typeof k.time === 'number' ? Math.floor(k.time) : k.time,
    value: k.volume,
    color: k.close >= k.open ? 'rgba(52, 199, 89, 0.3)' : 'rgba(255, 59, 48, 0.3)',
  }));

  return { candleData, volumeData };
}

export default function PriceChart({ klines, symbol, interval, positions = [] }) {
  const chartRef = useRef(null);
  const containerRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const priceLinesRef = useRef([]);

  const initChart = useCallback(() => {
    if (!containerRef.current) return;

    // Cleanup previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createChart(containerRef.current, CHART_OPTIONS);

    const candleSeries = chart.addSeries(CandlestickSeries, CANDLE_OPTIONS);
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    });

    chart.priceScale('volume').applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, []);

  // Initialize chart on mount
  useEffect(() => {
    const cleanup = initChart();
    return cleanup;
  }, [initChart]);

  // Update data when klines change
  useEffect(() => {
    if (!klines || klines.length === 0 || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const { candleData, volumeData } = formatKlineData(klines);
    candleSeriesRef.current.setData(candleData);
    volumeSeriesRef.current.setData(volumeData);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [klines]);

  // Dibuja líneas de entrada / stop loss / take profit de las posiciones del activo.
  useEffect(() => {
    const series = candleSeriesRef.current;
    if (!series) return;

    // Limpia líneas anteriores
    priceLinesRef.current.forEach((line) => {
      try { series.removePriceLine(line); } catch (_) {}
    });
    priceLinesRef.current = [];

    positions.forEach((p) => {
      const isBuy = p.side === 'buy';
      const sideTxt = isBuy ? 'LONG' : 'SHORT';
      const add = (price, color, title) => {
        if (price == null) return;
        const line = series.createPriceLine({
          price, color, lineWidth: 1, lineStyle: 2,
          axisLabelVisible: true, title,
        });
        priceLinesRef.current.push(line);
      };
      add(p.entry_price, isBuy ? '#34C759' : '#FF3B30', `ENTRADA ${sideTxt}`);
      add(p.stop_loss, '#f59e0b', 'STOP LOSS');
      add(p.take_profit_1, '#06b6d4', 'TAKE PROFIT');
    });
  }, [positions, klines]);

  return (
    <div data-testid="price-chart" className="w-full h-full relative">
      <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
        <span className="font-heading font-bold text-white text-sm">{symbol}</span>
        <span className="text-zinc-500 text-xs font-mono">{interval}</span>
      </div>
      <div ref={containerRef} className="w-full h-full" style={{ minHeight: '400px' }} />
    </div>
  );
}
