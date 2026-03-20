"""
AI-powered weather analysis using Anthropic Claude API.

Analyzes weather events that numerical models might miss:
- Extreme weather (storms, cold fronts, heat waves)
- Model disagreement patterns
- NWS alerts that could shift temperature forecasts

Gracefully degrades when ANTHROPIC_API_KEY is not set.
"""

import os
import logging
import requests
from datetime import datetime, timezone

from src.trading.markets import CITY_COORDS

logger = logging.getLogger(__name__)

# NWS alerts endpoint (US cities only)
NWS_ALERTS_URL = "https://api.weather.gov/alerts/active"

# US cities that have NWS coverage
US_CITIES = {"nyc", "chicago", "dallas", "atlanta", "miami", "los_angeles"}

# Neutral result returned when API key is missing or call fails
NEUTRAL_RESULT = {
    "adjustment": 0.0,
    "reasoning": "AI analysis unavailable",
    "risk_flags": [],
    "recommendation": "HOLD",
}


def _get_client():
    """Create Anthropic client if API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=api_key)
    except ImportError:
        logger.warning("anthropic package not installed — pip install anthropic")
        return None
    except Exception as e:
        logger.warning("Failed to create Anthropic client: %s", e)
        return None


def _call_claude(prompt: str, max_tokens: int = 512) -> str | None:
    """Send a prompt to Claude and return the text response."""
    client = _get_client()
    if client is None:
        return None

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.warning("Claude API call failed: %s", e)
        return None


# ════════════════════════════════════════
# NWS ALERTS
# ════════════════════════════════════════

def check_extreme_weather(city: str, date: str) -> dict:
    """
    Check for extreme weather events that could affect predictions.
    Uses NWS alerts API for US cities.

    Args:
        city: City key (e.g. "nyc", "chicago")
        date: Target date "YYYY-MM-DD"

    Returns:
        {
            "has_alerts": bool,
            "alerts": [{"event": str, "severity": str, "headline": str}],
            "risk_level": "none" | "low" | "moderate" | "high" | "extreme"
        }
    """
    result = {
        "has_alerts": False,
        "alerts": [],
        "risk_level": "none",
    }

    # Only US cities have NWS coverage
    if city not in US_CITIES:
        return result

    coords = CITY_COORDS.get(city)
    if not coords:
        return result

    try:
        params = {"point": f"{coords['lat']},{coords['lon']}"}
        resp = requests.get(
            NWS_ALERTS_URL,
            params=params,
            headers={"User-Agent": "PolyWeatherBot/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning("NWS alerts request failed for %s: %s", city, e)
        return result

    features = data.get("features", [])
    if not features:
        return result

    severity_rank = {"Extreme": 4, "Severe": 3, "Moderate": 2, "Minor": 1, "Unknown": 0}
    max_severity = 0

    for feature in features:
        props = feature.get("properties", {})
        event = props.get("event", "")
        severity = props.get("severity", "Unknown")
        headline = props.get("headline", "")
        effective = props.get("effective", "")
        expires = props.get("expires", "")

        # Check if alert overlaps with our target date
        alert_start = effective[:10] if effective else ""
        alert_end = expires[:10] if expires else ""
        if alert_end and alert_end < date:
            continue  # Alert expires before target date
        if alert_start and alert_start > date:
            continue  # Alert starts after target date

        result["alerts"].append({
            "event": event,
            "severity": severity,
            "headline": headline,
        })

        rank = severity_rank.get(severity, 0)
        if rank > max_severity:
            max_severity = rank

    result["has_alerts"] = len(result["alerts"]) > 0

    # Map severity rank to risk level
    risk_map = {0: "none", 1: "low", 2: "moderate", 3: "high", 4: "extreme"}
    result["risk_level"] = risk_map.get(max_severity, "none")

    return result


# ════════════════════════════════════════
# MAIN ANALYSIS
# ════════════════════════════════════════

def analyze_weather_event(city: str, date: str, model_data: dict, market_data: dict) -> dict:
    """
    Send weather context to Claude for analysis.

    Args:
        city: City key (e.g. "nyc")
        date: Target date "YYYY-MM-DD"
        model_data: Output from multi_model_probability() — contains per_model,
                    probability, spread, consensus, mean_high, etc.
        market_data: Market info — temp_low, temp_high, unit, yes_price, etc.

    Returns:
        {
            "adjustment": float,        # e.g. +0.05 means +5% confidence boost
            "reasoning": str,           # explanation
            "risk_flags": list[str],    # e.g. ["extreme_weather", "model_disagreement"]
            "recommendation": str,      # "HOLD" / "BUY" / "SKIP"
        }
    """
    # Check NWS alerts first (cheap, no API cost)
    alerts = check_extreme_weather(city, date)

    # Build context for Claude
    per_model = model_data.get("per_model", [])
    model_summary = ", ".join(
        f"{m['model_name']}={m['probability']:.0%}" for m in per_model
    )

    unit_symbol = "F" if market_data.get("unit") == "F" else "C"
    temp_low = market_data.get("temp_low", "?")
    temp_high = market_data.get("temp_high", "?")

    # Format temp range for display
    if temp_low == -999:
        temp_range_str = f"<={temp_high - 1} deg{unit_symbol}"
    elif temp_high == 999:
        temp_range_str = f">={temp_low} deg{unit_symbol}"
    else:
        temp_range_str = f"{temp_low}-{temp_high - 1} deg{unit_symbol}"

    alert_text = "None"
    if alerts["has_alerts"]:
        alert_lines = [f"- {a['event']} ({a['severity']})" for a in alerts["alerts"][:5]]
        alert_text = "\n".join(alert_lines)

    prompt = f"""Analyze this weather prediction market. Be concise.

City: {city}, Date: {date}
Temperature bucket: {temp_range_str}
Model consensus probability: {model_data.get('weighted_probability', 0):.0%}
Model spread: {model_data.get('spread', 0):.2f}
Consensus: {model_data.get('consensus', 'N/A')}
Mean forecast high: {model_data.get('mean_high', 0):.1f} deg{unit_symbol}
Min/Max forecast: {model_data.get('min_high', 0):.1f} - {model_data.get('max_high', 0):.1f} deg{unit_symbol}
Per-model: {model_summary}
Market YES price: ${market_data.get('yes_price', 0):.3f}
NWS alerts: {alert_text}

Reply in EXACTLY this format (no extra text):
ADJUSTMENT: <float between -0.15 and +0.15>
REASONING: <one sentence>
RISK_FLAGS: <comma-separated or "none">
RECOMMENDATION: <BUY or HOLD or SKIP>"""

    raw = _call_claude(prompt, max_tokens=256)

    if raw is None:
        # No API key or call failed — return neutral with any alert info
        result = NEUTRAL_RESULT.copy()
        result["risk_flags"] = list(result["risk_flags"])  # copy the list
        if alerts["has_alerts"]:
            result["risk_flags"].append("nws_alert_active")
            result["reasoning"] = f"AI unavailable. NWS alert: {alerts['risk_level']} risk"
        return result

    # Parse Claude's response
    return _parse_analysis_response(raw, alerts)


def _parse_analysis_response(raw: str, alerts: dict) -> dict:
    """Parse structured response from Claude."""
    result = {
        "adjustment": 0.0,
        "reasoning": "",
        "risk_flags": [],
        "recommendation": "HOLD",
    }

    for line in raw.strip().split("\n"):
        line = line.strip()
        if line.startswith("ADJUSTMENT:"):
            try:
                val = float(line.split(":", 1)[1].strip())
                result["adjustment"] = max(-0.15, min(0.15, val))
            except ValueError:
                pass
        elif line.startswith("REASONING:"):
            result["reasoning"] = line.split(":", 1)[1].strip()
        elif line.startswith("RISK_FLAGS:"):
            flags_str = line.split(":", 1)[1].strip().lower()
            if flags_str and flags_str != "none":
                result["risk_flags"] = [f.strip() for f in flags_str.split(",") if f.strip()]
        elif line.startswith("RECOMMENDATION:"):
            rec = line.split(":", 1)[1].strip().upper()
            if rec in ("BUY", "HOLD", "SKIP"):
                result["recommendation"] = rec

    # Inject NWS alert flag if present
    if alerts.get("has_alerts") and "nws_alert_active" not in result["risk_flags"]:
        result["risk_flags"].append("nws_alert_active")

    return result


# ════════════════════════════════════════
# DAILY BRIEF
# ════════════════════════════════════════

def get_daily_weather_brief(cities: list) -> str:
    """
    Get a daily weather brief from Claude for monitored cities.
    Returns a formatted Telegram message with key weather events.

    Args:
        cities: List of city keys (e.g. ["nyc", "chicago", "miami"])

    Returns:
        Formatted string for Telegram (Markdown).
    """
    if not cities:
        return "No cities to monitor."

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Collect NWS alerts for US cities (free, no AI cost)
    alerts_summary = []
    for city in cities:
        alerts = check_extreme_weather(city, today)
        if alerts["has_alerts"]:
            alert_events = [a["event"] for a in alerts["alerts"][:3]]
            alerts_summary.append(f"{city.upper()}: {', '.join(alert_events)}")

    alerts_block = "\n".join(alerts_summary) if alerts_summary else "No active NWS alerts"

    # Get city coordinates for context
    city_list = []
    for city in cities:
        coords = CITY_COORDS.get(city)
        if coords:
            city_list.append(f"{city} ({coords['lat']:.1f}N, {coords['lon']:.1f}E)")
        else:
            city_list.append(city)

    prompt = f"""Give a brief weather outlook for prediction markets. Today: {today}.

Cities: {', '.join(city_list)}
Active NWS alerts:
{alerts_block}

Write a SHORT Telegram-ready message (max 600 chars) using this format:
- Header line with date
- One bullet per city with key weather factor
- Any risk warnings at the bottom
Use plain text, no markdown."""

    raw = _call_claude(prompt, max_tokens=400)

    if raw is None:
        # Fallback: just return NWS alerts
        lines = [f"Weather Brief - {today}", ""]
        if alerts_summary:
            lines.append("Active Alerts:")
            lines.extend(f"  {a}" for a in alerts_summary)
        else:
            lines.append("No active NWS alerts for monitored cities.")
        lines.append("")
        lines.append("(AI analysis unavailable - set ANTHROPIC_API_KEY)")
        return "\n".join(lines)

    return raw


# ════════════════════════════════════════
# CONVENIENCE
# ════════════════════════════════════════

def is_ai_available() -> bool:
    """Check whether the Anthropic API key is configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


if __name__ == "__main__":
    # Quick test
    print(f"AI available: {is_ai_available()}")
    print()

    # Test NWS alerts for NYC
    print("Checking NWS alerts for NYC...")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    alerts = check_extreme_weather("nyc", today)
    print(f"  Has alerts: {alerts['has_alerts']}")
    print(f"  Risk level: {alerts['risk_level']}")
    for a in alerts["alerts"][:5]:
        print(f"  - {a['event']} ({a['severity']}): {a['headline'][:80]}")

    print()

    # Test daily brief (uses Claude if key is set)
    print("Getting daily brief...")
    brief = get_daily_weather_brief(["nyc", "chicago", "miami"])
    print(brief)
