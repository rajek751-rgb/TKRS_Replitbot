import os
from datetime import date, time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
ApplicationBuilder,
CommandHandler,
CallbackQueryHandler,
MessageHandler,
ContextTypes,
filters
)

from database import cursor, conn
from web import app

from threading import Thread

TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = -100000000000

# WEB SERVER
def run_web():
    app.run(host="0.0.0.0", port=10000)

Thread(target=run_web, daemon=True).start()

# MENU
def menu():

    keyboard = [

        [InlineKeyboardButton("📝 Создать отчёт",callback_data="create")],

        [InlineKeyboardButton("📊 Мой отчёт",callback_data="my")],

        [InlineKeyboardButton("📈 Статистика",callback_data="stat")]

    ]

    return InlineKeyboardMarkup(keyboard)

# START
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📊 Report CRM Bot",
        reply_markup=menu()
    )

# BUTTONS
async def buttons(update:Update,context:ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data=="create":

        context.user_data["state"]="done"

        await query.message.reply_text(
            "Что сделали сегодня?"
        )

    elif query.data=="my":

        today=str(date.today())

        cursor.execute(
        "SELECT done,problems,plan FROM reports WHERE user_id=? AND date=?",
        (query.from_user.id,today)
        )

        r=cursor.fetchone()

        if not r:

            await query.message.reply_text("Нет отчёта")

            return

        text=f"""
📊 Ваш отчёт

✅ Сделано
{r[0]}

⚠️ Проблемы
{r[1]}

📅 План
{r[2]}
"""

        await query.message.reply_text(text)

    elif query.data=="stat":

        cursor.execute(
        "SELECT COUNT(*) FROM reports WHERE user_id=?",
        (query.from_user.id,)
        )

        total=cursor.fetchone()[0]

        await query.message.reply_text(
        f"📈 Всего отчётов: {total}"
        )

# TEXT
async def messages(update:Update,context:ContextTypes.DEFAULT_TYPE):

    state=context.user_data.get("state")

    if not state:
        return

    user=update.effective_user

    if state=="done":

        context.user_data["done"]=update.message.text
        context.user_data["state"]="problems"

        await update.message.reply_text("Какие проблемы?")

    elif state=="problems":

        context.user_data["problems"]=update.message.text
        context.user_data["state"]="plan"

        await update.message.reply_text("План на завтра?")

    elif state=="plan":

        done=context.user_data["done"]
        problems=context.user_data["problems"]
        plan=update.message.text

        today=str(date.today())

        cursor.execute("""
        INSERT INTO reports
        (user_id,username,date,done,problems,plan)
        VALUES (?,?,?,?,?,?)
        """,(user.id,user.username,today,done,problems,plan))

        conn.commit()

        text=f"""
📊 Отчёт

✅ Сделано
{done}

⚠️ Проблемы
{problems}

📅 План
{plan}

👤 @{user.username}
"""

        await context.bot.send_message(
        chat_id=GROUP_ID,
        text=text
        )

        await update.message.reply_text(
        "✅ Отчёт отправлен"
        )

        context.user_data["state"]=None

# REMINDER
async def reminder(context:ContextTypes.DEFAULT_TYPE):

    await context.bot.send_message(
    chat_id=GROUP_ID,
    text="⏰ Напоминание отправить отчёты"
    )

# SUMMARY
async def summary(context:ContextTypes.DEFAULT_TYPE):

    today=str(date.today())

    cursor.execute(
    "SELECT username FROM reports WHERE date=?",
    (today,)
    )

    users=cursor.fetchall()

    text="📊 Отчёты сегодня\n\n"

    for u in users:
        text+=f"@{u[0]} ✅\n"

    await context.bot.send_message(
    chat_id=GROUP_ID,
    text=text
    )

# BOT
app_bot = ApplicationBuilder().token(TOKEN).build()

app_bot.add_handler(CommandHandler("start",start))
app_bot.add_handler(CallbackQueryHandler(buttons))
app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,messages))

app_bot.job_queue.run_daily(reminder,time=time(hour=18))
app_bot.job_queue.run_daily(summary,time=time(hour=19))

print("BOT STARTED")

app_bot.run_polling()