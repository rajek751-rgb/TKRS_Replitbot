import os
import json
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

DATA_FILE = "data.json"


# ================= ХРАНЕНИЕ =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"reports": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def next_number(data, brigade):
    nums = [r["number"] for r in data["reports"] if r["brigade"] == brigade]
    return max(nums) + 1 if nums else 1


# ================= TELEGRAM =================

app = Application.builder().token(BOT_TOKEN).build()


# ===== START =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📑 Новый отчёт", callback_data="new")]
    ]
    await update.message.reply_text(
        "🏗 Система ТКРС",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ===== СОЗДАНИЕ ОТЧЁТА =====

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    data = load_data()

    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта:")
        context.user_data["state"] = "date"

    elif state == "date":
        context.user_data["date"] = update.message.text
        await update.message.reply_text("Введите объект:")
        context.user_data["state"] = "well"

    elif state == "well":
        brigade = context.user_data["brigade"]
        number = next_number(data, brigade)

        report = {
            "id": len(data["reports"]) + 1,
            "brigade": brigade,
            "number": number,
            "date": context.user_data["date"],
            "well": update.message.text,
            "operations": []
        }

        data["reports"].append(report)
        save_data(data)
        context.user_data.clear()

        await show_report(update.message, report["id"])

    # ===== ДОБАВЛЕНИЕ ОПЕРАЦИИ =====

    elif state == "op_name":
        context.user_data["op_name"] = update.message.text
        await update.message.reply_text("Введите технику:")
        context.user_data["state"] = "op_eq"

    elif state == "op_eq":
        context.user_data["op_eq"] = update.message.text
        await update.message.reply_text("Введите материалы:")
        context.user_data["state"] = "op_mat"

    elif state == "op_mat":
        data = load_data()
        report_id = context.user_data["report_id"]

        for r in data["reports"]:
            if r["id"] == report_id:
                r["operations"].append({
                    "name": context.user_data["op_name"],
                    "equipment": context.user_data["op_eq"],
                    "materials": update.message.text
                })

        save_data(data)
        context.user_data.clear()
        await show_report(update.message, report_id)


# ===== ПОКАЗ ОТЧЁТА =====

def build_text(report):
    text = f"""📑 Отчёт №{report['number']}

Бригада: {report['brigade']}
Объект: {report['well']}
Дата: {report['date']}

──────────────
"""

    for i, op in enumerate(report["operations"]):
        text += f"""{i+1}. {op['name']}
🚜 {op['equipment']}
📦 {op['materials']}

"""

    return text


async def show_report(message, report_id):
    data = load_data()
    report = next(r for r in data["reports"] if r["id"] == report_id)

    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("✏ Редактировать операцию", callback_data=f"edit_{report_id}")],
        [InlineKeyboardButton("📤 Отправить в группу", callback_data=f"send_{report_id}")]
    ]

    await message.reply_text(
        build_text(report),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ===== CALLBACKS =====

async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    report_id = int(q.data.split("_")[1])
    context.user_data["report_id"] = report_id
    context.user_data["state"] = "op_name"
    await q.edit_message_text("Введите название операции:")


async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    report_id = int(q.data.split("_")[1])

    data = load_data()
    report = next(r for r in data["reports"] if r["id"] == report_id)

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=build_text(report)
    )

    await q.answer("Отправлено в группу ✅")


async def edit_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    report_id = int(q.data.split("_")[1])
    context.user_data["report_id"] = report_id
    context.user_data["state"] = "op_name"
    await q.edit_message_text("Введите новое название операции:")


# ===== HANDLERS =====

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="new"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="add_"))
app.add_handler(CallbackQueryHandler(send_to_group, pattern="send_"))
app.add_handler(CallbackQueryHandler(edit_operation, pattern="edit_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


if __name__ == "__main__":
    app.run_polling()