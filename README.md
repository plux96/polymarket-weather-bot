# 🌦️ Polymarket Weather Trading Bot v3

An automated trading bot for Polymarket weather prediction markets using **16 weather models**, real-time React dashboard, Telegram controls, and copy trading.

---

## 📊 Backtest Results

| Metric | Result |
|---|---|
| Win Rate | **85%** (175W / 30L) |
| P&L | **+$1,311.88** |
| ROI | **+320%** |
| Total Trades | 205 |
| Resolved Events | 21 |

---

## 🧠 Weather Models (16 total)

### Ensemble — Probabilistic (~156 members)
| # | Model | Organization | Members |
|---|---|---|---|
| 1 | GFS | NOAA, USA | ~31 |
| 2 | ECMWF IFS | European Centre | ~51 |
| 3 | ICON EPS | DWD, Germany | ~40 |
| 4 | GEM | Environment Canada | ~21 |
| 5 | ACCESS-GE | BOM, Australia | ~18 |

### Deterministic — Cross-validation
| # | Model | Organization |
|---|---|---|
| 6 | MeteoFrance Arpege | France |
| 7 | JMA | Japan |
| 8 | UKMO | UK Met Office |
| 9 | KNMI | Netherlands |
| 10 | CMA GRAPES | China |
| 11 | ARPAE COSMO | Italy |
| 12 | MetNorway | Norway |
| 13 | DMI | Denmark |
| 14 | NCEP HRRR | USA (3km, US cities only) |

### External Sources
| # | Model | Description |
|---|---|---|
| 15 | Tomorrow.io | ML-based ensemble |
| 16 | NWS/NOAA | weather.gov (US cities only) |

---

## 🏗️ Architecture

```
polymarket-weather-bot/
├── bot.py                  # Main bot — integrates all modules
├── weather.py              # 16-model weather forecast engine
├── markets.py              # Fetches Polymarket weather markets
├── strategy.py             # Multi-model edge + Kelly criterion
├── smart_timing.py         # Stronger bets near resolution
├── accuracy.py             # Per-model accuracy tracking
├── kalshi.py               # Kalshi arbitrage
├── ws_monitor.py           # WebSocket real-time price monitor
├── ai_analysis.py          # NWS alerts + AI analysis
├── leaderboard.py          # Top traders + copy trading
├── tracker.py              # P&L result tracking
├── backtest.py             # Historical backtest
├── telegram_commands.py    # 16 Telegram commands
├── telegram_bot.py         # Telegram message sending
├── api_server.py           # FastAPI REST API (port 8899)
└── dashboard/              # React + Vite dashboard
```

---

## ⚙️ Configuration

Create a `.env` file:

```env
# Polymarket API (required for live trading)
POLY_API_KEY=your_api_key_here
POLY_API_SECRET=your_api_secret_here
POLY_API_PASSPHRASE=your_passphrase_here
POLY_PRIVATE_KEY=your_wallet_private_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Tomorrow.io (free at tomorrow.io)
TOMORROW_API_KEY=your_tomorrow_api_key

# Trading settings
MIN_EDGE=0.20          # Minimum edge threshold (20%)
MAX_BET_USD=1.0        # Max bet size per trade ($)
BANKROLL=500.0         # Total capital ($)
MAX_TRADES_PER_DAY=40  # Daily trade limit
DRY_RUN=true           # false = live trading
```

---

## 🚀 Installation

### Local (Mac/Linux)

```bash
git clone https://github.com/plux96/polymarket-weather-bot.git
cd polymarket-weather-bot

# Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Dashboard
cd dashboard
npm install
npm run dev  # runs on port 3010

# Start bot
cd ..
python bot.py
```

### VPS (Ubuntu 22/24)

```bash
apt-get install -y python3 python3-venv python3-pip nodejs npm nginx

git clone https://github.com/plux96/polymarket-weather-bot.git /opt/polymarket-bot
cd /opt/polymarket-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install fastapi uvicorn

cd dashboard && npm install && npm run build && cd ..

systemctl enable --now polymarket-api polymarket-bot
```

---

## 📱 Telegram Commands

| Command | Description |
|---|---|
| `/signals` | Current trading signals |
| `/today` | Today's trades |
| `/result` | P&L results |
| `/stats` | Overall statistics |
| `/accuracy` | Per-model accuracy |
| `/backtest` | Backtest results |
| `/leaderboard` | Top Polymarket weather traders |
| `/copytrade` | Copy trading signals |
| `/arbitrage` | Kalshi arbitrage opportunities |
| `/cities` | Monitored cities |
| `/status` | Bot status |
| `/settings` | Current settings |
| `/buy` | Manual YES trade |
| `/sell` | Manual NO trade |
| `/alert` | Set price alert |
| `/help` | Help |

---

## 📈 Strategy

```
1. Scans all weather markets across 21 cities every 15 minutes
2. 16 models compute probability (~156 ensemble members)
3. Edge = model_probability - market_price
4. Signal fires when edge >= 20% AND >= 5 models agree
5. Kelly criterion determines bet size
6. Smart timing boosts size near resolution date
7. Max 3 signals per scan, max 40 trades per day
```

---

## 🌍 Monitored Cities (21)

New York · Chicago · Dallas · Atlanta · Miami · Los Angeles · London · Paris · Berlin · Madrid · Rome · Tokyo · Sydney · Toronto · Amsterdam · Brussels · Vienna · Zurich · Stockholm · Oslo · Copenhagen

---

## 🖥️ Dashboard

Real-time React dashboard at `http://your-server` or `http://localhost:3010`

- **Status Bar** — bot mode, model count, trade count, bankroll
- **Signals** — live signals with edge, confidence, consensus
- **P&L Chart** — daily profit/loss graph
- **Win Rate** — model accuracy breakdown
- **Leaderboard** — top 20 Polymarket weather traders
- **Copy Trading** — signals from top 5 traders
- **Investment** — capital deployed + resolution timeline

---

## 🔧 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Schedule, Rich |
| Frontend | React 18, Vite, Recharts, Framer Motion |
| Data | Open-Meteo, Tomorrow.io, NWS/NOAA, Polymarket Data API |
| Deploy | Ubuntu 24.04, Nginx, Systemd |

---

## ⚠️ Disclaimer

This bot is built for **research and testing purposes**. With `DRY_RUN=true` no real money is spent. Before switching to live trading:
- Obtain a Polymarket CLOB API key
- Fund a wallet with USDC on Polygon network
- Run at least 1 month in dry run mode

---

## 📄 License

MIT License — free for personal and commercial use.
