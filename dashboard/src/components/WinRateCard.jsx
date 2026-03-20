import { motion, useMotionValue, useTransform, animate } from 'framer-motion';
import { useEffect } from 'react';
import { Target } from 'lucide-react';
import { usePnl } from '../hooks/useApi';

function AnimatedRing({ percentage }) {
  const radius = 70;
  const stroke = 8;
  const circumference = 2 * Math.PI * radius;
  const mv = useMotionValue(circumference);
  const dashOffset = useTransform(mv, v => v);

  useEffect(() => {
    const target = circumference - (percentage / 100) * circumference;
    animate(mv, target, { duration: 1.5, ease: 'easeOut' });
  }, [percentage, circumference, mv]);

  const color = percentage >= 55 ? 'var(--green)' : percentage >= 45 ? 'var(--cyan)' : 'var(--red)';

  return (
    <svg width="170" height="170" viewBox="0 0 170 170" className="ring-svg">
      <circle cx="85" cy="85" r={radius} className="ring-bg" strokeWidth={stroke} />
      <motion.circle
        cx="85"
        cy="85"
        r={radius}
        className="ring-progress"
        strokeWidth={stroke}
        stroke={color}
        strokeDasharray={circumference}
        style={{ strokeDashoffset: dashOffset }}
        transform="rotate(-90 85 85)"
      />
      <text x="85" y="80" textAnchor="middle" className="ring-text">
        {percentage.toFixed(1)}%
      </text>
      <text x="85" y="100" textAnchor="middle" className="ring-label">
        Win Rate
      </text>
    </svg>
  );
}

export default function WinRateCard() {
  const { data, loading } = usePnl();

  const wins = data?.wins ?? 0;
  const losses = data?.losses ?? 0;
  const pending = data?.pending ?? 0;
  const winRate = data?.win_rate != null ? data.win_rate * 100 : 0;

  return (
    <motion.div
      className="glass-card col-4"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.2 }}
    >
      <div className="card-header">
        <Target size={18} className="icon" />
        <span className="card-title">Win Rate</span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 170, borderRadius: 8 }} />
      ) : (
        <div className="ring-container">
          <AnimatedRing percentage={winRate} />
          <div className="wl-stats">
            <div className="wl-stat">
              <div className="wl-count" style={{ color: 'var(--green)' }}>{wins}</div>
              <div className="wl-label">Wins</div>
            </div>
            <div className="wl-stat">
              <div className="wl-count" style={{ color: 'var(--red)' }}>{losses}</div>
              <div className="wl-label">Losses</div>
            </div>
            {pending > 0 && (
              <div className="wl-stat">
                <div className="wl-count" style={{ color: 'var(--yellow)' }}>{pending}</div>
                <div className="wl-label">Pending</div>
              </div>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}
