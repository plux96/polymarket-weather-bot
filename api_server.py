"""
REST API server — React dashboard uchun bot ma'lumotlarini uzatadi.
FastAPI + CORS bilan ishlaydi.
"""

import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

load_dotenv()

app = FastAPI(title="Polymarket Weather Bot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(filename):
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return []


@app.get("/api/status")
def get_status():
    trades = load_json("trades.json")
    results = load_json("results.json")
    return {
        "status": "running",
        "mode": "DRY RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "LIVE",
        "min_edge": float(os.getenv("MIN_EDGE", "0.08")),
        "max_bet": float(os.getenv("MAX_BET_USD", "5.0")),
        "bankroll": float(os.getenv("BANKROLL", "100.0")),
        "total_trades": len(trades),
        "total_results": len(results),
        "models": 16,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/trades")
def get_trades(limit: int = 100):
    trades = load_json("trades.json")
    return trades[-limit:]


@app.get("/api/trades/today")
def get_today_trades():
    trades = load_json("trades.json")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return [t for t in trades if t.get("timestamp", "").startswith(today)]


@app.get("/api/results")
def get_results():
    results = load_json("results.json")
    return results


@app.get("/api/pnl")
def get_pnl():
    trades = load_json("trades.json")
    results = load_json("results.json")

    total_bet = sum(t.get("bet_size", 0) for t in trades)
    wins = sum(1 for r in results if r.get("won") is True)
    losses = sum(1 for r in results if r.get("won") is False)
    total_pnl = sum(r.get("pnl", 0) for r in results)

    # Kunlik P&L
    by_date = {}
    for r in results:
        date = r.get("trade", {}).get("date", "unknown")
        if date not in by_date:
            by_date[date] = {"date": date, "pnl": 0, "wins": 0, "losses": 0, "trades": 0}
        by_date[date]["pnl"] += r.get("pnl", 0)
        by_date[date]["trades"] += 1
        if r.get("won"):
            by_date[date]["wins"] += 1
        else:
            by_date[date]["losses"] += 1

    return {
        "total_pnl": round(total_pnl, 2),
        "total_bet": round(total_bet, 2),
        "roi": round(total_pnl / total_bet, 4) if total_bet > 0 else 0,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / (wins + losses), 4) if (wins + losses) > 0 else 0,
        "pending": len(trades) - len(results),
        "daily": sorted(by_date.values(), key=lambda x: x["date"]),
    }


@app.get("/api/cities")
def get_cities():
    trades = load_json("trades.json")
    results = load_json("results.json")

    result_map = {r.get("market_id"): r for r in results}

    cities = {}
    for t in trades:
        city = t.get("city", "unknown")
        if city not in cities:
            cities[city] = {"city": city, "trades": 0, "total_bet": 0, "pnl": 0, "wins": 0, "losses": 0, "avg_edge": 0, "edges": []}
        cities[city]["trades"] += 1
        cities[city]["total_bet"] += t.get("bet_size", 0)
        cities[city]["edges"].append(t.get("edge", 0))

        r = result_map.get(t.get("market_id"))
        if r:
            cities[city]["pnl"] += r.get("pnl", 0)
            if r.get("won"):
                cities[city]["wins"] += 1
            else:
                cities[city]["losses"] += 1

    for c in cities.values():
        c["avg_edge"] = round(sum(c["edges"]) / len(c["edges"]), 4) if c["edges"] else 0
        c["win_rate"] = round(c["wins"] / (c["wins"] + c["losses"]), 4) if (c["wins"] + c["losses"]) > 0 else 0
        c["pnl"] = round(c["pnl"], 2)
        del c["edges"]

    return sorted(cities.values(), key=lambda x: x["pnl"], reverse=True)


@app.get("/api/signals")
def get_signals():
    """Oxirgi scan signallarini qaytaradi."""
    trades = load_json("trades.json")
    # Oxirgi scan — oxirgi 15 daqiqadagi savdolar
    now = datetime.now(timezone.utc)
    recent = []
    for t in reversed(trades):
        ts = t.get("timestamp", "")
        if ts:
            try:
                trade_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                diff = (now - trade_time).total_seconds()
                if diff < 1200:  # 20 daqiqa
                    recent.append(t)
                else:
                    break
            except Exception:
                continue
    return list(reversed(recent))


@app.get("/api/models")
def get_models():
    accuracy = load_json("accuracy.json")
    if isinstance(accuracy, dict):
        return accuracy
    return {}


@app.get("/api/activity")
def get_activity():
    """Oxirgi 24 soatlik faollik — dashboard chart uchun."""
    trades = load_json("trades.json")
    now = datetime.now(timezone.utc)

    hourly = {}
    for t in trades:
        ts = t.get("timestamp", "")
        if not ts:
            continue
        try:
            trade_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            diff_hours = (now - trade_time).total_seconds() / 3600
            if diff_hours <= 24:
                hour_key = trade_time.strftime("%H:00")
                if hour_key not in hourly:
                    hourly[hour_key] = {"hour": hour_key, "trades": 0, "total_bet": 0, "avg_edge": 0, "edges": []}
                hourly[hour_key]["trades"] += 1
                hourly[hour_key]["total_bet"] += t.get("bet_size", 0)
                hourly[hour_key]["edges"].append(t.get("edge", 0))
        except Exception:
            continue

    for h in hourly.values():
        h["avg_edge"] = round(sum(h["edges"]) / len(h["edges"]), 4) if h["edges"] else 0
        h["total_bet"] = round(h["total_bet"], 2)
        del h["edges"]

    return sorted(hourly.values(), key=lambda x: x["hour"])


@app.get("/api/investment")
def get_investment():
    """Jami quyilgan pul va natija vaqtlari."""
    trades = load_json("trades.json")

    total_invested = sum(t.get("bet_size", 0) for t in trades)

    # Resolution dates - qachon natija chiqadi
    resolutions = {}
    for t in trades:
        date = t.get("date", "")
        if date:
            if date not in resolutions:
                resolutions[date] = {"date": date, "trades": 0, "invested": 0, "cities": set()}
            resolutions[date]["trades"] += 1
            resolutions[date]["invested"] += t.get("bet_size", 0)
            resolutions[date]["cities"].add(t.get("city", ""))

    # Convert sets to lists for JSON
    timeline = []
    for d in sorted(resolutions.values(), key=lambda x: x["date"]):
        timeline.append({
            "date": d["date"],
            "trades": d["trades"],
            "invested": round(d["invested"], 2),
            "cities": len(d["cities"]),
            "status": "resolved" if d["date"] < datetime.now(timezone.utc).strftime("%Y-%m-%d") else "pending"
        })

    return {
        "total_invested": round(total_invested, 2),
        "total_trades": len(trades),
        "timeline": timeline,
        "mode": "DRY RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "LIVE",
    }

@app.get("/api/leaderboard")
def get_leaderboard():
    """Top weather traderlar."""
    try:
        from leaderboard import fetch_weather_leaderboard
        return fetch_weather_leaderboard(period="MONTH", limit=20)
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/copy-signals")
def get_copy_signals():
    """Copy trading signallari."""
    try:
        from leaderboard import get_copy_signals
        return get_copy_signals(top_n=5)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8899)
