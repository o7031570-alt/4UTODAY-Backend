# app.py - 4UTODAY Telegram Bot with PostgreSQL (Webhook Version - Fixed for Flask 3.0+)
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, Bot
import asyncio
from datetime import datetime

# ========== Flask App Setup ==========
app = Flask(__name__)
CORS(app)

# Environment Variables
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
# Render URL setup
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL')
WEBHOOK_PATH = f"/tg-{TOKEN[:8]}" # Security suffix
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}" if RENDER_URL else None

# ========== Database Functions ==========
def get_db_connection():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url: return None
        if "sslmode" not in db_url:
            db_url += ("&" if "?" in db_url else "?") + "sslmode=require"
        conn = psycopg2.connect(db_url, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_database():
    conn = get_db_connection()
    if not conn: return False
    try:
        cur = conn.cursor()
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
        cur.close()
        conn.close()
        print("✅ Database table ready")
        return True
    except Exception as e:
        print(f"❌ Database init error: {e}")
        return False

# ========== Webhook Handling ==========
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, Bot(TOKEN))
        if update.channel_post:
            await process_post(update.channel_post)
        return "OK", 200
    except Exception as e:
        print(f"❌ Webhook Processing Error: {e}")
        return "Error", 500

async def process_post(message):
    try:
        text = message.caption or message.text or ""
        title = text[:150] + "..." if len(text) > 150 else (text or "Media Post")
        
        file_url = ""
        bot = Bot(TOKEN)
        if message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            file_url = file.file_path
        elif message.video:
            file = await bot.get_file(message.video.file_id)
            file_url = file.file_path
        
        tags = [word for word in text.split() if word.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO posts (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (message.message_id, title, text, file_url, tags_str, message.chat.title))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Saved: {title[:30]}")
    except Exception as e:
        print(f"❌ Post logic error: {e}")

# Webhook Setup Function (Manual initialization)
def setup_webhook():
    """Set up webhook and initialize database manually before app starts"""
    init_database()
    if not TOKEN or not WEBHOOK_URL:
        print("⚠️ Bot Token or Webhook URL is missing. Skipping webhook setup.")
        return

    async def set_webhook():
        try:
            bot = Bot(TOKEN)
            await bot.set_webhook(url=WEBHOOK_URL)
            print(f"🌐 Webhook linked: {WEBHOOK_URL}")
        except Exception as e:
            print(f"❌ Webhook setup failed: {e}")

    try:
        asyncio.run(set_webhook())
    except Exception as e:
        print(f"❌ Asyncio run error: {e}")

# ========== API Routes ==========
@app.route('/')
def home():
    return jsonify({"service": "4UTODAY API", "status": "running", "webhook": WEBHOOK_URL})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "now": datetime.now().isoformat()})

@app.route('/api/posts')
def get_posts():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT 50")
        posts = cur.fetchall()
        for p in posts: p['created_at'] = p['created_at'].isoformat()
        cur.close()
        conn.close()
        return jsonify(posts)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== App Initialization ==========
# Flask 3.0+ မှာ before_first_request မရှိတော့လို့ 
# App မ run ခင် ဒီကနေ တိုက်ရိုက် ခေါ်ပေးရပါတယ်။
setup_webhook()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
