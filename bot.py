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

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # внешний URL от Render

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
# HELPER: RENDER REPORT
# =========================
async def render_report(report_id, message):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT brigade, report_number, report_date, well_field FROM reports WHERE id=%s", (report_id,))
    row = cur.fetchone()
    if not row:
        await message.reply_text("Отчёт не найден")
        conn.close()
        return
    brigade, number, date, well = row
    cur.execute("""
        SELECT operation_date, start_time, end_time, name, request_number, equipment, representative, materials
        FROM operations WHERE report_id=%s ORDER BY operation_date, start_time
    """, (report_id,))
    ops = cur.fetchall()
    conn.close()
    text = f"📑 Отчёт №{number}\n\n📌 Сетевой график\nБригада: {brigade}\nОбъект: {well}\nДата отчёта: {date.strftime('%d.%m.%Y')}\n──────────────\n"
    current_date = None
    for op_date, start, end, name, req, eq, rep, mat in ops:
        if op_date != current_date:
            current_date = op_date
            text += f"\n📅 {op_date.strftime('%d.%m.%Y')}\n\n"
        text += f"🔹 {start.strftime('%H:%M')}–{end.strftime('%H:%M')} | {name}\n   📄 Заявка №{req}\n   🚜 {eq}\n   👷 {rep}\n   📦 {mat}\n\n"
    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("📜 Журнал изменений", callback_data=f"log_{report_id}")],
        [InlineKeyboardButton("🔄 Новый график", callback_data="new")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text("🏗 Корпоративная система ТКРС", reply_markup=InlineKeyboardMarkup(keyboard))

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"

# Добавь handle_message, open_report, add_operation, show_log
# (твой старый код без изменений)

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
# ... добавь остальные обработчики

# =========================
# FLASK WEBHOOK
# =========================
flask_app = Flask(__name__)

@flask_app.route(WEBHOOK_PATH, methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)
    asyncio.run(app.process_update(update))
    return "ok"

@flask_app.route("/", methods=["GET"])
def health():
    return "Bot is running"

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    init_db()
    asyncio.run(app.initialize())
    asyncio.run(app.start())
    webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
    asyncio.run(app.bot.set_webhook(webhook_url))
    print("Webhook установлен:", webhook_url)
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))