import os
import json
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ===============================
# CONFIG
# ===============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"

# ===============================
# FLASK SERVER (для Render Free)
# ===============================

web = Flask(__name__)

@web.route("/")
def home():
    return "Bot is running"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web.run(host="0.0.0.0", port=port)

# ===============================
# FILE STORAGE
# ===============================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"reports": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def next_report_number(data, brigade):
    numbers = [r["number"] for r in data["reports"] if r["brigade"] == brigade]
    return max(numbers) + 1 if numbers else 1

# ===============================
# TELEGRAM APP
# ===============================

app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# ===============================
# CREATE REPORT
# ===============================

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    data = load_data()

    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта (ДД.ММ.ГГГГ):")
        context.user_data["state"] = "date"

    elif state == "date":
        context.user_data["date"] = update.message.text
        await update.message.reply_text("Введите скважину / месторождение:")
        context.user_data["state"] = "well"

    elif state == "well":
        brigade = context.user_data["brigade"]
        date = context.user_data["date"]
        well = update.message.text

        number = next_report_number(data, brigade)
        report_id = len(data["reports"]) + 1

        data["reports"].append({
            "id": report_id,
            "brigade": brigade,
            "number": number,
            "date": date,
            "well": well,
            "operations": []
        })

        save_data(data)
        context.user_data.clear()

        keyboard = [[InlineKeyboardButton("Открыть отчёт", callback_data=f"open_{report_id}")]]
        await update.message.reply_text(
            f"✅ Отчёт №{number} создан",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ================= ADD OPERATION =================

    elif state == "op_date":
        context.user_data["op_date"] = update.message.text
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
        report_id = context.user_data["report_id"]

        for r in data["reports"]:
            if r["id"] == report_id:
                r["operations"].append({
                    "date": context.user_data["op_date"],
                    "start": context.user_data["op_start"],
                    "end": context.user_data["op_end"],
                    "name": context.user_data["op_name"],
                    "request": context.user_data["op_req"],
                    "equipment": context.user_data["op_eq"],
                    "rep": context.user_data["op_rep"],
                    "materials": update.message.text
                })

        save_data(data)
        context.user_data.clear()
        await render_report(report_id, update.message)

# ===============================
# RENDER REPORT
# ===============================

async def render_report(report_id, message):
    data = load_data()
    report = next(r for r in data["reports"] if r["id"] == report_id)

    text = f"""📑 Отчёт №{report['number']}

Бригада: {report['brigade']}
Объект: {report['well']}
Дата: {report['date']}

──────────────
"""

    for op in report["operations"]:
        text += f"""🔹 {op['date']} {op['start']}–{op['end']} | {op['name']}
   📄 №{op['request']}
   🚜 {op['equipment']}
   👷 {op['rep']}
   📦 {op['materials']}

"""

    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("🔄 Новый график", callback_data="new")]
    ]

    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===============================
# CALLBACKS
# ===============================

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

# ===============================
# HANDLERS
# ===============================

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
app.add_handler(CallbackQueryHandler(open_report, pattern="open_"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="add_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# ===============================
# RUN
# ===============================

if __name__ == "__main__":
    Thread(target=run_web).start()
    app.run_polling()