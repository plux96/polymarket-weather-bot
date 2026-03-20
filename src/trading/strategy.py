"""
Multi-model savdo strategiyasi.
10 ta ob-havo modeli: GFS, ECMWF, ICON, GEM, BOM + MeteoFrance, JMA, UKMO, KNMI + NWS.
3+ model consensus bo'lganda savdo qiladi.
"""

import json
import os
from datetime import datetime, timezone
from src.weather.models import fetch_all_models, multi_model_probability
from src.trading.markets import fetch_weather_events, parse_weather_event, CITY_COORDS

TRADES_FILE = "storage/trades.json"


def load_trades() -> list[dict]:
    if os.path.exists(TRADES_FILE):
        with open(TRADES_FILE) as f:
            return json.load(f)
    return []


def save_trade(trade: dict):
    trades = load_trades()
    trades.append(trade)
    with open(TRADES_FILE, "w") as f:
        json.dump(trades, f, indent=2, default=str)


def kelly_size(prob: float, price: float, bankroll: float,
               fraction: float = 0.15, max_pct: float = 0.05) -> float:
    if price <= 0 or price >= 1 or prob <= 0:
        return 0
    b = (1.0 / price) - 1.0
    if b <= 0:
        return 0
    q = 1.0 - prob
    kelly = (b * prob - q) / b
    if kelly <= 0:
        return 0
    size = kelly * fraction * bankroll
    return min(size, bankroll * max_pct)


def analyze_market(market: dict, all_data: dict,
                   min_edge: float = 0.20, min_consensus: int = 5) -> dict | None:
    """
    10 ta model bilan bitta market bucket'ini tahlil qiladi.

    min_consensus: kamida nechta model rozi bo'lishi kerak (default: 3)
    """
    date_str = market.get("date")
    if not date_str:
        return None

    yes_price = market.get("yes_price", 0)
    if not yes_price or yes_price <= 0.01:
        return None

    # 10 model ehtimollik
    result = multi_model_probability(
        all_data, date_str,
        market["temp_low"], market["temp_high"],
        unit=market.get("unit", "C"),
    )

    if "error" in result or result.get("total_members", 0) == 0:
        return None

    model_prob = result["weighted_probability"]
    consensus_count = result["models_agreeing"]
    total_models = result["total_models"]
    confidence = result["confidence"]
    no_price = market.get("no_price", 1 - yes_price)

    # Edge hisoblash
    yes_edge = model_prob - yes_price
    no_edge = (1 - model_prob) - no_price

    if yes_edge >= no_edge and yes_edge >= min_edge:
        side = "YES"
        edge = yes_edge
        price = yes_price
        prob = model_prob
    elif no_edge >= min_edge:
        side = "NO"
        edge = no_edge
        price = no_price
        prob = 1 - model_prob
    else:
        return None

    # Consensus filter — kamida min_consensus model rozi bo'lishi kerak
    # YES uchun: nechta model bu oraliqda ehtimollik yuqori ko'rsatadi
    # NO uchun: nechta model bu oraliqda ehtimollik past ko'rsatadi
    if side == "YES":
        agreeing = sum(1 for m in result.get("per_model", []) if m["probability"] >= 0.3)
    else:
        agreeing = sum(1 for m in result.get("per_model", []) if m["probability"] <= 0.3)

    if agreeing < min_consensus and edge < 0.30:
        return None

    # Confidence bonus — yuqori consensus bo'lsa Kelly fraksiyasini oshiramiz
    confidence_multiplier = 1.0
    if confidence >= 0.8:
        confidence_multiplier = 1.5
    elif confidence >= 0.6:
        confidence_multiplier = 1.2

    return {
        "market_id": market["market_id"],
        "condition_id": market["condition_id"],
        "clob_token": market["clob_token_yes"] if side == "YES" else market["clob_token_no"],
        "question": market["question"],
        "event_title": market["event_title"],
        "city": market["city"],
        "date": date_str,
        "unit": market["unit"],
        "temp_low": market["temp_low"],
        "temp_high": market["temp_high"],
        "side": side,
        "model_prob": round(prob, 4),
        "market_price": round(price, 4),
        "edge": round(edge, 4),
        "consensus": result["consensus"],
        "confidence": confidence,
        "spread": result["spread"],
        "total_members": result["total_members"],
        "members_in_range": result["members_in_range"],
        "mean_high": round(result.get("mean_high", 0), 1),
        "confidence_multiplier": confidence_multiplier,
        "per_model_summary": ", ".join(
            f"{m['model']}:{m['probability']:.0%}"
            for m in result.get("per_model", [])
        ),
    }


def scan_all_opportunities(min_edge: float = 0.20, bankroll: float = 500.0,
                           max_bet: float = 1.0, min_consensus: int = 5) -> list[dict]:
    """
    Barcha weather bozorlarni 6 ta model bilan skanerlaydi.
    """
    print("  Bozorlarni yuklamoqda...")
    events = fetch_weather_events()
    print(f"  {len(events)} ta event topildi")

    all_markets = []
    for event in events:
        parsed = parse_weather_event(event)
        all_markets.extend(parsed)
    print(f"  {len(all_markets)} ta bucket parse qilindi")

    # Qaysi shaharlar va unit kerakligini aniqlaymiz
    city_units = {}
    for m in all_markets:
        city = m["city"]
        unit = m["unit"]
        if city not in city_units:
            city_units[city] = unit

    # 10 ta model yuklaymiz (shahar boshiga)
    city_data = {}
    for city, unit in city_units.items():
        if city in CITY_COORDS:
            print(f"  {city} — 10 model yuklanmoqda ({unit})...", end=" ", flush=True)
            all_data = fetch_all_models(city, unit=unit)
            if all_data:
                city_data[city] = all_data
                print(f"{all_data['total_models']} model, {all_data['total_ensemble_members']} ens.member")
            else:
                print("xatolik!")

    # Har bir bucket'ni tahlil qilamiz
    signals = []
    for market in all_markets:
        data = city_data.get(market["city"])
        if not data:
            continue

        signal = analyze_market(market, data, min_edge, min_consensus)
        if signal:
            # Kelly sizing — confidence bonus bilan
            base_bet = kelly_size(signal["model_prob"], signal["market_price"], bankroll)
            bet = base_bet * signal["confidence_multiplier"]
            bet = min(bet, max_bet)
            if bet >= 0.10:
                signal["bet_size"] = round(bet, 2)
                signals.append(signal)

    signals.sort(key=lambda x: (x["confidence"], x["edge"]), reverse=True)
    return signals


if __name__ == "__main__":
    from rich.table import Table
    from rich.console import Console

    console = Console()
    console.print("[bold]Multi-model scan boshlanmoqda (6 ta model)...[/]\n")

    signals = scan_all_opportunities(min_edge=0.08, bankroll=100.0, max_bet=5.0)

    if not signals:
        console.print("[yellow]Signal topilmadi.[/]")
    else:
        table = Table(title=f"SIGNALLAR — {len(signals)} ta ({len(MODELS)} model)")
        table.add_column("#", style="dim")
        table.add_column("Shahar", style="cyan")
        table.add_column("Sana")
        table.add_column("Harorat", style="yellow")
        table.add_column("Side", style="bold")
        table.add_column("Prob", style="green")
        table.add_column("Market", style="red")
        table.add_column("EDGE", style="bold magenta")
        table.add_column("Consensus", style="cyan")
        table.add_column("Conf", style="bold")
        table.add_column("Bet $", style="bold green")
        table.add_column("Models")

        for i, s in enumerate(signals[:30], 1):
            unit = "°" + s["unit"]
            tl, th = s["temp_low"], s["temp_high"]
            if tl == -999:
                temp = f"<={th-1}{unit}"
            elif th == 999:
                temp = f">={tl}{unit}"
            else:
                temp = f"{tl}-{th-1}{unit}"

            conf_color = "green" if s["confidence"] >= 0.7 else "yellow" if s["confidence"] >= 0.4 else "red"

            table.add_row(
                str(i), s["city"], s["date"], temp,
                f"[{'green' if s['side']=='YES' else 'red'}]{s['side']}[/]",
                f"{s['model_prob']:.0%}",
                f"${s['market_price']:.3f}",
                f"[bold]{s['edge']:.0%}[/]",
                s["consensus"],
                f"[{conf_color}]{s['confidence']:.0%}[/{conf_color}]",
                f"${s['bet_size']:.2f}",
                s["per_model_summary"][:40],
            )

        console.print(table)
