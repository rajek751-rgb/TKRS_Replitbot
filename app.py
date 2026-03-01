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


def load_data():
    if not os.path.exists(DATA_FILE):
        return {"reports": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


app = Application.builder().token(BOT_TOKEN).build()


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["report"] = {
        "header": {},
        "operations": []
    }
    await show_stage1(update.message)


# ================= ЭТАП 1 =================

async def show_stage1(message):
    keyboard = [
        [InlineKeyboardButton("Номер бригады ТКРС", callback_data="brigade")],
        [InlineKeyboardButton("Номер скважины", callback_data="well")],
        [InlineKeyboardButton("Месторождение", callback_data="field")],
        [InlineKeyboardButton("▶ Начать заполнение", callback_data="start_stage2")]
    ]
    await message.reply_text(
        "ЭТАП 1 — Заполнение шапки",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stage1_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    field = q.data
    context.user_data["state"] = field
    await q.edit_message_text(f"Введите: {field}")


# ================= ЭТАП 2 =================

async def show_stage2(message):
    keyboard = [
        [InlineKeyboardButton("Дата", callback_data="op_date")],
        [InlineKeyboardButton("Время начала", callback_data="op_start")],
        [InlineKeyboardButton("Время окончания", callback_data="op_end")],
        [InlineKeyboardButton("Название операции", callback_data="op_name")],
        [InlineKeyboardButton("Заявка", callback_data="op_request")],
        [InlineKeyboardButton("➕ Добавить операцию", callback_data="add_operation")]
    ]

    await message.reply_text(
        "ЭТАП 2 — Операции",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stage2_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action = q.data

    if action == "start_stage2":
        await show_stage2(q.message)
        return

    if action in ["op_date", "op_start", "op_end", "op_name"]:
        context.user_data["state"] = action
        await q.edit_message_text(f"Введите {action}")

    if action == "op_request":
        await show_request_menu(q)

    if action == "add_operation":
        await save_operation(q, context)


# ================= ЗАЯВКА МЕНЮ =================

async def show_request_menu(q):
    keyboard = [
        [InlineKeyboardButton("Техника", callback_data="req_equipment")],
        [InlineKeyboardButton("Представитель заказчика", callback_data="req_rep")],
        [InlineKeyboardButton("Оборудование и материалы", callback_data="req_materials")],
        [InlineKeyboardButton("⬅ Назад", callback_data="back_stage2")]
    ]
    await q.edit_message_text(
        "Заполнение заявки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def request_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    action = q.data

    if action == "req_equipment":
        await show_equipment_menu(q)

    elif action == "req_rep":
        context.user_data["state"] = "rep"
        await q.edit_message_text("Введите представителя заказчика:")

    elif action == "req_materials":
        context.user_data["state"] = "materials"
        await q.edit_message_text("Введите оборудование и материалы:")

    elif action == "back_stage2":
        await show_stage2(q.message)


# ================= ТЕХНИКА =================

async def show_equipment_menu(q):
    keyboard = []
    row = []

    for i, eq in enumerate(EQUIPMENT_LIST, start=1):
        row.append(InlineKeyboardButton(eq, callback_data=f"equip_{eq}"))
        if i % 3 == 0:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("➕ Добавить технику", callback_data="equip_add")])

    await q.edit_message_text(
        "Выберите технику:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def equipment_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "equip_add":
        context.user_data["state"] = "add_equipment"
        await q.edit_message_text("Введите новую технику:")
        return

    equipment = q.data.replace("equip_", "")
    context.user_data["equipment"] = equipment
    await q.edit_message_text(f"Выбрана техника: {equipment}")


# ================= СОХРАНЕНИЕ =================

async def save_operation(q, context):
    operation = {
        "date": context.user_data.get("op_date"),
        "start": context.user_data.get("op_start"),
        "end": context.user_data.get("op_end"),
        "name": context.user_data.get("op_name"),
        "equipment": context.user_data.get("equipment"),
        "representative": context.user_data.get("rep"),
        "materials": context.user_data.get("materials"),
    }

    context.user_data["report"]["operations"].append(operation)

    await q.edit_message_text("✅ Операция добавлена")


# ================= TEXT HANDLER =================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if state in ["brigade", "well", "field"]:
        context.user_data["report"]["header"][state] = update.message.text
        context.user_data["state"] = None
        await show_stage1(update.message)

    elif state in ["op_date", "op_start", "op_end", "op_name"]:
        context.user_data[state] = update.message.text
        context.user_data["state"] = None
        await show_stage2(update.message)

    elif state == "rep":
        context.user_data["rep"] = update.message.text
        context.user_data["state"] = None
        await show_stage2(update.message)

    elif state == "materials":
        context.user_data["materials"] = update.message.text
        context.user_data["state"] = None
        await show_stage2(update.message)

    elif state == "add_equipment":
        EQUIPMENT_LIST.append(update.message.text)
        context.user_data["equipment"] = update.message.text
        context.user_data["state"] = None
        await show_stage2(update.message)


# ================= HANDLERS =================

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(stage1_buttons, pattern="brigade|well|field"))
app.add_handler(CallbackQueryHandler(stage2_buttons, pattern="start_stage2|op_.*|add_operation"))
app.add_handler(CallbackQueryHandler(request_buttons, pattern="req_.*|back_stage2"))
app.add_handler(CallbackQueryHandler(equipment_buttons, pattern="equip_.*"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))


if __name__ == "__main__":
    app.run_polling()