# 🌦️ Polymarket Weather Trading Bot v3

Polymarket weather prediction markets uchun avtomatik trading bot — **16 ta ob-havo modeli**, React dashboard, Telegram boshqaruvi va copy trading.

---

## 📊 Backtest Natijasi

| Metrika | Natija |
|---|---|
| Win Rate | **85%** (175W / 30L) |
| P&L | **+$1,311.88** |
| ROI | **+320%** |
| Jami savdolar | 205 |
| Resolved events | 21 |

---

## 🧠 Ob-havo Modellari (16 ta)

### Ensemble (probabilistik, ~156 member)
| # | Model | Tashkilot | Members |
|---|---|---|---|
| 1 | GFS | NOAA, AQSh | ~31 |
| 2 | ECMWF IFS | Yevropa | ~51 |
| 3 | ICON | DWD, Germaniya | ~40 |
| 4 | GEM | Kanada | ~21 |
| 5 | ACCESS-GE | BOM, Avstraliya | ~18 |

### Deterministic (cross-validation)
| # | Model | Tashkilot |
|---|---|---|
| 6 | MeteoFrance Arpege | Fransiya |
| 7 | JMA | Yaponiya |
| 8 | UKMO | Britaniya |
| 9 | KNMI | Niderlandiya |
| 10 | CMA GRAPES | Xitoy |
| 11 | ARPAE COSMO | Italiya |
| 12 | MetNorway | Norvegiya |
| 13 | DMI | Daniya |
| 14 | NCEP HRRR | AQSh (3km, US only) |

### Tashqi manbalar
| # | Model | Xususiyat |
|---|---|---|
| 15 | Tomorrow.io | ML ensemble |
| 16 | NWS/NOAA | weather.gov (US only) |

---

## 🏗️ Arxitektura

```
polymarket-weather-bot/
├── bot.py                  # Asosiy bot — barcha modullarni birlashtiradi
├── weather.py              # 16 model ob-havo prognozi
├── markets.py              # Polymarket weather bozorlarini oladi
├── strategy.py             # Multi-model edge + Kelly criterion
├── smart_timing.py         # Resolution yaqinida kuchliroq savdo
├── accuracy.py             # Model aniqlik tracking
├── kalshi.py               # Kalshi arbitraj
├── ws_monitor.py           # WebSocket real-time narx kuzatish
├── ai_analysis.py          # NWS alerts + AI tahlil
├── leaderboard.py          # Top traderlar + copy trading
├── tracker.py              # P&L natija tracking
├── backtest.py             # Historical backtest
├── telegram_commands.py    # 16 ta Telegram komanda
├── telegram_bot.py         # Telegram xabar yuborish
├── api_server.py           # FastAPI REST API (port 8899)
└── dashboard/              # React + Vite dashboard
```

---

## ⚙️ Sozlamalar

`.env` fayl yarating:

```env
# Polymarket API (haqiqiy savdo uchun)
POLY_API_KEY=your_api_key_here
POLY_API_SECRET=your_api_secret_here
POLY_API_PASSPHRASE=your_passphrase_here
POLY_PRIVATE_KEY=your_wallet_private_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Tomorrow.io (bepul: tomorrow.io)
TOMORROW_API_KEY=your_tomorrow_api_key

# Trading sozlamalari
MIN_EDGE=0.20          # Minimal edge (20%)
MAX_BET_USD=1.0        # Har bir savdo maksimal $
BANKROLL=500.0         # Jami kapital
MAX_TRADES_PER_DAY=40  # Kunlik maksimal savdolar
DRY_RUN=true           # false = haqiqiy savdo
```

---

## 🚀 O'rnatish

### Local (Mac/Linux)

```bash
# Repo clone
git clone https://github.com/plux96/polymarket-weather-bot.git
cd polymarket-weather-bot

# Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Dashboard
cd dashboard
npm install
npm run dev  # port 3010

# Bot ishga tushirish
cd ..
python bot.py
```

### VPS (Ubuntu 22/24)

```bash
# Paketlar
apt-get install -y python3 python3-venv python3-pip nodejs npm nginx

# Loyiha
git clone https://github.com/plux96/polymarket-weather-bot.git /opt/polymarket-bot
cd /opt/polymarket-bot

# Python
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install fastapi uvicorn

# Dashboard build
cd dashboard && npm install && npm run build && cd ..

# Systemd servislar
cp deploy/polymarket-api.service /etc/systemd/system/
cp deploy/polymarket-bot.service /etc/systemd/system/
systemctl enable --now polymarket-api polymarket-bot
```

---

## 📱 Telegram Komandalar

| Komanda | Funksiya |
|---|---|
| `/signals` | Hozirgi signallar |
| `/today` | Bugungi savdolar |
| `/result` | P&L natijalari |
| `/stats` | Umumiy statistika |
| `/accuracy` | Model aniqligi |
| `/backtest` | Backtest natijasi |
| `/leaderboard` | Top weather traderlar |
| `/copytrade` | Copy trading signallari |
| `/arbitrage` | Kalshi arbitraj |
| `/cities` | Kuzatiladigan shaharlar |
| `/status` | Bot holati |
| `/settings` | Sozlamalar |
| `/buy` | Qo'lda savdo (YES) |
| `/sell` | Qo'lda savdo (NO) |
| `/alert` | Narx ogohlantirish |
| `/help` | Yordam |

---

## 📈 Strategiya

```
1. Har 15 daqiqada 21 shahar, barcha weather bozorlarni skanerlaydi
2. 16 model ehtimollikni hisoblaydi (~156 ensemble member)
3. Edge = model_probability - market_price
4. MIN_EDGE >= 20% bo'lsa signal
5. MIN_CONSENSUS >= 5 model rozi bo'lishi kerak
6. Kelly criterion bilan bet size hisoblash
7. Smart timing — resolution yaqinida kuchliroq
8. Kuniga max 40 savdo, scan boshiga top 3 signal
```

---

## 🌍 Kuzatiladigan Shaharlar (21)

New York, Chicago, Dallas, Atlanta, Miami, Los Angeles, London, Paris, Berlin, Madrid, Rome, Tokyo, Sydney, Toronto, Amsterdam, Brussels, Vienna, Zurich, Stockholm, Oslo, Copenhagen

---

## 🖥️ Dashboard

React + Vite dashboard real-time ma'lumotlarni ko'rsatadi:

- **Status bar** — bot holati, model soni, savdolar, bankroll
- **Signals** — hozirgi signallar + edge, confidence
- **P&L Chart** — kunlik foyda/zarar grafigi
- **Win Rate** — model aniqligi
- **Leaderboard** — top 20 Polymarket weather trader
- **Copy Trading** — top 5 trader signallari
- **Investment** — quyilgan kapital + resolution vaqtlari

---

## 🔧 Texnologiyalar

**Backend:** Python 3.12, FastAPI, Schedule, Rich
**Frontend:** React 18, Vite, Recharts, Framer Motion
**Ma'lumot:** Open-Meteo API, Tomorrow.io, NWS/NOAA, Polymarket Data API
**Deploy:** Ubuntu 24.04, Nginx, Systemd

---

## ⚠️ Eslatma

Bu bot **test maqsadida** yaratilgan. `DRY_RUN=true` rejimida haqiqiy pul sarflanmaydi. Haqiqiy savdoga o'tishdan oldin:
- Polymarket CLOB API key oling
- Polygon network'da USDC tayyorlang
- Kamida 1 oy DRY RUN test qiling

---

## 📄 Litsenziya

MIT License — shaxsiy va tijorat maqsadida foydalanish mumkin.
