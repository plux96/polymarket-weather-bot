"""
Polymarket weather bozorlarini topish va tahlil qilish moduli.
Gamma API tag_slug=weather orqali ob-havo bozorlarini qidiradi.
"""

import re
import requests
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com"


def fetch_weather_events(limit: int = 100) -> list[dict]:
    """
    Polymarket'dagi barcha aktiv weather event'larini oladi.
    """
    events = []
    offset = 0

    while len(events) < limit:
        params = {
            "limit": 100,
            "offset": offset,
            "tag_slug": "weather",
            "active": "true",
            "closed": "false",
            "order": "startDate",
            "ascending": "false",
        }

        try:
            resp = requests.get(f"{GAMMA_API}/events", params=params, timeout=15)
            resp.raise_for_status()
            batch = resp.json()
        except requests.RequestException as e:
            print(f"Gamma API xatosi: {e}")
            break

        if not batch:
            break

        events.extend(batch)
        offset += 100

        if len(batch) < 100:
            break

    return events[:limit]


def parse_weather_event(event: dict) -> list[dict]:
    """
    Bitta weather event'ini tahlil qiladi.
    Har bir harorat bucket'ini alohida imkoniyat sifatida qaytaradi.

    Event misol: "Highest temperature in NYC on March 23?"
    Markets: "51°F or below", "52-53°F", "54-55°F", ..., "62°F or above"
    """
    title = event.get("title", "")
    markets = event.get("markets", [])

    if not markets:
        return []

    # Shaharni aniqlash
    city = extract_city(title)

    # Sanani aniqlash
    date_str = extract_date(title, event)

    # Harorat birligi (°C yoki °F)
    sample_q = markets[0].get("question", "")
    unit = "C" if "°C" in sample_q or "°c" in sample_q else "F"

    parsed = []
    for m in markets:
        question = m.get("question", "")
        prices_raw = m.get("outcomePrices", "[]")

        # Parse prices
        if isinstance(prices_raw, str):
            try:
                prices = eval(prices_raw)
            except Exception:
                prices = [0, 0]
        else:
            prices = prices_raw

        yes_price = float(prices[0]) if len(prices) > 0 else 0
        no_price = float(prices[1]) if len(prices) > 1 else 0

        # Harorat oralig'ini aniqlash
        temp_range = extract_temp_range(question, unit)
        if not temp_range:
            continue

        # clobTokenIds
        clob_raw = m.get("clobTokenIds", "[]")
        if isinstance(clob_raw, str):
            try:
                clob_ids = eval(clob_raw)
            except Exception:
                clob_ids = []
        else:
            clob_ids = clob_raw

        parsed.append({
            "event_title": title,
            "market_id": m.get("id"),
            "condition_id": m.get("conditionId"),
            "question": question,
            "city": city,
            "date": date_str,
            "temp_low": temp_range["low"],
            "temp_high": temp_range["high"],
            "unit": unit,
            "yes_price": yes_price,
            "no_price": no_price,
            "clob_token_yes": clob_ids[0] if len(clob_ids) > 0 else None,
            "clob_token_no": clob_ids[1] if len(clob_ids) > 1 else None,
            "volume": float(m.get("volume", 0) or 0),
            "active": m.get("active", True),
        })

    return parsed


def extract_city(title: str) -> str:
    """Event sarlavhasidan shahar nomini ajratadi."""
    title_lower = title.lower()

    city_map = {
        "new york": "nyc", "nyc": "nyc",
        "london": "london",
        "paris": "paris",
        "tokyo": "tokyo",
        "buenos aires": "buenos_aires",
        "madrid": "madrid",
        "toronto": "toronto",
        "taipei": "taipei",
        "tel aviv": "tel_aviv",
        "ankara": "ankara",
        "sao paulo": "sao_paulo",
        "warsaw": "warsaw",
        "hong kong": "hong_kong",
        "shanghai": "shanghai",
        "wellington": "wellington",
        "atlanta": "atlanta",
        "dallas": "dallas",
        "lucknow": "lucknow",
        "chicago": "chicago",
        "los angeles": "los_angeles",
        "mumbai": "mumbai",
        "delhi": "delhi",
        "sydney": "sydney",
        "berlin": "berlin",
        "rome": "rome",
        "moscow": "moscow",
        "seoul": "seoul",
        "miami": "miami",
    }

    for pattern, key in city_map.items():
        if pattern in title_lower:
            return key

    # Noma'lum shahar — title'dan ajratamiz
    match = re.search(r'in\s+(.+?)\s+on\s', title, re.IGNORECASE)
    if match:
        return match.group(1).lower().replace(" ", "_")

    return "unknown"


def extract_date(title: str, event: dict) -> str:
    """Sanani aniqlaydi."""
    # "on March 23" formatidan
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    for month_name, month_num in months.items():
        match = re.search(rf'{month_name}\s+(\d{{1,2}})', title, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            # Yilni endDate dan olamiz
            end_date = event.get("endDate", "")
            year = end_date[:4] if end_date else str(datetime.now().year)
            return f"{year}-{month_num}-{day:02d}"

    # Fallback: endDate ishlatamiz
    end_date = event.get("endDate", "")
    return end_date[:10] if end_date else ""


def extract_temp_range(question: str, unit: str) -> dict | None:
    """
    Savoldan harorat oralig'ini ajratadi.

    Formatlar:
    - "51°F or below" → {"low": -999, "high": 52}
    - "between 52-53°F" → {"low": 52, "high": 54}
    - "52°C" (exact) → {"low": 52, "high": 53}
    - "62°F or higher" → {"low": 62, "high": 999}
    """
    q = question.lower()
    symbol = "°f" if unit == "F" else "°c"

    # "X°F or below" / "X°C or below"
    match = re.search(r'(-?\d+)\s*°[fc]\s*or\s*(?:below|less|lower)', q)
    if match:
        high = int(match.group(1)) + 1  # "51 or below" = < 52
        return {"low": -999, "high": high}

    # "between X-Y°F" / "between X and Y"
    match = re.search(r'(?:between\s+)?(-?\d+)\s*[-–]\s*(-?\d+)\s*°[fc]', q)
    if match:
        low = int(match.group(1))
        high = int(match.group(2)) + 1  # inclusive
        return {"low": low, "high": high}

    # "X°F or higher" / "X°C or above"
    match = re.search(r'(-?\d+)\s*°[fc]\s*or\s*(?:higher|above|more)', q)
    if match:
        low = int(match.group(1))
        return {"low": low, "high": 999}

    # Exact temperature: "be 25°C on"
    match = re.search(r'be\s+(-?\d+)\s*°[fc]\s+on', q)
    if match:
        temp = int(match.group(1))
        return {"low": temp, "high": temp + 1}

    return None


def get_all_opportunities() -> list[dict]:
    """
    Barcha weather bozorlarni oladi va parse qiladi.
    """
    events = fetch_weather_events()
    all_opps = []
    for event in events:
        parsed = parse_weather_event(event)
        all_opps.extend(parsed)
    return all_opps


# ═══════════════════════════════════════
# Koordinatalar — GFS ensemble uchun
# ═══════════════════════════════════════
CITY_COORDS = {
    "nyc": {"lat": 40.7128, "lon": -74.0060},
    "london": {"lat": 51.5074, "lon": -0.1278},
    "paris": {"lat": 48.8566, "lon": 2.3522},
    "tokyo": {"lat": 35.6762, "lon": 139.6503},
    "buenos_aires": {"lat": -34.6037, "lon": -58.3816},
    "madrid": {"lat": 40.4168, "lon": -3.7038},
    "toronto": {"lat": 43.6532, "lon": -79.3832},
    "taipei": {"lat": 25.0330, "lon": 121.5654},
    "tel_aviv": {"lat": 32.0853, "lon": 34.7818},
    "ankara": {"lat": 39.9334, "lon": 32.8597},
    "sao_paulo": {"lat": -23.5505, "lon": -46.6333},
    "warsaw": {"lat": 52.2297, "lon": 21.0122},
    "hong_kong": {"lat": 22.3193, "lon": 114.1694},
    "shanghai": {"lat": 31.2304, "lon": 121.4737},
    "wellington": {"lat": -41.2865, "lon": 174.7762},
    "atlanta": {"lat": 33.7490, "lon": -84.3880},
    "dallas": {"lat": 32.7767, "lon": -96.7970},
    "lucknow": {"lat": 26.8467, "lon": 80.9462},
    "chicago": {"lat": 41.8781, "lon": -87.6298},
    "los_angeles": {"lat": 34.0522, "lon": -118.2437},
    "mumbai": {"lat": 19.0760, "lon": 72.8777},
    "delhi": {"lat": 28.7041, "lon": 77.1025},
    "sydney": {"lat": -33.8688, "lon": 151.2093},
    "berlin": {"lat": 52.5200, "lon": 13.4050},
    "rome": {"lat": 41.9028, "lon": 12.4964},
    "seoul": {"lat": 37.5665, "lon": 126.9780},
    "miami": {"lat": 25.7617, "lon": -80.1918},
}


if __name__ == "__main__":
    from rich.table import Table
    from rich.console import Console

    console = Console()

    console.print("[bold]Polymarket weather bozorlarini yuklamoqda...[/]")
    opps = get_all_opportunities()
    console.print(f"Jami: [green]{len(opps)}[/] ta bucket topildi\n")

    # Shaharlar bo'yicha guruhlash
    cities = {}
    for o in opps:
        c = o["city"]
        if c not in cities:
            cities[c] = []
        cities[c].append(o)

    console.print(f"Shaharlar: [cyan]{len(cities)}[/]\n")

    for city, markets in sorted(cities.items()):
        table = Table(title=f"{city.upper()} — {markets[0]['date']}")
        table.add_column("Harorat", style="yellow")
        table.add_column("YES $", style="green")
        table.add_column("NO $", style="red")
        table.add_column("Savol", max_width=55)

        for m in markets:
            unit = "°" + m["unit"]
            if m["temp_low"] == -999:
                temp_str = f"≤{m['temp_high']-1}{unit}"
            elif m["temp_high"] == 999:
                temp_str = f"≥{m['temp_low']}{unit}"
            else:
                temp_str = f"{m['temp_low']}–{m['temp_high']-1}{unit}"

            table.add_row(
                temp_str,
                f"${m['yes_price']:.3f}",
                f"${m['no_price']:.3f}",
                m["question"][:55],
            )

        console.print(table)
        console.print()
