"""
Telegram Trading Bot - Single-file starter
Files contained here (single-file repo for easy copy/paste):
- telegram_trading_bot.py  (this file)
- requirements.txt        (contents shown below)
- Procfile                (contents shown below)
- README.md               (deployment notes below)

DESCRIPTION
This is a starter Telegram bot that demonstrates how to:
- receive signals (placeholder for your SNIPPER HAVOC V2 logic)
- execute trades via a generic HTTP trading API (you must supply your broker endpoint)
- run scheduled "run for N times" cycles (10-15) and allow quick manual commands
- be deployed on Railway or similar platforms using environment variables

SECURITY & RISK
- This bot is a template. Do NOT run it with real money until you fully test it on a sandbox/demo account.
- Keep API keys secret. Use Railway environment variables or GitHub Secrets when deploying.
- The signal generation here is a placeholder. Replace with your own SNIPPER HAVOC V2 algorithm.

ENVIRONMENT VARIABLES (set these in Railway / .env locally)
- TELEGRAM_TOKEN : Telegram bot token (from BotFather)
- TELEGRAM_CHAT_ID : Chat id to send updates to (optional)
- TRADING_API_URL : Your trading broker HTTP endpoint for placing trades (placeholder)
- TRADING_API_KEY : API key for trading endpoint
- MODE : "demo" or "live" (optional)

REQUIREMENTS (requirements.txt)
# Put these lines in requirements.txt
python-telegram-bot==20.5
requests==2.31.0
apscheduler==3.10.1
python-dotenv==1.1.0

PROCFILE (Procfile)
# For Railway / Heroku-style
web: python telegram_trading_bot.py

HOW TO USE
1. Create a new GitHub repo and add this file and the small requirements.txt/Procfile.
2. Connect the repo to Railway and set the environment variables listed above.
3. Test the bot locally with a demo trading API before switching to live.

-- CODE STARTS BELOW --
"""

import os
import time
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load local .env if present (for local testing). Railway will use env vars.
load_dotenv()

# Basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration from environment ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # optional: where bot reports
TRADING_API_URL = os.getenv("TRADING_API_URL", "https://example-trading-api.local/place_trade")
TRADING_API_KEY = os.getenv("TRADING_API_KEY")
MODE = os.getenv("MODE", "demo")  # demo or live

# Strategy parameters based on your message
STRATEGY = {
    "market": "Volatility 75 (1s)",
    "contract_type": "OVER",  # Over
    "entry": True,
    "digit": 4,
    "strategy_name": "SNIPPER HAVOC V2",
    "run_min": 10,
    "run_max": 15,
    "signal_valid_seconds": 120,
}

# Scheduler
scheduler = BackgroundScheduler()

# State
active_runs = {}

# --- Helper functions ---

def place_trade(amount: float, prediction: str, market: str, digit: int) -> dict:
    """Sends a request to the trading API. Replace this with your broker's API format.
    This template uses a POST with JSON and API key header. Returns dict with response.
    """
    payload = {
        "amount": amount,
        "prediction": prediction,
        "market": market,
        "digit": digit,
        "contract_type": STRATEGY["contract_type"],
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    headers = {"Authorization": f"Bearer {TRADING_API_KEY}", "Content-Type": "application/json"}

    logger.info("Placing trade: %s", payload)

    try:
        # NOTE: many brokers use different auth / endpoints. Adapt accordingly.
        resp = requests.post(TRADING_API_URL, json=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.exception("Trade request failed: %s", e)
        return {"error": str(e)}


def mock_signal_generator() -> Optional[dict]:
    """Placeholder for SNIPPER HAVOC V2.
    Replace this with the real algorithm that inspects ticks/micro candles.
    For demo, randomly returns a signal about 30% of calls.
    """
    if random.random() < 0.3:
        # create a signal dict
        signal = {
            "time": datetime.utcnow().isoformat() + "Z",
            "type": "ENTRY",
            "prediction": "OVER",  # user asked Over (can change to OVER_1/2 etc.)
            "digit": STRATEGY["digit"],
            "valid_until": (datetime.utcnow() + timedelta(seconds=STRATEGY["signal_valid_seconds"]) ).isoformat() + "Z",
            "note": "Mock signal - replace with SNIPPER HAVOC V2 logic",
        }
        return signal
    return None


async def send_telegram_message(bot: Bot, text: str):
    """Send message to configured chat id if provided; otherwise do nothing.
    """
    if not TELEGRAM_CHAT_ID:
        logger.info("No TELEGRAM_CHAT_ID set — skipping message: %s", text)
        return
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
    except Exception:
        logger.exception("Failed sending Telegram message")


# --- Run cycle logic: run the strategy N times (10-15) ---

def run_strategy_cycle(identifier: str, runs: int, amount: float, prediction_override: Optional[str] = None):
    """Runs the strategy up to 'runs' times or until externally stopped. This is synchronous
    and intended to be run inside a background thread, scheduler job, or similar.
    """
    logger.info("Starting strategy cycle %s for %s runs", identifier, runs)
    executed = 0
    start_time = datetime.utcnow()

    while executed < runs:
        # 1) Generate or get a signal
        signal = mock_signal_generator()
        if not signal:
            logger.debug("No signal generated this tick. Sleeping briefly.")
            time.sleep(0.8)  # throttle loop; in real life you'd subscribe to tick stream
            continue

        # 2) Validate signal
        valid_until = datetime.fromisoformat(signal["valid_until"].replace("Z", ""))
        if datetime.utcnow() > valid_until:
            logger.info("Signal expired, skipping")
            continue

        # 3) Apply overrides and execution policy
        prediction = prediction_override or signal.get("prediction", "OVER")
        # user allowed choosing Over 1 or 2 — treat as mapping to a safer contract name, here kept simple

        # 4) Place trade
        resp = place_trade(amount=amount, prediction=prediction, market=STRATEGY["market"], digit=signal["digit"])

        # 5) Log and increment
        logger.info("Executed trade #%d for cycle %s. Response: %s", executed + 1, identifier, resp)
        executed += 1

        # Short pause between trades to avoid being too aggressive; adjust as needed
        time.sleep(1.0)

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info("Finished cycle %s: executed %d trades in %.1f seconds", identifier, executed, elapsed)
    # remove from active
    active_runs.pop(identifier, None)


# --- Telegram Bot Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I am your trading bot template. Use /run to start a cycle.")


async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts a run cycle from Telegram: /run <runs> <amount> [prediction]
    Example: /run 12 1.5 OVER
    """
    args = context.args
    try:
        runs = int(args[0]) if len(args) >= 1 else STRATEGY["run_min"]
        if runs < STRATEGY["run_min"]:
            runs = STRATEGY["run_min"]
        if runs > STRATEGY["run_max"]:
            runs = STRATEGY["run_max"]
    except Exception:
        runs = STRATEGY["run_min"]

    try:
        amount = float(args[1]) if len(args) >= 2 else 1.0
    except Exception:
        amount = 1.0

    prediction_override = args[2].upper() if len(args) >= 3 else None

    identifier = f"tg-{update.effective_user.id}-{int(time.time())}"
    # schedule the run in background (non-blocking)
    from threading import Thread

    t = Thread(target=run_strategy_cycle, args=(identifier, runs, amount, prediction_override), daemon=True)
    active_runs[identifier] = {"thread": t, "started_by": update.effective_user.username}
    t.start()

    await update.message.reply_text(f"Started cycle {identifier}: runs={runs}, amount={amount}, prediction={prediction_override}")


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Attempt to stop all active cycles. We mark them for stop — in this simple template we don't implement hard-stop.
    """
    # For simplicity, we won't forcibly kill threads here. In production use a better-controlled loop.
    active_count = len(active_runs)
    await update.message.reply_text(f"Active cycles: {active_count}. To stop, restart the bot or implement a stop flag in the template.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Active cycles: {len(active_runs)}\nStrategy: {STRATEGY}")


# --- Main application bootstrap ---

def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set. Exiting.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("stop", stop_command))
    app.add_handler(CommandHandler("status", status_command))

    # Optionally send a startup message
    async def on_startup(app):
        bot = app.bot
        startup_text = (
            f"Trading bot started. Mode={MODE}. Strategy={STRATEGY['strategy_name']}.\n"
            "Use /run <runs> <amount> [prediction] to start a cycle."
        )
        await send_telegram_message(bot, startup_text)

    app.post_init.append(on_startup)

    logger.info("Starting Telegram bot polling...")
    # For deployment on Railway, long-running process should be fine. Use web process in Procfile.
    app.run_polling()


if __name__ == "__main__":
    main()
