import { motion, AnimatePresence } from 'framer-motion';
import { Radio } from 'lucide-react';
import { useSignals } from '../hooks/useApi';

function SignalItem({ signal, index }) {
  return (
    <motion.div
      className="signal-item"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
      layout
    >
      <span className="signal-city">{signal.city}</span>
      <span className="signal-temp">
        {signal.temp_low}-{signal.temp_high}{signal.unit || 'F'}
      </span>
      <span className={`signal-side ${signal.side?.toLowerCase()}`}>
        {signal.side}
      </span>
      <span className="signal-edge">
        {(signal.edge * 100).toFixed(1)}% edge
      </span>
      {signal.consensus && (
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {signal.consensus}
        </span>
      )}
      <span className="signal-bet">
        ${signal.bet_size?.toFixed(2)}
      </span>
    </motion.div>
  );
}

export default function SignalsCard() {
  const { data, loading } = useSignals();
  const signals = Array.isArray(data) ? data : [];

  return (
    <motion.div
      className="glass-card col-4"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.3 }}
    >
      <div className="card-header">
        <Radio size={18} className="icon" />
        <span className="card-title">Live Signals</span>
        {signals.length > 0 && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.7rem',
            color: 'var(--cyan)',
            fontFamily: 'var(--font-mono)',
          }}>
            {signals.length} active
          </span>
        )}
      </div>

      {loading ? (
        <div className="shimmer scanning-text" style={{ height: 200 }}>
          <span className="dot" /><span className="dot" /><span className="dot" />
          <span style={{ marginLeft: 4 }}>Scanning markets...</span>
        </div>
      ) : signals.length === 0 ? (
        <div className="empty-state">
          <Radio size={24} style={{ opacity: 0.3 }} />
          <span>No active signals</span>
        </div>
      ) : (
        <div className="signals-feed">
          <AnimatePresence mode="popLayout">
            {signals.map((s, i) => (
              <SignalItem
                key={`${s.city}-${s.temp_low}-${s.side}`}
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
