import os
import sqlite3
import pandas as pd
import asyncio
from datetime import datetime
from threading import Thread

from flask import Flask

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("BOT_TOKEN")

DONE, PROBLEMS, PLAN = range(3)

# ---------------- DATABASE ----------------

conn = sqlite3.connect("reports.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reports(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
username TEXT,
date TEXT,
done TEXT,
problems TEXT,
plan TEXT
)
""")

conn.commit()

# ---------------- WEB PANEL ----------------

app = Flask(__name__)

@app.route("/")
def home():

    cursor.execute("""
    SELECT username,date,done,problems,plan
    FROM reports
    ORDER BY id DESC
    LIMIT 100
    """)

    rows = cursor.fetchall()

    html = "<h2>Team Reports</h2><table border=1>"
    html += "<tr><th>User</th><th>Date</th><th>Done</th><th>Problems</th><th>Plan</th></tr>"

    for r in rows:
        html += f"""
        <tr>
        <td>@{r[0]}</td>
        <td>{r[1]}</td>
        <td>{r[2]}</td>
        <td>{r[3]}</td>
        <td>{r[4]}</td>
        </tr>
        """

    html += "</table>"
    return html


def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


# ---------------- BOT ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📋 Daily Report\n\nЧто сделал сегодня?"
    )

    return DONE


async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["done"] = update.message.text

    await update.message.reply_text(
        "⚠️ Были проблемы?"
    )

    return PROBLEMS


async def problems(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["problems"] = update.message.text

    await update.message.reply_text(
        "📅 План на завтра?"
    )

    return PLAN


async def plan(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["plan"] = update.message.text

    user = update.message.from_user

    cursor.execute(
        """
        INSERT INTO reports
        (user_id, username, date, done, problems, plan)
        VALUES (?,?,?,?,?,?)
        """,
        (
            user.id,
            user.username,
            datetime.now().strftime("%Y-%m-%d"),
            context.user_data["done"],
            context.user_data["problems"],
            context.user_data["plan"],
        ),
    )

    conn.commit()

    await update.message.reply_text(
        "✅ Отчёт сохранён!"
    )

    return ConversationHandler.END


# ---------------- EXCEL ----------------

async def excel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    df = pd.read_sql_query("SELECT * FROM reports", conn)

    file = "reports.xlsx"
    df.to_excel(file, index=False)

    await update.message.reply_document(
        document=open(file, "rb")
    )


# ---------------- MAIN ----------------

async def main():

    app_bot = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, done)],
            PROBLEMS: [MessageHandler(filters.TEXT & ~filters.COMMAND, problems)],
            PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan)],
        },
        fallbacks=[],
    )

    app_bot.add_handler(conv)
    app_bot.add_handler(CommandHandler("excel", excel))

    print("BOT STARTED")

    await app_bot.run_polling()


# ---------------- RUN ----------------

if __name__ == "__main__":

    Thread(target=run_web).start()

    asyncio.run(main())