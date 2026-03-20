"""
Kalshi va Polymarket o'rtasida arbitraj imkoniyatlarini topish moduli.
Kalshi weather bozorlarini API orqali oladi, Polymarket bozorlari bilan solishtirib,
narx farqlari (arbitraj) ni aniqlaydi.
"""

import re
import requests
from datetime import datetime, timezone

KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"

# Kalshi temperature series ticker'lari
KALSHI_SERIES_TICKERS = [
    "KXHIGH",       # Daily high temperature
    "KXHIGHNY",     # NYC high
    "KXHIGHCHI",    # Chicago high
    "KXHIGHLA",     # LA high
    "KXHIGHDAL",    # Dallas high
    "KXHIGHMIA",    # Miami high
    "KXHIGHATL",    # Atlanta high
]

# Kalshi ticker -> shahar nomi (Polymarket formatida)
KALSHI_CITY_MAP = {
    "KXHIGH": "nyc",
    "KXHIGHNY": "nyc",
    "KXHIGHCHI": "chicago",
    "KXHIGHLA": "los_angeles",
    "KXHIGHDAL": "dallas",
    "KXHIGHMIA": "miami",
    "KXHIGHATL": "atlanta",
    # Ticker ichidagi shahar nomlari uchun fallback
    "NYC": "nyc", "NY": "nyc", "NEWYORK": "nyc",
    "CHI": "chicago", "CHICAGO": "chicago",
    "LA": "los_angeles", "LOSANGELES": "los_angeles",
    "DAL": "dallas", "DALLAS": "dallas",
    "MIA": "miami", "MIAMI": "miami",
    "ATL": "atlanta", "ATLANTA": "atlanta",
    "LONDON": "london",
    "PARIS": "paris",
    "TOKYO": "tokyo",
    "TORONTO": "toronto",
}


def fetch_kalshi_weather_markets(series_tickers: list[str] | None = None) -> list[dict]:
    """
    Kalshi API'dan aktiv weather/temperature bozorlarini oladi.
    Auth kerak emas — public data.

    Returns:
        Har bir market uchun dict:
        - ticker, title, city, date, temp_low, temp_high, unit
        - yes_price, no_price, volume, status
    """
    if series_tickers is None:
        series_tickers = KALSHI_SERIES_TICKERS

    all_markets = []

    for series_ticker in series_tickers:
        try:
            markets = _fetch_series_markets(series_ticker)
            all_markets.extend(markets)
        except requests.RequestException as e:
            print(f"Kalshi API xatosi ({series_ticker}): {e}")
        except Exception as e:
            print(f"Kalshi parse xatosi ({series_ticker}): {e}")

    return all_markets


def _fetch_series_markets(series_ticker: str) -> list[dict]:
    """Bitta series ticker uchun barcha aktiv marketlarni oladi."""
    markets = []
    cursor = None

    while True:
        params = {
            "series_ticker": series_ticker,
            "status": "open",
            "limit": 200,
        }
        if cursor:
            params["cursor"] = cursor

        resp = requests.get(
            f"{KALSHI_API_BASE}/markets",
            params=params,
            timeout=15,
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

        batch = data.get("markets", [])
        if not batch:
            break

        for raw in batch:
            parsed = _parse_kalshi_market(raw, series_ticker)
            if parsed:
                markets.append(parsed)

        # Pagination
        cursor = data.get("cursor")
        if not cursor or len(batch) < 200:
            break

    return markets


def _parse_kalshi_market(raw: dict, series_ticker: str) -> dict | None:
    """
    Bitta Kalshi market ma'lumotini parse qiladi.

    Kalshi market tuzilishi:
    - ticker: "KXHIGH-26MAR21-T55" (series-date-threshold)
    - title/subtitle: "Will the high temperature in NYC be 55°F or above on March 21?"
    - yes_price / no_price: 0-100 (cents) yoki 0-1.0
    """
    ticker = raw.get("ticker", "")
    title = raw.get("title", "") or raw.get("subtitle", "")
    status = raw.get("status", "")

    if status not in ("open", "active", ""):
        return None

    # Shahar aniqlash
    city = _extract_kalshi_city(ticker, title, series_ticker)
    if not city:
        return None

    # Sana aniqlash
    date_str = _extract_kalshi_date(raw)
    if not date_str:
        return None

    # Harorat oralig'ini aniqlash
    temp_range = _extract_kalshi_temp_range(ticker, title)
    if not temp_range:
        return None

    # Narxlarni olish (Kalshi 0-100 cents yoki 0-1.0 formatda bo'lishi mumkin)
    yes_price = _normalize_price(raw.get("yes_ask", 0) or raw.get("last_price", 0))
    no_price = _normalize_price(raw.get("no_ask", 0))

    # Agar no_price yo'q bo'lsa, hisoblash
    if no_price <= 0 and yes_price > 0:
        no_price = round(1.0 - yes_price, 4)

    # yes_bid/no_bid ham foydali
    yes_bid = _normalize_price(raw.get("yes_bid", 0))
    no_bid = _normalize_price(raw.get("no_bid", 0))

    volume = raw.get("volume", 0) or 0

    return {
        "source": "kalshi",
        "ticker": ticker,
        "title": title,
        "city": city,
        "date": date_str,
        "temp_low": temp_range["low"],
        "temp_high": temp_range["high"],
        "unit": temp_range.get("unit", "F"),
        "yes_price": yes_price,
        "no_price": no_price,
        "yes_bid": yes_bid,
        "no_bid": no_bid,
        "volume": volume,
        "status": status,
    }


def _extract_kalshi_city(ticker: str, title: str, series_ticker: str) -> str | None:
    """Kalshi market'dan shahar nomini ajratadi."""
    # 1) Series ticker bo'yicha
    if series_ticker in KALSHI_CITY_MAP:
        return KALSHI_CITY_MAP[series_ticker]

    # 2) Title ichidan qidirish
    title_lower = title.lower()
    city_patterns = {
        "new york": "nyc", "nyc": "nyc",
        "chicago": "chicago",
        "los angeles": "los_angeles",
        "dallas": "dallas",
        "miami": "miami",
        "atlanta": "atlanta",
        "london": "london",
        "paris": "paris",
        "tokyo": "tokyo",
        "toronto": "toronto",
    }

    for pattern, city_key in city_patterns.items():
        if pattern in title_lower:
            return city_key

    # 3) Ticker ichidagi shahar kodi
    ticker_upper = ticker.upper()
    for code, city_key in KALSHI_CITY_MAP.items():
        if code in ticker_upper:
            return city_key

    return None


def _extract_kalshi_date(raw: dict) -> str | None:
    """Kalshi market'dan sanani ajratadi (YYYY-MM-DD)."""
    # close_time yoki expiration_time dan
    for field in ("close_time", "expiration_time", "expected_expiration_time"):
        val = raw.get(field, "")
        if val:
            try:
                if "T" in val:
                    dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
                    return dt.strftime("%Y-%m-%d")
                elif len(val) >= 10:
                    return val[:10]
            except (ValueError, TypeError):
                continue

    # Ticker ichidan sana (masalan: KXHIGH-26MAR21-T55 -> 2026-03-21)
    ticker = raw.get("ticker", "")
    match = re.search(r'-(\d{2})([A-Z]{3})(\d{2})-', ticker)
    if match:
        year_prefix = match.group(1)
        month_abbr = match.group(2)
        day = match.group(3)

        months = {
            "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
            "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
            "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
        }
        month_num = months.get(month_abbr)
        if month_num:
            year = f"20{year_prefix}"
            return f"{year}-{month_num}-{day}"

    # Title dan sana
    title = raw.get("title", "")
    months_map = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    for month_name, month_num in months_map.items():
        m = re.search(rf'{month_name}\s+(\d{{1,2}})', title, re.IGNORECASE)
        if m:
            day = int(m.group(1))
            year = str(datetime.now(timezone.utc).year)
            return f"{year}-{month_num}-{day:02d}"

    return None


def _extract_kalshi_temp_range(ticker: str, title: str) -> dict | None:
    """
    Kalshi market'dan harorat oralig'ini ajratadi.

    Ticker formatlari:
    - KXHIGH-26MAR21-T55  (threshold at 55)
    - KXHIGHNY-26MAR21-B40T50 (between 40-50)

    Title formatlari:
    - "55°F or above" / "55°F or higher"
    - "below 55°F" / "under 55°F"
    - "between 50°F and 55°F"
    """
    title_lower = title.lower()
    unit = "C" if "°c" in title_lower else "F"

    # Title-based parsing

    # "X°F or above/higher" — threshold va undan yuqori
    match = re.search(r'(-?\d+)\s*°[fc]\s*or\s*(?:above|higher|more)', title_lower)
    if match:
        low = int(match.group(1))
        return {"low": low, "high": 999, "unit": unit}

    # "X°F or below/under" — threshold va undan past
    match = re.search(r'(-?\d+)\s*°[fc]\s*or\s*(?:below|under|less|lower)', title_lower)
    if match:
        high = int(match.group(1)) + 1
        return {"low": -999, "high": high, "unit": unit}

    # "below X°F" / "under X°F"
    match = re.search(r'(?:below|under)\s*(-?\d+)\s*°[fc]', title_lower)
    if match:
        high = int(match.group(1))
        return {"low": -999, "high": high, "unit": unit}

    # "between X and Y" / "between X-Y"
    match = re.search(r'between\s+(-?\d+)\s*°?[fc]?\s*(?:and|[-–])\s*(-?\d+)\s*°[fc]', title_lower)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) + 1
        return {"low": low, "high": high, "unit": unit}

    # "X-Y°F" range
    match = re.search(r'(-?\d+)\s*[-–]\s*(-?\d+)\s*°[fc]', title_lower)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) + 1
        return {"low": low, "high": high, "unit": unit}

    # Ticker-based parsing fallback
    # T55 -> threshold 55 (usually "X or above")
    match = re.search(r'-T(-?\d+)$', ticker)
    if match:
        threshold = int(match.group(1))
        return {"low": threshold, "high": 999, "unit": "F"}

    # B40T50 -> between 40 and 50
    match = re.search(r'-B(-?\d+)T(-?\d+)$', ticker)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) + 1
        return {"low": low, "high": high, "unit": "F"}

    return None


def _normalize_price(price) -> float:
    """
    Kalshi narxni 0.0-1.0 formatga keltiradi.
    Kalshi ba'zan 0-100 (cents), ba'zan 0-1.0 formatda beradi.
    """
    if price is None:
        return 0.0
    try:
        p = float(price)
    except (ValueError, TypeError):
        return 0.0

    if p > 1.0:
        # Cents formatda (masalan 55 = $0.55)
        return round(p / 100.0, 4)
    return round(p, 4)


# ═══════════════════════════════════════
# ARBITRAJ ANIQLASH
# ═══════════════════════════════════════

def _ranges_overlap(low1: int, high1: int, low2: int, high2: int) -> bool:
    """Ikki harorat oralig'i bir-biriga to'g'ri keladimi?"""
    # -999 va 999 — cheksiz oraliq
    effective_low1 = low1 if low1 != -999 else -1000
    effective_high1 = high1 if high1 != 999 else 1000
    effective_low2 = low2 if low2 != -999 else -1000
    effective_high2 = high2 if high2 != 999 else 1000

    return effective_low1 < effective_high2 and effective_low2 < effective_high1


def _ranges_match(low1: int, high1: int, low2: int, high2: int) -> bool:
    """Ikki harorat oralig'i bir xilmi (yoki juda yaqinmi)?"""
    # Aniq bir xil
    if low1 == low2 and high1 == high2:
        return True

    # 1 daraja farq bilan ham match (Polymarket va Kalshi boundary farqlari)
    if abs(low1 - low2) <= 1 and abs(high1 - high2) <= 1:
        return True

    # Ikkalasi ham "X va undan yuqori" yoki "X va undan past" turida
    if low1 == -999 and low2 == -999 and abs(high1 - high2) <= 1:
        return True
    if high1 == 999 and high2 == 999 and abs(low1 - low2) <= 1:
        return True

    return False


def find_arbitrage_opportunities(poly_markets: list[dict],
                                 kalshi_markets: list[dict],
                                 min_profit: float = 0.01) -> list[dict]:
    """
    Polymarket va Kalshi bozorlarini solishtiradi, arbitraj imkoniyatlarini topadi.

    Arbitraj qoidasi:
    Agar ikki bozor BIR XIL hodisani sotsa:
    - Polymarket YES + Kalshi NO < $1.00 → Profit = $1.00 - (YES + NO)
    - Polymarket NO + Kalshi YES < $1.00 → Profit = $1.00 - (NO + YES)

    Args:
        poly_markets: Polymarket weather market'lari (markets.py dan)
        kalshi_markets: Kalshi weather market'lari (fetch_kalshi_weather_markets dan)
        min_profit: Minimal foyda ($) — default $0.01

    Returns:
        Arbitraj imkoniyatlari ro'yxati, foydasi bo'yicha tartiblangan.
    """
    opportunities = []

    # Kalshi marketlarni (city, date) bo'yicha indekslash
    kalshi_index = {}
    for km in kalshi_markets:
        key = (km["city"], km["date"])
        if key not in kalshi_index:
            kalshi_index[key] = []
        kalshi_index[key].append(km)

    for pm in poly_markets:
        city = pm.get("city")
        date = pm.get("date")
        if not city or not date:
            continue

        key = (city, date)
        matching_kalshi = kalshi_index.get(key, [])

        for km in matching_kalshi:
            # Birlik tekshiruvi
            if pm.get("unit", "F") != km.get("unit", "F"):
                continue

            # Harorat oralig'i mos kelishi kerak
            if not _ranges_match(
                pm["temp_low"], pm["temp_high"],
                km["temp_low"], km["temp_high"],
            ):
                continue

            # Narxlarni olish
            poly_yes = pm.get("yes_price", 0)
            poly_no = pm.get("no_price", 0)
            kalshi_yes = km.get("yes_price", 0)
            kalshi_no = km.get("no_price", 0)

            # Narxlar 0 bo'lsa skip
            if poly_yes <= 0 and poly_no <= 0:
                continue
            if kalshi_yes <= 0 and kalshi_no <= 0:
                continue

            # Strategiya 1: Poly YES + Kalshi NO
            if poly_yes > 0 and kalshi_no > 0:
                total_cost = poly_yes + kalshi_no
                profit = 1.0 - total_cost
                if profit >= min_profit:
                    opportunities.append(_build_opportunity(
                        pm, km,
                        poly_side="YES", kalshi_side="NO",
                        poly_price=poly_yes, kalshi_price=kalshi_no,
                        total_cost=total_cost, profit=profit,
                    ))

            # Strategiya 2: Poly NO + Kalshi YES
            if poly_no > 0 and kalshi_yes > 0:
                total_cost = poly_no + kalshi_yes
                profit = 1.0 - total_cost
                if profit >= min_profit:
                    opportunities.append(_build_opportunity(
                        pm, km,
                        poly_side="NO", kalshi_side="YES",
                        poly_price=poly_no, kalshi_price=kalshi_yes,
                        total_cost=total_cost, profit=profit,
                    ))

    # Foydasi bo'yicha tartiblash
    opportunities.sort(key=lambda x: x["profit"], reverse=True)
    return opportunities


def _build_opportunity(pm: dict, km: dict,
                       poly_side: str, kalshi_side: str,
                       poly_price: float, kalshi_price: float,
                       total_cost: float, profit: float) -> dict:
    """Bitta arbitraj imkoniyatini dict sifatida tuzadi."""
    return {
        "city": pm["city"],
        "date": pm["date"],
        "temp_low": pm["temp_low"],
        "temp_high": pm["temp_high"],
        "unit": pm.get("unit", "F"),
        # Polymarket tomon
        "poly_side": poly_side,
        "poly_price": round(poly_price, 4),
        "poly_question": pm.get("question", ""),
        "poly_market_id": pm.get("market_id"),
        # Kalshi tomon
        "kalshi_side": kalshi_side,
        "kalshi_price": round(kalshi_price, 4),
        "kalshi_ticker": km.get("ticker", ""),
        "kalshi_title": km.get("title", ""),
        # Natija
        "total_cost": round(total_cost, 4),
        "profit": round(profit, 4),
        "profit_pct": round((profit / total_cost) * 100, 2) if total_cost > 0 else 0,
    }


# ═══════════════════════════════════════
# TELEGRAM FORMAT
# ═══════════════════════════════════════

def format_arbitrage_telegram(opportunities: list[dict]) -> str:
    """
    Arbitraj imkoniyatlarini Telegram uchun formatlaydi (HTML).
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    if not opportunities:
        return (
            f"🔄 <b>Arbitraj Scan</b>\n"
            f"📅 {now}\n\n"
            f"😐 Polymarket-Kalshi arbitraj topilmadi."
        )

    top = opportunities[:10]
    total_profit = sum(o["profit"] for o in opportunities)

    lines = [
        f"🔄 <b>ARBITRAJ: Polymarket vs Kalshi</b>",
        f"📅 {now}",
        f"💰 <b>{len(opportunities)}</b> ta imkoniyat | "
        f"Jami potensial: <b>${total_profit:.2f}</b>",
        "",
    ]

    for i, o in enumerate(top, 1):
        unit = "°" + o.get("unit", "F")
        tl, th = o["temp_low"], o["temp_high"]
        if tl == -999:
            temp = f"≤{th - 1}{unit}"
        elif th == 999:
            temp = f"≥{tl}{unit}"
        else:
            temp = f"{tl}-{th - 1}{unit}"

        lines.append(
            f"{i}. <b>{o['city']}</b> {temp} | {o['date']}\n"
            f"   Poly {o['poly_side']} ${o['poly_price']:.2f} + "
            f"Kalshi {o['kalshi_side']} ${o['kalshi_price']:.2f}\n"
            f"   💵 Foyda: <b>${o['profit']:.3f}</b> ({o['profit_pct']:.1f}%)"
        )

    return "\n".join(lines)


# ═══════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════

if __name__ == "__main__":
    from rich.table import Table
    from rich.console import Console

    console = Console()

    # 1) Kalshi marketlarni olish
    console.print("[bold]Kalshi weather bozorlarini yuklamoqda...[/]")
    kalshi_markets = fetch_kalshi_weather_markets()
    console.print(f"Kalshi: [green]{len(kalshi_markets)}[/] ta market topildi\n")

    if kalshi_markets:
        table = Table(title="Kalshi Weather Markets")
        table.add_column("Ticker", style="cyan", max_width=30)
        table.add_column("Shahar", style="yellow")
        table.add_column("Sana")
        table.add_column("Harorat", style="magenta")
        table.add_column("YES $", style="green")
        table.add_column("NO $", style="red")

        for km in kalshi_markets[:20]:
            unit = "°" + km["unit"]
            tl, th = km["temp_low"], km["temp_high"]
            if tl == -999:
                temp = f"≤{th - 1}{unit}"
            elif th == 999:
                temp = f"≥{tl}{unit}"
            else:
                temp = f"{tl}-{th - 1}{unit}"

            table.add_row(
                km["ticker"][:30],
                km["city"],
                km["date"],
                temp,
                f"${km['yes_price']:.3f}",
                f"${km['no_price']:.3f}",
            )

        console.print(table)
        console.print()

    # 2) Polymarket marketlarni olish
    console.print("[bold]Polymarket weather bozorlarini yuklamoqda...[/]")
    try:
        from markets import get_all_opportunities
        poly_markets = get_all_opportunities()
        console.print(f"Polymarket: [green]{len(poly_markets)}[/] ta market topildi\n")
    except Exception as e:
        console.print(f"[red]Polymarket xatosi: {e}[/]")
        poly_markets = []

    # 3) Arbitraj qidirish
    if poly_markets and kalshi_markets:
        console.print("[bold]Arbitraj qidirilmoqda...[/]")
        arbs = find_arbitrage_opportunities(poly_markets, kalshi_markets)
        console.print(f"Arbitraj: [green]{len(arbs)}[/] ta imkoniyat topildi\n")

        if arbs:
            arb_table = Table(title="ARBITRAJ IMKONIYATLARI")
            arb_table.add_column("#", style="dim")
            arb_table.add_column("Shahar", style="cyan")
            arb_table.add_column("Sana")
            arb_table.add_column("Harorat", style="yellow")
            arb_table.add_column("Poly", style="green")
            arb_table.add_column("Kalshi", style="blue")
            arb_table.add_column("Cost", style="red")
            arb_table.add_column("Foyda", style="bold green")
            arb_table.add_column("ROI %", style="magenta")

            for i, a in enumerate(arbs[:15], 1):
                unit = "°" + a["unit"]
                tl, th = a["temp_low"], a["temp_high"]
                if tl == -999:
                    temp = f"≤{th - 1}{unit}"
                elif th == 999:
                    temp = f"≥{tl}{unit}"
                else:
                    temp = f"{tl}-{th - 1}{unit}"

                arb_table.add_row(
                    str(i),
                    a["city"],
                    a["date"],
                    temp,
                    f"{a['poly_side']} ${a['poly_price']:.3f}",
                    f"{a['kalshi_side']} ${a['kalshi_price']:.3f}",
                    f"${a['total_cost']:.3f}",
                    f"${a['profit']:.3f}",
                    f"{a['profit_pct']:.1f}%",
                )

            console.print(arb_table)
        else:
            console.print("[yellow]Arbitraj imkoniyati topilmadi.[/]")

        # Telegram format
        console.print("\n[bold]Telegram xabar formati:[/]")
        console.print(format_arbitrage_telegram(arbs))
    else:
        console.print("[yellow]Solishtirib bo'lmaydi — market ma'lumotlari yetarli emas.[/]")
