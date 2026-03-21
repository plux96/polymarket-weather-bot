import { motion, AnimatePresence } from 'framer-motion';
import { Trophy } from 'lucide-react';
import { useResults } from '../hooks/useApi';

function formatDate(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
      ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
}

export default function ResultsCard() {
  const { data, loading } = useResults();
  const results = Array.isArray(data) ? [...data].reverse() : [];

  const wins   = results.filter(r => r.won).length;
  const losses = results.filter(r => !r.won).length;
  const totalPnl = results.reduce((s, r) => s + (r.pnl || 0), 0);
  const winRate = results.length ? (wins / results.length * 100).toFixed(0) : 0;

  return (
    <motion.div
      className="glass-card col-12"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
    >
      <div className="card-header">
        <Trophy size={18} className="icon" />
        <span className="card-title">Resolved Trades</span>
        {results.length > 0 && (
          <div style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
            <span style={{ color: 'var(--green)' }}>W: {wins}</span>
            <span style={{ color: 'var(--red, #ff4d4d)' }}>L: {losses}</span>
            <span style={{ color: winRate >= 50 ? 'var(--green)' : '#ff4d4d' }}>WR: {winRate}%</span>
            <span style={{ color: totalPnl >= 0 ? 'var(--green)' : '#ff4d4d', fontWeight: 600 }}>
              P&L: {totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}
            </span>
          </div>
        )}
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 200, borderRadius: 8 }} />
      ) : results.length === 0 ? (
        <div className="empty-state">
          <Trophy size={24} style={{ opacity: 0.3 }} />
          <span>No resolved trades yet</span>
        </div>
      ) : (
        <div className="trades-table-wrapper">
          <table className="trades-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>City</th>
                <th>Question</th>
                <th>Side</th>
                <th>Edge</th>
                <th>Bet</th>
                <th>Outcome</th>
                <th>Result</th>
                <th>P&L</th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence mode="popLayout">
                {results.map((r, i) => {
                  const t = r.trade || {};
                  const unit = t.unit || 'C';
                  const tl = t.temp_low;
                  const th = t.temp_high;
                  let temp = '—';
                  if (tl === -999) temp = `≤${th - 1}°${unit}`;
                  else if (th === 999) temp = `≥${tl}°${unit}`;
                  else if (tl != null && th != null) temp = `${tl}-${th - 1}°${unit}`;

                  return (
                    <motion.tr
                      key={r.market_id || i}
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.25, delay: i * 0.02 }}
                      layout
                      style={{ cursor: t.condition_id ? 'pointer' : 'default' }}
                      onClick={async () => {
                        if (!t.market_id) return;
                        const tab = window.open('', '_blank');
                        try {
                          const res = await fetch(`/api/market-url/${t.market_id}`);
                          const d = await res.json();
                          if (d.slug && tab) tab.location.href = `https://polymarket.com/event/${d.slug}`;
                          else if (tab) tab.close();
                        } catch { if (tab) tab.close(); }
                      }}
                    >
                      <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                        {formatDate(r.checked_at)}
                      </td>
                      <td style={{ fontWeight: 500 }}>{t.city || '—'}</td>
                      <td style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', maxWidth: 180 }}>
                        {temp}
                      </td>
                      <td>
                        <span className={`trade-side ${(t.side || '').toLowerCase()}`}>{t.side}</span>
                      </td>
                      <td style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>
                        {t.edge != null ? `${(t.edge * 100).toFixed(0)}%` : '—'}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)' }}>
                        ${(t.bet_size || 0).toFixed(2)}
                      </td>
                      <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                        {r.outcome || '—'}
                      </td>
                      <td>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: 4,
                          fontSize: '0.7rem',
                          fontWeight: 700,
                          background: r.won ? 'rgba(0,255,136,0.15)' : 'rgba(255,77,77,0.15)',
                          color: r.won ? 'var(--green)' : '#ff4d4d',
                        }}>
                          {r.won ? 'WIN' : 'LOSS'}
                        </span>
                      </td>
                      <td style={{
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        color: r.pnl >= 0 ? 'var(--green)' : '#ff4d4d',
                      }}>
                        {r.pnl >= 0 ? '+' : ''}${(r.pnl || 0).toFixed(2)}
                      </td>
                    </motion.tr>
                  );
                })}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
