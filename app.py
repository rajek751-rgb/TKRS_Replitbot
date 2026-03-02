import os
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен!")

# -------- /start --------
async def start(update, context):
    keyboard = [["Меню 📋", "Помощь ℹ️"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        "Привет 👋 Выбери действие:",
        reply_markup=markup
    )

# -------- текст --------
async def handle_text(update, context):
    text = update.message.text

    if text == "Меню 📋":
        keyboard = [
            [
                InlineKeyboardButton("Кнопка 1", callback_data="btn1"),
                InlineKeyboardButton("Кнопка 2", callback_data="btn2")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Вот inline кнопки:",
            reply_markup=reply_markup
        )

    elif text == "Помощь ℹ️":
        await update.message.reply_text("Это простой бот 🚀")

    else:
        await update.message.reply_text(f"Ты написал: {text}")

# -------- inline кнопки --------
async def button_handler(update, context):
    query = update.callback_query
    await query.answer()

    if query.data == "btn1":
        await query.edit_message_text("Нажата кнопка 1 ✅")
    elif query.data == "btn2":
        await query.edit_message_text("Нажата кнопка 2 ✅")

# -------- запуск --------
def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()