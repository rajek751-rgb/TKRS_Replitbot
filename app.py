import os
import json
import asyncio
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")  # ID группы для отправки отчётов

# =========================
# FILE-BASED DATABASE
# =========================

DATA_DIR = "data"
REPORTS_FILE = os.path.join(DATA_DIR, "reports.json")
OPERATIONS_FILE = os.path.join(DATA_DIR, "operations.json")
CHANGE_LOG_FILE = os.path.join(DATA_DIR, "change_log.json")

def ensure_data_dir():
    """Создаёт директорию для данных, если её нет"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def load_json(file_path, default=None):
    """Загружает данные из JSON файла"""
    if default is None:
        default = []
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return default

def save_json(file_path, data):
    """Сохраняет данные в JSON файл"""
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

def init_db():
    """Инициализация файлового хранилища"""
    ensure_data_dir()
    
    # Создаём файлы с пустыми структурами, если их нет
    if not os.path.exists(REPORTS_FILE):
        save_json(REPORTS_FILE, [])
    if not os.path.exists(OPERATIONS_FILE):
        save_json(OPERATIONS_FILE, [])
    if not os.path.exists(CHANGE_LOG_FILE):
        save_json(CHANGE_LOG_FILE, [])

def get_next_report_number(brigade):
    """Получает следующий номер отчёта для бригады"""
    reports = load_json(REPORTS_FILE)
    brigade_reports = [r for r in reports if r.get('brigade') == brigade]
    if brigade_reports:
        return max(r.get('report_number', 0) for r in brigade_reports) + 1
    return 1

def add_change_log(report_id, user_id, action):
    """Добавляет запись в журнал изменений"""
    logs = load_json(CHANGE_LOG_FILE)
    logs.append({
        'report_id': report_id,
        'user_id': user_id,
        'action': action,
        'timestamp': datetime.now().isoformat()
    })
    save_json(CHANGE_LOG_FILE, logs)

# =========================
# TELEGRAM APP
# =========================

app = Application.builder().token(BOT_TOKEN).build()

# =========================
# SEND TO TELEGRAM GROUP
# =========================

async def send_to_group(report_id):
    """Отправляет отчёт в Telegram группу"""
    try:
        report = get_report_by_id(report_id)
        if not report:
            return
        
        operations = get_operations_for_report(report_id)
        
        text = f"""📑 ОТЧЁТ №{report['report_number']}

📌 Сетевой график
Бригада: {report['brigade']}
Объект: {report['well_field']}
Дата отчёта: {datetime.fromisoformat(report['report_date']).strftime('%d.%m.%Y')}

──────────────
"""
        
        current_date = None
        for op in operations:
            op_date = datetime.fromisoformat(op['operation_date']).date()
            start = datetime.fromisoformat(op['start_time']).time() if isinstance(op['start_time'], str) else op['start_time']
            end = datetime.fromisoformat(op['end_time']).time() if isinstance(op['end_time'], str) else op['end_time']
            
            if op_date != current_date:
                current_date = op_date
                text += f"\n📅 {op_date.strftime('%d.%m.%Y')}\n\n"
            
            text += f"""🔹 {start.strftime('%H:%M') if hasattr(start, 'strftime') else start}–{end.strftime('%H:%M') if hasattr(end, 'strftime') else end} | {op['name']}
   📄 Заявка №{op['request_number']}
   🚜 {op['equipment']}
   👷 {op['representative']}
   📦 {op['materials']}

"""
        
        # Создаём клавиатуру для открытия отчёта
        keyboard = [[InlineKeyboardButton("📋 Открыть отчёт", callback_data=f"open_{report_id}")]]
        
        # Отправляем в группу
        await app.bot.send_message(
            chat_id=TELEGRAM_GROUP_ID,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        print(f"Ошибка отправки в группу: {e}")

def get_report_by_id(report_id):
    """Получает отчёт по ID"""
    reports = load_json(REPORTS_FILE)
    for report in reports:
        if report.get('id') == report_id:
            return report
    return None

def get_operations_for_report(report_id):
    """Получает операции для отчёта"""
    operations = load_json(OPERATIONS_FILE)
    return [op for op in operations if op.get('report_id') == report_id]

# =========================
# RENDER REPORT SCREEN
# =========================

async def render_report(report_id, message):
    """Отрисовывает отчёт"""
    report = get_report_by_id(report_id)
    if not report:
        await message.edit_text("❌ Отчёт не найден")
        return
    
    operations = get_operations_for_report(report_id)
    
    text = f"""📑 Отчёт №{report['report_number']}

📌 Сетевой график
Бригада: {report['brigade']}
Объект: {report['well_field']}
Дата отчёта: {datetime.fromisoformat(report['report_date']).strftime('%d.%m.%Y')}

──────────────
"""
    
    current_date = None
    
    for op in operations:
        op_date = datetime.fromisoformat(op['operation_date']).date()
        start = datetime.fromisoformat(op['start_time']).time() if isinstance(op['start_time'], str) else op['start_time']
        end = datetime.fromisoformat(op['end_time']).time() if isinstance(op['end_time'], str) else op['end_time']
        
        if op_date != current_date:
            current_date = op_date
            text += f"\n📅 {op_date.strftime('%d.%m.%Y')}\n\n"
        
        text += f"""🔹 {start.strftime('%H:%M') if hasattr(start, 'strftime') else start}–{end.strftime('%H:%M') if hasattr(end, 'strftime') else end} | {op['name']}
   📄 Заявка №{op['request_number']}
   🚜 {op['equipment']}
   👷 {op['representative']}
   📦 {op['materials']}

"""
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить операцию", callback_data=f"add_{report_id}")],
        [InlineKeyboardButton("📜 Журнал изменений", callback_data=f"log_{report_id}")],
        [InlineKeyboardButton("📤 Отправить в группу", callback_data=f"share_{report_id}")],
        [InlineKeyboardButton("🔄 Новый график", callback_data="new")]
    ]
    
    await message.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    keyboard = [[InlineKeyboardButton("📑 Новый график", callback_data="new")]]
    await update.message.reply_text(
        "🏗 Корпоративная система ТКРС\n\n"
        "Бот для создания и управления сетевыми графиками работ",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

# =========================
# CREATE REPORT
# =========================

async def new_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создание нового отчёта"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Введите номер бригады:")
    context.user_data["state"] = "brigade"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    state = context.user_data.get("state")
    
    if not state:
        return
    
    if state == "brigade":
        context.user_data["brigade"] = update.message.text
        await update.message.reply_text("Введите дату отчёта (ДД.ММ.ГГГГ):")
        context.user_data["state"] = "date"
    
    elif state == "date":
        try:
            context.user_data["date"] = datetime.strptime(
                update.message.text, "%d.%m.%Y"
            ).date()
            await update.message.reply_text("Введите скважина / месторождение:")
            context.user_data["state"] = "well"
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    
    elif state == "well":
        brigade = context.user_data["brigade"]
        report_date = context.user_data["date"]
        well = update.message.text
        
        # Создаём отчёт
        reports = load_json(REPORTS_FILE)
        number = get_next_report_number(brigade)
        
        report_id = len(reports) + 1
        new_report = {
            'id': report_id,
            'brigade': brigade,
            'report_number': number,
            'report_date': report_date.isoformat(),
            'well_field': well,
            'created_by': update.effective_user.id,
            'created_at': datetime.now().isoformat()
        }
        
        reports.append(new_report)
        save_json(REPORTS_FILE, reports)
        
        # Логируем создание
        add_change_log(report_id, update.effective_user.id, f"Создан отчёт №{number}")
        
        context.user_data.clear()
        
        keyboard = [[InlineKeyboardButton("📋 Открыть отчёт", callback_data=f"open_{report_id}")]]
        await update.message.reply_text(
            f"✅ Отчёт №{number} создан",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ================= ADD OPERATION =================
    
    elif state == "op_date":
        try:
            context.user_data["op_date"] = datetime.strptime(
                update.message.text, "%d.%m.%Y"
            ).date()
            await update.message.reply_text("Время начала (ЧЧ:ММ):")
            context.user_data["state"] = "op_start"
        except ValueError:
            await update.message.reply_text("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
    
    elif state == "op_start":
        try:
            datetime.strptime(update.message.text, "%H:%M")
            context.user_data["op_start"] = update.message.text
            await update.message.reply_text("Время окончания (ЧЧ:ММ):")
            context.user_data["state"] = "op_end"
        except ValueError:
            await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ")
    
    elif state == "op_end":
        try:
            datetime.strptime(update.message.text, "%H:%M")
            context.user_data["op_end"] = update.message.text
            await update.message.reply_text("Название операции:")
            context.user_data["state"] = "op_name"
        except ValueError:
            await update.message.reply_text("❌ Неверный формат времени. Используйте ЧЧ:ММ")
    
    elif state == "op_name":
        context.user_data["op_name"] = update.message.text
        await update.message.reply_text("Номер заявки:")
        context.user_data["state"] = "op_req"
    
    elif state == "op_req":
        context.user_data["op_req"] = update.message.text
        await update.message.reply_text("Техника:")
        context.user_data["state"] = "op_eq"
    
    elif state == "op_eq":
        context.user_data["op_eq"] = update.message.text
        await update.message.reply_text("Представитель:")
        context.user_data["state"] = "op_rep"
    
    elif state == "op_rep":
        context.user_data["op_rep"] = update.message.text
        await update.message.reply_text("Материалы:")
        context.user_data["state"] = "op_mat"
    
    elif state == "op_mat":
        # Сохраняем операцию
        operations = load_json(OPERATIONS_FILE)
        
        new_operation = {
            'id': len(operations) + 1,
            'report_id': context.user_data["report_id"],
            'operation_date': context.user_data["op_date"].isoformat(),
            'start_time': context.user_data["op_start"],
            'end_time': context.user_data["op_end"],
            'name': context.user_data["op_name"],
            'request_number': context.user_data["op_req"],
            'equipment': context.user_data["op_eq"],
            'representative': context.user_data["op_rep"],
            'materials': update.message.text
        }
        
        operations.append(new_operation)
        save_json(OPERATIONS_FILE, operations)
        
        # Логируем добавление
        add_change_log(
            context.user_data["report_id"], 
            update.effective_user.id, 
            f"Добавлена операция: {context.user_data['op_name']}"
        )
        
        report_id = context.user_data["report_id"]
        context.user_data.clear()
        
        await render_report(report_id, update.message)

# =========================
# CALLBACKS
# =========================

async def open_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Открывает отчёт"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    await render_report(report_id, query.message)

async def add_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет операцию"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    context.user_data["report_id"] = report_id
    context.user_data["state"] = "op_date"
    await query.edit_message_text("Введите дату операции (ДД.ММ.ГГГГ):")

async def share_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет отчёт в группу"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    
    if not TELEGRAM_GROUP_ID:
        await query.edit_message_text("❌ ID группы не настроен")
        return
    
    await query.edit_message_text("📤 Отправка отчёта в группу...")
    await send_to_group(report_id)
    
    # Возвращаемся к отчёту
    await asyncio.sleep(1)
    await render_report(report_id, query.message)

async def show_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает журнал изменений"""
    query = update.callback_query
    await query.answer()
    report_id = int(query.data.split("_")[1])
    
    logs = load_json(CHANGE_LOG_FILE)
    report_logs = [log for log in logs if log.get('report_id') == report_id]
    
    text = "📜 Журнал изменений\n\n"
    if not report_logs:
        text += "Нет записей"
    else:
        for log in report_logs[-10:]:  # Показываем последние 10 записей
            ts = datetime.fromisoformat(log['timestamp'])
            text += f"{ts.strftime('%d.%m %H:%M')} | {log['action']}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data=f"open_{report_id}")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# =========================
# HANDLERS
# =========================

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(new_report, pattern="^new$"))
app.add_handler(CallbackQueryHandler(open_report, pattern="^open_"))
app.add_handler(CallbackQueryHandler(add_operation, pattern="^add_"))
app.add_handler(CallbackQueryHandler(show_log, pattern="^log_"))
app.add_handler(CallbackQueryHandler(share_report, pattern="^share_"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

if __name__ == "__main__":
    init_db()
    print("Бот запущен...")
    asyncio.run(app.run_polling())