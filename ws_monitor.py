"""
Polymarket weather bozorlarini real-vaqt WebSocket orqali kuzatish moduli.
Narx o'zgarishlarini kuzatadi va katta edge paydo bo'lganda Telegram'ga alert yuboradi.
"""

import asyncio
import json
import logging
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

import websockets

from telegram_bot import send_message

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════
# Konfiguratsiya
# ═══════════════════════════════════════

WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

# Narx tarixi — har bir market uchun oxirgi N ta narxni saqlaymiz
MAX_PRICE_HISTORY = 100

# Alert chegaralari
PRICE_DROP_THRESHOLD = 0.05      # Narx 5% tushsa alert
EDGE_INCREASE_THRESHOLD = 0.10   # Edge 10% oshsa alert
MIN_EDGE_FOR_ALERT = 0.08        # Kamida 8% edge bo'lsin

# Reconnect sozlamalari
RECONNECT_DELAY_BASE = 2         # Boshlang'ich kutish (sekund)
RECONNECT_DELAY_MAX = 60         # Maksimal kutish (sekund)
PING_INTERVAL = 30               # Ping har 30 sekundda
PING_TIMEOUT = 10                # Ping javob kutish

# ═══════════════════════════════════════
# Global state
# ═══════════════════════════════════════

# market_id -> deque of {"price": float, "timestamp": str}
price_history: dict[str, deque] = defaultdict(lambda: deque(maxlen=MAX_PRICE_HISTORY))

# market_id -> {"yes_price": float, "no_price": float}
current_prices: dict[str, dict] = {}

# market_id -> {"city": str, "question": str, "model_prob": float, ...}
market_metadata: dict[str, dict] = {}

# Monitor holati
_monitor_thread: threading.Thread | None = None
_stop_event = threading.Event()
_is_running = False


# ═══════════════════════════════════════
# Narx yangilanish callback
# ═══════════════════════════════════════

def on_price_update(market_id: str, old_price: float, new_price: float):
    """
    Narx o'zgarganda chaqiriladi.
    Tarixga yozadi va alert tekshiradi.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Tarixga qo'shish
    price_history[market_id].append({
        "price": new_price,
        "timestamp": now,
    })

    # Narxni yangilash
    current_prices[market_id] = {
        "yes_price": new_price,
        "updated_at": now,
    }

    change = new_price - old_price
    direction = "+" if change > 0 else ""

    logger.info(
        f"Narx yangilandi: {market_id[:12]}... "
        f"${old_price:.3f} -> ${new_price:.3f} ({direction}{change:.3f})"
    )

    # Metadata mavjud bo'lsa, alert tekshirish
    meta = market_metadata.get(market_id)
    if meta and "model_prob" in meta:
        check_price_alert(market_id, new_price, meta["model_prob"])


def check_price_alert(market_id: str, new_price: float, model_prob: float):
    """
    Edge oshganmi tekshiradi. Agar oshgan bo'lsa Telegram'ga alert yuboradi.

    Edge = model_prob - market_price (YES uchun)
    Narx tushsa -> edge oshadi -> yaxshi imkoniyat
    """
    meta = market_metadata.get(market_id, {})
    history = price_history.get(market_id)

    if not history or len(history) < 2:
        return

    # Oldingi narx
    old_entry = history[-2]
    old_price = old_entry["price"]

    # Edge hisoblash
    old_edge = model_prob - old_price
    new_edge = model_prob - new_price

    # Narx pasayishi (biz uchun yaxshi — arzonlashdi)
    price_drop = old_price - new_price

    # Alert sharti: narx sezilarli tushgan VA edge yetarli katta
    should_alert = (
        price_drop >= PRICE_DROP_THRESHOLD
        and new_edge >= MIN_EDGE_FOR_ALERT
        and (new_edge - old_edge) >= EDGE_INCREASE_THRESHOLD
    )

    if not should_alert:
        return

    # Alert yuborish
    city = meta.get("city", "???")
    question = meta.get("question", "")
    temp_low = meta.get("temp_low", "?")
    temp_high = meta.get("temp_high", "?")
    unit = meta.get("unit", "F")

    # Harorat oralig'ini formatlash
    if temp_low == -999:
        temp_str = f"<={temp_high - 1} degrees {unit}"
    elif temp_high == 999:
        temp_str = f">={temp_low} degrees {unit}"
    else:
        temp_str = f"{temp_low}-{temp_high - 1} degrees {unit}"

    # Edge yo'nalishi
    edge_direction = "^^" if new_edge > old_edge else "vv"

    alert_text = (
        f"NARX ALERT\n"
        f"{city.upper()} {temp_str} | YES narxi ${old_price:.2f} -> ${new_price:.2f}\n"
        f"Edge: {old_edge:.0%} -> {new_edge:.0%} {edge_direction}\n"
        f"Model: {model_prob:.0%} vs Market: ${new_price:.2f}"
    )

    logger.warning(f"ALERT: {alert_text}")
    send_message(alert_text, parse_mode="HTML")


# ═══════════════════════════════════════
# WebSocket ulanish va monitoring
# ═══════════════════════════════════════

async def _subscribe(ws, market_ids: list[str]):
    """Bozorlarga obuna bo'lish."""
    for market_id in market_ids:
        sub_msg = json.dumps({
            "type": "subscribe",
            "channel": "market",
            "market": market_id,
        })
        await ws.send(sub_msg)
        logger.info(f"Obuna: {market_id[:16]}...")


async def _handle_message(raw_msg: str):
    """
    WebSocket xabarini qayta ishlash.
    Polymarket CLOB narx yangilanishlarini parse qiladi.
    """
    try:
        msg = json.loads(raw_msg)
    except json.JSONDecodeError:
        logger.warning(f"JSON parse xatosi: {raw_msg[:200]}")
        return

    msg_type = msg.get("type", "")

    # Heartbeat / pong — skip
    if msg_type in ("pong", "heartbeat", "connected"):
        return

    # Narx yangilanishi
    if msg_type in ("market", "price_change", "book"):
        _process_price_message(msg)
        return

    # Subscription confirmation
    if msg_type == "subscribed":
        channel = msg.get("channel", "")
        market = msg.get("market", "")
        logger.info(f"Obuna tasdiqlandi: {channel} / {market[:16]}...")
        return

    # Boshqa xabar turlari — log qilish
    logger.debug(f"WS xabar: {msg_type} -> {json.dumps(msg)[:300]}")


def _process_price_message(msg: dict):
    """Narx xabarini qayta ishlash va callback chaqirish."""
    market_id = msg.get("market", msg.get("market_id", msg.get("asset_id", "")))

    if not market_id:
        # Xabar ichidan market ma'lumotini qidirish
        data = msg.get("data", msg)
        market_id = data.get("market", data.get("market_id", ""))

    if not market_id:
        return

    # Narxni ajratib olish — Polymarket turli formatlarda yuboradi
    new_price = _extract_price(msg)
    if new_price is None or new_price <= 0:
        return

    # Oldingi narx
    old_data = current_prices.get(market_id, {})
    old_price = old_data.get("yes_price", new_price)

    # Agar narx o'zgarmagan bo'lsa — skip
    if abs(new_price - old_price) < 0.0001:
        return

    on_price_update(market_id, old_price, new_price)


def _extract_price(msg: dict) -> float | None:
    """Xabardan YES narxini ajratib olish."""
    # Direct price field
    for key in ("price", "yes_price", "best_ask", "best_bid"):
        val = msg.get(key)
        if val is not None:
            try:
                return float(val)
            except (ValueError, TypeError):
                pass

    # Nested data
    data = msg.get("data", {})
    if isinstance(data, dict):
        for key in ("price", "yes_price", "best_ask", "best_bid"):
            val = data.get(key)
            if val is not None:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass

        # Outcome prices array
        prices = data.get("outcome_prices", data.get("outcomePrices", []))
        if prices and len(prices) > 0:
            try:
                return float(prices[0])
            except (ValueError, TypeError):
                pass

    # Prices array at top level
    prices = msg.get("outcome_prices", msg.get("outcomePrices", []))
    if prices and len(prices) > 0:
        try:
            return float(prices[0])
        except (ValueError, TypeError):
            pass

    return None


async def _ws_loop(market_ids: list[str]):
    """
    Asosiy WebSocket loop — ulanish, obuna, xabarlarni tinglash.
    Uzilib qolsa qayta ulanadi (exponential backoff).
    """
    reconnect_delay = RECONNECT_DELAY_BASE

    while not _stop_event.is_set():
        try:
            logger.info(f"WebSocket ulanmoqda: {WS_URL}")

            async with websockets.connect(
                WS_URL,
                ping_interval=PING_INTERVAL,
                ping_timeout=PING_TIMEOUT,
                close_timeout=10,
            ) as ws:
                logger.info("WebSocket ulandi!")
                reconnect_delay = RECONNECT_DELAY_BASE  # Reset backoff

                # Obuna bo'lish
                await _subscribe(ws, market_ids)

                # Xabarlarni tinglash
                async for raw_msg in ws:
                    if _stop_event.is_set():
                        break
                    await _handle_message(raw_msg)

        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket yopildi: {e}")
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket xatosi: {e}")
        except asyncio.CancelledError:
            logger.info("WebSocket loop bekor qilindi")
            break
        except Exception as e:
            logger.error(f"Kutilmagan xato: {e}", exc_info=True)

        if _stop_event.is_set():
            break

        # Qayta ulanish kutish (exponential backoff)
        logger.info(f"Qayta ulanish {reconnect_delay}s dan keyin...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, RECONNECT_DELAY_MAX)


def _run_ws_in_thread(market_ids: list[str]):
    """Background thread uchun WebSocket loop'ini ishga tushirish."""
    global _is_running

    _is_running = True
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_ws_loop(market_ids))
    except Exception as e:
        logger.error(f"WS thread xatosi: {e}", exc_info=True)
    finally:
        loop.close()
        _is_running = False
        logger.info("WebSocket monitor to'xtadi")


# ═══════════════════════════════════════
# Public API
# ═══════════════════════════════════════

def start_ws_monitor(market_ids: list[str]) -> threading.Thread:
    """
    WebSocket monitorni background thread'da ishga tushiradi.

    Args:
        market_ids: Kuzatiladigan bozor ID lari

    Returns:
        threading.Thread obyekti
    """
    global _monitor_thread, _stop_event

    if _is_running:
        logger.warning("Monitor allaqachon ishlayapti!")
        return _monitor_thread

    if not market_ids:
        logger.error("Market ID ro'yxati bo'sh!")
        return None

    _stop_event.clear()

    logger.info(f"WS Monitor ishga tushmoqda — {len(market_ids)} ta bozor")

    _monitor_thread = threading.Thread(
        target=_run_ws_in_thread,
        args=(market_ids,),
        daemon=True,
        name="ws-price-monitor",
    )
    _monitor_thread.start()

    return _monitor_thread


def stop_ws_monitor():
    """Monitorni to'xtatadi."""
    global _monitor_thread

    logger.info("WS Monitor to'xtatilmoqda...")
    _stop_event.set()

    if _monitor_thread and _monitor_thread.is_alive():
        _monitor_thread.join(timeout=15)

    _monitor_thread = None
    logger.info("WS Monitor to'xtadi")


def set_market_metadata(market_id: str, metadata: dict):
    """
    Market uchun metadata o'rnatadi (city, question, model_prob, ...).
    Bu ma'lumotlar alert xabarlarida ishlatiladi.

    Args:
        market_id: Bozor ID
        metadata: {
            "city": "nyc",
            "question": "51-52 degrees F",
            "model_prob": 0.40,
            "temp_low": 45,
            "temp_high": 51,
            "unit": "F",
        }
    """
    market_metadata[market_id] = metadata
    logger.debug(f"Metadata o'rnatildi: {market_id[:16]}... -> {metadata.get('city')}")


def get_price_history(market_id: str) -> list[dict]:
    """Market uchun narx tarixini qaytaradi."""
    return list(price_history.get(market_id, []))


def get_current_price(market_id: str) -> float | None:
    """Market uchun joriy narxni qaytaradi."""
    data = current_prices.get(market_id)
    if data:
        return data.get("yes_price")
    return None


def get_all_current_prices() -> dict[str, float]:
    """Barcha kuzatilayotgan bozorlarning joriy narxlarini qaytaradi."""
    return {
        mid: data.get("yes_price", 0)
        for mid, data in current_prices.items()
    }


def is_running() -> bool:
    """Monitor ishlayaptimi?"""
    return _is_running


# ═══════════════════════════════════════
# Standalone test
# ═══════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=== Polymarket WS Monitor Test ===")
    print(f"WS URL: {WS_URL}")
    print()

    # Test uchun market ID lari (haqiqiy ID bo'lishi kerak)
    test_ids = input(
        "Market ID kiriting (vergul bilan ajrating, yoki Enter bosing test uchun): "
    ).strip()

    if test_ids:
        ids = [mid.strip() for mid in test_ids.split(",")]
    else:
        print("Market ID kiritilmadi. Haqiqiy ID kerak bo'ladi.")
        print("markets.py dan get_all_opportunities() orqali oling.")
        exit(0)

    # Metadata o'rnatish (test)
    for mid in ids:
        set_market_metadata(mid, {
            "city": "test",
            "question": "Test market",
            "model_prob": 0.40,
            "temp_low": 45,
            "temp_high": 51,
            "unit": "F",
        })

    # Monitorni ishga tushirish
    thread = start_ws_monitor(ids)
    print(f"\nMonitor ishlayapti (thread: {thread.name})")
    print("Ctrl+C bosib to'xtatishingiz mumkin\n")

    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nTo'xtatilmoqda...")
        stop_ws_monitor()
        print("Tayyor!")
