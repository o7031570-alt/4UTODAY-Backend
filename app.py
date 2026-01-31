# app.py - 4UTODAY Telegram Bot with PostgreSQL (Webhook Version)
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
# Render URL (automatically uses your app name)
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL') or f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"
WEBHOOK_PATH = f"/telegram-webhook/{TOKEN[:10]}" # Security identifier
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

# ========== Database Functions (မူရင်းအတိုင်း) ==========
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

# ========== Webhook Logic (Polling အစားထိုးခြင်း) ==========
@app.route(WEBHOOK_PATH, methods=['POST'])
async def telegram_webhook():
    """Telegram ကနေ စာအသစ်ဝင်လာတိုင်း ဒီကို ရောက်မှာပါ"""
    try:
        update = Update.de_json(request.get_json(force=True), Bot(TOKEN))
        if update.channel_post:
            await process_post(update.channel_post)
        return "OK", 200
    except Exception as e:
        print(f"❌ Webhook Error: {e}")
        return "Error", 500

async def process_post(message):
    """မူရင်း handle_channel_post ထဲက logic များအားလုံး"""
    try:
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
        
        # File URL logic
        file_url = ""
        bot = Bot(TOKEN)
        if message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            file_url = file.file_path
        elif message.video:
            file = await bot.get_file(message.video.file_id)
            file_url = file.file_path
        elif message.document:
            file = await bot.get_file(message.document.file_id)
            file_url = file.file_path
        
        # Tags logic
        tags = [word for word in (description or "").split() if word.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        channel_name = message.chat.username or message.chat.title
        
        # Database Insert (RETURNING id fix အပါအဝင်)
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO posts 
                (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (message.message_id, title, description, file_url, tags_str, channel_name))
            conn.commit()
            cur.close()
            conn.close()
            print(f"✅ Webhook Saved: {title[:50]}...")
    except Exception as e:
        print(f"❌ Post processing error: {e}")

# Webhook Setup on Startup
@app.before_first_request
def setup():
    init_database()
    async def set_webhook():
        bot = Bot(TOKEN)
        await bot.set_webhook(url=WEBHOOK_URL)
        print(f"🌐 Webhook linked to: {WEBHOOK_URL}")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    if loop.is_running():
        loop.create_task(set_webhook())
    else:
        loop.run_until_complete(set_webhook())

# ========== API Routes (မူရင်းအတိုင်း အားလုံးပါတယ်) ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY API",
        "status": "active",
        "mode": "webhook"
    })

@app.route('/api/health')
def health():
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn: conn.close()
    return jsonify({"status": "healthy", "database": db_status, "time": datetime.now().isoformat()})

@app.route('/api/posts')
def get_posts():
    try:
        conn = get_db_connection()
        if not conn: return jsonify({"error": "DB offline"}), 500
        cur = conn.cursor()
        tag_filter = request.args.get('tag', 'all')
        limit = int(request.args.get('limit', 50))
        
        if tag_filter != 'all':
            cur.execute("SELECT * FROM posts WHERE tags LIKE %s ORDER BY created_at DESC LIMIT %s", (f'%{tag_filter}%', limit))
        else:
            cur.execute("SELECT * FROM posts ORDER BY created_at DESC LIMIT %s", (limit,))
        
        posts = cur.fetchall()
        for p in posts: p['created_at'] = p['created_at'].isoformat()
        cur.close()
        conn.close()
        return jsonify({"count": len(posts), "posts": posts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as total FROM posts")
        total = cur.fetchone()['total']
        cur.execute("SELECT tags, COUNT(*) as count FROM posts GROUP BY tags ORDER BY count DESC LIMIT 10")
        tags_stats = cur.fetchall()
        cur.execute("SELECT DATE(created_at) as date, COUNT(*) as count FROM posts GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 7")
        activity = cur.fetchall()
        for a in activity: a['date'] = str(a['date'])
        cur.close()
        conn.close()
        return jsonify({"total_posts": total, "top_tags": tags_stats, "recent_activity": activity})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
