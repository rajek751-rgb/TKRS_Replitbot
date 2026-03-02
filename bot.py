import os
import asyncio
import psycopg2
from datetime import datetime
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# ENV VARIABLES
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not DATABASE_URL or not RENDER_URL:
    raise ValueError("BOT_TOKEN, DATABASE_URL и RENDER_EXTERNAL_URL должны быть заданы!")

WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# =========================
# DATABASE
# =========================
def get_db():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            brigade TEXT NOT NULL,
            report_number INTEGER NOT NULL,
            report_date DATE NOT NULL,
            well_field TEXT NOT NULL,
            created_by BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operations (
            id SERIAL PRIMARY KEY,
            report_id INTEGER REFERENCES reports(id) ON DELETE CASCADE,
            operation_date DATE,
            start_time TIME,
            end_time TIME,
            name TEXT,
            request_number TEXT,
            equipment TEXT,
            representative TEXT,
            materials TEXT
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS change_log (
            id SERIAL PRIMARY KEY,
            report_id INTEGER,
            user_id BIGINT,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()

# =========================
# TELEGRAM APP
# =========================
app = Application.builder().token(BOT_TOKEN).build()

# =========================
# TELEGRAM HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Здесь можно добавить остальные handlers: new_report, handle_message, open_report, add_operation, show_log
# Я оставляю их как в твоём предыдущем коде, просто подставь сюда

# =========================
# ADD HANDLERS
# =========================
app.add_handler(CommandHandler("start", start))
# app.add_handler(CallbackQueryHandler(...))  # остальные callback handlers
# app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# =========================
# FLASK WEBHOOK
# =========================
flask_app = Flask(__name__)

@flask_app.post(WEBHOOK_PATH)
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, app.bot)
        asyncio.run(app.process_update(update))
    except Exception as e:
        print("Webhook error:", e)
    return "ok"

@flask_app.get("/")
def health():
    return "Bot is running"

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    # 1. Создаём таблицы
    init_db()

    # 2. Инициализация бота
    asyncio.run(app.initialize())
    asyncio.run(app.start())

    # 3. Устанавливаем webhook
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    asyncio.run(app.bot.set_webhook(webhook_url))
    print("Webhook установлен:", webhook_url)

    # 4. Запускаем Flask
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))