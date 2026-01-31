# app.py - 4UTODAY Telegram Bot (Polling Version - Stable for Free Tier)
from flask import Flask, jsonify
from flask_cors import CORS
import os
import psycopg
from psycopg.rows import dict_row
from telegram import Bot
from datetime import datetime, timedelta
import requests  # For making HTTP requests to Telegram API

# ========== Flask App Setup ==========
app = Flask(__name__)
CORS(app)

# Environment Variables
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
CHANNEL_USERNAME = os.environ.get('CHANNEL_USERNAME', '@your_channel_username')  # Your channel username

# ========== Database Functions (Psycopg 3 Version) ==========
def get_db_connection():
    try:
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            print("❌ DATABASE_URL is missing")
            return None
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
                    telegram_message_id BIGINT UNIQUE,  -- ADD UNIQUE constraint
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

# ========== Polling Logic ==========
def check_new_posts():
    """
    This function should be called periodically (e.g., every 5-10 minutes)
    via Render Cron Job or another scheduler.
    """
    if not TOKEN or not CHANNEL_USERNAME:
        print("⚠️ Token or Channel username missing. Skipping check.")
        return {"status": "error", "message": "Missing credentials"}

    bot = Bot(TOKEN)
    try:
        # 1. Get the last saved message ID from database
        last_message_id = None
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(telegram_message_id) as last_id FROM posts")
                result = cur.fetchone()
                last_message_id = result['last_id'] if result['last_id'] else 0
            conn.close()

        # 2. Fetch recent posts from channel (last 20 messages)
        # Using Telegram Bot API directly via python-telegram-bot
        from telegram.constants import ParseMode
        updates = bot.get_updates(offset=last_message_id + 1, timeout=10)
        
        new_posts_count = 0
        for update in updates:
            if update.channel_post and update.channel_post.chat.username == CHANNEL_USERNAME.lstrip('@'):
                message = update.channel_post
                
                # Check if already exists in DB
                conn = get_db_connection()
                if conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM posts WHERE telegram_message_id = %s", (message.message_id,))
                        exists = cur.fetchone()
                        
                        if not exists:
                            # Process and save the post
                            text = message.caption or message.text or ""
                            title = text[:150] + "..." if len(text) > 150 else (text or "Media Post")
                            
                            file_url = ""
                            if message.photo:
                                file = bot.get_file(message.photo[-1].file_id)
                                file_url = file.file_path
                            elif message.video:
                                file = bot.get_file(message.video.file_id)
                                file_url = file.file_path

                            tags = [word for word in text.split() if word.startswith("#")]
                            tags_str = ", ".join(tags) if tags else "general"
                            
                            cur.execute("""
                                INSERT INTO posts 
                                (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                                VALUES (%s, %s, %s, %s, %s, %s)
                            """, (message.message_id, title, text, file_url, tags_str, CHANNEL_USERNAME))
                            conn.commit()
                            new_posts_count += 1
                            print(f"✅ Saved new post: {title[:30]}")
                    conn.close()

        print(f"🔍 Polling complete. Found {new_posts_count} new posts.")
        return {"status": "success", "new_posts": new_posts_count}

    except Exception as e:
        print(f"❌ Polling error: {e}")
        return {"status": "error", "message": str(e)}

# ========== API Endpoints ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY API (Polling Mode)",
        "status": "online",
        "polling_endpoint": "/api/check-posts",
        "note": "Use Render Cron Job to schedule /api/check-posts"
    })

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

# 👇 This endpoint can be called manually or by Render Cron Job
@app.route('/api/check-posts')
def trigger_check():
    result = check_new_posts()
    return jsonify(result)

# Initialize database on startup
init_database()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
