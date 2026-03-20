import { motion } from 'framer-motion';
import { Activity, Cpu, BarChart3, Wallet } from 'lucide-react';
import { useStatus } from '../hooks/useApi';

export default function StatusBar() {
  const { data, loading } = useStatus();

  if (loading || !data) {
    return (
      <motion.div
        className="status-bar shimmer"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ height: 56 }}
      />
    );
  }

  const isLive = data.mode?.toUpperCase() === 'LIVE';

  return (
    <motion.div
      className="status-bar"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: 'easeOut' }}
    >
      <div className="status-item">
        <span className={`status-dot ${data.status === 'running' ? 'online' : 'offline'}`} />
        <span className="status-value" style={{ textTransform: 'capitalize' }}>
          {data.status || 'Unknown'}
        </span>
        <span className={`badge ${isLive ? 'badge-live' : 'badge-dry'}`}>
          {isLive ? 'LIVE' : 'DRY RUN'}
        </span>
      </div>

      <div className="status-item">
        <Cpu size={15} style={{ color: 'var(--cyan)', opacity: 0.7 }} />
        <span className="status-label">Models</span>
        <span className="status-value">{data.models ?? '—'}</span>
      </div>

      <div className="status-item">
        <BarChart3 size={15} style={{ color: 'var(--cyan)', opacity: 0.7 }} />
        <span className="status-label">Trades</span>
        <span className="status-value">{data.total_trades ?? 0}</span>
      </div>

      <div className="status-item">
        <Activity size={15} style={{ color: 'var(--cyan)', opacity: 0.7 }} />
        <span className="status-label">Min Edge</span>
        <span className="status-value">{data.min_edge != null ? `${(data.min_edge * 100).toFixed(1)}%` : '—'}</span>
      </div>

      <div className="status-item">
        <Wallet size={15} style={{ color: 'var(--cyan)', opacity: 0.7 }} />
        <span className="status-label">Bankroll</span>
        <span className="status-value">${data.bankroll != null ? Number(data.bankroll).toFixed(2) : '—'}</span>
      </div>
    </motion.div>
  );
}
