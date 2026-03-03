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
# CONFIG
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

    conn.commit()
    conn.close()

# =========================
# TELEGRAM APP
# =========================
app = Application.builder().token(BOT_TOKEN).build()

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта (ДД.ММ.ГГГГ):")
        context.user_data["state"] = "date"

    elif state == "date":
        context.user_data["date"] = datetime.strptime(
            update.message.text, "%d.%m.%Y"
        ).date()
        await update.message.reply_text("Введите скважина / месторождение:")
        context.user_data["state"] = "well"

    elif state == "well":
        brigade = context.user_data["brigade"]
        report_date = context.user_data["date"]
        well = update.message.text

        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT COALESCE(MAX(report_number),0)+1
            FROM reports WHERE brigade=%s
        """, (brigade,))
        number = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO reports
            (brigade, report_number, report_date, well_field, created_by)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            brigade,
            number,
            report_date,
            well,
            update.effective_user.id
        ))

        conn.commit()
        conn.close()
        context.user_data.clear()

        await update.message.reply_text(f"✅ Отчёт №{number} создан")

# Регистрируем обработчики
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# =========================
# FLASK WEBHOOK
# =========================
flask_app = Flask(__name__)

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), app.bot)

    # Используем существующий event loop Telegram
    asyncio.run(app.process_update(update))

    return "ok"

@flask_app.route("/")
def health():
    return "Bot is running"

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
    asyncio.run(main())

    flask_app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )