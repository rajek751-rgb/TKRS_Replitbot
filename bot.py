import os
import logging
import psycopg2
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# =========================
# DATABASE
# =========================

def get_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            username TEXT,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

def save_report(user_id, username, message):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reports (user_id, username, message) VALUES (%s, %s, %s)",
        (user_id, username, message),
    )
    conn.commit()
    cur.close()
    conn.close()

def get_all_reports():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, message, created_at FROM reports ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# =========================
# HANDLERS
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Отправь сообщение — я сохраню его как отчёт.\n"
        "/reports — показать отчёты"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    save_report(
        user_id=user.id,
        username=user.username or user.first_name,
        message=text,
    )

    await update.message.reply_text("✅ Отчёт сохранён!")

async def reports(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_all_reports()

    if not rows:
        await update.message.reply_text("Отчётов пока нет.")
        return

    text = "📊 Последние отчёты:\n\n"
    for username, message, created_at in rows[:20]:
        text += f"👤 {username}\n📝 {message}\n🕒 {created_at}\n\n"

    await update.message.reply_text(text)

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reports", reports))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен (long polling)...")

    app.run_polling()