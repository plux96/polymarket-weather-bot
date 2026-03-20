import { motion, AnimatePresence } from 'framer-motion';
import { Trophy, Copy } from 'lucide-react';
import { useLeaderboard } from '../hooks/useApi';

function getMedal(rank) {
  if (rank === 1) return '\u{1F947}';
  if (rank === 2) return '\u{1F948}';
  if (rank === 3) return '\u{1F949}';
  return null;
}

function shortenAddress(addr) {
  if (!addr) return 'Unknown';
  if (addr.length <= 16) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function TraderRow({ trader, index, maxPnl }) {
  const rank = index + 1;
  const medal = getMedal(rank);
  const pnl = trader.pnl ?? trader.profit ?? 0;
  const volume = trader.volume ?? 0;
  const name = trader.username || trader.name || shortenAddress(trader.wallet || trader.address);
  const isPositive = pnl >= 0;
  const barWidth = maxPnl > 0 ? Math.min(Math.abs(pnl) / maxPnl * 100, 100) : 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.03, duration: 0.3 }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 12px',
        background: rank <= 3 ? 'rgba(0, 212, 255, 0.04)' : 'rgba(255, 255, 255, 0.02)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: 'var(--radius-sm)',
        transition: 'background 0.2s, border-color 0.2s',
      }}
      whileHover={{
        backgroundColor: 'rgba(0, 212, 255, 0.06)',
        borderColor: 'rgba(0, 212, 255, 0.15)',
      }}
    >
      {/* Rank */}
      <span style={{
        minWidth: 28,
        fontFamily: 'var(--font-mono)',
        fontSize: '0.8rem',
        fontWeight: 700,
        color: rank <= 3 ? 'var(--cyan)' : 'var(--text-secondary)',
        textAlign: 'center',
      }}>
        {medal || `#${rank}`}
      </span>

      {/* Name */}
      <span style={{
        flex: 1,
        fontSize: '0.82rem',
        fontWeight: 500,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        minWidth: 0,
      }}>
        {name}
      </span>

      {/* PnL bar */}
      <div style={{
        width: 80,
        height: 16,
        background: 'rgba(255, 255, 255, 0.04)',
        borderRadius: 4,
        overflow: 'hidden',
        flexShrink: 0,
      }}>
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${barWidth}%` }}
          transition={{ duration: 0.8, delay: index * 0.03 }}
          style={{
            height: '100%',
            borderRadius: 4,
            background: isPositive
              ? 'linear-gradient(90deg, rgba(0, 255, 136, 0.4), var(--green))'
              : 'linear-gradient(90deg, rgba(255, 71, 87, 0.4), var(--red))',
          }}
        />
      </div>

      {/* PnL value */}
      <span style={{
        minWidth: 70,
        textAlign: 'right',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.8rem',
        fontWeight: 600,
        color: isPositive ? 'var(--green)' : 'var(--red)',
      }}>
        {isPositive ? '+' : ''}${Math.abs(pnl).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
      </span>

      {/* Volume */}
      <span style={{
        minWidth: 60,
        textAlign: 'right',
        fontSize: '0.72rem',
        color: 'var(--text-muted)',
        fontFamily: 'var(--font-mono)',
      }}>
        ${volume >= 1000 ? `${(volume / 1000).toFixed(1)}k` : volume.toFixed(0)}
      </span>

      {/* Copy button */}
      <button
        style={{
          background: 'rgba(0, 212, 255, 0.1)',
          border: '1px solid rgba(0, 212, 255, 0.2)',
          borderRadius: 6,
          padding: '3px 8px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          gap: 4,
          color: 'var(--cyan)',
          fontSize: '0.65rem',
          fontWeight: 600,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          transition: 'all 0.2s',
          flexShrink: 0,
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = 'rgba(0, 212, 255, 0.2)';
          e.currentTarget.style.borderColor = 'rgba(0, 212, 255, 0.4)';
        }}
        onMouseLeave={e => {
          e.currentTarget.style.background = 'rgba(0, 212, 255, 0.1)';
          e.currentTarget.style.borderColor = 'rgba(0, 212, 255, 0.2)';
        }}
      >
        <Copy size={10} />
        Copy
      </button>
    </motion.div>
  );
}

export default function LeaderboardCard() {
  const { data, loading, error } = useLeaderboard();

  const traders = Array.isArray(data?.traders || data)
    ? (data?.traders || data)
    : [];

  const maxPnl = traders.length > 0
    ? Math.max(...traders.map(t => Math.abs(t.pnl ?? t.profit ?? 0)))
    : 1;

  return (
    <motion.div
      className="glass-card col-6"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
    >
      <div className="card-header">
        <Trophy size={18} className="icon" />
        <span className="card-title">Weather Leaderboard</span>
        <span style={{
          marginLeft: 'auto',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
        }}>
          Top 20 &middot; Monthly
        </span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 300, borderRadius: 8 }} />
      ) : error || data?.error ? (
        <div className="empty-state">
          <Trophy size={24} style={{ opacity: 0.3 }} />
          <span>{data?.error || error || 'Failed to load leaderboard'}</span>
        </div>
      ) : traders.length === 0 ? (
        <div className="empty-state">
          <Trophy size={24} style={{ opacity: 0.3 }} />
          <span>No leaderboard data</span>
        </div>
      ) : (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          maxHeight: 460,
          overflowY: 'auto',
          paddingRight: 4,
        }}>
          {/* Header row */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            padding: '4px 12px',
            fontSize: '0.68rem',
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '1px',
          }}>
            <span style={{ minWidth: 28, textAlign: 'center' }}>Rank</span>
            <span style={{ flex: 1 }}>Trader</span>
            <span style={{ width: 80 }}>PnL</span>
            <span style={{ minWidth: 70, textAlign: 'right' }}>Profit</span>
            <span style={{ minWidth: 60, textAlign: 'right' }}>Volume</span>
            <span style={{ minWidth: 52 }}></span>
          </div>

          <AnimatePresence>
            {traders.map((trader, i) => (
              <TraderRow
                key={trader.wallet || trader.address || trader.username || i}
                trader={trader}
                index={i}
                maxPnl={maxPnl}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
