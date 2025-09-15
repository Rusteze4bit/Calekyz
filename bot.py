import os
import time
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Load .env (for local) – Railway will use env vars
load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MODE = os.getenv("MODE", "demo")

STRATEGY = {
    "market": "Volatility 75 (1s)",
    "contract_type": "OVER",
    "digit": 4,
    "strategy_name": "SNIPPER HAVOC V2",
    "run_min": 10,
    "run_max": 15,
    "signal_valid_seconds": 120,
}

active_runs = {}

# --- Signal generator (placeholder for SNIPPER HAVOC V2) ---
def mock_signal_generator() -> Optional[dict]:
    if random.random() < 0.3:  # ~30% chance
        return {
            "time": datetime.utcnow().isoformat() + "Z",
            "prediction": "OVER",
            "digit": STRATEGY["digit"],
            "valid_until": (datetime.utcnow() + timedelta(seconds=STRATEGY["signal_valid_seconds"])).isoformat() + "Z",
            "note": "Mock signal - replace with SNIPPER HAVOC V2 logic",
        }
    return None

# --- Run cycle logic ---
def run_signal_cycle(identifier: str, runs: int):
    from telegram import Bot
    bot = Bot(token=TELEGRAM_TOKEN)

    executed = 0
    while executed < runs:
        signal = mock_signal_generator()
        if signal:
            msg = (
                f"📢 SIGNAL #{executed+1}\n"
                f"Market: {STRATEGY['market']}\n"
                f"Prediction: {signal['prediction']} {signal['digit']}\n"
                f"Valid until: {signal['valid_until']}\n"
                f"Strategy: {STRATEGY['strategy_name']}"
            )
            try:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=msg)
                logger.info("Sent signal: %s", msg)
            except Exception as e:
                logger.error("Failed to send signal: %s", e)

            executed += 1

        time.sleep(1)  # avoid spamming too fast

    active_runs.pop(identifier, None)
    logger.info("Finished signal cycle %s with %d signals", identifier, executed)

# --- Telegram commands ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📡 Signal Bot ready! Use /run to generate signals.")

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    try:
        runs = int(args[0]) if args else STRATEGY["run_min"]
        runs = max(STRATEGY["run_min"], min(STRATEGY["run_max"], runs))
    except Exception:
        runs = STRATEGY["run_min"]

    identifier = f"sig-{update.effective_user.id}-{int(time.time())}"
    from threading import Thread
    t = Thread(target=run_signal_cycle, args=(identifier, runs), daemon=True)
    active_runs[identifier] = {"thread": t, "started_by": update.effective_user.username}
    t.start()

    await update.message.reply_text(f"✅ Started signal cycle {identifier} for {runs} runs.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📊 Active signal cycles: {len(active_runs)}")

# --- Main ---
def main():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set. Exiting.")
        return

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("status", status_command))

    logger.info("Starting Signal Bot polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
