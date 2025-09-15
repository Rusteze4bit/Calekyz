import time
import requests
import json
import websocket
import threading
from datetime import datetime, timedelta
import statistics

# Telegram bot credentials
TOKEN = "8444887959:AAFUB37iJVvbX68oZ4hkI8nMDiZO_cEWgC8"
GROUP_ID = -1002882813831
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

# Deriv API WebSocket endpoint
DERIV_API_URL = "wss://ws.binaryws.com/websockets/v3?app_id=1089"

# Markets to analyze
MARKETS = ["R_10", "R_25", "R_50", "R_75", "R_100"]

# Market symbol to name mapping
MARKET_NAMES = {
    "R_10": "Volatility 10 Index",
    "R_25": "Volatility 25 Index",
    "R_50": "Volatility 50 Index",
    "R_75": "Volatility 75 Index",
    "R_100": "Volatility 100 Index",
}

# Store last 200 ticks for analysis
market_ticks = {market: [] for market in MARKETS}

# Track message IDs
active_messages = []
last_expired_id = None


def send_telegram_message(message: str, keep=False):
    """Send plain text message to Telegram with debug logs."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Run on Calekyz", "url": "https://www.kashytrader.site/"}
        ]]
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            data={
                "chat_id": GROUP_ID,
                "text": message,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
            }
        )

        if resp.ok:
            msg_id = resp.json()["result"]["message_id"]
            print(f"[Telegram ✅] Sent message ID {msg_id}: {message[:60]}...")
            if not keep:
                active_messages.append(msg_id)
            return msg_id
        else:
            print("[Telegram ❌] Failed:", resp.text)
    except Exception as e:
        print("[Telegram ❌] Exception:", e)

    return None


def delete_messages():
    """Delete old active messages."""
    global active_messages
    for msg_id in active_messages:
        try:
            requests.post(f"{BASE_URL}/deleteMessage", data={
                "chat_id": GROUP_ID,
                "message_id": msg_id
            })
            print(f"[Telegram 🗑️] Deleted message {msg_id}")
        except Exception as e:
            print("[Telegram ❌] Delete error:", e)
    active_messages = []


def delete_last_expired():
    """Delete last expired message before sending a new cycle."""
    global last_expired_id
    if last_expired_id:
        try:
            requests.post(f"{BASE_URL}/deleteMessage", data={
                "chat_id": GROUP_ID,
                "message_id": last_expired_id
            })
            print(f"[Telegram 🗑️] Deleted expired {last_expired_id}")
        except Exception as e:
            print("[Telegram ❌] Delete expired error:", e)
        last_expired_id = None


def analyze_market(market: str, ticks: list):
    """Analyze market digits and return best signal with confidence."""
    if len(ticks) < 30:
        return None

    last_digits = [int(str(t)[-1]) for t in ticks]

    under6_count = sum(d < 6 for d in last_digits)
    under8_count = sum(d < 8 for d in last_digits)

    # streak detection
    last5 = last_digits[-5:]
    streak_under6 = sum(d < 6 for d in last5) / 5
    streak_under8 = sum(d < 8 for d in last5) / 5

    # volatility filter (stddev of last 20 digits)
    vol = statistics.pstdev(last_digits[-20:]) or 1  # avoid div/0

    # weights for signals
    strength = {
        "Under 6": (under6_count / len(last_digits) + streak_under6 * 0.4) / (1 + vol / 10),
        "Under 8": (
            (under8_count / len(last_digits)) * 0.5 +
            streak_under8 * 0.3 +
            (1 / vol) * 0.2
        )
    }

    best_signal = max(strength, key=strength.get)
    confidence = strength[best_signal]

    return best_signal, confidence


def fetch_and_analyze():
    """Pick the best market and send signal."""
    global last_expired_id

    delete_last_expired()

    best_market, best_signal, best_confidence = None, None, 0

    for market in MARKETS:
        if len(market_ticks[market]) > 20:
            result = analyze_market(market, market_ticks[market])
            if result:
                signal, confidence = result
                print(f"[Analysis] {market} → {signal} ({confidence:.2%})")
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_signal = signal
                    best_market = market

    if best_market:
        now = datetime.now()
        entry_digit = int(str(market_ticks[best_market][-1])[-1])
        market_name = MARKET_NAMES.get(best_market, best_market)

        main_msg = (
            f"⚡ <b>KashyTrader Premium Signal</b>\n\n"
            f"⏰ Time: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📊 Market: {market_name}\n"
            f"🎯 Signal: <b>{best_signal}</b>\n"
            f"🔢 Entry Point Digit: <b>{entry_digit}</b>\n"
            f"📈 Confidence: <b>{best_confidence:.2%}</b>\n"
            f"🔥 Execute now!"
        )

        send_telegram_message(main_msg)
    else:
        print("[Analysis] No valid signal yet (not enough ticks).")


def on_message(ws, message):
    """Handle incoming tick data."""
    data = json.loads(message)

    if "tick" in data:
        symbol = data["tick"]["symbol"]
        quote = data["tick"]["quote"]

        market_ticks[symbol].append(quote)
        if len(market_ticks[symbol]) > 200:
            market_ticks[symbol].pop(0)

        print(f"[Tick] {symbol} → {quote}")


def on_error(ws, error):
    print("[WebSocket ❌] Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("[WebSocket 🔌] Closed:", close_status_code, close_msg)


def subscribe_to_ticks(ws):
    for market in MARKETS:
        ws.send(json.dumps({"ticks": market}))
    print("[WebSocket 📡] Subscribed to ticks.")


def run_websocket():
    ws = websocket.WebSocketApp(
        DERIV_API_URL,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.on_open = lambda w: subscribe_to_ticks(w)
    print("[WebSocket 🚀] Connecting...")
    ws.run_forever()


def schedule_signals():
    while True:
        fetch_and_analyze()
        time.sleep(60)  # check every 1 min


if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()
    schedule_signals()
