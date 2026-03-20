"""
Natija tracker — resolved bozorlarni tekshiradi va P&L hisoblaydi.
Har kuni Telegram'ga kunlik hisobot yuboradi.
"""

import json
import os
import requests
from datetime import datetime, timezone, timedelta
from src.trading.strategy import load_trades, TRADES_FILE

GAMMA_API = "https://gamma-api.polymarket.com"
RESULTS_FILE = "storage/results.json"


def load_results() -> list[dict]:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []


def save_results(results: list[dict]):
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)


def check_market_resolution(market_id: str) -> dict | None:
    """
    Polymarket'da bozor resolve bo'lganmi tekshiradi.
    Qaytaradi: {"resolved": True, "outcome": "Yes"/"No", "winning_price": 1.0}
    """
    try:
        resp = requests.get(f"{GAMMA_API}/markets/{market_id}", timeout=10)
        resp.raise_for_status()
        market = resp.json()
    except requests.RequestException:
        return None

    closed = market.get("closed", False)
    resolved = market.get("resolved", False)

    if not closed and not resolved:
        return {"resolved": False}

    # Winning outcome
    outcomes = market.get("outcomes", "[]")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = []

    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            prices = []

    # Resolve bo'lganda — yutgan tomon narxi 1.0 ga yaqin bo'ladi
    winning_outcome = None
    if prices:
        for i, price in enumerate(prices):
            p = float(price)
            if p >= 0.95:  # ~1.0 = yutgan
                if i < len(outcomes):
                    winning_outcome = outcomes[i]
                break

    # Agar narxdan aniqlab bo'lmasa — resolution source'dan
    if not winning_outcome:
        resolution = market.get("resolutionSource", "")
        if "yes" in str(market.get("resolution", "")).lower():
            winning_outcome = "Yes"
        elif "no" in str(market.get("resolution", "")).lower():
            winning_outcome = "No"

    return {
        "resolved": True,
        "outcome": winning_outcome,
        "question": market.get("question", ""),
    }


def evaluate_trades() -> dict:
    """
    Barcha savdolarni tekshiradi — qaysilari yutgan, qaysilari yutqazgan.

    Qaytaradi:
    {
        "total_trades": 100,
        "resolved": 60,
        "pending": 40,
        "wins": 45,
        "losses": 15,
        "win_rate": 0.75,
        "total_bet": 300.0,
        "total_pnl": 45.50,
        "roi": 0.15,
        "by_date": {"2026-03-19": {"wins": 10, "losses": 3, ...}},
        "by_city": {"nyc": {"wins": 5, "losses": 1, ...}},
    }
    """
    trades = load_trades()
    results = load_results()

    # Allaqachon tekshirilgan market_id lar
    checked = {r["market_id"]: r for r in results}

    # Unique market_id larni topamiz (API chaqiruvlarni kamaytirish)
    unique_mids = set()
    for trade in trades:
        mid = trade.get("market_id")
        if mid and mid not in checked:
            unique_mids.add(str(mid))

    # Har bir unique market_id ni faqat 1 marta tekshiramiz
    # Max 20 ta API chaqiruv (tezlik uchun)
    resolutions = {}
    for mid in list(unique_mids)[:20]:
        resolution = check_market_resolution(mid)
        if resolution:
            resolutions[mid] = resolution

    new_results = []
    for trade in trades:
        mid = trade.get("market_id")
        if not mid or mid in checked:
            continue

        resolution = resolutions.get(str(mid))
        if not resolution or not resolution.get("resolved"):
            continue

        result = {
            "market_id": mid,
            "trade": trade,
            "outcome": resolution.get("outcome"),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

        # Yutgan yoki yutqazgan?
        side = trade.get("side", "")
        outcome = resolution.get("outcome", "")

        if side.upper() == outcome.upper():
            result["won"] = True
            price = trade.get("market_price", 0)
            bet = trade.get("bet_size", 0)
            result["pnl"] = round(bet * (1.0 / price - 1), 2) if price > 0 else 0
        elif outcome:
            result["won"] = False
            result["pnl"] = -trade.get("bet_size", 0)
        else:
            result["won"] = None
            result["pnl"] = 0

        new_results.append(result)
        checked[mid] = result

    # Yangi natijalarni saqlash
    if new_results:
        all_results = results + new_results
        save_results(all_results)

    # Statistika hisoblash
    all_results = load_results()

    stats = {
        "total_trades": len(trades),
        "resolved": 0,
        "pending": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0,
        "total_bet": 0,
        "total_pnl": 0,
        "roi": 0,
        "by_date": {},
        "by_city": {},
    }

    for r in all_results:
        stats["resolved"] += 1
        trade = r.get("trade", {})
        date = trade.get("date", "unknown")
        city = trade.get("city", "unknown")
        bet = trade.get("bet_size", 0)
        pnl = r.get("pnl", 0)
        won = r.get("won")

        stats["total_bet"] += bet
        stats["total_pnl"] += pnl

        if won is True:
            stats["wins"] += 1
        elif won is False:
            stats["losses"] += 1

        # By date
        if date not in stats["by_date"]:
            stats["by_date"][date] = {"wins": 0, "losses": 0, "pnl": 0, "bets": 0}
        stats["by_date"][date]["pnl"] += pnl
        stats["by_date"][date]["bets"] += bet
        if won is True:
            stats["by_date"][date]["wins"] += 1
        elif won is False:
            stats["by_date"][date]["losses"] += 1

        # By city
        if city not in stats["by_city"]:
            stats["by_city"][city] = {"wins": 0, "losses": 0, "pnl": 0}
        stats["by_city"][city]["pnl"] += pnl
        if won is True:
            stats["by_city"][city]["wins"] += 1
        elif won is False:
            stats["by_city"][city]["losses"] += 1

    stats["pending"] = stats["total_trades"] - stats["resolved"]
    total_decided = stats["wins"] + stats["losses"]
    stats["win_rate"] = stats["wins"] / total_decided if total_decided > 0 else 0
    stats["roi"] = stats["total_pnl"] / stats["total_bet"] if stats["total_bet"] > 0 else 0

    return stats


def format_daily_pnl(stats: dict) -> str:
    """Kunlik P&L xabarini formatlaydi."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"📊 <b>KUNLIK NATIJA</b>",
        f"📅 {now}",
        "",
    ]

    if stats["resolved"] == 0:
        lines.append("⏳ Hali hech bir bozor resolve bo'lmagan.")
        lines.append(f"📋 Kutilmoqda: {stats['pending']} ta savdo")
        return "\n".join(lines)

    # Umumiy
    pnl = stats["total_pnl"]
    pnl_emoji = "🟢" if pnl >= 0 else "🔴"
    lines.extend([
        f"{pnl_emoji} <b>Umumiy P&L: ${pnl:+.2f}</b>",
        f"📈 ROI: <b>{stats['roi']:+.1%}</b>",
        f"🎯 Win rate: <b>{stats['win_rate']:.0%}</b> ({stats['wins']}W / {stats['losses']}L)",
        f"📋 Resolved: {stats['resolved']} / {stats['total_trades']}",
        f"⏳ Kutilmoqda: {stats['pending']}",
        "",
    ])

    # Kunlar bo'yicha
    by_date = stats.get("by_date", {})
    if by_date:
        lines.append("<b>📅 Kunlik:</b>")
        for date in sorted(by_date.keys(), reverse=True)[:7]:
            d = by_date[date]
            day_pnl = d["pnl"]
            emoji = "🟢" if day_pnl >= 0 else "🔴"
            lines.append(
                f"  {emoji} {date}: <b>${day_pnl:+.2f}</b> "
                f"({d['wins']}W/{d['losses']}L)"
            )
        lines.append("")

    # Shaharlar bo'yicha
    by_city = stats.get("by_city", {})
    if by_city:
        lines.append("<b>🏙 Shaharlar:</b>")
        sorted_cities = sorted(by_city.items(), key=lambda x: x[1]["pnl"], reverse=True)
        for city, d in sorted_cities[:8]:
            c_pnl = d["pnl"]
            emoji = "🟢" if c_pnl >= 0 else "🔴"
            lines.append(f"  {emoji} {city}: ${c_pnl:+.2f} ({d['wins']}W/{d['losses']}L)")

    return "\n".join(lines)


if __name__ == "__main__":
    from rich import print as rprint

    rprint("[bold]Natijalarni tekshirmoqda...[/]\n")
    stats = evaluate_trades()

    rprint(f"Jami savdolar: {stats['total_trades']}")
    rprint(f"Resolved: {stats['resolved']}")
    rprint(f"Pending: {stats['pending']}")
    rprint(f"Wins: {stats['wins']}")
    rprint(f"Losses: {stats['losses']}")
    rprint(f"Win rate: {stats['win_rate']:.0%}")
    rprint(f"Total P&L: ${stats['total_pnl']:+.2f}")
    rprint(f"ROI: {stats['roi']:+.1%}")
