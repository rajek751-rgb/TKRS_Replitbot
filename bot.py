import os
import requests
import psycopg2
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("BOT_TOKEN не установлен")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен")

API_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

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

def get_reports():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username, message, created_at FROM reports ORDER BY created_at DESC LIMIT 20")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# =========================
# TELEGRAM SEND
# =========================

def send_message(chat_id, text):
    requests.post(
        f"{API_URL}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        }
    )

# =========================
# ROUTES
# =========================

@app.route("/")
def home():
    return "Bot is running"

@app.route(f"/webhook/{TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()

    if "message" not in data:
        return "ok"

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user = message["from"]

    if text == "/start":
        send_message(
            chat_id,
            "👋 Привет!\n\n"
            "Отправь сообщение — я сохраню его как отчёт.\n"
            "/reports — показать отчёты"
        )

    elif text == "/reports":
        rows = get_reports()

        if not rows:
            send_message(chat_id, "Отчётов пока нет.")
        else:
            response = "📊 Последние отчёты:\n\n"
            for username, message_text, created_at in rows:
                response += f"👤 {username}\n📝 {message_text}\n🕒 {created_at}\n\n"

            send_message(chat_id, response)

    elif text:
        save_report(
            user_id=user["id"],
            username=user.get("username", user.get("first_name")),
            message=text
        )
        send_message(chat_id, "✅ Отчёт сохранён!")

    return "ok"

# =========================
# MAIN
# =========================

if __name__ == "__main__":
    init_db()

    # Устанавливаем webhook автоматически
    webhook_url = os.getenv("RENDER_EXTERNAL_URL") + f"/webhook/{TOKEN}"
    requests.post(f"{API_URL}/setWebhook", json={"url": webhook_url})

    print("Webhook установлен:", webhook_url)

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))