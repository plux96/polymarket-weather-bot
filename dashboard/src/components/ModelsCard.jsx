import { motion } from 'framer-motion';
import { Brain } from 'lucide-react';
import { useModels } from '../hooks/useApi';

const MODEL_EMOJI = {
  GFS: '🇺🇸',
  ECMWF: '🇪🇺',
  ICON: '🇩🇪',
  GEM: '🇨🇦',
  UKMO: '🇬🇧',
  JMA: '🇯🇵',
  NAM: '🇺🇸',
  HRRR: '🇺🇸',
  ARPEGE: '🇫🇷',
  BOM: '🇦🇺',
};

function aggregateModels(raw) {
  if (!raw || typeof raw !== 'object') return [];
  const agg = {};

  for (const city of Object.values(raw)) {
    if (!city || typeof city !== 'object') continue;
    for (const [model, stats] of Object.entries(city)) {
      if (!agg[model]) {
        agg[model] = { model, correct: 0, total: 0 };
      }
      agg[model].correct += stats.correct || 0;
      agg[model].total += stats.total || 0;
    }
  }

  return Object.values(agg)
    .map(m => ({
      ...m,
      accuracy: m.total > 0 ? m.correct / m.total : 0,
      emoji: MODEL_EMOJI[m.model.toUpperCase()] || '🌐',
    }))
    .sort((a, b) => b.accuracy - a.accuracy);
}

export default function ModelsCard() {
  const { data, loading } = useModels();
  const models = aggregateModels(data);

  return (
    <motion.div
      className="glass-card col-6"
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 0.45 }}
    >
      <div className="card-header">
        <Brain size={18} className="icon" />
        <span className="card-title">Model Accuracy</span>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 240, borderRadius: 8 }} />
      ) : models.length === 0 ? (
        <div className="empty-state">
          <Brain size={24} style={{ opacity: 0.3 }} />
          <span>No model data yet</span>
        </div>
      ) : (
        <div className="models-list">
          {models.map((m, i) => (
            <motion.div
              key={m.model}
              className="model-row"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, delay: i * 0.05 }}
            >
              <span className="model-name">
                {m.emoji} {m.model}
              </span>
              <div className="model-bar-track">
                <motion.div
                  className="model-bar-fill"
                  initial={{ width: 0 }}
                  animate={{ width: `${m.accuracy * 100}%` }}
                  transition={{ duration: 0.8, delay: i * 0.06, ease: 'easeOut' }}
                />
              </div>
              <span className="model-accuracy">
                {(m.accuracy * 100).toFixed(1)}%
              </span>
              <span className="model-count">
                {m.correct}/{m.total}
              </span>
            </motion.div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
