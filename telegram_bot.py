"""
Telegram notification moduli.
Signallar va natijalarni Telegram'ga yuboradi.
"""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """Telegram'ga xabar yuboradi."""
    if not BOT_TOKEN or not CHAT_ID:
        print("  Telegram sozlanmagan (token/chat_id yo'q)")
        return False

    try:
        resp = requests.post(f"{API_URL}/sendMessage", json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }, timeout=10)
        resp.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  Telegram xatosi: {e}")
        return False


def format_signals_message(signals: list[dict]) -> str:
    """Signallar ro'yxatini Telegram formatlaydi."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not signals:
        return f"🌤 <b>Weather Bot Scan</b>\n📅 {now}\n\n😐 Signal topilmadi."

    # Top 15 signal
    top = signals[:15]
    total_bet = sum(s.get("bet_size", 0) for s in signals)
    avg_edge = sum(s["edge"] for s in signals) / len(signals)

    lines = [
        f"🌤 <b>Weather Bot Scan</b>",
        f"📅 {now}",
        f"📊 <b>{len(signals)}</b> ta signal | O'rtacha edge: <b>{avg_edge:.0%}</b>",
        f"💰 Jami bet: <b>${total_bet:.2f}</b>",
        "",
        "🎯 <b>TOP signallar:</b>",
        "",
    ]

    for i, s in enumerate(top, 1):
        unit = "°" + s.get("unit", "F")
        tl, th = s["temp_low"], s["temp_high"]
        if tl == -999:
            temp = f"≤{th-1}{unit}"
        elif th == 999:
            temp = f"≥{tl}{unit}"
        else:
            temp = f"{tl}-{th-1}{unit}"

        side_emoji = "🟢" if s["side"] == "YES" else "🔴"
        consensus = s.get("consensus", "?/?")
        conf = s.get("confidence", 0)
        conf_emoji = "🔥" if conf >= 0.7 else "⚡" if conf >= 0.4 else "⚠️"
        lines.append(
            f"{i}. {side_emoji} <b>{s['city']}</b> {temp} "
            f"| Edge: <b>{s['edge']:.0%}</b> "
            f"| {s['model_prob']:.0%} vs ${s['market_price']:.2f} "
            f"| {conf_emoji} {consensus} "
            f"| ${s['bet_size']:.2f}"
        )

    return "\n".join(lines)


def format_daily_summary(signals: list[dict], trades: list[dict]) -> str:
    """Kunlik xulosa xabarini formatlaydi."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Bugungi savdolar
    today_trades = [t for t in trades if t.get("timestamp", "").startswith(now)]

    # Shaharlar statistikasi
    cities = {}
    for s in signals:
        c = s.get("city", "?")
        cities[c] = cities.get(c, 0) + 1

    top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:5]

    total_bet = sum(s.get("bet_size", 0) for s in signals)
    avg_edge = sum(s["edge"] for s in signals) / len(signals) if signals else 0

    lines = [
        f"📋 <b>KUNLIK XULOSA</b> — {now}",
        "",
        f"📊 Signallar: <b>{len(signals)}</b>",
        f"💰 Jami bet: <b>${total_bet:.2f}</b>",
        f"📈 O'rtacha edge: <b>{avg_edge:.0%}</b>",
        f"🔄 Bugungi savdolar: <b>{len(today_trades)}</b>",
        "",
        "🏙 Top shaharlar:",
    ]

    for city, count in top_cities:
        lines.append(f"  • {city}: {count} ta signal")

    lines.append(f"\n⚙️ Mode: {'DRY RUN' if os.getenv('DRY_RUN', 'true').lower() == 'true' else 'LIVE'}")

    return "\n".join(lines)


def send_signals(signals: list[dict]) -> bool:
    """Signallarni Telegram'ga yuboradi."""
    msg = format_signals_message(signals)
    return send_message(msg)


def send_daily_summary(signals: list[dict], trades: list[dict]) -> bool:
    """Kunlik xulosani yuboradi."""
    msg = format_daily_summary(signals, trades)
    return send_message(msg)


def send_startup_message() -> bool:
    """Bot ishga tushganini xabar beradi."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    dry = "DRY RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "LIVE"
    msg = (
        f"🚀 <b>Weather Bot ishga tushdi!</b>\n"
        f"📅 {now}\n"
        f"⚙️ Mode: <b>{dry}</b>\n"
        f"🔄 Har 15 daqiqada scan\n"
        f"📬 Har 6 soatda hisobot"
    )
    return send_message(msg)


if __name__ == "__main__":
    print("Telegram test xabar yuborilmoqda...")
    ok = send_message("✅ <b>Polymarket Weather Bot</b> ulandi!\n\nTest xabar muvaffaqiyatli yuborildi.")
    if ok:
        print("Yuborildi!")
    else:
        print("Xatolik!")
