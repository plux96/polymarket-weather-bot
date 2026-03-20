import { motion } from 'framer-motion';
import { MapPin } from 'lucide-react';
import { useCities } from '../hooks/useApi';

export default function CitiesCard() {
  const { data, loading } = useCities();
  const cities = Array.isArray(data) ? [...data].sort((a, b) => b.pnl - a.pnl) : [];

  const maxAbs = cities.reduce((m, c) => Math.max(m, Math.abs(c.pnl)), 0) || 1;

  return (
    <motion.div
      className="glass-card col-6"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.4 }}
    >
      <div className="card-header">
        <MapPin size={18} className="icon" />
        <span className="card-title">Cities Performance</span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 240, borderRadius: 8 }} />
      ) : cities.length === 0 ? (
        <div className="empty-state">
          <MapPin size={24} style={{ opacity: 0.3 }} />
          <span>No city data yet</span>
        </div>
      ) : (
        <div className="cities-list">
          {cities.map((city, i) => {
            const isPositive = city.pnl >= 0;
            const width = Math.max((Math.abs(city.pnl) / maxAbs) * 100, 3);
            return (
              <motion.div
                key={city.city}
                className="city-row"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.4, delay: i * 0.05 }}
              >
                <span className="city-name">{city.city}</span>
                <div className="city-bar-track">
                  <motion.div
                    className={`city-bar-fill ${isPositive ? 'positive' : 'negative'}`}
                    initial={{ width: 0 }}
                    animate={{ width: `${width}%` }}
                    transition={{ duration: 0.8, delay: i * 0.05, ease: 'easeOut' }}
                  />
                </div>
                <span className="city-pnl" style={{ color: isPositive ? 'var(--green)' : 'var(--red)' }}>
                  {isPositive ? '+' : ''}${city.pnl.toFixed(2)}
                </span>
                <span className="city-wr">
                  {city.win_rate != null ? `${(city.win_rate * 100).toFixed(0)}%` : '—'}
                </span>
              </motion.div>
            );
          })}
        </div>
      )}
    </motion.div>
  );
}
