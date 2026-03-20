import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { DollarSign, CheckCircle, Clock, AlertCircle } from 'lucide-react';
import { useInvestment } from '../hooks/useApi';

function AnimatedNumber({ value, prefix = '', suffix = '', decimals = 0 }) {
  const [display, setDisplay] = useState(0);
  const rafRef = useRef(null);
  const startRef = useRef(0);
  const startTimeRef = useRef(null);

  useEffect(() => {
    startRef.current = display;
    startTimeRef.current = null;
    const duration = 1200;

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

  const formatted = decimals > 0
    ? display.toFixed(decimals)
    : Math.round(display).toLocaleString();

  return (
    <span>
      {prefix}{formatted}{suffix}
    </span>
  );
}

function StatusIcon({ status }) {
  if (status === 'resolved') {
    return <CheckCircle size={14} style={{ color: 'var(--green)' }} />;
  }
  if (status === 'resolving') {
    return (
      <motion.div
        animate={{ opacity: [1, 0.4, 1] }}
        transition={{ duration: 1.5, repeat: Infinity }}
        style={{ display: 'flex', alignItems: 'center' }}
      >
        <AlertCircle size={14} style={{ color: 'var(--yellow)' }} />
      </motion.div>
    );
  }
  return <Clock size={14} style={{ color: 'var(--text-muted)' }} />;
}

function getDisplayStatus(item) {
  const today = new Date().toISOString().slice(0, 10);
  if (item.date === today) return 'resolving';
  return item.status;
}

function getStatusLabel(status) {
  if (status === 'resolved') return 'Resolved';
  if (status === 'resolving') return 'Resolving today...';
  return 'Pending';
}

export default function InvestmentCard() {
  const { data, loading } = useInvestment();

  const totalInvested = data?.total_invested ?? 0;
  const totalTrades = data?.total_trades ?? 0;
  const mode = data?.mode ?? 'DRY RUN';
  const timeline = data?.timeline ?? [];

  return (
    <motion.div
      className="glass-card col-4"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.12 }}
    >
      <div className="card-header">
        <DollarSign size={18} className="icon" />
        <span className="card-title">Total Investment</span>
        <span
          className={`badge ${mode === 'DRY RUN' ? 'badge-dry' : 'badge-live'}`}
          style={{ marginLeft: 'auto' }}
        >
          {mode}
        </span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 48, borderRadius: 8 }} />
      ) : (
        <>
          <motion.div
            className="big-number"
            style={{ color: 'var(--cyan)', textShadow: '0 0 30px rgba(0, 212, 255, 0.2)' }}
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ duration: 0.6, type: 'spring' }}
          >
            <AnimatedNumber value={totalInvested} prefix="$" />
          </motion.div>
          <div className="sub-metric" style={{ marginTop: 8 }}>
            {totalTrades} trades across {timeline.length} dates
          </div>
        </>
      )}

      {!loading && timeline.length > 0 && (
        <div style={{
          marginTop: 20,
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          maxHeight: 220,
          overflowY: 'auto',
          paddingRight: 4,
        }}>
          <div style={{
            fontSize: '0.7rem',
            textTransform: 'uppercase',
            letterSpacing: '1.5px',
            color: 'var(--text-secondary)',
            marginBottom: 4,
          }}>
            Resolution Timeline
          </div>
          {timeline.map((item, i) => {
            const displayStatus = getDisplayStatus(item);
            return (
              <motion.div
                key={item.date}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05, duration: 0.3 }}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '8px 12px',
                  background: displayStatus === 'resolving'
                    ? 'rgba(255, 193, 7, 0.06)'
                    : 'rgba(255, 255, 255, 0.03)',
                  border: `1px solid ${
                    displayStatus === 'resolving'
                      ? 'rgba(255, 193, 7, 0.2)'
                      : 'rgba(255, 255, 255, 0.05)'
                  }`,
                  borderRadius: 'var(--radius-sm)',
                }}
              >
                <StatusIcon status={displayStatus} />
                <span style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.8rem',
                  fontWeight: 600,
                  minWidth: 82,
                }}>
                  {item.date}
                </span>
                <span style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                }}>
                  {item.trades} trades
                </span>
                <span style={{
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--cyan)',
                }}>
                  ${item.invested}
                </span>
                <span style={{
                  fontSize: '0.7rem',
                  color: 'var(--text-muted)',
                  marginLeft: 'auto',
                }}>
                  {item.cities} {item.cities === 1 ? 'city' : 'cities'}
                </span>
                <span style={{
                  fontSize: '0.68rem',
                  color: displayStatus === 'resolved'
                    ? 'var(--green)'
                    : displayStatus === 'resolving'
                    ? 'var(--yellow)'
                    : 'var(--text-muted)',
                  fontWeight: 600,
                  textTransform: 'uppercase',
                  letterSpacing: '0.5px',
                }}>
                  {getStatusLabel(displayStatus)}
                </span>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
