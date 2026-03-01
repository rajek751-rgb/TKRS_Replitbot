import os
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# =========================
# TOKEN
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден")

print("TOKEN загружен")

# =========================
# DUMMY SERVER (для Render)
# =========================

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyHandler)
    print(f"Dummy server запущен на порту {port}")
    server.serve_forever()


# =========================
# GROUP SAVE
# =========================

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


async def capture_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_ID

    chat = update.effective_chat

    if chat.type in ["group", "supergroup"]:
        if GROUP_ID != chat.id:
            GROUP_ID = chat.id
            save_group_id(chat.id)
            print(f"GROUP_ID сохранён: {GROUP_ID}")


# =========================
# ОБОРУДОВАНИЕ
# =========================

EQUIPMENT_LIST = [
    "ЦА", "АЦН-10", "АКН",
    "АХО", "ППУ", "Цементосмеситель",
    "Автокран", "Звено глушения",
    "Звено СКБ", "Тягач",
    "Седельный тягач", "АЗА"
]

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data["report"] = {"header": {}, "operations": []}
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
        await show_stage2(update.message)

    elif state == "op_name":
        context.user_data["op"]["name"] = update.message.text
        context.user_data["state"] = None
        await show_requests(update.message, context)


# =========================
# ЭТАП 2
# =========================

async def show_stage2(message):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data="add_op")],
        [InlineKeyboardButton("📤 Отправить отчёт", callback_data="send_report")]
    ]
    await message.reply_text("ЭТАП 2 — Операции",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["op"] = {
        "date": datetime.now().strftime("%d.%m.%Y"),
        "name": "",
        "equipment": []
    }

    context.user_data["state"] = "op_name"
    await query.edit_message_text("Введите название операции:")


async def show_requests(message, context):
    keyboard = [
        [InlineKeyboardButton("🚜 Техника", callback_data="equipment")],
        [InlineKeyboardButton("💾 Сохранить операцию", callback_data="save_op")]
    ]
    await message.reply_text("Заявки:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def equipment_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    selected = context.user_data["op"]["equipment"]

    for item in EQUIPMENT_LIST:
        mark = " ✅" if item in selected else ""
        keyboard.append([InlineKeyboardButton(item + mark, callback_data=f"eq_{item}")])

    keyboard.append([InlineKeyboardButton("⬅ Назад", callback_data="back")])

    await query.edit_message_text("Выберите технику:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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

    await equipment_menu(update, context)


async def save_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["report"]["operations"].append(context.user_data["op"])
    await query.edit_message_text("✅ Операция сохранена")
    await show_stage2(query.message)


async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GROUP_ID
    query = update.callback_query
    await query.answer()

    if not GROUP_ID:
        await query.edit_message_text("Бот не знает ID группы.")
        return

    report = context.user_data["report"]
    header = report["header"]
    operations = report["operations"]

    text = f"📑 ОТЧЁТ\n\n"
    text += f"Бригада: {header.get('brigade')}\n"
    text += f"Скважина: {header.get('well')}\n"
    text += f"Месторождение: {header.get('field')}\n\n"

    for i, op in enumerate(operations, 1):
        text += f"{i}. {op['date']} — {op['name']}\n"
        text += f"Техника: {', '.join(op['equipment'])}\n\n"

    await context.bot.send_message(GROUP_ID, text)
    await query.edit_message_text("📤 Отчёт отправлен")


async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query

    if query.data == "add_op":
        await add_operation(update, context)
    elif query.data == "equipment":
        await equipment_menu(update, context)
    elif query.data.startswith("eq_"):
        await toggle_equipment(update, context)
    elif query.data == "back":
        await show_requests(query.message, context)
    elif query.data == "save_op":
        await save_operation(update, context)
    elif query.data == "send_report":
        await send_report(update, context)


# =========================
# MAIN (БЕЗ asyncio.run !!!)
# =========================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.ALL, capture_group), group=0)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CallbackQueryHandler(callbacks))

    threading.Thread(target=run_dummy_server).start()

    print("Polling запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()