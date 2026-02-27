import os
import asyncio
import psycopg2
from datetime import datetime
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
    brigade, number, date, well = cur.fetchone()

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

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


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
            RETURNING id
        """, (
            brigade,
            number,
            report_date,
            well,
            update.effective_user.id
        ))

        report_id = cur.fetchone()[0]
        conn.commit()
        conn.close()

        context.user_data.clear()

        keyboard = [[InlineKeyboardButton("Открыть отчёт", callback_data=f"open_{report_id}")]]
        await update.message.reply_text(
            f"✅ Отчёт №{number} создан",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= ADD OPERATION =================

    elif state == "op_date":
        context.user_data["op_date"] = datetime.strptime(
            update.message.text, "%d.%m.%Y"
        ).date()
        await update.message.reply_text("Время начала (ЧЧ:ММ):")
        context.user_data["state"] = "op_start"

    elif state == "op_start":
        context.user_data["op_start"] = update.message.text
        await update.message.reply_text("Время окончания (ЧЧ:ММ):")
        context.user_data["state"] = "op_end"

    elif state == "op_end":
        context.user_data["op_end"] = update.message.text
        await update.message.reply_text("Название операции:")
        context.user_data["state"] = "op_name"

    elif state == "op_name":
        context.user_data["op_name"] = update.message.text
        await update.message.reply_text("Номер заявки:")
        context.user_data["state"] = "op_req"

    elif state == "op_req":
        context.user_data["op_req"] = update.message.text
        await update.message.reply_text("Техника:")
        context.user_data["state"] = "op_eq"

    elif state == "op_eq":
        context.user_data["op_eq"] = update.message.text
        await update.message.reply_text("Представитель:")
        context.user_data["state"] = "op_rep"

    elif state == "op_rep":
        context.user_data["op_rep"] = update.message.text
        await update.message.reply_text("Материалы:")
        context.user_data["state"] = "op_mat"

    elif state == "op_mat":
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
            update.message.text,
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


if __name__ == "__main__":
    init_db()
    asyncio.run(app.run_polling())