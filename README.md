# Polymarket Weather Trading Bot

An automated trading bot for Polymarket weather prediction markets. Uses 16 weather models, real-time WebSocket monitoring, Telegram controls, and a React dashboard.

---

## Backtest Results

| Metric | Result |
|---|---|
| Win Rate | **85%** (175W / 30L) |
| P&L | **+$1,311.88** |
| ROI | **+320%** |
| Total Trades | 205 |
| Resolved Events | 21 |

---

## Architecture

```
polymarket-weather-bot/
├── bot.py                        # Entry point — runs every 15 min
├── api_server.py                 # FastAPI REST API (port 8899)
├── src/
│   ├── weather/
│   │   ├── models.py             # 16-model weather forecast engine
│   │   └── accuracy.py           # Per-model accuracy tracking
│   ├── trading/
│   │   ├── markets.py            # Polymarket weather market fetcher
│   │   ├── strategy.py           # Edge calculation + Kelly criterion
│   │   ├── smart_timing.py       # Timing multiplier near resolution
│   │   ├── tracker.py            # P&L tracking
│   │   ├── kalshi.py             # Kalshi arbitrage
│   │   └── backtest.py           # Historical backtesting
│   ├── monitoring/
│   │   ├── ws_monitor.py         # WebSocket real-time price monitor
│   │   └── ai_analysis.py        # NWS alerts + AI analysis
│   ├── notifications/
│   │   ├── telegram_bot.py       # Telegram message sender
│   │   └── telegram_commands.py  # 16 Telegram commands
│   └── leaderboard/
│       └── leaderboard.py        # Top traders + copy trading
├── dashboard/                    # React + Vite dashboard (port 3000)
├── storage/                      # trades.json, results.json (gitignored)
├── logs/                         # Runtime logs (gitignored)
└── scripts/                      # launchd service plists (macOS)
```

---

## Weather Models (16)

### Ensemble — ~156 members
| Model | Organization |
|---|---|
| GFS | NOAA, USA (~31 members) |
| ECMWF IFS | European Centre (~51 members) |
| ICON EPS | DWD, Germany (~40 members) |
| GEM | Environment Canada (~21 members) |
| ACCESS-GE | BOM, Australia (~18 members) |

### Deterministic — Cross-validation
| Model | Organization |
|---|---|
| MeteoFrance Arpege | France |
| JMA | Japan |
| UKMO | UK Met Office |
| KNMI | Netherlands |
| CMA GRAPES | China |
| ARPAE COSMO | Italy |
| MetNorway | Norway |
| DMI | Denmark |
| NCEP HRRR | USA (3km resolution, US cities) |

### External Sources
| Model | Description |
|---|---|
| Tomorrow.io | ML-based ensemble |
| NWS/NOAA | weather.gov (US cities) |

---

## Strategy

1. Scans all weather markets across 21 cities every 15 minutes
2. 16 models compute probability (~156 ensemble members total)
3. Edge = model probability − market price
4. Signal fires when edge ≥ 20% AND ≥ 5 models agree
5. Kelly criterion determines bet size
6. Smart timing multiplier boosts size near resolution
7. Max 40 trades per day

---

## Installation

```bash
git clone https://github.com/plux96/polymarket-weather-bot.git
cd polymarket-weather-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# fill in your API keys

python bot.py
```

**Dashboard:**
```bash
cd dashboard
npm install
npm run dev   # http://localhost:3000
```

---

## Configuration (.env)

```env
# Polymarket CLOB API (required for live trading)
POLY_API_KEY=
POLY_API_SECRET=
POLY_API_PASSPHRASE=
POLY_PRIVATE_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Tomorrow.io (free tier available)
TOMORROW_API_KEY=

# Trading
MIN_EDGE=0.20           # Minimum edge threshold
MAX_BET_USD=1.0         # Max bet per trade ($)
BANKROLL=500.0          # Total capital ($)
MAX_TRADES_PER_DAY=40
DRY_RUN=true            # Set false for live trading
```

---

## Telegram Commands

| Command | Description |
|---|---|
| `/signals` | Current trading signals |
| `/today` | Today's trades |
| `/result` | P&L results |
| `/stats` | Overall statistics |
| `/accuracy` | Per-model accuracy breakdown |
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

## Monitored Cities (21)

New York · Chicago · Dallas · Atlanta · Miami · Los Angeles · London · Paris · Berlin · Madrid · Rome · Tokyo · Sydney · Toronto · Amsterdam · Brussels · Vienna · Zurich · Stockholm · Oslo · Copenhagen

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Schedule, Rich |
| Frontend | React 18, Vite, Recharts, Framer Motion |
| Data Sources | Open-Meteo, Tomorrow.io, NWS/NOAA, Polymarket CLOB API |
| macOS Deploy | launchd (scripts/) |
| VPS Deploy | Ubuntu 24.04, Nginx, Systemd |

---

## Disclaimer

This project is for **research and educational purposes**. With `DRY_RUN=true` no real money is used. Before live trading:
- Obtain a [Polymarket CLOB API key](https://docs.polymarket.com)
- Fund a wallet with USDC on Polygon
- Run at least 30 days in dry run mode

---

## License

MIT
