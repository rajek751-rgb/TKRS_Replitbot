import os
import re
import logging
from datetime import datetime
from flask import Flask, request
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

users = {}

TECH_LIST = [
    "ЦА","АЦН-10","АКН","АХО","ППУ","Цементосмеситель",
    "Автокран","Звено глушения","Звено СКБ","Тягач",
    "Седельный тягач","АЗА","Седельный тягач с КМУ",
    "Бортовой с КМУ","Топливозаправщик","Водовозка",
    "АРОК","Вахтовый автобус","УАЗ"
]

def valid_date(d):
    try:
        datetime.strptime(d, "%d.%m.%Y")
        return True
    except:
        return False

def valid_time(t):
    return re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", t)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users[update.effective_user.id] = {"step": "date"}
    await update.message.reply_text("📅 Введите дату (ДД.ММ.ГГГГ)")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    user = users.get(uid)

    if not user:
        await update.message.reply_text("Введите /start")
        return

    if user["step"] == "date":
        if not valid_date(text):
            await update.message.reply_text("❌ Неверная дата")
            return
        user["date"] = text
        user["step"] = "shift"
        keyboard = [["I смена","II смена"],["Обе смены"]]
        await update.message.reply_text(
            "Выберите смену",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if user["step"] == "shift":
        user["shift"] = text
        user["step"] = "name"
        await update.message.reply_text("📝 Название операции", reply_markup=ReplyKeyboardRemove())
        return

    if user["step"] == "name":
        user["name"] = text
        user["step"] = "done"
        await update.message.reply_text("✅ Тест успешен. Бот работает на Render.")
        return

bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    await bot_app.process_update(update)
    return "ok"

@app.route("/")
def home():
    return "TKRS Bot Running"

if __name__ == "__main__":
    bot_app.initialize()
    bot_app.start()
    app.run(host="0.0.0.0", port=PORT)