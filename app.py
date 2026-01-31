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
CORS(app)  # Allow frontend requests

# ========== Database Functions ==========
def get_db_connection():
    """Connect to PostgreSQL database on Render"""
    try:
        conn = psycopg2.connect(
            os.environ['DATABASE_URL'],
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
        
        # Extract post data
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
            
            # Get the inserted post
            cur.execute("SELECT * FROM posts WHERE id = %s", (cur.lastrowid,))
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
            # Initialize database
            if not init_database():
                print("⚠️ Database initialization failed")
            
            # Create bot application
            self.application = Application.builder().token(token).build()
            
            # Add channel post handler
            self.application.add_handler(
                MessageHandler(filters.ChatType.CHANNEL, handle_channel_post)
            )
            
            # Start bot in background
            self.is_running = True
            bot_thread = threading.Thread(target=self.run_bot, daemon=True)
            bot_thread.start()
            
            print("🤖 4UTODAY Bot started successfully")
            print("📡 Listening for channel posts...")
            
        except Exception as e:
            print(f"❌ Failed to start bot: {e}")
            self.is_running = False
    
    def run_bot(self):
        """Run bot with polling"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.application.run_polling()
        except Exception as e:
            print(f"❌ Bot polling error: {e}")
            self.is_running = False

# Initialize bot manager
bot_manager = BotManager()

# ========== API Routes for Frontend ==========
@app.route('/')
def home():
    return jsonify({
        "service": "4UTODAY Telegram Bot API",
        "status": "running",
        "bot_status": "active" if bot_manager.is_running else "inactive",
        "endpoints": {
            "posts": "/api/posts",
            "health": "/api/health",
            "stats": "/api/stats"
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
        "bot_running": bot_manager.is_running,
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/posts')
def get_posts():
    """Get all posts for frontend"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        
        # Get filter parameters
        tag_filter = request.args.get('tag', 'all')
        limit = int(request.args.get('limit', 50))
        
        # Build query
        query = "SELECT * FROM posts ORDER BY created_at DESC LIMIT %s"
        params = [limit]
        
        if tag_filter != 'all':
            query = "SELECT * FROM posts WHERE tags LIKE %s ORDER BY created_at DESC LIMIT %s"
            params = [f'%{tag_filter}%', limit]
        
        cur.execute(query, params)
        posts = cur.fetchall()
        
        # Convert datetime to string for JSON
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
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get statistics for dashboard"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database unavailable"}), 500
        
        cur = conn.cursor()
        
        # Get total posts
        cur.execute("SELECT COUNT(*) as total FROM posts")
        total = cur.fetchone()['total']
        
        # Get posts by tag
        cur.execute("""
            SELECT tags, COUNT(*) as count 
            FROM posts 
            GROUP BY tags 
            ORDER BY count DESC 
            LIMIT 10
        """)
        tags_stats = cur.fetchall()
        
        # Get recent activity
        cur.execute("""
            SELECT DATE(created_at) as date, COUNT(*) as count
            FROM posts 
            GROUP BY DATE(created_at) 
            ORDER BY date DESC 
            LIMIT 7
        """)
        activity = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            "total_posts": total,
            "top_tags": tags_stats,
            "recent_activity": activity
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========== Application Startup ==========
if __name__ == '__main__':
    # Start bot automatically
    print("🚀 Starting 4UTODAY Telegram Bot...")
    bot_manager.start_bot()
    
    # Start Flask server
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
