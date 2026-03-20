import { motion, AnimatePresence } from 'framer-motion';
import { Users, Zap } from 'lucide-react';
import { useCopySignals } from '../hooks/useApi';

function shortenAddress(addr) {
  if (!addr) return 'Unknown';
  if (addr.length <= 16) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

function SignalRow({ signal, index }) {
  const name = signal.trader_username || signal.trader_name || signal.trader || signal.username || shortenAddress(signal.wallet || signal.address);
  const side = (signal.side || '').toUpperCase();
  const isYes = side === 'YES';
  const price = signal.price ?? signal.avg_price ?? 0;
  const question = signal.question || signal.market || signal.market_question || '';
  const time = signal.time || signal.timestamp || '';
  const displayTime = time ? new Date(time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.97 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -10, scale: 0.97 }}
      transition={{ duration: 0.35, delay: index * 0.05 }}
      layout
      style={{
        padding: '12px 14px',
        background: 'rgba(255, 255, 255, 0.03)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        borderRadius: 'var(--radius-sm)',
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
        transition: 'background 0.2s, border-color 0.2s',
      }}
      whileHover={{
        backgroundColor: 'rgba(255, 255, 255, 0.06)',
        borderColor: 'rgba(0, 212, 255, 0.15)',
      }}
    >
      {/* Top row: trader name + side badge + time */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Zap size={12} style={{ color: 'var(--cyan)', flexShrink: 0 }} />
        <span style={{
          fontWeight: 600,
          fontSize: '0.85rem',
        }}>
          {name}
        </span>

        <span style={{
          padding: '2px 8px',
          borderRadius: 4,
          fontSize: '0.68rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          background: isYes ? 'rgba(0, 255, 136, 0.12)' : 'rgba(255, 71, 87, 0.12)',
          color: isYes ? 'var(--green)' : 'var(--red)',
        }}>
          {side || 'N/A'}
        </span>

        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.78rem',
          color: 'var(--cyan)',
          fontWeight: 600,
        }}>
          @{typeof price === 'number' ? price.toFixed(2) : price}
        </span>

        {displayTime && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.7rem',
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
          }}>
            {displayTime}
          </span>
        )}
      </div>

      {/* Question / market */}
      {question && (
        <div style={{
          fontSize: '0.76rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.4,
          paddingLeft: 20,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
        }}>
          {question}
        </div>
      )}
    </motion.div>
  );
}

export default function CopyTradeCard() {
  const { data, loading, error } = useCopySignals();

  const signals = Array.isArray(data?.signals || data)
    ? (data?.signals || data)
    : [];

  const followingCount = data?.following ?? signals.length;

  return (
    <motion.div
      className="glass-card col-6"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.45 }}
    >
      <div className="card-header">
        <Users size={18} className="icon" />
        <span className="card-title">Copy Trading - Top 5 Traders</span>
        {followingCount > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.7rem',
            color: 'var(--cyan)',
            fontFamily: 'var(--font-mono)',
            display: 'flex',
            alignItems: 'center',
            gap: 4,
          }}>
            <motion.span
              animate={{ opacity: [1, 0.5, 1] }}
              transition={{ duration: 2, repeat: Infinity }}
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--green)',
                display: 'inline-block',
              }}
            />
            Following {followingCount} traders
          </span>
        )}
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 240, borderRadius: 8 }} />
      ) : error || data?.error ? (
        <div className="empty-state">
          <Users size={24} style={{ opacity: 0.3 }} />
          <span>{data?.error || error || 'Failed to load signals'}</span>
        </div>
      ) : signals.length === 0 ? (
        <div className="empty-state">
          <Users size={24} style={{ opacity: 0.3 }} />
          <span>No copy signals available</span>
        </div>
      ) : (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          maxHeight: 420,
          overflowY: 'auto',
          paddingRight: 4,
        }}>
          <AnimatePresence mode="popLayout">
            {signals.map((s, i) => (
              <SignalRow
                key={`${s.trader || s.wallet || i}-${s.market || i}-${s.timestamp || i}`}
                signal={s}
                index={i}
              />
            ))}
          </AnimatePresence>
        </div>
      )}
    </motion.div>
  );
}
