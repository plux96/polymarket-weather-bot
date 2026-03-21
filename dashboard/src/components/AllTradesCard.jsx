import { useState } from 'react';
import { motion } from 'framer-motion';
import { BarChart2, ChevronLeft, ChevronRight } from 'lucide-react';
import { useState as useS, useEffect, useCallback } from 'react';

function usePaginatedTrades(page, perPage = 20) {
  const [data, setData] = useS(null);
  const [loading, setLoading] = useS(true);

  const fetch_ = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/trades?page=${page}&per_page=${perPage}`);
      const d = await res.json();
      setData(d);
    } catch { /* silent */ }
    setLoading(false);
  }, [page, perPage]);

  useEffect(() => { fetch_(); }, [fetch_]);
  return { data, loading, refetch: fetch_ };
}

function formatDate(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) +
    ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatResolveDate(dateStr) {
  if (!dateStr) return '—';
  const d = new Date(dateStr + 'T12:00:00Z');
  const now = new Date();
  const diffH = (d - now) / 3600000;
  if (diffH < 0) return 'Resolved';
  if (diffH < 24) return `${Math.round(diffH)}h left`;
  return `${Math.round(diffH / 24)}d left`;
}

function TempStr({ t }) {
  const unit = t.unit || 'C';
  const tl = t.temp_low, th = t.temp_high;
  if (tl === -999) return <span>≤{th - 1}°{unit}</span>;
  if (th === 999)  return <span>≥{tl}°{unit}</span>;
  return <span>{tl}-{th - 1}°{unit}</span>;
}

export default function AllTradesCard() {
  const [page, setPage] = useState(1);
  const PER_PAGE = 20;
  const { data, loading } = usePaginatedTrades(page, PER_PAGE);

  const trades = data?.trades || [];
  const total  = data?.total || 0;
  const pages  = data?.pages || 1;

  const totalBet    = trades.reduce((s, t) => s + (t.bet_size || 0), 0);
  const resolved    = trades.filter(t => t.status === 'resolved').length;
  const wins        = trades.filter(t => t.won === true).length;
  const pnl         = trades.reduce((s, t) => s + (t.pnl || 0), 0);

  return (
    <motion.div
      className="glass-card col-12"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
    >
      {/* Header */}
      <div className="card-header">
        <BarChart2 size={18} className="icon" />
        <span className="card-title">All Trades</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 16, fontSize: '0.72rem', fontFamily: 'var(--font-mono)', flexWrap: 'wrap' }}>
          <span style={{ color: 'var(--text-secondary)' }}>Total: <b style={{ color: 'var(--cyan)' }}>{total}</b></span>
          <span style={{ color: 'var(--text-secondary)' }}>Bet: <b style={{ color: 'var(--yellow, #f5c518)' }}>${totalBet.toFixed(2)}</b></span>
          <span style={{ color: 'var(--text-secondary)' }}>Resolved: <b>{resolved}</b></span>
          {wins > 0 && <span style={{ color: 'var(--green)' }}>W: {wins}</span>}
          {pnl !== 0 && (
            <span style={{ color: pnl >= 0 ? 'var(--green)' : '#ff4d4d', fontWeight: 700 }}>
              P&L: {pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}
            </span>
          )}
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="shimmer" style={{ height: 300, borderRadius: 8 }} />
      ) : trades.length === 0 ? (
        <div className="empty-state">
          <BarChart2 size={24} style={{ opacity: 0.3 }} />
          <span>No trades yet</span>
        </div>
      ) : (
        <>
          <div className="trades-table-wrapper">
            <table className="trades-table">
              <thead>
                <tr>
                  <th>Vaqt</th>
                  <th>Shahar</th>
                  <th>Harorat</th>
                  <th>Side</th>
                  <th>Yutish %</th>
                  <th>Edge</th>
                  <th>Quyilgan $</th>
                  <th>Qachon chiqadi</th>
                  <th>Holat</th>
                  <th>Natija</th>
                  <th>P&L</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr
                    key={`${t.market_id}-${i}`}
                    style={{ cursor: t.market_id ? 'pointer' : 'default' }}
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
                    <td style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
                      {formatDate(t.timestamp)}
                    </td>
                    <td style={{ fontWeight: 500 }}>{t.city || '—'}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                      <TempStr t={t} />
                    </td>
                    <td>
                      <span className={`trade-side ${(t.side || '').toLowerCase()}`}>{t.side}</span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)', fontWeight: 600 }}>
                      {t.model_prob != null ? `${(t.model_prob * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>
                      {t.edge != null ? `${(t.edge * 100).toFixed(0)}%` : '—'}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                      ${(t.bet_size || 0).toFixed(2)}
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                      {t.date || '—'} <span style={{ opacity: 0.6 }}>({formatResolveDate(t.date)})</span>
                    </td>
                    <td>
                      <span style={{
                        padding: '2px 7px', borderRadius: 4, fontSize: '0.68rem', fontWeight: 600,
                        background: t.status === 'resolved' ? 'rgba(0,255,136,0.1)' : 'rgba(255,200,0,0.1)',
                        color: t.status === 'resolved' ? 'var(--green)' : '#f5c518',
                      }}>
                        {t.status === 'resolved' ? 'Resolved' : 'Pending'}
                      </span>
                    </td>
                    <td>
                      {t.won !== null && t.won !== undefined ? (
                        <span style={{
                          padding: '2px 7px', borderRadius: 4, fontSize: '0.68rem', fontWeight: 700,
                          background: t.won ? 'rgba(0,255,136,0.15)' : 'rgba(255,77,77,0.15)',
                          color: t.won ? 'var(--green)' : '#ff4d4d',
                        }}>
                          {t.won ? 'WIN' : 'LOSS'}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>
                          {t.outcome || '—'}
                        </span>
                      )}
                    </td>
                    <td style={{
                      fontFamily: 'var(--font-mono)', fontWeight: 700,
                      color: t.pnl == null ? 'var(--text-secondary)' : t.pnl >= 0 ? 'var(--green)' : '#ff4d4d',
                    }}>
                      {t.pnl != null ? `${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 12, padding: '12px 0 4px', fontSize: '0.78rem',
            color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)',
          }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={{
                background: 'none', border: '1px solid rgba(255,255,255,0.1)',
                color: page === 1 ? 'var(--text-secondary)' : 'var(--cyan)',
                borderRadius: 6, cursor: page === 1 ? 'default' : 'pointer',
                padding: '4px 8px', display: 'flex', alignItems: 'center',
              }}
            >
              <ChevronLeft size={14} />
            </button>

            {Array.from({ length: pages }, (_, i) => i + 1)
              .filter(p => p === 1 || p === pages || Math.abs(p - page) <= 2)
              .map((p, idx, arr) => (
                <span key={p}>
                  {idx > 0 && arr[idx - 1] !== p - 1 && <span style={{ opacity: 0.4 }}>…</span>}
                  <button
                    onClick={() => setPage(p)}
                    style={{
                      background: p === page ? 'var(--cyan)' : 'none',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: p === page ? '#000' : 'var(--text-secondary)',
                      borderRadius: 6, cursor: 'pointer',
                      padding: '4px 10px', fontFamily: 'var(--font-mono)',
                      fontSize: '0.75rem', fontWeight: p === page ? 700 : 400,
                      marginLeft: idx > 0 && arr[idx - 1] !== p - 1 ? 4 : 0,
                    }}
                  >
                    {p}
                  </button>
                </span>
              ))}

            <button
              onClick={() => setPage(p => Math.min(pages, p + 1))}
              disabled={page === pages}
              style={{
                background: 'none', border: '1px solid rgba(255,255,255,0.1)',
                color: page === pages ? 'var(--text-secondary)' : 'var(--cyan)',
                borderRadius: 6, cursor: page === pages ? 'default' : 'pointer',
                padding: '4px 8px', display: 'flex', alignItems: 'center',
              }}
            >
              <ChevronRight size={14} />
            </button>

            <span style={{ marginLeft: 8, opacity: 0.5 }}>
              {(page - 1) * PER_PAGE + 1}–{Math.min(page * PER_PAGE, total)} / {total}
            </span>
          </div>
        </>
      )}
    </motion.div>
  );
}
