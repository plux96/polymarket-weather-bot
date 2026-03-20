"""
16-manba ob-havo prognozi moduli.

ENSEMBLE modellar (Open-Meteo) — ehtimollik hisoblash uchun:
  1. GFS (NOAA/USA) — 30 member
  2. ECMWF (Yevropa) — 50 member
  3. ICON (DWD/Germaniya) — 39 member
  4. GEM (Kanada) — 20 member
  5. BOM (Avstraliya) — 17 member
  Total: ~156 ensemble member

DETERMINISTIC modellar (Open-Meteo) — cross-validation:
  6. MeteoFrance Arpege/Arome
  7. JMA (Yaponiya)
  8. UKMO (UK Met Office)
  9. KNMI (Niderlandiya)
 10. CMA GRAPES (Xitoy)
 11. ARPAE COSMO (Italiya)
 12. MetNorway (Norvegiya)
 13. NCEP HRRR (AQSh — yuqori aniqlik)
 14. DMI (Daniya)

TASHQI manba:
 15. Tomorrow.io (ML ensemble) — barcha shaharlar
 16. NWS/NOAA (weather.gov) — faqat US shaharlari

Jami: 16 ta model, ~156+ ensemble member
"""

import os
import requests
from datetime import datetime, timezone
from markets import CITY_COORDS

ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
DETERMINISTIC_URL = "https://api.open-meteo.com/v1/forecast"
NWS_API = "https://api.weather.gov"
TOMORROW_API = "https://api.tomorrow.io/v4/weather/forecast"

# ═══════════════════════════════════════
# ENSEMBLE MODELLAR
# ═══════════════════════════════════════
ENSEMBLE_MODELS = {
    "gfs": {"name": "GFS (USA)", "model_id": "gfs_seamless", "max_members": 31},
    "ecmwf": {"name": "ECMWF (EU)", "model_id": "ecmwf_ifs025", "max_members": 51},
    "icon": {"name": "ICON (DE)", "model_id": "icon_seamless", "max_members": 40},
    "gem": {"name": "GEM (CA)", "model_id": "gem_global", "max_members": 21},
    "bom": {"name": "BOM (AU)", "model_id": "bom_access_global_ensemble", "max_members": 18},
}

# ═══════════════════════════════════════
# DETERMINISTIC MODELLAR
# ═══════════════════════════════════════
DETERMINISTIC_MODELS = {
    "meteofrance": {"name": "MeteoFrance (FR)", "model_id": "meteofrance_seamless"},
    "jma":         {"name": "JMA (JP)",          "model_id": "jma_seamless"},
    "ukmo":        {"name": "UKMO (UK)",          "model_id": "ukmo_seamless"},
    "knmi":        {"name": "KNMI (NL)",          "model_id": "knmi_seamless"},
    "cma":         {"name": "CMA GRAPES (CN)",    "model_id": "cma_grapes_global"},
    "cosmo":       {"name": "COSMO/ARPAE (IT)",   "model_id": "arpae_cosmo_seamless"},
    "metno":       {"name": "MetNorway (NO)",      "model_id": "metno_seamless"},
    "dmi":         {"name": "DMI (DK)",            "model_id": "dmi_seamless"},
}

# HRRR — faqat US (3km grid, ~18 soatlik prognoz)
HRRR_CITIES = {"nyc", "chicago", "dallas", "atlanta", "miami", "los_angeles"}

# NWS gridpoints — US shaharlari uchun
NWS_GRIDPOINTS = {
    "nyc": "OKX/33,35",
    "chicago": "LOT/76,73",
    "dallas": "FWD/80,103",
    "atlanta": "FFC/52,88",
    "miami": "MFL/110,50",
    "los_angeles": "LOX/154,44",
}


def fetch_ensemble(city_key: str, model_key: str, unit: str = "C",
                   forecast_days: int = 7) -> dict | None:
    """Bitta ensemble model prognozini oladi."""
    coords = CITY_COORDS.get(city_key)
    model = ENSEMBLE_MODELS.get(model_key)
    if not coords or not model:
        return None

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": "temperature_2m",
        "models": model["model_id"],
        "forecast_days": forecast_days,
        "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
    }

    try:
        resp = requests.get(ENSEMBLE_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    members = {}
    for i in range(model["max_members"]):
        key = f"temperature_2m_member{i}"
        if key in hourly:
            members[i] = hourly[key]

    if not members:
        return None

    return {
        "type": "ensemble",
        "model": model_key,
        "model_name": model["name"],
        "city_key": city_key,
        "unit": unit,
        "times": times,
        "members": members,
        "member_count": len(members),
    }


def fetch_deterministic(city_key: str, model_key: str, unit: str = "C",
                        forecast_days: int = 7) -> dict | None:
    """Deterministic model — daily max haroratni oladi."""
    coords = CITY_COORDS.get(city_key)
    model = DETERMINISTIC_MODELS.get(model_key)
    if not coords or not model:
        return None

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "daily": "temperature_2m_max",
        "models": model["model_id"],
        "forecast_days": forecast_days,
        "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
    }

    try:
        resp = requests.get(DETERMINISTIC_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])

    if not dates or not highs:
        return None

    # date → high mapping
    daily_highs = {}
    for d, h in zip(dates, highs):
        if h is not None:
            daily_highs[d] = h

    return {
        "type": "deterministic",
        "model": model_key,
        "model_name": model["name"],
        "city_key": city_key,
        "unit": unit,
        "daily_highs": daily_highs,
    }


def fetch_deterministic_hrrr(city_key: str, unit: str = "C",
                             forecast_days: int = 2) -> dict | None:
    """NCEP HRRR — AQSh uchun 3km yuqori aniqlikli model."""
    coords = CITY_COORDS.get(city_key)
    if not coords or city_key not in HRRR_CITIES:
        return None

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "daily": "temperature_2m_max",
        "models": "ncep_hrrr",
        "forecast_days": forecast_days,
        "temperature_unit": "fahrenheit" if unit == "F" else "celsius",
    }

    try:
        resp = requests.get(DETERMINISTIC_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])

    if not dates or not highs:
        return None

    daily_highs = {d: h for d, h in zip(dates, highs) if h is not None}
    return {
        "type": "deterministic",
        "model": "hrrr",
        "model_name": "NCEP HRRR (US)",
        "city_key": city_key,
        "unit": unit,
        "daily_highs": daily_highs,
    }


def fetch_tomorrow_forecast(city_key: str, unit: str = "C") -> dict | None:
    """Tomorrow.io ML ensemble — kunlik max harorat (bepul: 500 req/kun)."""
    api_key = os.getenv("TOMORROW_API_KEY", "")
    if not api_key:
        return None

    coords = CITY_COORDS.get(city_key)
    if not coords:
        return None

    params = {
        "location": f"{coords['lat']},{coords['lon']}",
        "apikey": api_key,
        "timesteps": "1d",
        "fields": "temperatureMax",
        "units": "imperial" if unit == "F" else "metric",
    }

    try:
        resp = requests.get(TOMORROW_API, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    timelines = data.get("timelines", {}).get("daily", [])
    if not timelines:
        return None

    daily_highs = {}
    for day in timelines:
        date = day.get("time", "")[:10]
        high = day.get("values", {}).get("temperatureMax")
        if date and high is not None:
            daily_highs[date] = high

    if not daily_highs:
        return None

    return {
        "type": "deterministic",
        "model": "tomorrow",
        "model_name": "Tomorrow.io (ML)",
        "city_key": city_key,
        "unit": unit,
        "daily_highs": daily_highs,
    }


def fetch_nws_forecast(city_key: str) -> dict | None:
    """NWS/NOAA prognozi — faqat US shaharlari."""
    gridpoint = NWS_GRIDPOINTS.get(city_key)
    if not gridpoint:
        return None

    try:
        url = f"{NWS_API}/gridpoints/{gridpoint}/forecast/hourly"
        resp = requests.get(url, headers={"User-Agent": "PolyWeatherBot/1.0"}, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return None

    periods = data.get("properties", {}).get("periods", [])
    if not periods:
        return None

    # Kunlik max haroratni hisoblaymiz
    daily_highs = {}
    for p in periods:
        date = p["startTime"][:10]
        temp = p["temperature"]
        unit = p.get("temperatureUnit", "F")
        if date not in daily_highs or temp > daily_highs[date]:
            daily_highs[date] = temp

    return {
        "type": "nws",
        "model": "nws",
        "model_name": "NWS/NOAA (US)",
        "city_key": city_key,
        "unit": "F",  # NWS always Fahrenheit
        "daily_highs": daily_highs,
    }


def fetch_all_models(city_key: str, unit: str = "C", forecast_days: int = 7) -> dict:
    """
    Barcha 10 ta manbadan prognoz oladi.

    Qaytaradi:
    {
        "ensembles": [...],         # Ensemble modellar
        "deterministics": [...],    # Deterministic modellar
        "nws": {...} or None,       # NWS (faqat US)
        "total_models": 10,
        "total_ensemble_members": 156,
    }
    """
    ensembles = []
    for model_key in ENSEMBLE_MODELS:
        ens = fetch_ensemble(city_key, model_key, unit, forecast_days)
        if ens:
            ensembles.append(ens)

    deterministics = []
    for model_key in DETERMINISTIC_MODELS:
        det = fetch_deterministic(city_key, model_key, unit, forecast_days)
        if det:
            deterministics.append(det)

    # HRRR — faqat US shaharlari (3km, yuqori aniqlik)
    if city_key in HRRR_CITIES:
        hrrr = fetch_deterministic_hrrr(city_key, unit)
        if hrrr:
            deterministics.append(hrrr)

    # Tomorrow.io — ML ensemble, barcha shaharlar
    tomorrow = fetch_tomorrow_forecast(city_key, unit)
    if tomorrow:
        deterministics.append(tomorrow)

    # NWS — faqat US shaharlari uchun
    nws = fetch_nws_forecast(city_key) if city_key in NWS_GRIDPOINTS else None

    total_members = sum(e["member_count"] for e in ensembles)
    total_models = len(ensembles) + len(deterministics) + (1 if nws else 0)

    return {
        "ensembles": ensembles,
        "deterministics": deterministics,
        "nws": nws,
        "total_models": total_models,
        "total_ensemble_members": total_members,
    }


# ═══════════════════════════════════════
# EHTIMOLLIK HISOBLASH
# ═══════════════════════════════════════

def daily_high_from_ensemble(ensemble: dict, date_str: str) -> list[float]:
    """Ensemble'dan shu kundagi daily high'larni qaytaradi."""
    times = ensemble["times"]
    day_indices = [i for i, t in enumerate(times) if t.startswith(date_str)]
    if not day_indices:
        return []

    highs = []
    for member_id, values in ensemble["members"].items():
        temps = [values[idx] for idx in day_indices
                 if idx < len(values) and values[idx] is not None]
        if temps:
            highs.append(max(temps))
    return highs


def multi_model_probability(all_data: dict, date_str: str,
                            temp_low: float, temp_high: float,
                            unit: str = "C") -> dict:
    """
    10 ta model asosida ehtimollik + confidence hisoblaydi.

    1. Ensemble memberlar → raw ehtimollik
    2. Deterministic modellar → binary vote (in range yoki yo'q)
    3. NWS → binary vote
    4. Umumiy weighted probability + consensus
    """
    model_results = []
    all_highs = []
    all_in_range = 0

    # 1) ENSEMBLE modellar
    for ens in all_data.get("ensembles", []):
        highs = daily_high_from_ensemble(ens, date_str)
        if not highs:
            continue
        in_range = sum(1 for h in highs if temp_low <= h < temp_high)
        prob = in_range / len(highs)
        model_results.append({
            "model": ens["model"],
            "model_name": ens["model_name"],
            "type": "ensemble",
            "probability": prob,
            "members": len(highs),
            "in_range": in_range,
            "high": sum(highs) / len(highs),
        })
        all_highs.extend(highs)
        all_in_range += in_range

    # 2) DETERMINISTIC modellar
    for det in all_data.get("deterministics", []):
        dh = det.get("daily_highs", {})
        high = dh.get(date_str)
        if high is None:
            continue

        # Fahrenheit → Celsius yoki aksincha konvertatsiya kerak bo'lsa
        # Open-Meteo allaqachon to'g'ri unitda qaytaradi

        in_range = 1 if temp_low <= high < temp_high else 0
        model_results.append({
            "model": det["model"],
            "model_name": det["model_name"],
            "type": "deterministic",
            "probability": float(in_range),
            "members": 1,
            "in_range": in_range,
            "high": high,
        })
        # Deterministic = 1 member sifatida qo'shamiz
        all_highs.append(high)
        all_in_range += in_range

    # 3) NWS/NOAA
    nws = all_data.get("nws")
    if nws:
        nws_highs = nws.get("daily_highs", {})
        nws_high = nws_highs.get(date_str)
        if nws_high is not None:
            # NWS Fahrenheit da keladi — agar Celsius kerak bo'lsa konvert
            if unit == "C":
                nws_high_conv = (nws_high - 32) * 5.0 / 9.0
            else:
                nws_high_conv = nws_high

            in_range = 1 if temp_low <= nws_high_conv < temp_high else 0
            model_results.append({
                "model": "nws",
                "model_name": "NWS/NOAA",
                "type": "nws",
                "probability": float(in_range),
                "members": 1,
                "in_range": in_range,
                "high": nws_high_conv,
            })
            all_highs.append(nws_high_conv)
            all_in_range += in_range

    if not all_highs:
        return {"probability": 0, "error": "Ma'lumot yo'q"}

    # ═══════════════════════════════════════
    # WEIGHTED PROBABILITY
    # Ensemble memberlar ko'proq vaznga ega
    # ═══════════════════════════════════════
    weighted_sum = sum(r["probability"] * r["members"] for r in model_results)
    weighted_total = sum(r["members"] for r in model_results)
    weighted_prob = weighted_sum / weighted_total if weighted_total > 0 else 0

    # Model consensus — nechta model 50%+ ko'rsatadi
    models_agree_yes = sum(1 for r in model_results if r["probability"] >= 0.5)
    models_agree_no = sum(1 for r in model_results if r["probability"] < 0.5)
    total_models = len(model_results)

    # Probability spread — modellar qanchalik farq qiladi
    probs = [r["probability"] for r in model_results]
    spread = max(probs) - min(probs) if len(probs) > 1 else 0

    # Confidence = consensus * (1 - spread)
    consensus_pct = max(models_agree_yes, models_agree_no) / total_models if total_models > 0 else 0
    confidence = consensus_pct * (1 - spread * 0.3)

    return {
        "probability": weighted_prob,
        "weighted_probability": weighted_prob,
        "models_agreeing": models_agree_yes,
        "total_models": total_models,
        "consensus": f"{max(models_agree_yes, models_agree_no)}/{total_models}",
        "confidence": round(confidence, 3),
        "spread": round(spread, 3),
        "total_members": len(all_highs),
        "members_in_range": all_in_range,
        "mean_high": sum(all_highs) / len(all_highs),
        "min_high": min(all_highs),
        "max_high": max(all_highs),
        "per_model": model_results,
        "date": date_str,
    }


# ═══════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════

def fetch_multi_model(city_key: str, unit: str = "C", forecast_days: int = 7) -> dict:
    """Eski API moslik — hozir to'liq 10 model qaytaradi."""
    return fetch_all_models(city_key, unit, forecast_days)


def fetch_gfs_ensemble(city_key: str, unit: str = "C", forecast_days: int = 7) -> dict | None:
    return fetch_ensemble(city_key, "gfs", unit, forecast_days)


def find_daily_high_probability(ensemble: dict, date_str: str,
                                temp_low: float, temp_high: float) -> dict:
    highs = daily_high_from_ensemble(ensemble, date_str)
    if not highs:
        return {"probability": 0, "error": f"Sana topilmadi: {date_str}"}
    in_range = sum(1 for h in highs if temp_low <= h < temp_high)
    return {
        "probability": in_range / len(highs),
        "members_in_range": in_range,
        "total_members": len(highs),
        "mean_high": sum(highs) / len(highs),
        "min_high": min(highs),
        "max_high": max(highs),
        "date": date_str,
    }


if __name__ == "__main__":
    from rich import print as rprint
    from rich.table import Table
    from rich.console import Console

    console = Console()
    tomorrow = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    city = "nyc"
    unit = "F"

    rprint(f"\n[bold]NYC — 10 ta model yuklanmoqda...[/]\n")

    all_data = fetch_all_models(city, unit=unit, forecast_days=5)

    ens_count = len(all_data["ensembles"])
    det_count = len(all_data["deterministics"])
    nws_ok = "✅" if all_data["nws"] else "❌"
    total_members = all_data["total_ensemble_members"]

    rprint(f"[green]Ensemble: {ens_count} model, {total_members} members[/]")
    rprint(f"[blue]Deterministic: {det_count} model[/]")
    rprint(f"[cyan]NWS/NOAA: {nws_ok}[/]")
    rprint(f"[bold]Jami: {all_data['total_models']} model[/]")

    result = multi_model_probability(all_data, tomorrow, 40, 50, unit)

    rprint(f"\n[bold]Daily High 40-50°F — {tomorrow}:[/]")
    rprint(f"  Probability: [bold cyan]{result['weighted_probability']:.0%}[/]")
    rprint(f"  Consensus: [bold]{result['consensus']}[/]")
    rprint(f"  Confidence: [bold]{result['confidence']:.0%}[/]")
    rprint(f"  Spread: {result['spread']:.2f}")
    rprint(f"  Total data points: {result['total_members']}")

    table = Table(title="Barcha modellar natijasi")
    table.add_column("Model", style="cyan")
    table.add_column("Turi")
    table.add_column("Ehtimollik", style="green")
    table.add_column("Members")
    table.add_column("High")

    for m in result.get("per_model", []):
        table.add_row(
            m["model_name"],
            m["type"],
            f"{m['probability']:.0%}",
            str(m["members"]),
            f"{m['high']:.1f}°F",
        )
    console.print(table)
