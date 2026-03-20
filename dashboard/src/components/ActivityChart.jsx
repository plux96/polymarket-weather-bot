import { motion } from 'framer-motion';
import { Clock } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from 'recharts';
import { useActivity } from '../hooks/useApi';

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="custom-tooltip">
      <div className="label">{label}:00</div>
      <div className="value" style={{ color: 'var(--cyan)' }}>
        {d.trades} trade{d.trades !== 1 ? 's' : ''}
      </div>
      {d.total_bet != null && (
        <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>
          ${d.total_bet.toFixed(2)} wagered
        </div>
      )}
    </div>
  );
}

function getBarColor(trades, max) {
  if (max === 0) return 'rgba(0, 212, 255, 0.3)';
  const ratio = trades / max;
  if (ratio > 0.7) return '#00d4ff';
  if (ratio > 0.4) return '#7b61ff';
  return 'rgba(0, 212, 255, 0.3)';
}

export default function ActivityChart() {
  const { data, loading } = useActivity();
  const activity = Array.isArray(data) ? data : [];

  // Fill in missing hours
  const hourMap = {};
  activity.forEach(a => { hourMap[a.hour] = a; });
  const chartData = Array.from({ length: 24 }, (_, i) => ({
    hour: String(i).padStart(2, '0'),
    trades: hourMap[i]?.trades ?? 0,
    total_bet: hourMap[i]?.total_bet ?? 0,
    avg_edge: hourMap[i]?.avg_edge ?? 0,
  }));

  const maxTrades = chartData.reduce((m, d) => Math.max(m, d.trades), 0);

  return (
    <motion.div
      className="glass-card col-4"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.55 }}
    >
      <div className="card-header">
        <Clock size={18} className="icon" />
        <span className="card-title">24h Activity</span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 220, borderRadius: 8 }} />
      ) : (
        <div style={{ height: 220 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis
                dataKey="hour"
                tick={{ fontSize: 9 }}
                interval={2}
              />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(0, 212, 255, 0.04)' }} />
              <Bar dataKey="trades" radius={[4, 4, 0, 0]} animationDuration={1000}>
                {chartData.map((entry, index) => (
                  <Cell key={index} fill={getBarColor(entry.trades, maxTrades)} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}
