# app.py - 4UTODAY Telegram Bot with PostgreSQL
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import threading
import asyncio
from datetime import datetime

# ========== Flask App Setup ==========
app = Flask(__name__)
CORS(app)

# ========== Database Functions ==========
def get_db_connection():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            return None
        
        # Render require SSL
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

# ========== Telegram Bot Handler ==========
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        message = update.channel_post
        if not message: return

        title = (message.caption or message.text or "Media Post")[:150]
        description = message.caption or message.text or ""
        
        file_url = ""
        if message.photo:
            file = await context.bot.get_file(message.photo[-1].file_id)
            file_url = file.file_path
        
        tags = [word for word in (description).split() if word.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO posts (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """, (message.message_id, title, description, file_url, tags_str, message.chat.title))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Saved: {title[:30]}")
    except Exception as e:
        print(f"❌ Processing error: {e}")

# ========== Bot Manager Class ==========
class BotManager:
    def __init__(self):
        self.application = None
        self.is_running = False

    def run_bot(self):
        """Internal method to run the event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # stop_signals=False is crucial for running in a thread
            self.application.run_polling(stop_signals=False, close_loop=False)
        except Exception as e:
            print(f"❌ Bot polling error: {e}")
            self.is_running = False

    def start_bot(self):
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN missing")
            return
        
        try:
            init_database()
            self.application = Application.builder().token(token).build()
            self.application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
            
            self.is_running = True
            thread = threading.Thread(target=self.run_bot, daemon=True)
            thread.start()
            print("🤖 4UTODAY Bot thread started")
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            self.is_running = False

bot_manager = BotManager()
bot_manager.start_bot()

# ========== API Routes ==========
@app.route('/')
def home():
    return jsonify({"service": "4UTODAY API", "bot": "active" if bot_manager.is_running else "inactive"})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "db": "ok", "time": datetime.now().isoformat()})

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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
