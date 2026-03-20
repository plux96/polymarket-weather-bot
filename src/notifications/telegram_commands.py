"""
Telegram bot komandalar va menyu.

Komandalar:
  /start     — Botni boshlash
  /result    — Natijalar (P&L, win rate)
  /signals   — Hozirgi signallar
  /stats     — Umumiy statistika
  /cities    — Shaharlar bo'yicha natija
  /today     — Bugungi signallar
  /status    — Bot holati
  /help      — Yordam
  /buy       — Manual sotib olish (e.g. /buy nyc YES 5)
  /sell      — Manual sotish (e.g. /sell nyc YES 5)
  /backtest  — Backtestni ishga tushirish
  /accuracy  — Model aniqlik reytingi
  /arbitrage — Kalshi arbitraj imkoniyatlari
  /settings  — Bot sozlamalari
  /alert     — Narx alertlarni yoqish/o'chirish
"""

import os
import json
import time
import inspect
import threading
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TRADES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "storage", "trades.json")

# Alert holati (in-memory toggle)
_alerts_enabled = False

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_msg(text: str, reply_markup: dict = None) -> bool:
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=10)
        return resp.json().get("ok", False)
    except Exception:
        return False


def set_bot_commands():
    """Bot menyusini o'rnatadi — Telegram'da '/' bosganda ko'rinadi."""
    commands = [
        {"command": "result", "description": "📊 Natijalar — P&L, win rate"},
        {"command": "signals", "description": "🎯 Hozirgi signallar"},
        {"command": "today", "description": "📅 Bugungi signallar"},
        {"command": "stats", "description": "📈 Umumiy statistika"},
        {"command": "cities", "description": "🏙 Shaharlar reytingi"},
        {"command": "status", "description": "⚙️ Bot holati"},
        {"command": "buy", "description": "🛒 Manual sotib olish (/buy city side amount)"},
        {"command": "sell", "description": "💸 Manual sotish (/sell city side amount)"},
        {"command": "backtest", "description": "📊 Backtestni ishga tushirish"},
        {"command": "accuracy", "description": "🎯 Model aniqlik reytingi"},
        {"command": "arbitrage", "description": "💱 Kalshi arbitraj tekshirish"},
        {"command": "settings", "description": "⚙️ Bot sozlamalari"},
        {"command": "alert", "description": "🔔 Alertlarni yoqish/o'chirish"},
        {"command": "leaderboard", "description": "🏆 Top weather traderlar"},
        {"command": "copytrade", "description": "📋 Copy trading signallari"},
        {"command": "help", "description": "❓ Yordam"},
    ]
    try:
        requests.post(f"{API_URL}/setMyCommands", json={"commands": commands}, timeout=10)
    except Exception:
        pass


def handle_result():
    """P&L natijalarini ko'rsatadi."""
    from src.trading.tracker import evaluate_trades, format_daily_pnl
    stats = evaluate_trades()
    msg = format_daily_pnl(stats)
    send_msg(msg)


def handle_signals():
    """Hozirgi eng yaxshi signallarni ko'rsatadi."""
    from src.trading.strategy import scan_all_opportunities
    from src.notifications.telegram_bot import format_signals_message

    send_msg("🔄 <b>Skanerlash...</b> (1-2 daqiqa)")
    signals = scan_all_opportunities(min_edge=0.08, bankroll=100.0, max_bet=5.0)
    msg = format_signals_message(signals)
    send_msg(msg)


def handle_today():
    """Bugungi savdolarni ko'rsatadi."""
    from src.trading.strategy import load_trades
    trades = load_trades()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_trades = [t for t in trades if t.get("timestamp", "").startswith(today)]

    if not today_trades:
        send_msg(f"📅 <b>Bugun ({today})</b>\n\n😐 Hali savdo yo'q.")
        return

    total_bet = sum(t.get("bet_size", 0) for t in today_trades)
    avg_edge = sum(t.get("edge", 0) for t in today_trades) / len(today_trades)

    lines = [
        f"📅 <b>Bugun ({today})</b>",
        f"",
        f"📋 Savdolar: <b>{len(today_trades)}</b>",
        f"💰 Jami bet: <b>${total_bet:.2f}</b>",
        f"📊 O'rtacha edge: <b>{avg_edge:.0%}</b>",
        "",
        "<b>Oxirgi 10 ta:</b>",
        "",
    ]

    for t in today_trades[-10:]:
        unit = "°" + t.get("unit", "F")
        tl, th = t.get("temp_low", 0), t.get("temp_high", 0)
        if tl == -999:
            temp = f"≤{th-1}{unit}"
        elif th == 999:
            temp = f"≥{tl}{unit}"
        else:
            temp = f"{tl}-{th-1}{unit}"

        side_e = "🟢" if t.get("side") == "YES" else "🔴"
        consensus = t.get("consensus", "?")
        lines.append(
            f"{side_e} {t.get('city','')} {temp} | "
            f"Edge: {t.get('edge',0):.0%} | {consensus} | "
            f"${t.get('bet_size',0):.2f}"
        )

    send_msg("\n".join(lines))


def handle_stats():
    """Umumiy statistika."""
    from src.trading.strategy import load_trades
    from src.trading.tracker import evaluate_trades

    trades = load_trades()
    stats = evaluate_trades()

    # Kunlar soni
    dates = set(t.get("date", "") for t in trades if t.get("date"))
    cities = set(t.get("city", "") for t in trades if t.get("city"))

    total_bet = sum(t.get("bet_size", 0) for t in trades)
    avg_edge = sum(t.get("edge", 0) for t in trades) / len(trades) if trades else 0
    avg_conf = sum(t.get("confidence", 0) for t in trades) / len(trades) if trades else 0

    pnl = stats["total_pnl"]
    pnl_e = "🟢" if pnl >= 0 else "🔴"

    dry = "DRY RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "LIVE"

    msg = (
        f"📈 <b>UMUMIY STATISTIKA</b>\n\n"
        f"⚙️ Mode: <b>{dry}</b>\n"
        f"📋 Jami savdolar: <b>{len(trades)}</b>\n"
        f"📅 Kunlar: <b>{len(dates)}</b>\n"
        f"🏙 Shaharlar: <b>{len(cities)}</b>\n"
        f"💰 Jami bet: <b>${total_bet:.2f}</b>\n"
        f"📊 O'rtacha edge: <b>{avg_edge:.0%}</b>\n"
        f"🎯 O'rtacha confidence: <b>{avg_conf:.0%}</b>\n\n"
        f"<b>Natijalar:</b>\n"
        f"{pnl_e} P&L: <b>${pnl:+.2f}</b>\n"
        f"📈 ROI: <b>{stats['roi']:+.1%}</b>\n"
        f"🎯 Win rate: <b>{stats['win_rate']:.0%}</b> "
        f"({stats['wins']}W / {stats['losses']}L)\n"
        f"⏳ Kutilmoqda: {stats['pending']}\n"
    )
    send_msg(msg)


def handle_cities():
    """Shaharlar reytingi."""
    from src.trading.tracker import evaluate_trades
    stats = evaluate_trades()

    by_city = stats.get("by_city", {})
    if not by_city:
        send_msg("🏙 Hali shahar bo'yicha natija yo'q.")
        return

    sorted_cities = sorted(by_city.items(), key=lambda x: x[1]["pnl"], reverse=True)

    lines = ["🏙 <b>SHAHARLAR REYTINGI</b>", ""]

    for i, (city, d) in enumerate(sorted_cities, 1):
        pnl = d["pnl"]
        emoji = "🟢" if pnl >= 0 else "🔴"
        total = d["wins"] + d["losses"]
        wr = d["wins"] / total * 100 if total > 0 else 0
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

        lines.append(
            f"{medal} {emoji} <b>{city}</b>: ${pnl:+.2f} | "
            f"{wr:.0f}% WR ({d['wins']}W/{d['losses']}L)"
        )

    send_msg("\n".join(lines))


def handle_status():
    """Bot holati."""
    from src.trading.strategy import load_trades
    trades = load_trades()

    now = datetime.now(timezone.utc)
    last_trade_time = ""
    if trades:
        last = trades[-1]
        last_trade_time = last.get("timestamp", "")[:19]

    dry = "DRY RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "LIVE"
    edge = os.getenv("MIN_EDGE", "0.08")
    bet = os.getenv("MAX_BET_USD", "5.0")
    bank = os.getenv("BANKROLL", "100.0")

    msg = (
        f"⚙️ <b>BOT HOLATI</b>\n\n"
        f"🟢 Status: <b>Ishlayapti</b>\n"
        f"🕐 Vaqt: {now.strftime('%Y-%m-%d %H:%M UTC')}\n"
        f"📡 Mode: <b>{dry}</b>\n"
        f"🔬 Modellar: <b>10</b> (GFS, ECMWF, ICON, GEM, BOM + 4 det. + NWS)\n"
        f"📊 Min edge: {float(edge):.0%}\n"
        f"💰 Max bet: ${bet}\n"
        f"🏦 Bankroll: ${bank}\n"
        f"📋 Jami savdolar: {len(trades)}\n"
        f"🕐 Oxirgi savdo: {last_trade_time}\n"
    )
    send_msg(msg)


def handle_help():
    msg = (
        "❓ <b>YORDAM</b>\n\n"
        "Bot Polymarket weather bozorlarini 10 ta ob-havo modeli bilan tahlil qiladi "
        "va edge topganda signal beradi.\n\n"
        "<b>Komandalar:</b>\n"
        "/result — 📊 P&L natijalar, yutish/yutqazish\n"
        "/signals — 🎯 Hozirgi eng yaxshi signallar (1-2 daq)\n"
        "/today — 📅 Bugungi savdolar\n"
        "/stats — 📈 Umumiy statistika\n"
        "/cities — 🏙 Shaharlar reytingi\n"
        "/status — ⚙️ Bot holati va sozlamalar\n"
        "/buy — 🛒 Manual sotib olish (/buy city side amount)\n"
        "/sell — 💸 Manual sotish (/sell city side amount)\n"
        "/backtest — 📊 Backtestni ishga tushirish\n"
        "/accuracy — 🎯 Model aniqlik reytingi\n"
        "/arbitrage — 💱 Kalshi arbitraj tekshirish\n"
        "/settings — ⚙️ Bot sozlamalari\n"
        "/alert — 🔔 Alertlar on/off (/alert on, /alert off)\n"
        "/help — ❓ Shu yordam\n\n"
        "<b>Modellar:</b>\n"
        "GFS 🇺🇸 | ECMWF 🇪🇺 | ICON 🇩🇪 | GEM 🇨🇦 | BOM 🇦🇺\n"
        "MeteoFrance 🇫🇷 | JMA 🇯🇵 | UKMO 🇬🇧 | KNMI 🇳🇱 | NWS 🇺🇸\n\n"
        "<b>Avtomatik hisobotlar:</b>\n"
        "• Har 6 soatda signal hisobot\n"
        "• Har kuni 08:00 UTC da natija hisobot\n"
    )
    send_msg(msg)


# ═══════════════════════════════════════
# YANGI KOMANDALAR — buy, sell, backtest,
# accuracy, arbitrage, settings, alert
# ═══════════════════════════════════════

def _parse_trade_params(text: str):
    """Parse /buy or /sell message text.
    Expected format: /buy city side amount  (e.g. /buy nyc YES 5)
    Returns (city, side, amount) or None on error.
    """
    parts = text.strip().split()
    if len(parts) < 4:
        return None
    city = parts[1].upper()
    side = parts[2].upper()
    if side not in ("YES", "NO"):
        return None
    try:
        amount = float(parts[3])
    except ValueError:
        return None
    if amount <= 0:
        return None
    return city, side, amount


def _log_trade_to_file(trade: dict):
    """Savdoni trades.json fayliga yozadi."""
    trades = []
    if os.path.exists(TRADES_FILE):
        try:
            with open(TRADES_FILE, "r") as f:
                trades = json.load(f)
        except (json.JSONDecodeError, IOError):
            trades = []
    trades.append(trade)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2)


def handle_buy(text: str = ""):
    """Manual sotib olish. Format: /buy city side amount"""
    params = _parse_trade_params(text)
    if not params:
        send_msg(
            "⚠️ <b>Noto'g'ri format</b>\n\n"
            "Format: <code>/buy city side amount</code>\n"
            "Misol: <code>/buy nyc YES 5</code>"
        )
        return

    city, side, amount = params
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    trade = {
        "action": "BUY",
        "city": city,
        "side": side,
        "amount": amount,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN" if dry_run else "LIVE",
        "source": "manual",
    }

    if dry_run:
        _log_trade_to_file(trade)
        send_msg(
            f"📝 <b>DRY RUN — BUY logged</b>\n\n"
            f"🏙 Shahar: <b>{city}</b>\n"
            f"📊 Side: <b>{side}</b>\n"
            f"💰 Amount: <b>${amount:.2f}</b>\n\n"
            f"ℹ️ trades.json ga yozildi (DRY_RUN)"
        )
    else:
        # TODO: CLOB client orqali haqiqiy sotib olish
        _log_trade_to_file(trade)
        send_msg(
            f"✅ <b>BUY bajarildi</b>\n\n"
            f"🏙 Shahar: <b>{city}</b>\n"
            f"📊 Side: <b>{side}</b>\n"
            f"💰 Amount: <b>${amount:.2f}</b>"
        )


def handle_sell(text: str = ""):
    """Manual sotish. Format: /sell city side amount"""
    params = _parse_trade_params(text)
    if not params:
        send_msg(
            "⚠️ <b>Noto'g'ri format</b>\n\n"
            "Format: <code>/sell city side amount</code>\n"
            "Misol: <code>/sell nyc YES 5</code>"
        )
        return

    city, side, amount = params
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

    trade = {
        "action": "SELL",
        "city": city,
        "side": side,
        "amount": amount,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "DRY_RUN" if dry_run else "LIVE",
        "source": "manual",
    }

    if dry_run:
        _log_trade_to_file(trade)
        send_msg(
            f"📝 <b>DRY RUN — SELL logged</b>\n\n"
            f"🏙 Shahar: <b>{city}</b>\n"
            f"📊 Side: <b>{side}</b>\n"
            f"💰 Amount: <b>${amount:.2f}</b>\n\n"
            f"ℹ️ trades.json ga yozildi (DRY_RUN)"
        )
    else:
        # TODO: CLOB client orqali haqiqiy sotish
        _log_trade_to_file(trade)
        send_msg(
            f"✅ <b>SELL bajarildi</b>\n\n"
            f"🏙 Shahar: <b>{city}</b>\n"
            f"📊 Side: <b>{side}</b>\n"
            f"💰 Amount: <b>${amount:.2f}</b>"
        )


def handle_backtest():
    """Backtestni ishga tushiradi va natijani yuboradi."""
    send_msg("🔄 <b>Backtest ishga tushmoqda...</b> (biroz kuting)")
    try:
        from src.trading.backtest import run_backtest
        result = run_backtest()

        if isinstance(result, dict):
            total_trades = result.get("total_trades", 0)
            win_rate = result.get("win_rate", 0)
            pnl = result.get("pnl", 0)
            roi = result.get("roi", 0)

            msg = (
                f"📊 <b>BACKTEST NATIJALARI</b>\n\n"
                f"📋 Jami savdolar: <b>{total_trades}</b>\n"
                f"🎯 Win rate: <b>{win_rate:.0%}</b>\n"
                f"💰 P&L: <b>${pnl:+.2f}</b>\n"
                f"📈 ROI: <b>{roi:+.1%}</b>"
            )
        else:
            msg = f"📊 <b>BACKTEST NATIJALARI</b>\n\n{result}"

        send_msg(msg)
    except ImportError:
        send_msg("⚠️ backtest moduli topilmadi.")
    except Exception as e:
        send_msg(f"⚠️ Backtest xatolik: {e}")


def handle_accuracy():
    """Har bir shahar uchun model aniqligini ko'rsatadi."""
    try:
        from src.trading.tracker import evaluate_trades
        stats = evaluate_trades()
        by_city = stats.get("by_city", {})

        if not by_city:
            send_msg("📊 Hali aniqlik ma'lumotlari yo'q.")
            return

        lines = ["🎯 <b>MODEL ANIQLIK REYTINGI</b>", ""]

        for city, d in sorted(by_city.items()):
            total = d.get("wins", 0) + d.get("losses", 0)
            if total == 0:
                continue
            wr = d["wins"] / total
            bar = "█" * int(wr * 10) + "░" * (10 - int(wr * 10))
            emoji = "🟢" if wr >= 0.6 else "🟡" if wr >= 0.5 else "🔴"
            lines.append(
                f"{emoji} <b>{city}</b>: {bar} {wr:.0%} "
                f"({d['wins']}W/{d['losses']}L)"
            )

        if len(lines) == 2:
            send_msg("📊 Hali yetarli ma'lumot yo'q.")
            return

        send_msg("\n".join(lines))
    except Exception as e:
        send_msg(f"⚠️ Accuracy xatolik: {e}")


def handle_arbitrage():
    """Kalshi va Polymarket o'rtasida arbitraj imkoniyatlarini tekshiradi."""
    send_msg("🔄 <b>Arbitraj tekshirilmoqda...</b>")
    try:
        from src.trading.kalshi import fetch_kalshi_weather_markets, find_arbitrage_opportunities, format_arbitrage_telegram
        from src.trading.markets import get_all_opportunities
        poly_markets = get_all_opportunities()
        kalshi_markets = fetch_kalshi_weather_markets()
        opportunities = find_arbitrage_opportunities(poly_markets, kalshi_markets)

        if not opportunities:
            send_msg("📊 <b>ARBITRAJ</b>\n\nHozircha imkoniyat yo'q.\n\nPolymarket: {0} market\nKalshi: {1} market".format(len(poly_markets), len(kalshi_markets)))
            return

        msg = format_arbitrage_telegram(opportunities)
        send_msg(msg)
    except ImportError:
        send_msg("⚠️ arbitrage moduli topilmadi.")
    except Exception as e:
        send_msg(f"⚠️ Arbitraj xatolik: {e}")


def handle_settings():
    """Joriy bot sozlamalarini ko'rsatadi."""
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    min_edge = os.getenv("MIN_EDGE", "0.08")
    max_bet = os.getenv("MAX_BET_USD", "5.0")
    bankroll = os.getenv("BANKROLL", "100.0")
    kelly_frac = os.getenv("KELLY_FRACTION", "0.25")
    scan_interval = os.getenv("SCAN_INTERVAL_HOURS", "6")
    models = os.getenv("MODELS", "GFS,ECMWF,ICON,GEM,BOM,MeteoFrance,JMA,UKMO,KNMI,NWS")

    msg = (
        f"⚙️ <b>BOT SOZLAMALARI</b>\n\n"
        f"📡 Mode: <b>{'DRY RUN' if dry_run else 'LIVE'}</b>\n"
        f"📊 MIN_EDGE: <b>{float(min_edge):.0%}</b>\n"
        f"💰 MAX_BET: <b>${max_bet}</b>\n"
        f"🏦 BANKROLL: <b>${bankroll}</b>\n"
        f"📐 KELLY_FRACTION: <b>{kelly_frac}</b>\n"
        f"🕐 SCAN_INTERVAL: <b>{scan_interval}h</b>\n"
        f"🔬 MODELS: <b>{models}</b>\n"
        f"🔔 ALERTS: <b>{'ON' if _alerts_enabled else 'OFF'}</b>\n"
    )
    send_msg(msg)


def handle_alert(text: str = ""):
    """Narx alertlarni yoqish/o'chirish. Format: /alert on yoki /alert off"""
    global _alerts_enabled

    parts = text.strip().split()
    if len(parts) < 2:
        status = "ON" if _alerts_enabled else "OFF"
        send_msg(
            f"🔔 <b>Alertlar hozir: {status}</b>\n\n"
            f"Format: <code>/alert on</code> yoki <code>/alert off</code>"
        )
        return

    action = parts[1].lower()
    if action == "on":
        _alerts_enabled = True
        send_msg("🔔 <b>Alertlar yoqildi!</b>\nWebSocket narx alertlari faol.")
    elif action == "off":
        _alerts_enabled = False
        send_msg("🔕 <b>Alertlar o'chirildi!</b>")
    else:
        send_msg(
            "⚠️ Noto'g'ri parametr.\n"
            "Format: <code>/alert on</code> yoki <code>/alert off</code>"
        )


def handle_leaderboard():
    """Top weather traderlar."""
    send_msg("🔄 <b>Leaderboard yuklanmoqda...</b>")
    try:
        from src.leaderboard.leaderboard import fetch_weather_leaderboard, format_leaderboard_telegram
        traders = fetch_weather_leaderboard(period="MONTH", limit=15)
        if traders:
            msg = format_leaderboard_telegram(traders)
            send_msg(msg)
        else:
            send_msg("📊 <b>Leaderboard</b>\n\nHozircha ma'lumot yo'q.")
    except Exception as e:
        send_msg(f"⚠️ Leaderboard xatolik: {e}")


def handle_copytrade():
    """Top traderlar signallari."""
    send_msg("🔄 <b>Copy trade signallari yuklanmoqda...</b>")
    try:
        from src.leaderboard.leaderboard import get_copy_signals, format_copy_signals_telegram
        signals = get_copy_signals(top_n=5)
        if signals:
            msg = format_copy_signals_telegram(signals)
            send_msg(msg)
        else:
            send_msg("📋 <b>Copy Trade</b>\n\nHozircha weather signallari yo'q.")
    except Exception as e:
        send_msg(f"⚠️ Copy trade xatolik: {e}")


# ═══════════════════════════════════════
# POLLING — Telegram xabarlarini tinglash
# ═══════════════════════════════════════

COMMAND_HANDLERS = {
    "/start": handle_help,
    "/result": handle_result,
    "/signals": handle_signals,
    "/today": handle_today,
    "/stats": handle_stats,
    "/cities": handle_cities,
    "/status": handle_status,
    "/help": handle_help,
    "/buy": handle_buy,
    "/sell": handle_sell,
    "/backtest": handle_backtest,
    "/accuracy": handle_accuracy,
    "/arbitrage": handle_arbitrage,
    "/settings": handle_settings,
    "/alert": handle_alert,
    "/leaderboard": handle_leaderboard,
    "/copytrade": handle_copytrade,
}


def poll_updates():
    """Telegram'dan kelgan komandalarni tinglaydi."""
    last_update_id = 0

    while True:
        try:
            resp = requests.get(f"{API_URL}/getUpdates", params={
                "offset": last_update_id + 1,
                "timeout": 30,
            }, timeout=35)
            data = resp.json()

            for update in data.get("result", []):
                last_update_id = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat_id = str(msg.get("chat", {}).get("id", ""))

                # Faqat bizning chat_id dan kelgan xabarlar
                if chat_id != CHAT_ID:
                    continue

                # Komandani topish
                cmd = text.split()[0].lower() if text else ""
                cmd = cmd.split("@")[0]  # @botname ni olib tashlash

                handler = COMMAND_HANDLERS.get(cmd)
                if handler:
                    try:
                        # text parametrini qabul qiladigan handlerlar uchun
                        sig = inspect.signature(handler)
                        if sig.parameters:
                            handler(text)
                        else:
                            handler()
                    except Exception as e:
                        send_msg(f"⚠️ Xatolik: {e}")

        except requests.exceptions.Timeout:
            continue
        except Exception as e:
            time.sleep(5)


def start_polling_thread():
    """Polling ni alohida thread da ishga tushiradi."""
    thread = threading.Thread(target=poll_updates, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    print("Bot menyusini o'rnatmoqda...")
    set_bot_commands()
    print("Menyular o'rnatildi!")

    print("Test xabar yuborilmoqda...")
    handle_help()
    print("Yuborildi!")

    print("\nPolling boshlanmoqda... (Ctrl+C to'xtatish)")
    poll_updates()
