import os
import asyncio
import logging
import psycopg2
from flask import Flask, request
from threading import Thread

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# НАСТРОЙКИ
# =========================

TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

if not RENDER_URL:
    raise ValueError("RENDER_EXTERNAL_URL не установлен!")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен!")

WEBHOOK_PATH = f"/webhook/{TOKEN}"

logging.basicConfig(level=logging.INFO)

# =========================
# БАЗА ДАННЫХ
# =========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_report(user_id, username, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reports (user_id, username, message) VALUES (%s, %s, %s)",
        (user_id, username, message),
    )
    conn.commit()
    cur.close()
    conn.close()

def get_all_reports():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, message, created_at FROM reports ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# =========================
# TELEGRAM
# =========================

app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Отправь сообщение — я сохраню его как отчёт.\n\n"
        "Команды:\n"
        "/reports — показать все отчёты"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    save_report(
        user_id=user.id,
        username=user.username or user.first_name,
        message=text,
    )

    await update.message.reply_text("✅ Отчёт сохранён!")

async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_reports()

    if not rows:
        await update.message.reply_text("Отчётов пока нет.")
        return

    text = "📊 Последние отчёты:\n\n"

    for username, message, created_at in rows[:20]:
        text += f"👤 {username}\n📝 {message}\n🕒 {created_at}\n\n"

    await update.message.reply_text(text)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reports", reports))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# =========================
# EVENT LOOP (фикс Render)
# =========================

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# =========================
# FLASK
# =========================

flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is running"

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)
    loop.create_task(app.process_update(update))
    return "ok"

# =========================
# MAIN
# =========================

async def main():
    init_db()
    await app.initialize()
    await app.start()

    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    await app.bot.set_webhook(webhook_url)

    print("Webhook установлен:", webhook_url)

if __name__ == "__main__":
    loop.create_task(main())

    Thread(target=loop.run_forever, daemon=True).start()

    flask_app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )