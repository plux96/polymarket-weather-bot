import { motion, AnimatePresence } from 'framer-motion';
import { ScrollText } from 'lucide-react';
import { useTrades } from '../hooks/useApi';

function formatTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return ts;
  }
}

export default function TradesCard() {
  const { data, loading } = useTrades();
  const trades = Array.isArray(data) ? data.slice(0, 20) : [];

  return (
    <motion.div
      className="glass-card col-8"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.5 }}
    >
      <div className="card-header">
        <ScrollText size={18} className="icon" />
        <span className="card-title">Recent Trades</span>
        {trades.length > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.7rem',
            color: 'var(--text-secondary)',
            fontFamily: 'var(--font-mono)',
          }}>
            Last {trades.length}
          </span>
        )}
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 300, borderRadius: 8 }} />
      ) : trades.length === 0 ? (
        <div className="empty-state">
          <ScrollText size={24} style={{ opacity: 0.3 }} />
          <span>No trades yet</span>
        </div>
      ) : (
        <div className="trades-table-wrapper">
          <table className="trades-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>City</th>
                <th>Temp</th>
                <th>Side</th>
                <th>Edge</th>
                <th>Bet</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence mode="popLayout">
                {trades.map((t, i) => (
                  <motion.tr
                    key={`${t.timestamp}-${t.city}-${i}`}
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.02 }}
                    layout
                    onClick={async () => {
                      if (!t.condition_id) return;
                      try {
                        const res = await fetch(`https://gamma-api.polymarket.com/markets?conditionId=${t.condition_id}`);
                        const d = await res.json();
                        const eventSlug = d[0]?.events?.[0]?.slug;
                        if (eventSlug) {
                          window.open(`https://polymarket.com/event/${eventSlug}`, '_blank');
                        } else {
                          window.open(`https://polymarket.com`, '_blank');
                        }
                      } catch {
                        window.open(`https://polymarket.com`, '_blank');
                      }
                    }}
                    style={{ cursor: t.condition_id ? 'pointer' : 'default' }}
                  >
                    <td>{formatTime(t.timestamp)}</td>
                    <td style={{ fontFamily: 'var(--font)', fontWeight: 500 }}>{t.city}</td>
                    <td>{t.temp_low}-{t.temp_high}{t.unit || 'F'}</td>
                    <td>
                      <span className={`trade-side ${t.side?.toLowerCase()}`}>{t.side}</span>
                    </td>
                    <td style={{ color: 'var(--cyan)' }}>{(t.edge * 100).toFixed(1)}%</td>
                    <td>${t.bet_size?.toFixed(2)}</td>
                    <td>
                      <span className={t.dry_run ? 'trade-dry' : 'trade-live'}>
                        {t.dry_run ? 'DRY' : 'LIVE'}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
