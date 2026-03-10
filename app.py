import os
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATA_FILE = "data.json"


# ================= STORAGE =================

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"reports": [], "group_id": None}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log_change(report, user, action):
    report["change_log"].append({
        "user": user or "unknown",
        "action": action,
        "time": datetime.now().strftime("%d.%m.%Y %H:%M")
    })


# ================= TELEGRAM =================

app = Application.builder().token(BOT_TOKEN).build()


# ===== SET GROUP =====

async def set_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("Выполните команду в группе.")
        return

    data = load_data()
    data["group_id"] = update.effective_chat.id
    save_data(data)

    await update.message.reply_text("✅ Группа сохранена.")


# ===== START =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📑 Новый отчёт", callback_data="new_report")]]
    await update.message.reply_text(
        "🏗 Система отчётности",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ===== NEW REPORT =====

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"


# ===== TEXT HANDLER =====

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    data = load_data()

    # ===== HEADER =====

    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите скважину:")
        context.user_data["state"] = "well"

    elif state == "well":
        context.user_data["well"] = update.message.text
        await update.message.reply_text("Введите месторождение:")
        context.user_data["state"] = "field"

    elif state == "field":
        report = {
            "id": len(data["reports"]) + 1,
            "header": {
                "brigade": context.user_data["brigade"],
                "well": context.user_data["well"],
                "field": update.message.text
            },
            "operations": [],
            "change_log": []
        }

        log_change(report, update.effective_user.username, "Создан отчёт")
        data["reports"].append(report)
        save_data(data)
        context.user_data.clear()

        await show_report(update.message, report["id"])

    # ===== ADD OPERATION =====

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
        await update.message.reply_text("Заявка №:")
        context.user_data["state"] = "op_request"

    elif state == "op_request":
        context.user_data["op_request"] = update.message.text
        await update.message.reply_text("Техника:")
        context.user_data["state"] = "op_equipment"

    elif state == "op_equipment":
        context.user_data["op_equipment"] = update.message.text
        await update.message.reply_text("Представитель:")
        context.user_data["state"] = "op_rep"

    elif state == "op_rep":
        context.user_data["op_rep"] = update.message.text
        await update.message.reply_text("Материалы:")
        context.user_data["state"] = "op_materials"

    elif state == "op_materials":
        report_id = context.user_data["report_id"]

        report = next((r for r in data["reports"] if r["id"] == report_id), None)
        if not report:
            await update.message.reply_text("Ошибка: отчёт не найден.")
            return

        operation = {
            "date": context.user_data["op_date"],
            "start": context.user_data["op_start"],
            "end": context.user_data["op_end"],
            "name": context.user_data["op_name"],
            "request": context.user_data["op_request"],
            "equipment": context.user_data["op_equipment"],
            "representative": context.user_data["op_rep"],
            "materials": update.message.text
        }

        report["operations"].append(operation)
        log_change(report, update.effective_user.username, f"Добавлена операция: {operation['name']}")
        save_data(data)

        context.user_data.clear()
        await show_report(update.message, report_id)


# ===== BUILD REPORT TEXT =====

def build_text(report):
    h = report["header"]

    text = (
        f"📑 Отчёт\n\n"
        f"Бригада: {h['brigade']}\n"
        f"Скважина: {h['well']}\n"
        f"Месторождение: {h['field']}\n\n"
        f"──────────────\n"
    )

    for i, op in enumerate(report["operations"], start=1):
        text += (
            f"{i}. {op['date']} {op['start']}–{op['end']}\n"
            f"{op['name']}\n"
            f"Заявка: {op['request']}\n"
            f"Техника: {op['equipment']}\n"
            f"Представитель: {op['representative']}\n"
            f"Материалы: {op['materials']}\n\n"
        )

    text += "──────────────\nЖурнал изменений:\n"

    for log in report["change_log"]:
        text += f"{log['time']} | {log['user']} | {log['action']}\n"

    return text


# ===== SHOW REPORT =====

async def show_report(message, report_id):
    data = load_data()
    report = next((r for r in data["reports"] if r["id"] == report_id), None)

    if not report:
        await message.reply_text("Отчёт не найден.")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
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
    context.user_data["state"] = "op_date"

    await q.edit_message_text("Введите дату операции (ДД.ММ.ГГГГ):")


async def send_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    report_id = int(q.data.split("_")[1])
    data = load_data()
    group_id = data.get("group_id")

    if not group_id:
        await q.answer("Сначала выполните /setgroup в группе.")
        return

    report = next((r for r in data["reports"] if r["id"] == report_id), None)
    if not report:
        await q.answer("Отчёт не найден.")
        return

    await context.bot.send_message(chat_id=group_id, text=build_text(report))
    await q.answer("Отправлено в группу ✅")


# ===== HANDLERS =====

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("setgroup", set_group))
app.add_handler(CallbackQueryHandler(new_report, pattern="new_report"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="add_"))
app.add_handler(CallbackQueryHandler(send_to_group, pattern="send_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))


if __name__ == "__main__":
    app.run_polling()