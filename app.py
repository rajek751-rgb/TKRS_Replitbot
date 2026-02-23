import os
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
PORT = int(os.environ.get("PORT", 10000))

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()


# ====== TELEGRAM COMMAND ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает на Render!")


application.add_handler(CommandHandler("start", start))


# ====== WEBHOOK ======
@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"


@app.route("/")
def home():
    return "Bot is running"


# ====== START SERVER ======
if __name__ == "__main__":
    application.initialize()
    application.start()
    app.run(host="0.0.0.0", port=PORT)