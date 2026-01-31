# app.py - 4UTODAY Telegram Bot (FINAL FIXED VERSION)

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg
from psycopg.rows import dict_row
from telegram import Update, Bot
from datetime import datetime
import threading
import time

# ========== Flask App Setup ==========
app = Flask(__name__)
CORS(app)

# ========== Environment Variables ==========
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL') or os.environ.get('RENDER_URL')
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
CHANNEL_ID = os.environ.get('TELEGRAM_CHANNEL_ID')

if TOKEN:
    WEBHOOK_PATH = f"/tg-hook-{TOKEN[:8]}"
    WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}" if RENDER_URL else None
else:
    WEBHOOK_PATH = "/tg-hook-default"
    WEBHOOK_URL = None

print("🔧 Configuration Check:")
print(f"   - TOKEN exists: {'✅ Yes' if TOKEN else '❌ No'}")
print(f"   - DATABASE_URL exists: {'✅ Yes' if DATABASE_URL else '❌ No'}")
print(f"   - RENDER_URL: {RENDER_URL}")
print(f"   - Webhook URL: {WEBHOOK_URL}")

# ========== Database Functions ==========
def get_db_connection():
    if not DATABASE_URL:
        return None
    try:
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)
    except Exception as e:
        print(f"❌ DB connection error: {e}")
        return None

def init_database():
    conn = get_db_connection()
    if not conn:
        print("❌ Cannot initialize DB")
        return
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                telegram_message_id BIGINT UNIQUE,
                post_title TEXT NOT NULL,
                post_description TEXT,
                file_url TEXT,
                tags TEXT,
                channel_username VARCHAR(255)
            )
        """)
        conn.commit()
    conn.close()
    print("✅ Database table 'posts' is ready")

# ========== Telegram Webhook Handler ==========
@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    try:
        data = request.get_json(force=True)
        bot = Bot(TOKEN)
        update = Update.de_json(data, bot)
        if update and update.channel_post:
            process_post(update.channel_post, bot)
        return "OK", 200
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return "Error", 500

def process_post(message, bot):
    try:
        text = message.caption or message.text or ""
        title = text[:100] + "..." if len(text) > 100 else (text or "Media Post")

        file_url = ""
        try:
            if message.photo:
                file = bot.get_file(message.photo[-1].file_id)
                file_url = file.file_path
            elif message.video:
                file = bot.get_file(message.video.file_id)
                file_url = file.file_path
        except Exception as e:
            print(f"⚠️ File fetch skipped: {e}")

        tags = [w for w in text.split() if w.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        channel_name = message.chat.title or message.chat.username or "Unknown"

        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts
                    (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (telegram_message_id) DO NOTHING
                """, (
                    message.message_id,
                    title,
                    text,
                    file_url,
                    tags_str,
                    channel_name
                ))
                conn.commit()
            conn.close()
            print(f"✅ Saved Post: {title[:50]}")
    except Exception as e:
        print(f"❌ Post save error: {e}")

# ========== Webhook Background Setup (SAFE VERSION) ==========
def setup_webhook_background():
    if not TOKEN or not WEBHOOK_URL:
        print("⚠️ Webhook setup skipped")
        return

    def task():
        time.sleep(5)
        try:
            bot = Bot(TOKEN)
            print("🔄 Deleting old webhook...")
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)
            print(f"🔄 Setting new webhook to: {WEBHOOK_URL}")
            bot.set_webhook(url=WEBHOOK_URL)
            print("✅ Webhook successfully set")
        except Exception as e:
            print(f"❌ Webhook setup error: {e}")

    t = threading.Thread(target=task, daemon=True)
    t.start()
    print("🔄 Webhook setup started in background")

# ========== API Endpoints ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY API",
        "status": "online",
        "webhook": WEBHOOK_URL
    })

@app.route('/api/health')
def health():
    return jsonify({
        "status": "healthy",
        "time": datetime.utcnow().isoformat()
    })

@app.route('/api/posts')
def get_posts():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 50")
        posts = cur.fetchall()
        for p in posts:
            if p.get("created_at"):
                p["created_at"] = p["created_at"].isoformat()
    conn.close()
    return jsonify(posts)

@app.route('/api/stats')
def get_stats():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM posts")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT tags, COUNT(*) AS count
            FROM posts
            GROUP BY tags
            ORDER BY count DESC
            LIMIT 5
        """)
        tags = cur.fetchall()
    conn.close()
    return jsonify({
        "total_posts": total,
        "top_tags": tags
    })

# ========== Startup ==========
def startup():
    print("🚀 Starting 4UTODAY Bot...")
    init_database()
    setup_webhook_background()
    print("✅ Startup completed")

startup()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
