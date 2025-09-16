import time
import requests
import json
import websocket
import threading
from datetime import datetime, timedelta
import statistics
import pytz

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
last_prep_id = None

# Timezone setup (EAT)
EAT = pytz.timezone("Africa/Nairobi")


def now_eat():
    """Return current datetime in EAT timezone."""
    return datetime.now(EAT)


def format_eat(dt):
    """Format datetime object to HH:MM:SS in EAT timezone."""
    return dt.astimezone(EAT).strftime("%H:%M:%S")


def send_telegram_message(message: str, keep=False):
    """Send plain text message to Telegram with debug logs."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "🚀 Run on Calekyz", "url": "https://www.calekyztrading.site/"}
        ]]
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/sendMessage",
            data={
                "chat_id": GROUP_ID,
                "text": message,
                "parse_mode": "Markdown",
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
    """Delete old active messages (temporary signals)."""
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


def delete_prep():
    """Delete the last prep message before posting a new one."""
    global last_prep_id
    if last_prep_id:
        try:
            requests.post(f"{BASE_URL}/deleteMessage", data={
                "chat_id": GROUP_ID,
                "message_id": last_prep_id
            })
            print(f"[Telegram 🗑️] Deleted prep message {last_prep_id}")
        except Exception as e:
            print("[Telegram ❌] Delete prep error:", e)
        last_prep_id = None


def delete_expired():
    """Delete the last expiration message before posting a new one."""
    global last_expired_id
    if last_expired_id:
        try:
            requests.post(f"{BASE_URL}/deleteMessage", data={
                "chat_id": GROUP_ID,
                "message_id": last_expired_id
            })
            print(f"[Telegram 🗑️] Deleted expired message {last_expired_id}")
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
    global last_expired_id, last_prep_id

    delete_messages()
    delete_expired()
    delete_prep()

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
        now = now_eat()
        entry_digit = int(str(market_ticks[best_market][-1])[-1])
        market_name = MARKET_NAMES.get(best_market, best_market)

        # --- Main Signal ---
        main_msg = (
            f"We are trading *Over/Under market 🎯*\n"
            f"(Under 8️⃣ recovery under 5️⃣ )\n\n"
            f"*{market_name}*\n\n"
            f"✅ *Contract Type:* {best_signal}\n"
            f"Set *use_entry = true* and *digit = {entry_digit}*\n"
            f"⚡️Use the *SNIPPER HAVOC V2*\n"
            f"🔄 Run for 10-15 times\n\n"
            f"🥊 SIGNAL VALID FOR 2 MINS! 🥊\n\n"
            f"🚦 *What to do when you get the signal* 🚦\n"
            f".*Load the bot on* calekyztrading.site\n"
            f"_🧩 Change stake and prediction as stated._\n"
            f"🚫 *NOTE:* You can change prediction to Over 1 or 2 if comfortable 😎\n\n"
            f"⏰ Time: {format_eat(now)} EAT"
        )
        send_telegram_message(main_msg)

        # --- Expiration Message (after 2 mins) ---
        time.sleep(120)
        exp_time = format_eat(now_eat())
        next_signal_time = format_eat(now + timedelta(minutes=10))
        exp_msg = (
            f"🎯 Session at {exp_time} EAT completed!\n"
            f"✅ Win Rate: {best_confidence:.2%}\n"
            f"🚦 Next signal at {next_signal_time} EAT\n"
            f"🚦 Keep trading with SNIPPER LITE Bot on calekyztrading.site!"
        )
        last_expired_id = send_telegram_message(exp_msg, keep=True)

        # --- Prep Message (1 min after expiration) ---
        time.sleep(60)
        prep_time = format_eat(now_eat())
        next_time = format_eat(now + timedelta(minutes=10))
        prep_msg = (
            f"🚀 Prepare for the next signal at {next_time} EAT\n"
            f"🕒 Current time: {prep_time} EAT"
        )
        last_prep_id = send_telegram_message(prep_msg, keep=True)

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
        time.sleep(600 - 180)  # 10 min total, minus ~3 min used for signal+expiration+prep


if __name__ == "__main__":
    ws_thread = threading.Thread(target=run_websocket)
    ws_thread.start()
    schedule_signals()
