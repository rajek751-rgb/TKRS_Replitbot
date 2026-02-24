import os
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TOKEN = TOKEN.replace("\n", "").replace("\r", "").strip()

logging.basicConfig(level=logging.INFO)

(
    MENU,
    BRIGADE,
    OBJECT,
    SHIFT,
    START,
    END,
    NAME,
    TECH,
    REPRESENTATIVE,
    EQUIPMENT,
    ACTION,
) = range(11)

TECH_LIST = [
    "ЦА","АЦН-10","АКН","АХО","ППУ","Цементосмеситель",
    "Автокран","Звено глушения","Звено СКБ","Тягач",
    "Седельный тягач","АЗА","Седельный тягач с КМУ",
    "Бортовой с КМУ","Топливозаправщик","Водовозка",
    "АРОК","Вахтовый автобус","УАЗ"
]

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [["▶ Начать заполнение"]],
    resize_keyboard=True
)

ACTION_KEYBOARD = ReplyKeyboardMarkup(
    [["➕ Добавить операцию"], ["✅ Завершить отчёт"]],
    resize_keyboard=True
)

SHIFT_KEYBOARD = ReplyKeyboardMarkup(
    [["🌞 I смена (08:00-20:00)"],
     ["🌙 II смена (20:00-08:00)"]],
    resize_keyboard=True
)

# ================== START ==================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *ОТЧЁТ ТКРС*\n\nНажмите кнопку ниже для начала.",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown"
    )
    return MENU


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "Начать" in update.message.text:
        await update.message.reply_text("🔹 Введите номер бригады ТКРС:")
        return BRIGADE
    return MENU


# ================== ОБЩИЕ ДАННЫЕ ==================

async def brigade(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["brigade"] = update.message.text
    await update.message.reply_text(
        "🔹 Введите номер скважины и месторождение\n\nПример:\n1256 Восточно-Сургутское"
    )
    return OBJECT


async def object_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["object"] = update.message.text
    context.user_data["operations"] = []
    await update.message.reply_text(
        "🔄 Выберите смену:",
        reply_markup=SHIFT_KEYBOARD
    )
    return SHIFT


# ================== ОПЕРАЦИЯ ==================

async def shift(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_shift"] = update.message.text
    await update.message.reply_text("⏰ Введите время НАЧАЛА (ЧЧ:ММ):")
    return START


async def start_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_start"] = update.message.text
    await update.message.reply_text("⏰ Введите время ОКОНЧАНИЯ (ЧЧ:ММ):")
    return END


async def end_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_end"] = update.message.text
    await update.message.reply_text("📝 Введите название операции:")
    return NAME


async def name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_name"] = update.message.text

    keyboard = [[t] for t in TECH_LIST]
    await update.message.reply_text(
        "🚜 Выберите технику:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    return TECH


async def tech(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_tech"] = update.message.text
    await update.message.reply_text(
        "👤 Введите представителя заказчика (или -):"
    )
    return REPRESENTATIVE


async def representative(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["current_rep"] = update.message.text
    await update.message.reply_text(
        "📦 Введите оборудование и материалы (или -):"
    )
    return EQUIPMENT


async def equipment(update: Update, context: ContextTypes.DEFAULT_TYPE):

    operation = {
        "shift": context.user_data["current_shift"],
        "start": context.user_data["current_start"],
        "end": context.user_data["current_end"],
        "name": context.user_data["current_name"],
        "tech": context.user_data["current_tech"],
        "rep": context.user_data["current_rep"],
        "equipment": update.message.text,
    }

    context.user_data["operations"].append(operation)

    await update.message.reply_text(
        "✅ Операция добавлена.\n\nВыберите действие:",
        reply_markup=ACTION_KEYBOARD
    )
    return ACTION


# ================== ДЕЙСТВИЕ ==================

async def action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if "Добавить" in text:
        await update.message.reply_text(
            "🔄 Выберите смену:",
            reply_markup=SHIFT_KEYBOARD
        )
        return SHIFT

    if "Завершить" in text:
        ops = context.user_data["operations"]

        report = f"""
📊 *ОТЧЁТ ТКРС*

👷 Бригада: {context.user_data['brigade']}
🛢 Объект: {context.user_data['object']}

────────────────────────────
№ | Смена | Начало | Конец
────────────────────────────
"""

        for i, op in enumerate(ops, 1):
            report += f"{i}. {op['shift']}\n"
            report += f"   ⏰ {op['start']} - {op['end']}\n"
            report += f"   📝 {op['name']}\n"
            report += f"   🚜 {op['tech']}\n"
            report += f"   👤 {op['rep']}\n"
            report += f"   📦 {op['equipment']}\n\n"

        await update.message.reply_text(report, parse_mode="Markdown")
        return ConversationHandler.END

    return ACTION


# ================== MAIN ==================

def main():
    app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, menu)],
            BRIGADE: [MessageHandler(filters.TEXT & ~filters.COMMAND, brigade)],
            OBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, object_data)],
            SHIFT: [MessageHandler(filters.TEXT & ~filters.COMMAND, shift)],
            START: [MessageHandler(filters.TEXT & ~filters.COMMAND, start_time)],
            END: [MessageHandler(filters.TEXT & ~filters.COMMAND, end_time)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name)],
            TECH: [MessageHandler(filters.TEXT & ~filters.COMMAND, tech)],
            REPRESENTATIVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, representative)],
            EQUIPMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, equipment)],
            ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, action)],
        },
        fallbacks=[],
    )

    app.add_handler(conv)
    app.run_polling()


if __name__ == "__main__":
    main()