"""
Polymarket Weather Leaderboard & Copy Trading Module

Fetches top weather traders from Polymarket and generates copy-trading signals.
"""

import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

DATA_API_BASE = "https://data-api.polymarket.com/v1"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

WEATHER_KEYWORDS = [
    "temperature", "weather", "rain", "snow", "hurricane",
    "celsius", "fahrenheit", "degrees", "heat", "cold",
    "warm", "cool", "storm", "wind", "precipitation",
    "climate", "forecast", "sunny", "cloudy",
    "highest", "°c", "°f",
]


def fetch_weather_leaderboard(period: str = "MONTH", limit: int = 20) -> list[dict]:
    """Fetch top Polymarket weather traders by PnL.

    Args:
        period: Time period - MONTH, WEEK, ALL, etc.
        limit: Number of traders to return (max 20).

    Returns:
        List of dicts with keys: rank, wallet, username, pnl, volume,
        win_rate, trades_count.
    """
    url = f"{DATA_API_BASE}/leaderboard"
    params = {
        "category": "WEATHER",
        "period": period,
        "limit": limit,
        "order": "pnl",
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Failed to fetch leaderboard: %s", exc)
        return []

    if not isinstance(data, list):
        logger.warning("Unexpected leaderboard response format: %s", type(data))
        return []

    traders = []
    for i, entry in enumerate(data, start=1):
        wallet = entry.get("proxyWallet", "")
        username = entry.get("userName", "") or entry.get("username", "")
        # Agar username wallet bilan bir xil bo'lsa — qisqartiramiz
        if not username or username == wallet:
            username = wallet[:6] + "..." + wallet[-4:] if wallet else "anonymous"

        traders.append({
            "rank": int(entry.get("rank", i)),
            "wallet": wallet,
            "username": username,
            "pnl": round(float(entry.get("pnl", 0)), 2),
            "volume": round(float(entry.get("vol", 0)), 2),
            "win_rate": float(entry.get("winRate", 0)),
            "trades_count": int(entry.get("tradesCount", 0)),
            "profile_image": entry.get("profileImage", ""),
            "x_username": entry.get("xUsername", ""),
        })

    return traders


def fetch_trader_activity(wallet_address: str, limit: int = 20) -> list[dict]:
    """Fetch recent trading activity for a specific wallet.

    Tries the data API first, falls back to the gamma API.

    Args:
        wallet_address: The trader's proxy wallet address.
        limit: Maximum number of activity entries.

    Returns:
        List of trade/activity dicts.
    """
    if not wallet_address:
        logger.warning("Empty wallet address provided")
        return []

    urls = [
        f"{DATA_API_BASE}/activity",
        f"{GAMMA_API_BASE}/activity",
    ]

    for url in urls:
        try:
            # Data API "user" param, Gamma API "address" param
            param_key = "user" if "data-api" in url else "address"
            resp = requests.get(
                url,
                params={param_key: wallet_address, "limit": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            if isinstance(data, list) and data:
                return data
            if isinstance(data, dict) and data.get("data"):
                return data["data"]

        except requests.RequestException as exc:
            logger.debug("Activity fetch failed for %s at %s: %s", wallet_address, url, exc)
            continue

    logger.warning("Could not fetch activity for wallet %s", wallet_address)
    return []


def _is_weather_market(text: str) -> bool:
    """Check whether a market question/title relates to weather."""
    lower = text.lower()
    return any(kw in lower for kw in WEATHER_KEYWORDS)


def get_copy_signals(top_n: int = 5) -> list[dict]:
    """Generate copy-trading signals from top weather traders.

    Fetches the top N weather traders, checks their recent activity,
    and filters for weather/temperature markets only.

    Args:
        top_n: Number of top traders to monitor.

    Returns:
        List of signal dicts with keys: trader_username, trader_pnl,
        market_question, side, price, timestamp.
    """
    traders = fetch_weather_leaderboard(limit=top_n)
    if not traders:
        logger.info("No traders found for copy signals")
        return []

    signals = []

    for trader in traders[:top_n]:
        wallet = trader.get("wallet", "")
        if not wallet:
            continue

        activity = fetch_trader_activity(wallet, limit=20)

        for trade in activity:
            question = (
                trade.get("question", "")
                or trade.get("market", {}).get("question", "")
                or trade.get("title", "")
                or trade.get("marketQuestion", "")
                or ""
            )

            if not question or not _is_weather_market(question):
                continue

            side = (
                trade.get("side", "")
                or trade.get("outcome", "")
                or trade.get("type", "")
                or "unknown"
            )

            price = float(trade.get("price", 0) or trade.get("avgPrice", 0) or 0)

            timestamp = (
                trade.get("timestamp", "")
                or trade.get("createdAt", "")
                or trade.get("time", "")
                or ""
            )

            signals.append({
                "trader_username": trader.get("username", "anonymous"),
                "trader_pnl": trader.get("pnl", 0),
                "market_question": question,
                "side": side,
                "price": price,
                "timestamp": timestamp,
            })

    signals.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
    return signals


def format_leaderboard_telegram(traders: list) -> str:
    """Format leaderboard data for a Telegram message.

    Args:
        traders: List of trader dicts from fetch_weather_leaderboard().

    Returns:
        Formatted string with medal emojis and stats.
    """
    if not traders:
        return "No weather traders found."

    medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}
    lines = ["\U0001f3c6 <b>Top Weather Traders</b>\n"]

    for trader in traders:
        rank = trader.get("rank", "?")
        medal = medals.get(rank, f"#{rank}")
        username = trader.get("username", "anonymous")
        pnl = trader.get("pnl", 0)
        volume = trader.get("volume", 0)
        win_rate = trader.get("win_rate", 0)
        trades_count = trader.get("trades_count", 0)

        pnl_sign = "+" if pnl >= 0 else ""
        pnl_str = f"{pnl_sign}${pnl:,.2f}"

        line = (
            f"{medal} <b>{username}</b>\n"
            f"   PnL: {pnl_str} | Vol: ${volume:,.0f}\n"
            f"   Win rate: {win_rate:.1%} | Trades: {trades_count}"
        )
        lines.append(line)

    lines.append(
        f"\n\U0001f552 Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return "\n".join(lines)


def format_copy_signals_telegram(signals: list) -> str:
    """Format copy-trading signals for a Telegram message.

    Args:
        signals: List of signal dicts from get_copy_signals().

    Returns:
        Formatted string with signal details.
    """
    if not signals:
        return "No weather copy-trading signals right now."

    lines = ["\U0001f4e1 <b>Copy Trading Signals</b>\n"]

    for i, sig in enumerate(signals, start=1):
        username = sig.get("trader_username", "anonymous")
        pnl = sig.get("trader_pnl", 0)
        question = sig.get("market_question", "N/A")
        side = sig.get("side", "unknown")
        price = sig.get("price", 0)
        ts = sig.get("timestamp", "")

        pnl_sign = "+" if pnl >= 0 else ""

        line = (
            f"<b>Signal #{i}</b>\n"
            f"\U0001f464 Trader: {username} ({pnl_sign}${pnl:,.2f} PnL)\n"
            f"\U00002753 {question}\n"
            f"\U000027a1 Side: <b>{side}</b> @ ${price:.2f}\n"
            f"\U0001f552 {ts}"
        )
        lines.append(line)

    return "\n\n".join(lines)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("Fetching weather leaderboard...")
    print("=" * 60)
    leaderboard = fetch_weather_leaderboard(period="MONTH", limit=10)

    if leaderboard:
        print(format_leaderboard_telegram(leaderboard))
        print()

        print("=" * 60)
        print(f"Fetching activity for top trader: {leaderboard[0].get('username')}")
        print("=" * 60)
        activity = fetch_trader_activity(leaderboard[0].get("wallet", ""), limit=5)
        for item in activity[:5]:
            print(item)
        print()
    else:
        print("No leaderboard data returned (API may be unavailable or category empty).")

    print("=" * 60)
    print("Generating copy-trading signals...")
    print("=" * 60)
    sigs = get_copy_signals(top_n=3)
    if sigs:
        print(format_copy_signals_telegram(sigs))
    else:
        print("No copy-trading signals generated.")
