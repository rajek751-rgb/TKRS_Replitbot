import os
import asyncio
import psycopg2
from datetime import datetime
from threading import Thread
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
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Для webhook

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")
if not RENDER_URL:
    raise ValueError("RENDER_EXTERNAL_URL not set")

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
# RENDER REPORT SCREEN
# =========================
async def render_report(report_id, message):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT brigade, report_number, report_date, well_field
        FROM reports WHERE id=%s
    """, (report_id,))
    row = cur.fetchone()
    if not row:
        await message.reply_text("Отчёт не найден")
        conn.close()
        return
    brigade, number, date, well = row

    cur.execute("""
        SELECT operation_date, start_time, end_time,
               name, request_number, equipment,
               representative, materials
        FROM operations
        WHERE report_id=%s
        ORDER BY operation_date, start_time
    """, (report_id,))
    ops = cur.fetchall()
    conn.close()

    text = f"""📑 Отчёт №{number}

📌 Сетевой график
Бригада: {brigade}
Объект: {well}
Дата отчёта: {date.strftime('%d.%m.%Y')}

──────────────
"""

    current_date = None
    for op in ops:
        op_date, start, end, name, req, eq, rep, mat = op
        if op_date != current_date:
            current_date = op_date
            text += f"\n📅 {op_date.strftime('%d.%m.%Y')}\n\n"
        text += f"""🔹 {start.strftime('%H:%M')}–{end.strftime('%H:%M')} | {name}
   📄 Заявка №{req}
   🚜 {eq}
   👷 {rep}
   📦 {mat}

"""

    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("📜 Журнал изменений", callback_data=f"log_{report_id}")],
        [InlineKeyboardButton("🔄 Новый график", callback_data="new")]
    ]
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# =========================
# CREATE REPORT
# =========================
async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    # ===== Создание отчёта =====
    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта (ДД.ММ.ГГГГ):")
        context.user_data["state"] = "date"

    elif state == "date":
        context.user_data["date"] = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        await update.message.reply_text("Введите скважина / месторождение:")
        context.user_data["state"] = "well"

    elif state == "well":
        brigade = context.user_data["brigade"]
        report_date = context.user_data["date"]
        well = update.message.text

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(report_number),0)+1 FROM reports WHERE brigade=%s", (brigade,))
        number = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO reports
            (brigade, report_number, report_date, well_field, created_by)
            VALUES (%s,%s,%s,%s,%s)
            RETURNING id
        """, (brigade, number, report_date, well, update.effective_user.id))

        report_id = cur.fetchone()[0]
        conn.commit()
        conn.close()
        context.user_data.clear()

        keyboard = [[InlineKeyboardButton("Открыть отчёт", callback_data=f"open_{report_id}")]]
        await update.message.reply_text(
            f"✅ Отчёт №{number} создан",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ===== Добавление операции =====
    elif state in ["op_date", "op_start", "op_end", "op_name", "op_req", "op_eq", "op_rep", "op_mat"]:
        keys = ["op_date","op_start","op_end","op_name","op_req","op_eq","op_rep","op_mat"]
        prompts = [
            "Введите дату операции (ДД.ММ.ГГГГ):",
            "Время начала (ЧЧ:ММ):",
            "Время окончания (ЧЧ:ММ):",
            "Название операции:",
            "Номер заявки:",
            "Техника:",
            "Представитель:",
            "Материалы:"
        ]
        idx = keys.index(state)
        if state == "op_date":
            context.user_data[state] = datetime.strptime(update.message.text, "%d.%m.%Y").date()
        else:
            context.user_data[state] = update.message.text
        if idx+1 < len(keys):
            context.user_data["state"] = keys[idx+1]
            await update.message.reply_text(prompts[idx+1])
        else:
            # Вставка операции в БД
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO operations
                (report_id, operation_date, start_time, end_time,
                 name, request_number, equipment, representative, materials)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                context.user_data["report_id"],
                context.user_data["op_date"],
                context.user_data["op_start"],
                context.user_data["op_end"],
                context.user_data["op_name"],
                context.user_data["op_req"],
                context.user_data["op_eq"],
                context.user_data["op_rep"],
                context.user_data["op_mat"]
            ))
            conn.commit()
            conn.close()
            report_id = context.user_data["report_id"]
            context.user_data.clear()
            await render_report(report_id, update.message)

# =========================
# CALLBACKS
# =========================
async def open_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    await render_report(report_id, query.message)

async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    context.user_data["report_id"] = report_id
    context.user_data["state"] = "op_date"
    await query.edit_message_text("Введите дату операции (ДД.ММ.ГГГГ):")

async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT action, timestamp
        FROM change_log
        WHERE report_id=%s
        ORDER BY timestamp DESC
    """, (report_id,))
    logs = cur.fetchall()
    conn.close()
    text = "📜 Журнал изменений\n\n"
    for action, ts in logs:
        text += f"{ts.strftime('%d.%m %H:%M')} | {action}\n"
    await query.edit_message_text(text)

# =========================
# HANDLERS
# =========================
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
app.add_handler(CallbackQueryHandler(open_report, pattern="open_"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="add_"))
app.add_handler(CallbackQueryHandler(show_log, pattern="log_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# =========================
# FLASK WEBHOOK
# =========================
flask_app = Flask(__name__)

@flask_app.post(WEBHOOK_PATH)
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app.bot)
    await app.process_update(update)
    return "ok"

@flask_app.get("/")
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
    # Flask сервер в отдельном потоке
    Thread(target=lambda: flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))).start()

if __name__ == "__main__":
    asyncio.run(main())