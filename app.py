import os
import asyncio
from flask import Flask, request
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ================= CONFIG =================
TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN not set")

if not WEBHOOK_URL:
    raise ValueError("WEBHOOK_URL not set")

# ================= FLASK =================
app = Flask(__name__)

# ================= TELEGRAM =================
application = Application.builder().token(TOKEN).build()


# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["Меню 📋", "Помощь ℹ️"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет 👋 Выбери действие:",
        reply_markup=markup,
    )


# ---------- TEXT ----------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "Меню 📋":
        keyboard = [
            [
                InlineKeyboardButton("Кнопка 1", callback_data="btn1"),
                InlineKeyboardButton("Кнопка 2", callback_data="btn2"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Вот inline кнопки:",
            reply_markup=reply_markup,
        )

    elif text == "Помощь ℹ️":
        await update.message.reply_text("Это бот с кнопками 🚀")

    else:
        await update.message.reply_text(f"Ты написал: {text}")


# ---------- INLINE ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "btn1":
        await query.edit_message_text("Нажата кнопка 1 ✅")
    elif query.data == "btn2":
        await query.edit_message_text("Нажата кнопка 2 ✅")


application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
application.add_handler(CallbackQueryHandler(button_handler))


# ================= WEBHOOK =================
@app.post(f"/{TOKEN}")
async def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return "ok"


@app.get("/")
def health():
    return "Bot is running!"


# ================= STARTUP =================
async def setup_webhook():
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(f"{WEBHOOK_URL}/{TOKEN}")


# Gunicorn hook
@app.before_first_request
def activate_job():
    asyncio.run(setup_webhook())


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)