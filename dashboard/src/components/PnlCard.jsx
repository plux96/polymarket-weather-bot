import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { usePnl } from '../hooks/useApi';

function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 2 }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);
  const startRef = useRef(0);
  const startTimeRef = useRef(null);

  useEffect(() => {
    startRef.current = display;
    startTimeRef.current = null;
    const duration = 800;

    function step(ts) {
      if (!startTimeRef.current) startTimeRef.current = ts;
      const elapsed = ts - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(startRef.current + (value - startRef.current) * eased);
      if (progress < 1) rafRef.current = requestAnimationFrame(step);
    }

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [value]);

  return (
    <span>
      {prefix}{display.toFixed(decimals)}{suffix}
    </span>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <div className="label">{label}</div>
      <div className="value" style={{ color: payload[0].value >= 0 ? 'var(--green)' : 'var(--red)' }}>
        ${payload[0].value?.toFixed(2)}
      </div>
    </div>
  );
}

export default function PnlCard() {
  const { data, loading } = usePnl();

  const totalPnl = data?.total_pnl ?? 0;
  const roi = data?.roi ?? 0;
  const totalBet = data?.total_bet ?? 0;
  const isPositive = totalPnl >= 0;

  const chartData = (data?.daily || []).map(d => ({
    date: d.date?.slice(5) || '',
    pnl: d.pnl,
  }));

  return (
    <motion.div
      className="glass-card col-4"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.1 }}
    >
      <div className="card-header">
        {isPositive ? <TrendingUp size={18} className="icon" /> : <TrendingDown size={18} style={{ color: 'var(--red)' }} />}
        <span className="card-title">Total P&L</span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 48, borderRadius: 8 }} />
      ) : (
        <>
          <div className={`big-number ${isPositive ? 'positive' : 'negative'}`}>
            <AnimatedNumber value={totalPnl} prefix={isPositive ? '+$' : '-$'} decimals={2} />
          </div>
          <div className="sub-metric" style={{ display: 'flex', gap: 16, marginTop: 8 }}>
            <span style={{ color: isPositive ? 'var(--green)' : 'var(--red)' }}>
              ROI {roi >= 0 ? '+' : ''}{(roi * 100).toFixed(1)}%
            </span>
            <span>Wagered ${totalBet.toFixed(2)}</span>
          </div>
        </>
      )}

      {chartData.length > 0 && (
        <div style={{ marginTop: 20, height: 140 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={isPositive ? '#00ff88' : '#ff4757'} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={isPositive ? '#00ff88' : '#ff4757'} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="pnl"
                stroke={isPositive ? '#00ff88' : '#ff4757'}
                strokeWidth={2}
                fill="url(#pnlGrad)"
                animationDuration={1200}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}
