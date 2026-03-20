"""
Polymarket Weather Trading Bot v3 — Asosiy fayl.

Modullar:
  - 10 model ob-havo prognozi (weather.py)
  - Smart timing — resolution yaqinida kuchli savdo (smart_timing.py)
  - WebSocket real-time narx kuzatish (ws_monitor.py)
  - Telegram bot — komandalar va menyular (telegram_commands.py)
"""

import os
import time
import json
import schedule
from datetime import datetime, timezone
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from src.trading.strategy import scan_all_opportunities, save_trade, load_trades, kelly_size
from src.notifications.telegram_bot import send_signals, send_daily_summary, send_startup_message, send_message

load_dotenv()
console = Console()

# ═══════════════════════════════════════
# SOZLAMALAR
# ═══════════════════════════════════════
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
MIN_EDGE = float(os.getenv("MIN_EDGE", "0.20"))
MAX_BET = float(os.getenv("MAX_BET_USD", "1.0"))
BANKROLL = float(os.getenv("BANKROLL", "500.0"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "40"))
MAX_SIGNALS_PER_SCAN = 3
SCAN_INTERVAL_MIN = 15
REPORT_HOURS = [0, 6, 8, 12, 18]

last_report_hour = -1
last_signals = []
last_executed = []


def get_clob_client():
    if DRY_RUN:
        return None
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        creds = ApiCreds(
            api_key=os.getenv("POLY_API_KEY", ""),
            api_secret=os.getenv("POLY_API_SECRET", ""),
            api_passphrase=os.getenv("POLY_API_PASSPHRASE", ""),
        )
        return ClobClient(
            "https://clob.polymarket.com",
            key=os.getenv("POLY_PRIVATE_KEY", ""),
            chain_id=137, creds=creds,
        )
    except Exception as e:
        console.print(f"[red]CLOB xato: {e}[/]")
        return None


def execute_trade(client, signal: dict) -> bool:
    if DRY_RUN or client is None:
        console.print(f"  [dim]DRY RUN: {signal['side']} ${signal['bet_size']:.2f} @ ${signal['market_price']:.2f}[/]")
        save_trade({"timestamp": datetime.now(timezone.utc).isoformat(), "dry_run": True, **signal})
        return True

    try:
        from py_clob_client.order_builder.constants import BUY
        signed_order = client.create_and_sign_order({
            "token_id": signal["market_id"],
            "price": signal["market_price"],
            "size": signal["bet_size"],
            "side": BUY,
        })
        result = client.post_order(signed_order)
        console.print(f"  [green]ORDER: {result}[/]")
        save_trade({"timestamp": datetime.now(timezone.utc).isoformat(), "dry_run": False, "order_result": str(result), **signal})
        return True
    except Exception as e:
        console.print(f"  [red]Savdo xatosi: {e}[/]")
        send_message(f"❌ <b>Savdo xatosi:</b>\n{signal['city']} | {signal['side']}\n{e}")
        return False


def apply_smart_timing(signals: list) -> list:
    """Smart timing bilan signallarni qayta baholaydi."""
    try:
        from src.trading.smart_timing import get_timing_score, adjust_bet_for_timing
        for s in signals:
            timing = get_timing_score(s.get("date", ""), s.get("date", "") + "T23:59:00Z")
            s["timing_score"] = timing.get("timing_score", 1.0)
            s["hours_to_resolution"] = timing.get("hours_to_resolution", 999)
            s["timing_phase"] = timing.get("phase", "unknown")
            s["bet_size"] = adjust_bet_for_timing(s.get("bet_size", 0), timing, MAX_BET)
        # Timing score bo'yicha qayta tartiblash
        signals.sort(key=lambda x: (x.get("timing_score", 0), x.get("edge", 0)), reverse=True)
    except Exception as e:
        console.print(f"[dim]Smart timing xatosi: {e}[/]")
    return signals



def run_scan():
    """Bitta to'liq scan sikli — barcha modullar integratsiya qilingan."""
    global last_signals, last_executed, last_report_hour

    now = datetime.now(timezone.utc)
    console.print(Panel(
        f"[bold]SCAN: {now.strftime('%Y-%m-%d %H:%M UTC')}[/]\n"
        f"Mode: {'[yellow]DRY RUN[/]' if DRY_RUN else '[green]LIVE[/]'} | "
        f"Edge: {MIN_EDGE:.0%} | Bet: ${MAX_BET} | Bank: ${BANKROLL}",
        title="Weather Bot v3",
    ))

    # 1) Multi-model scan
    try:
        signals = scan_all_opportunities(min_edge=MIN_EDGE, bankroll=BANKROLL, max_bet=MAX_BET)
    except Exception as e:
        console.print(f"[red]Scan xatosi: {e}[/]")
        send_message(f"⚠️ <b>Scan xatosi:</b>\n{e}")
        return

    # 2) Smart timing
    signals = apply_smart_timing(signals)

    last_signals = signals

    if not signals:
        console.print("[dim]Signal topilmadi.[/]\n")
    else:
        # Bugungi savdolar sonini hisoblash
        today_str = now.strftime("%Y-%m-%d")
        all_trades = load_trades()
        today_count = sum(1 for t in all_trades if str(t.get("timestamp", "")).startswith(today_str))
        remaining = MAX_TRADES_PER_DAY - today_count

        if remaining <= 0:
            console.print(f"[yellow]Kunlik limit ({MAX_TRADES_PER_DAY}) to'ldi. Bugun savdo yo'q.[/]\n")
            return

        # Faqat eng kuchli signallar (max MAX_SIGNALS_PER_SCAN, kunlik limitdan oshmagan holda)
        take = min(MAX_SIGNALS_PER_SCAN, remaining)
        signals = signals[:take]

        console.print(f"\n[bold green]{len(signals)} ta signal! (bugun: {today_count}/{MAX_TRADES_PER_DAY})[/]\n")

        client = get_clob_client()
        executed = []
        for i, signal in enumerate(signals, 1):
            unit = "°" + signal.get("unit", "F")
            tl, th = signal["temp_low"], signal["temp_high"]
            if tl == -999:
                temp_str = f"<={th-1}{unit}"
            elif th == 999:
                temp_str = f">={tl}{unit}"
            else:
                temp_str = f"{tl}-{th-1}{unit}"

            phase = signal.get("timing_phase", "")
            phase_icon = "🔥" if phase == "optimal" else "⚡" if phase == "good" else ""

            console.print(
                f"[bold]#{i}[/] {signal['city']} | {temp_str} | "
                f"{signal['side']} | Edge: [magenta]{signal['edge']:.0%}[/] | "
                f"{signal['model_prob']:.0%} vs ${signal['market_price']:.2f} | "
                f"Bet: [green]${signal['bet_size']:.2f}[/] {phase_icon}"
            )
            if execute_trade(client, signal):
                executed.append(signal)
        last_executed = executed

    # ═══════════════════════════════════════
    # Telegram hisobotlar
    # ═══════════════════════════════════════
    current_hour = now.hour
    if current_hour in REPORT_HOURS and current_hour != last_report_hour:
        last_report_hour = current_hour
        console.print("[cyan]Telegram hisobot...[/]")

        send_signals(last_executed)

        # Kunlik xulosa (00:00 UTC)
        if current_hour == 0:
            trades = load_trades()
            send_daily_summary(signals, trades)

        # P&L hisobot (08:00 UTC)
        if current_hour == 8:
            try:
                from src.trading.tracker import evaluate_trades, format_daily_pnl
                stats = evaluate_trades()
                send_message(format_daily_pnl(stats))
            except Exception as e:
                console.print(f"[red]P&L xatosi: {e}[/]")

    console.print()


def start_websocket_monitor():
    """WebSocket narx kuzatishni boshlaydi."""
    try:
        from src.monitoring.ws_monitor import start_ws_monitor, set_market_metadata
        # Hozirgi signallardagi market_id larni track qilamiz
        if last_signals:
            market_ids = [str(s.get("market_id", "")) for s in last_signals[:20] if s.get("market_id")]
            if market_ids:
                start_ws_monitor(market_ids)
                console.print(f"[green]WebSocket: {len(market_ids)} ta market kuzatilmoqda[/]")

                for s in last_signals[:20]:
                    mid = str(s.get("market_id", ""))
                    if mid:
                        set_market_metadata(mid, {
                            "city": s.get("city"),
                            "question": s.get("question", ""),
                            "model_prob": s.get("model_prob", 0),
                            "temp_range": f"{s.get('temp_low','')}-{s.get('temp_high','')}",
                        })
    except Exception as e:
        console.print(f"[dim]WebSocket xatosi: {e}[/]")


def main():
    console.print(Panel(
        "[bold]POLYMARKET WEATHER BOT v3[/]\n\n"
        f"Mode: {'[yellow]DRY RUN[/]' if DRY_RUN else '[bold red]LIVE TRADING[/]'}\n"
        f"Modullar: 10-model, Smart Timing, AI, WebSocket, Kalshi, Accuracy\n"
        f"Scan: har {SCAN_INTERVAL_MIN} daqiqa\n"
        f"Edge: {MIN_EDGE:.0%} | Bet: ${MAX_BET} | Bank: ${BANKROLL}\n\n"
        "[dim]To'xtatish: Ctrl+C[/]",
        title="Boshlash",
        border_style="green" if DRY_RUN else "red",
    ))

    # Telegram menyu + polling
    from src.notifications.telegram_commands import set_bot_commands, start_polling_thread
    set_bot_commands()
    start_polling_thread()
    console.print("[green]Telegram menyular + polling boshlandi[/]")

    # Startup xabari
    send_startup_message()

    # Birinchi scan
    run_scan()

    # WebSocket monitor boshlash
    start_websocket_monitor()

    # Birinchi bajarilgan savdolarni Telegram'ga
    if last_executed:
        send_signals(last_executed)

    # Schedule
    schedule.every(SCAN_INTERVAL_MIN).minutes.do(run_scan)

    # Har soatda WebSocket'ni yangilash
    schedule.every(60).minutes.do(start_websocket_monitor)

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        console.print("\n[yellow]Bot to'xtatildi.[/]")
        try:
            from src.monitoring.ws_monitor import stop_ws_monitor
            stop_ws_monitor()
        except Exception:
            pass
        send_message("🛑 <b>Weather Bot v3 to'xtatildi.</b>")


if __name__ == "__main__":
    main()
