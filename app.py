# app.py - 4UTODAY Telegram Bot with PostgreSQL & WEBHOOK
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackContext
import hmac
import hashlib
import google.auth
from google.oauth2.service_account import Credentials

# ========== Flask & Config Setup ==========
app = Flask(__name__)
CORS(app)

# Load configuration from environment
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(32).hex())
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', TELEGRAM_BOT_TOKEN)  # Optional extra security

# ========== Database Functions ==========
def get_db_connection():
    """Connect to PostgreSQL database on Render"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        app.logger.error(f"❌ Database connection failed: {e}")
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
        app.logger.info("✅ Database table ready")
        return True
    except Exception as e:
        app.logger.error(f"❌ Database init error: {e}")
        return False

# ========== Telegram Bot Handler ==========
async def handle_channel_post(update: Update, context: CallbackContext):
    """Process new posts from Telegram channel (WEBHOOK VERSION)"""
    try:
        message = update.channel_post
        if not message:
            return
        
        app.logger.info(f"📨 New post from channel: {message.chat.title}")
        
        # Extract post data (same as before)
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
        
        # Get file URL if available
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
        
        # Extract hashtags
        tags = []
        text_source = message.caption or message.text or ""
        for word in text_source.split():
            if word.startswith("#"):
                tags.append(word)
        
        tags_str = ", ".join(tags) if tags else "general"
        channel_name = message.chat.username or message.chat.title
        
        # Save to PostgreSQL
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO posts 
                (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (message.message_id, title, description, file_url, tags_str, channel_name))
            conn.commit()
            cur.close()
            conn.close()
            
            app.logger.info(f"✅ Post saved to database: {title[:50]}...")
        else:
            app.logger.error("❌ Failed to save post: Database unavailable")
            
    except Exception as e:
        app.logger.error(f"❌ Error processing post: {e}")

# ========== Webhook Security ==========
def verify_telegram_webhook(data, telegram_token):
    """Verify the webhook request is actually from Telegram"""
    try:
        secret_key = hashlib.sha256(telegram_token.encode()).digest()
        received_hash = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        
        if not received_hash:
            app.logger.warning("⚠️ No secret token in headers")
            return False
            
        expected_hash = hmac.new(secret_key, data, hashlib.sha256).hexdigest()
        return hmac.compare_digest(received_hash, expected_hash)
    except Exception as e:
        app.logger.error(f"❌ Webhook verification error: {e}")
        return False

# ========== Flask Routes (WEBHOOK) ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY Telegram Bot API (Webhook)",
        "status": "running",
        "webhook_set": TELEGRAM_BOT_TOKEN is not None,
        "endpoints": {
            "webhook": "/webhook",
            "posts": "/api/posts",
            "health": "/api/health",
            "set_webhook": "/set-webhook/<secret_key>"
        }
    })

@app.route('/api/health')
def health_check():
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return jsonify({
        "status": "healthy",
        "database": db_status,
        "webhook_ready": TELEGRAM_BOT_TOKEN is not None,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/posts')
def get_posts():
    """Get all posts for frontend (same as before)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        tag_filter = request.args.get('tag', 'all')
        limit = int(request.args.get('limit', 50))
        
        query = "SELECT * FROM posts ORDER BY created_at DESC LIMIT %s"
        params = [limit]
        
        if tag_filter != 'all':
            query = "SELECT * FROM posts WHERE tags LIKE %s ORDER BY created_at DESC LIMIT %s"
            params = [f'%{tag_filter}%', limit]
        
        cur.execute(query, params)
        posts = cur.fetchall()
        
        for post in posts:
            if post['created_at']:
                post['created_at'] = post['created_at'].isoformat()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "count": len(posts),
            "posts": posts
        })
        
    except Exception as e:
        app.logger.error(f"❌ Error fetching posts: {e}")
        return jsonify({"error": str(e)}), 500

# ====== WEBHOOK ENDPOINT ======
@app.route('/webhook', methods=['POST'])
async def telegram_webhook():
    """Main webhook endpoint for Telegram updates"""
    # 1. Verify request is from Telegram (optional but recommended)
    if not verify_telegram_webhook(request.get_data(), TELEGRAM_BOT_TOKEN):
        app.logger.warning("⚠️ Unverified webhook request received")
        return jsonify({"status": "unauthorized"}), 401
    
    # 2. Process the update
    try:
        update_data = request.get_json()
        if not update_data:
            return jsonify({"status": "no data"}), 400
        
        # Create Update object from Telegram's data
        update = Update.de_json(update_data, Bot(TELEGRAM_BOT_TOKEN))
        
        # Create minimal context for handler
        class SimpleContext:
            def __init__(self, bot):
                self.bot = bot
        
        context = SimpleContext(Bot(TELEGRAM_BOT_TOKEN))
        
        # Process the update
        await handle_channel_post(update, context)
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        app.logger.error(f"❌ Webhook processing error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/set-webhook/<secret_key>')
def set_webhook(secret_key):
    """Endpoint to programmatically set webhook on Telegram"""
    if secret_key != WEBHOOK_SECRET:
        return jsonify({"error": "Invalid secret key"}), 401
    
    if not TELEGRAM_BOT_TOKEN:
        return jsonify({"error": "Bot token not configured"}), 500
    
    try:
        bot = Bot(TELEGRAM_BOT_TOKEN)
        webhook_url = f"https://{request.host}/webhook"
        
        # Set webhook on Telegram
        result = bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=["channel_post"]
        )
        
        return jsonify({
            "status": "success",
            "webhook_url": webhook_url,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== Application Startup ==========
if __name__ == '__main__':
    # Initialize database on startup
    print("🚀 Starting 4UTODAY Telegram Bot (Webhook Version)...")
    init_database()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
