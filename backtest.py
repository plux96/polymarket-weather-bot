"""
Backtest — resolved bozorlarni Polymarket natijasi bilan solishtiradi.

Mantiq:
- Resolved eventdan HAQIQIY yutgan bucket'ni olamiz
- Historical forecast API dan o'sha kundagi prognoz high'ni olamiz
- Har bir bucket uchun: bot YES/NO degan bo'lardimi?
- Haqiqiy natija bilan solishtirish → Win/Loss/P&L
"""

import json
import re
import requests
from datetime import datetime, timezone
from markets import CITY_COORDS, extract_city, extract_temp_range
from telegram_bot import send_message

GAMMA_API = "https://gamma-api.polymarket.com"
HISTORICAL_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"

# Ko'p modellardan historical daily high olish
HIST_MODELS = ["gfs_seamless", "ecmwf_ifs025", "icon_seamless", "gem_global"]


def fetch_resolved_events(limit: int = 30) -> list[dict]:
    resp = requests.get(f"{GAMMA_API}/events", params={
        "limit": limit, "tag_slug": "weather",
        "closed": "true", "order": "endDate", "ascending": "false",
    }, timeout=15)
    return resp.json()


def get_historical_highs(city_key: str, date_str: str, unit: str = "C") -> list[float]:
    """Ko'p modellardan o'sha kundagi prognoz daily high larni oladi."""
    coords = CITY_COORDS.get(city_key)
    if not coords:
        return []

    temp_unit = "fahrenheit" if unit == "F" else "celsius"
    highs = []

    for model in HIST_MODELS:
        try:
            resp = requests.get(HISTORICAL_URL, params={
                "latitude": coords["lat"], "longitude": coords["lon"],
                "daily": "temperature_2m_max",
                "start_date": date_str, "end_date": date_str,
                "models": model, "temperature_unit": temp_unit,
            }, timeout=10)
            data = resp.json()
            h = data.get("daily", {}).get("temperature_2m_max", [None])[0]
            if h is not None:
                highs.append(h)
        except Exception:
            pass

    return highs


def backtest_event(event: dict) -> dict | None:
    """Bitta resolved event uchun backtest."""
    title = event.get("title", "")
    markets = event.get("markets", [])

    if "temperature" not in title.lower() and "highest" not in title.lower():
        return None

    city = extract_city(title)
    if city == "unknown" or city not in CITY_COORDS:
        return None

    # Unit
    sample_q = markets[0].get("question", "") if markets else ""
    unit = "F" if "°F" in sample_q else "C"

    # Sana
    end_date = event.get("endDate", "")[:10]
    date_str = end_date
    months = {"january":"01","february":"02","march":"03","april":"04","may":"05","june":"06",
              "july":"07","august":"08","september":"09","october":"10","november":"11","december":"12"}
    for mname, mnum in months.items():
        match = re.search(rf'{mname}\s+(\d{{1,2}})', title, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            year = end_date[:4] if end_date else "2026"
            date_str = f"{year}-{mnum}-{day:02d}"
            break

    # Yutgan bucket'ni topish
    winner_idx = None
    for i, m in enumerate(markets):
        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                continue
        if prices and float(prices[0]) >= 0.95:
            winner_idx = i
            break

    if winner_idx is None:
        return None

    winner_q = markets[winner_idx].get("question", "")

    # Historical prognoz high'larni olamiz
    hist_highs = get_historical_highs(city, date_str, unit)
    if not hist_highs:
        return None

    # Har bir bucket uchun: model nima degan bo'lardi
    trades = []
    for m in markets:
        question = m.get("question", "")
        temp_range = extract_temp_range(question, unit)
        if not temp_range:
            continue

        # Nechta model shu bucket'da degan
        in_range = sum(1 for h in hist_highs if temp_range["low"] <= h < temp_range["high"])
        model_prob = in_range / len(hist_highs)

        # Haqiqiy natija — shu bucket yutganmi?
        this_is_winner = (question == winner_q)

        # Bot savdo qilardimi?
        # YES savdo: model_prob yuqori, lekin bozor past narxda (edge bor)
        # Backtest uchun: agar model_prob >= 0.5 → YES deb hisoblaymiz
        if model_prob >= 0.5:
            side = "YES"
            won = this_is_winner
            # Estimated price — kam narxda bo'lgandek hisoblaymiz
            est_price = max(0.10, model_prob - 0.15)
            bet = 2.0
            pnl = round(bet * (1/est_price - 1), 2) if won else -bet
        elif model_prob == 0:
            # Model bu bucket'da emas deydi — NO savdo
            # Faqat agar bozor narxi yuqori bo'lsa (edge)
            side = "NO"
            won = not this_is_winner
            est_price = 0.20
            bet = 2.0
            pnl = round(bet * (1/est_price - 1), 2) if won else -bet
        else:
            continue  # Noaniq — savdo yo'q

        trades.append({
            "question": question[:55],
            "temp_range": temp_range,
            "side": side,
            "model_prob": model_prob,
            "is_winner": this_is_winner,
            "won": won,
            "bet": bet,
            "pnl": pnl,
        })

    if not trades:
        return None

    wins = sum(1 for t in trades if t["won"])
    losses = sum(1 for t in trades if not t["won"])
    pnl = sum(t["pnl"] for t in trades)

    return {
        "city": city,
        "date": date_str,
        "title": title,
        "winner": winner_q[:55],
        "hist_highs": [round(h, 1) for h in hist_highs],
        "models_used": len(hist_highs),
        "trades": trades,
        "trade_count": len(trades),
        "wins": wins,
        "losses": losses,
        "win_rate": wins / (wins + losses) if (wins + losses) else 0,
        "pnl": round(pnl, 2),
    }


def run_backtest(limit: int = 30, send_telegram: bool = True):
    """To'liq backtest."""
    print("Resolved bozorlarni yuklamoqda...")
    events = fetch_resolved_events(limit)
    print(f"{len(events)} ta event")

    results = []
    for event in events:
        parsed = backtest_event(event)
        if not parsed:
            continue

        e = "✅" if parsed["pnl"] >= 0 else "❌"
        print(f"  {e} {parsed['city']} {parsed['date']} | "
              f"{parsed['wins']}W/{parsed['losses']}L = ${parsed['pnl']:+.2f} | "
              f"Highs: {parsed['hist_highs']}")
        results.append(parsed)

    if not results:
        print("Backtest uchun yetarli ma'lumot yo'q.")
        return

    # Umumiy
    total_trades = sum(r["trade_count"] for r in results)
    total_wins = sum(r["wins"] for r in results)
    total_losses = sum(r["losses"] for r in results)
    total_pnl = sum(r["pnl"] for r in results)
    total_bet = total_trades * 2.0
    wr = total_wins / (total_wins + total_losses) if (total_wins + total_losses) else 0
    roi = total_pnl / total_bet if total_bet > 0 else 0

    print(f"\n{'='*55}")
    print(f"  BACKTEST NATIJA — {len(results)} event, {total_trades} savdo")
    print(f"{'='*55}")
    print(f"  Win rate: {wr:.0%} ({total_wins}W / {total_losses}L)")
    print(f"  P&L:     ${total_pnl:+.2f}")
    print(f"  ROI:     {roi:+.1%}")
    print(f"{'='*55}")

    if send_telegram:
        pnl_e = "🟢" if total_pnl >= 0 else "🔴"
        lines = [
            "🔬 <b>BACKTEST NATIJASI</b>",
            f"📅 Oxirgi {len(results)} ta resolved event",
            "",
            f"{pnl_e} <b>P&L: ${total_pnl:+.2f}</b>",
            f"📈 ROI: <b>{roi:+.1%}</b>",
            f"🎯 Win rate: <b>{wr:.0%}</b> ({total_wins}W / {total_losses}L)",
            f"📋 Savdolar: {total_trades} (har biri $2)",
            "",
            "<b>Batafsil:</b>",
            "",
        ]

        for r in results:
            e = "🟢" if r["pnl"] >= 0 else "🔴"
            lines.append(
                f"{e} <b>{r['city']}</b> {r['date']} "
                f"| ${r['pnl']:+.2f} ({r['wins']}W/{r['losses']}L)"
            )
            lines.append(f"   🏆 {r['winner']}")
            lines.append(f"   📊 Modellar: {r['hist_highs']}")
            lines.append("")

        send_message("\n".join(lines))
        print("Telegram'ga yuborildi!")

    return results


if __name__ == "__main__":
    run_backtest(limit=30, send_telegram=True)
