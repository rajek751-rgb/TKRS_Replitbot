import os
import json
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ====== ФАЙЛ ДЛЯ СОХРАНЕНИЯ GROUP_ID ======
GROUP_FILE = "group.json"


def save_group_id(chat_id):
    with open(GROUP_FILE, "w") as f:
        json.dump({"group_id": chat_id}, f)


def load_group_id():
    if os.path.exists(GROUP_FILE):
        with open(GROUP_FILE, "r") as f:
            return json.load(f).get("group_id")
    return None


GROUP_ID = load_group_id()

# ====== СПИСОК ТЕХНИКИ ======

EQUIPMENT_LIST = [
    "ЦА", "АЦН-10", "АКН",
    "АХО", "ППУ", "Цементосмеситель",
    "Автокран", "Звено глушения",
    "Звено СКБ", "Тягач",
    "Седельный тягач",
    "АЗА",
    "Седельный тягач с КМУ",
    "Бортовой с КМУ",
    "Топливозаправщик",
    "Водовозка",
    "АРОК",
    "Вахтовый автобус",
    "УАЗ"
]

# =============================
# ===== АВТООПРЕДЕЛЕНИЕ ГРУППЫ
# =============================

async def capture_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_ID

    chat = update.effective_chat

    if chat.type in ["group", "supergroup"]:
        if GROUP_ID != chat.id:
            GROUP_ID = chat.id
            save_group_id(chat.id)
            print(f"GROUP_ID сохранён: {GROUP_ID}")


# =============================
# ===== ЭТАП 1 — ШАПКА ========
# =============================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    context.user_data["report"] = {
        "header": {},
        "operations": []
    }

    context.user_data["state"] = "brigade"
    await update.message.reply_text("Введите номер бригады ТКРС:")


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state == "brigade":
        context.user_data["report"]["header"]["brigade"] = update.message.text
        context.user_data["state"] = "well"
        await update.message.reply_text("Введите номер скважины:")

    elif state == "well":
        context.user_data["report"]["header"]["well"] = update.message.text
        context.user_data["state"] = "field"
        await update.message.reply_text("Введите месторождение:")

    elif state == "field":
        context.user_data["report"]["header"]["field"] = update.message.text
        context.user_data["state"] = None
        await show_stage2_menu(update.message)

    elif state == "op_name":
        context.user_data["op"]["name"] = update.message.text
        context.user_data["state"] = None
        await show_request_menu(update.message, context)

    elif state == "rep":
        context.user_data["op"]["representative"] = update.message.text
        context.user_data["state"] = None
        await show_request_menu(update.message, context)

    elif state == "materials":
        context.user_data["op"]["materials"] = update.message.text
        context.user_data["state"] = None
        await show_request_menu(update.message, context)


# =============================
# ===== ЭТАП 2 — МЕНЮ =========
# =============================

async def show_stage2_menu(message):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data="add_operation")],
        [InlineKeyboardButton("📤 Отправить отчёт", callback_data="send_report")]
    ]
    await message.reply_text(
        "ЭТАП 2 — Операции",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =============================
# ===== ДОБАВИТЬ ОПЕРАЦИЮ =====
# =============================

async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["op"] = {
        "date": datetime.now().strftime("%d.%m.%Y"),
        "name": "",
        "equipment": [],
        "representative": "",
        "materials": ""
    }

    context.user_data["state"] = "op_name"
    await query.edit_message_text("Введите название операции:")


# =============================
# ===== МЕНЮ ЗАЯВКИ ===========
# =============================

def build_request_keyboard(context):
    op = context.user_data["op"]

    eq_mark = " ✅" if op["equipment"] else ""
    rep_mark = " ✅" if op["representative"] else ""
    mat_mark = " ✅" if op["materials"] else ""

    keyboard = [
        [InlineKeyboardButton(f"🚜 Техника{eq_mark}", callback_data="req_equipment")],
        [InlineKeyboardButton(f"👤 Представитель{rep_mark}", callback_data="req_rep")],
        [InlineKeyboardButton(f"🧰 Материалы{mat_mark}", callback_data="req_materials")],
        [InlineKeyboardButton("💾 Сохранить операцию", callback_data="save_operation")]
    ]

    return InlineKeyboardMarkup(keyboard)


async def show_request_menu(message, context):
    await message.reply_text(
        "Заявки:",
        reply_markup=build_request_keyboard(context)
    )


# =============================
# ===== ТЕХНИКА ===============
# =============================

def build_equipment_keyboard(selected):
    keyboard = []

    for item in EQUIPMENT_LIST:
        mark = " ✅" if item in selected else ""
        keyboard.append([
            InlineKeyboardButton(
                item + mark,
                callback_data=f"eq_{item}"
            )
        ])

    keyboard.append(
        [InlineKeyboardButton("⬅ Назад", callback_data="back_to_requests")]
    )

    return InlineKeyboardMarkup(keyboard)


async def equipment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "Выберите технику:",
        reply_markup=build_equipment_keyboard(
            context.user_data["op"]["equipment"]
        )
    )


async def toggle_equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    item = query.data.replace("eq_", "")
    selected = context.user_data["op"]["equipment"]

    if item in selected:
        selected.remove(item)
    else:
        selected.append(item)

    await query.edit_message_text(
        "Выберите технику:",
        reply_markup=build_equipment_keyboard(selected)
    )


# =============================
# ===== СОХРАНИТЬ ОП ==========
# =============================

async def save_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["report"]["operations"].append(
        context.user_data["op"]
    )

    await query.edit_message_text("✅ Операция сохранена")

    await show_stage2_menu(query.message)


# =============================
# ===== ОТПРАВКА ОТЧЁТА =======
# =============================

async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_ID

    query = update.callback_query
    await query.answer()

    if not GROUP_ID:
        await query.edit_message_text(
            "Бот ещё не получил ID группы.\n"
            "Напишите любое сообщение в группе."
        )
        return

    report = context.user_data["report"]
    header = report["header"]
    operations = report["operations"]

    if not operations:
        await query.edit_message_text("Нет операций.")
        return

    text = (
        f"📑 ОТЧЁТ\n\n"
        f"Бригада: {header['brigade']}\n"
        f"Скважина: {header['well']}\n"
        f"Месторождение: {header['field']}\n\n"
    )

    for i, op in enumerate(operations, 1):
        text += (
            f"{i}. {op['date']}\n"
            f"Операция: {op['name']}\n"
            f"Техника: {', '.join(op['equipment'])}\n"
            f"Представитель: {op['representative']}\n"
            f"Материалы: {op['materials']}\n\n"
        )

    await context.bot.send_message(chat_id=GROUP_ID, text=text)

    await query.edit_message_text("📤 Отчёт отправлен в группу")


# =============================
# ===== CALLBACK ROUTER =======
# =============================

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "add_operation":
        await add_operation(update, context)

    elif query.data == "req_equipment":
        await equipment_menu(update, context)

    elif query.data.startswith("eq_"):
        await toggle_equipment(update, context)

    elif query.data == "back_to_requests":
        await query.edit_message_text(
            "Заявки:",
            reply_markup=build_request_keyboard(context)
        )

    elif query.data == "req_rep":
        context.user_data["state"] = "rep"
        await query.edit_message_text("Введите представителя:")

    elif query.data == "req_materials":
        context.user_data["state"] = "materials"
        await query.edit_message_text("Введите материалы:")

    elif query.data == "save_operation":
        await save_operation(update, context)

    elif query.data == "send_report":
        await send_report(update, context)


# =============================
# ===== ЗАПУСК =================
# =============================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, capture_group), group=0)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callbacks))

    app.run_polling()


if __name__ == "__main__":
    main()