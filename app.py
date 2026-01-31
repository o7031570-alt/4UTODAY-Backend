# app.py - 4UTODAY Telegram Bot (Stable Webhook Version for Python 3.13)
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg  # Version 3
from psycopg.rows import dict_row
from telegram import Update, Bot
import asyncio
from datetime import datetime

# ========== Flask App Setup ==========
app = Flask(__name__)
CORS(app)

# Environment Variables
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
# Render URL (Environment Variable ထဲမှာ RENDER_EXTERNAL_URL ကို https://your-app.onrender.com လို့ ထည့်ထားပေးပါ)
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
WEBHOOK_PATH = f"/tg-hook-{TOKEN[:8] if TOKEN else 'default'}"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}" if RENDER_URL else None

# ========== Database Functions (Psycopg 3 Version) ==========
def get_db_connection():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("❌ DATABASE_URL is missing")
            return None
        
        # Psycopg 3 သည် SSL mode ကို connection string မှတစ်ဆင့် ကောင်းစွာ handle လုပ်နိုင်သည်
        conn = psycopg.connect(db_url, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_database():
    conn = get_db_connection()
    if not conn: return False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id BIGINT,
                    post_title TEXT NOT NULL,
                    post_description TEXT,
                    file_url TEXT,
                    tags TEXT,
                    channel_username VARCHAR(255)
                )
            """)
            conn.commit()
        conn.close()
        print("✅ Database table ready")
        return True
    except Exception as e:
        print(f"❌ Database init error: {e}")
        return False

# ========== Webhook Handling Logic ==========
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    try:
        data = request.get_json(force=True)
        async with Bot(TOKEN) as bot:
            update = Update.de_json(data, bot)
            if update.channel_post:
                await process_post(update.channel_post, bot)
        return "OK", 200
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return "Error", 500

async def process_post(message, bot):
    try:
        text = message.caption or message.text or ""
        title = text[:150] + "..." if len(text) > 150 else (text or "Media Post")
        
        file_url = ""
        if message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            file_url = file.file_path
        elif message.video:
            file = await bot.get_file(message.video.file_id)
            file_url = file.file_path

        tags = [word for word in text.split() if word.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        channel_name = message.chat.title or message.chat.username or "Unknown"

        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts 
                    (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (message.message_id, title, text, file_url, tags_str, channel_name))
                conn.commit()
            conn.close()
            print(f"✅ Saved Post: {title[:30]}")
    except Exception as e:
        print(f"❌ Post processing error: {e}")

# ========== Startup Configuration ==========
def setup_webhook():
    """Initialize DB and Set Webhook during Startup"""
    init_database()
    if not TOKEN or not WEBHOOK_URL:
        print("⚠️ Token or URL missing. Skipping Webhook Setup.")
        return

    async def set_it():
        try:
            async with Bot(TOKEN) as bot:
                await bot.set_webhook(url=WEBHOOK_URL)
                print(f"🌐 Webhook successfully set to: {WEBHOOK_URL}")
        except Exception as e:
            print(f"❌ Webhook setting failed: {e}")

    try:
        # Flask 3.0+ setup
        asyncio.run(set_it())
    except Exception as e:
        print(f"❌ Startup Async error: {e}")

# Run setup once before app starts
setup_webhook()

# ========== API Endpoints (မူရင်းအတိုင်း) ==========
@app.route('/')
def home():
    return jsonify({"service": "4UTODAY API", "status": "online", "webhook_url": WEBHOOK_URL})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/api/posts')
def get_posts():
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"error": "DB connection failed"}), 500
        
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 50")
            posts = cur.fetchall()
            for p in posts:
                p['created_at'] = p['created_at'].isoformat()
        conn.close()
        return jsonify(posts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM posts")
            total = cur.fetchone()['total']
            
            cur.execute("SELECT tags, COUNT(*) as count FROM posts GROUP BY tags ORDER BY count DESC LIMIT 5")
            tags = cur.fetchall()
        conn.close()
        return jsonify({"total": total, "tags": tags})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
