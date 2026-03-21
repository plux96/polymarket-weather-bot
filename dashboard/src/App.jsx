import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CloudSun } from 'lucide-react';
import StatusBar from './components/StatusBar';
import PnlCard from './components/PnlCard';
import WinRateCard from './components/WinRateCard';
import SignalsCard from './components/SignalsCard';
import CitiesCard from './components/CitiesCard';
import TradesCard from './components/TradesCard';
import ModelsCard from './components/ModelsCard';
import ActivityChart from './components/ActivityChart';
import InvestmentCard from './components/InvestmentCard';
import LeaderboardCard from './components/LeaderboardCard';
import CopyTradeCard from './components/CopyTradeCard';
import ResultsCard from './components/ResultsCard';
import AllTradesCard from './components/AllTradesCard';

function Header() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  const timeStr = time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const dateStr = time.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });

  return (
    <motion.div
      className="dashboard-header"
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
    >
      <div>
        <div className="header-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <CloudSun size={28} style={{ color: 'var(--cyan)' }} />
          <span className="gradient-text">Weather Trading Bot</span>
        </div>
        <div className="header-subtitle">Polymarket Automated Weather Derivatives</div>
      </div>
      <div className="header-time">
        {dateStr} &middot; {timeStr}
      </div>
    </motion.div>
  );
}

export default function App() {
  return (
    <>
      <div className="bg-mesh" />
      <div className="dashboard">
        <Header />
        <StatusBar />

        <motion.div
          className="dashboard-grid"
          initial="hidden"
          animate="visible"
          variants={{
            hidden: {},
            visible: { transition: { staggerChildren: 0.08 } },
          }}
        >
          <PnlCard />
          <InvestmentCard />
          <WinRateCard />
          <SignalsCard />
          <TradesCard />
          <ActivityChart />
          <CitiesCard />
          <ModelsCard />
          <AllTradesCard />
          <ResultsCard />
          <LeaderboardCard />
          <CopyTradeCard />
        </motion.div>
      </div>
    </>
  );
}
