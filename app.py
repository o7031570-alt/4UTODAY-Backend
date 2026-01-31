# app.py - 4UTODAY Telegram Bot with PostgreSQL
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
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
    """Connect to PostgreSQL database with SSL requirement for Render"""
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("❌ ERROR: DATABASE_URL environment variable is missing!")
            return None
        
        # Render database require SSL mode
        if "sslmode" not in db_url:
            if "?" in db_url:
                db_url += "&sslmode=require"
            else:
                db_url += "?sslmode=require"
                
        conn = psycopg2.connect(
            db_url,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_database():
    """Initialize database table if not exists"""
    conn = get_db_connection()
    if not conn:
        return False
    
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
    """Process new posts from Telegram channel"""
    try:
        message = update.channel_post
        if not message:
            return
        
        print(f"📨 New post from channel: {message.chat.title}")
        
        title = ""
        description = ""
        
        if message.caption:
            title = message.caption[:150] + "..." if len(message.caption) > 150 else message.caption
            description = message.caption
        elif message.text:
            title = message.text[:150] + "..." if len(message.text) > 150 else message.text
            description = message.text
        else:
            title = "Media Post"
            description = "No text content"
        
        file_url = ""
        if message.photo:
            file_id = message.photo[-1].file_id
            file = await context.bot.get_file(file_id)
            file_url = file.file_path
        elif message.video:
            file = await context.bot.get_file(message.video.file_id)
            file_url = file.file_path
        elif message.document:
            file = await context.bot.get_file(message.document.file_id)
            file_url = file.file_path
        
        tags = []
        text_source = message.caption or message.text or ""
        for word in text_source.split():
            if word.startswith("#"):
                tags.append(word)
        
        tags_str = ", ".join(tags) if tags else "general"
        channel_name = message.chat.username or message.chat.title
        
        # Save to PostgreSQL using RETURNING for compatibility
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO posts 
                (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (message.message_id, title, description, file_url, tags_str, channel_name))
            
            new_id = cur.fetchone()['id']
            conn.commit()
            
            cur.execute("SELECT * FROM posts WHERE id = %s", (new_id,))
            new_post = cur.fetchone()
            
            cur.close()
            conn.close()
            
            print(f"✅ Post saved to database: {title[:50]}...")
            return new_post
        
    except Exception as e:
        print(f"❌ Error processing post: {e}")
        return None

# ========== Bot Manager ==========
class BotManager:
    def __init__(self):
        self.application = None
        self.is_running = False
    
    def start_bot(self):
        """Start Telegram bot in background thread"""
        if self.is_running:
            return
        
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN not set")
            return
        
        try:
            if not init_database():
                print("⚠️ Database initialization failed")
            
            self.application = Application.builder().token(token).build()
            self.application.add_handler(
                MessageHandler(filters.ChatType.CHANNEL, handle_channel_post)
            )
            
            self.is_running = True
            bot_thread = threading.Thread(target=self.run_bot, daemon=True)
            bot_thread.start()
            
            print("🤖 4UTODAY Bot started successfully")
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            self.is_running = False
    
def run_bot(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # close_loop=False နဲ့ stop_signals=False ထည့်ပေးရပါမယ်
            self.application.run_polling(close_loop=False, stop_signals=False)
        except Exception as e:
            print(f"❌ Bot polling error: {e}")
            self.is_running = False

# Global instance to ensure it starts regardless of how Flask is called
bot_manager = BotManager()
bot_manager.start_bot()

# ========== API Routes for Frontend ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY Telegram Bot API",
        "status": "running",
        "bot_status": "active" if bot_manager.is_running else "inactive"
    })

@app.route('/api/health')
def health_check():
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn: conn.close()
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/posts')
def get_posts():
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        tag_filter = request.args.get('tag', 'all')
        limit = int(request.args.get('limit', 50))
        
        if tag_filter != 'all':
            query = "SELECT * FROM posts WHERE tags LIKE %s ORDER BY created_at DESC LIMIT %s"
            params = [f'%{tag_filter}%', limit]
        else:
            query = "SELECT * FROM posts ORDER BY created_at DESC LIMIT %s"
            params = [limit]
        
        cur.execute(query, params)
        posts = cur.fetchall()
        
        for post in posts:
            if post['created_at']:
                post['created_at'] = post['created_at'].isoformat()
        
        cur.close()
        conn.close()
        return jsonify({"count": len(posts), "posts": posts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM posts")
        total = cur.fetchone()['total']
        
        cur.execute("SELECT tags, COUNT(*) as count FROM posts GROUP BY tags ORDER BY count DESC LIMIT 10")
        tags_stats = cur.fetchall()
        
        cur.execute("SELECT DATE(created_at) as date, COUNT(*) as count FROM posts GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 7")
        activity = cur.fetchall()
        
        # Convert date to string
        for act in activity:
            act['date'] = str(act['date'])
            
        cur.close()
        conn.close()
        return jsonify({"total_posts": total, "top_tags": tags_stats, "recent_activity": activity})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
