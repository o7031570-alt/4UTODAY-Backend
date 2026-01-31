# app.py - 4UTODAY Telegram Bot (Stable Sync Webhook Version)
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
CORS(app)  # Enable CORS for all routes

# ========== Environment Variables ==========
TOKEN = os.environ.get('8537979478:AAEaj5NWtKyGQoKNkcl_X6qMOX1JMr6RJvc')
DATABASE_URL = os.environ.get('postgresql://telegram_bot_db_zhdg_user:y7FwDpfpcJvBwG3b7MJaaRmCZf5vMkOB@dpg-d5upqp14tr6s7396psdg-a/telegram_bot_db_zhdg')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://fourutoday.onrender.com')

# Validate critical environment variables
if not TOKEN:
    print("❌ CRITICAL: TELEGRAM_BOT_TOKEN environment variable is not set!")
if not DATABASE_URL:
    print("❌ CRITICAL: DATABASE_URL environment variable is not set!")

# Webhook configuration
WEBHOOK_PATH = f"/tg-hook-{TOKEN[:8]}" if TOKEN else "/tg-hook-default"
WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"

print(f"🔧 Configuration loaded:")
print(f"   - Webhook URL: {WEBHOOK_URL}")
print(f"   - Database: {'✅ Connected' if DATABASE_URL else '❌ Missing'}")

# ========== Database Functions (Psycopg 3) ==========
def get_db_connection():
    """Create and return a database connection"""
    if not DATABASE_URL:
        print("❌ DATABASE_URL is missing")
        return None
    
    try:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def init_database():
    """Initialize database tables"""
    print("🔄 Initializing database...")
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to initialize database: No connection")
        return False
    
    try:
        with conn.cursor() as cur:
            # Create posts table if not exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    telegram_message_id BIGINT,
                    post_title TEXT NOT NULL,
                    post_description TEXT,
                    file_url TEXT,
                    tags TEXT,
                    channel_username VARCHAR(255),
                    UNIQUE(telegram_message_id)  -- Prevent duplicate posts
                )
            """)
            conn.commit()
            print("✅ Database table 'posts' is ready")
        
        # Create index for better performance
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_telegram_message_id ON posts(telegram_message_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON posts(created_at DESC)")
            conn.commit()
        
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

# ========== SYNC Webhook Handler ==========
@app.route(WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    """
    Main webhook handler - receives POST requests from Telegram
    NOTE: This is a SYNC function (no async/await)
    """
    try:
        # Parse incoming JSON data
        data = request.get_json(force=True)
        print(f"📥 Webhook received: {data.get('update_id')}")
        
        # Create bot instance and process update
        bot = Bot(TOKEN) if TOKEN else None
        if not bot:
            print("❌ Bot token not available")
            return "Bot Error", 500
        
        update = Update.de_json(data, bot)
        
        # Process channel posts only
        if update and update.channel_post:
            print(f"📝 Processing channel post: {update.channel_post.message_id}")
            process_post(update.channel_post, bot)
            return "OK", 200
        else:
            print("ℹ️ No channel post in update")
            return "OK", 200
            
    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        return "Error", 500

def process_post(message, bot):
    """
    Process and save a Telegram post to database
    NOTE: This is a SYNC function (no async/await)
    """
    try:
        # Extract post content
        text = message.caption or message.text or ""
        title = text[:150] + "..." if len(text) > 150 else text
        if not title:
            title = "Media Post"
        
        # Extract file URL if available
        file_url = ""
        try:
            if message.photo:
                file = bot.get_file(message.photo[-1].file_id)
                file_url = file.file_path
            elif message.video:
                file = bot.get_file(message.video.file_id)
                file_url = file.file_path
            elif message.document:
                file = bot.get_file(message.document.file_id)
                file_url = file.file_path
        except Exception as file_error:
            print(f"⚠️ File processing error: {file_error}")
        
        # Extract hashtags
        tags = [word for word in text.split() if word.startswith("#")]
        tags_str = ", ".join(tags) if tags else "general"
        
        # Get channel info
        channel_name = message.chat.title or message.chat.username or "Unknown Channel"
        
        # Save to database
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Insert post (ON CONFLICT DO NOTHING prevents duplicates)
                    cur.execute("""
                        INSERT INTO posts 
                        (telegram_message_id, post_title, post_description, file_url, tags, channel_username)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (telegram_message_id) DO NOTHING
                    """, (message.message_id, title, text, file_url, tags_str, channel_name))
                    conn.commit()
                    
                    # Check if row was inserted
                    if cur.rowcount > 0:
                        print(f"✅ Saved Post: {title[:50]}")
                    else:
                        print(f"ℹ️ Post already exists: {message.message_id}")
            finally:
                conn.close()
        else:
            print("❌ Failed to save post: No database connection")
            
    except Exception as e:
        print(f"❌ Post processing error: {e}")

# ========== Webhook Setup in Background Thread ==========
def setup_webhook_in_background():
    """Set up webhook in a background thread to avoid blocking"""
    print("🔄 Starting webhook setup in background...")
    
    def background_webhook_setup():
        """Background function to set webhook"""
        # Small delay to ensure Flask is ready
        time.sleep(3)
        
        if not TOKEN or not WEBHOOK_URL:
            print("⚠️ Skipping webhook setup: Token or URL missing")
            return
        
        try:
            bot = Bot(TOKEN)
            print(f"🔄 Deleting old webhook...")
            bot.delete_webhook(drop_pending_updates=True)
            time.sleep(1)  # Short delay
            
            print(f"🔄 Setting new webhook to: {WEBHOOK_URL}")
            success = bot.set_webhook(url=WEBHOOK_URL)
            
            if success:
                print(f"✅ Webhook successfully set to: {WEBHOOK_URL}")
            else:
                print(f"❌ Failed to set webhook")
                
        except Exception as e:
            print(f"❌ Webhook setup failed: {e}")
    
    # Start the background thread
    thread = threading.Thread(target=background_webhook_setup)
    thread.daemon = True  # Thread will exit when main program exits
    thread.start()

# ========== API Endpoints ==========
@app.route('/')
def home():
    """Root endpoint - shows API information"""
    return jsonify({
        "service": "4UTODAY Telegram Bot API",
        "status": "online",
        "version": "2.0",
        "endpoints": {
            "posts": "/api/posts",
            "stats": "/api/stats",
            "health": "/api/health"
        },
        "webhook_configured": bool(TOKEN and WEBHOOK_URL),
        "webhook_url": WEBHOOK_URL,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    db_status = "healthy" if get_db_connection() else "unhealthy"
    return jsonify({
        "status": "running",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/posts')
def get_all_posts():
    """Get all posts from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, post_title, post_description, 
                       file_url, tags, channel_username
                FROM posts 
                ORDER BY created_at DESC 
                LIMIT 100
            """)
            posts = cur.fetchall()
            
            # Convert datetime objects to ISO format strings
            for post in posts:
                if post.get('created_at'):
                    post['created_at'] = post['created_at'].isoformat()
        
        conn.close()
        return jsonify(posts)
        
    except Exception as e:
        print(f"❌ API Error in /api/posts: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/posts/latest')
def get_latest_posts():
    """Get latest 10 posts"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, created_at, post_title, post_description, 
                       file_url, tags, channel_username
                FROM posts 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            posts = cur.fetchall()
            
            for post in posts:
                if post.get('created_at'):
                    post['created_at'] = post['created_at'].isoformat()
        
        conn.close()
        return jsonify(posts)
        
    except Exception as e:
        print(f"❌ API Error in /api/posts/latest: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats')
def get_statistics():
    """Get statistics about posts"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        with conn.cursor() as cur:
            # Total posts count
            cur.execute("SELECT COUNT(*) as total_posts FROM posts")
            total = cur.fetchone()['total_posts']
            
            # Posts per channel
            cur.execute("""
                SELECT channel_username, COUNT(*) as count 
                FROM posts 
                GROUP BY channel_username 
                ORDER BY count DESC
            """)
            channels = cur.fetchall()
            
            # Top tags
            cur.execute("""
                SELECT tags, COUNT(*) as count 
                FROM posts 
                WHERE tags != 'general' 
                GROUP BY tags 
                ORDER BY count DESC 
                LIMIT 10
            """)
            tags = cur.fetchall()
            
            # Latest post date
            cur.execute("SELECT MAX(created_at) as latest_post FROM posts")
            latest = cur.fetchone()['latest_post']
        
        conn.close()
        
        return jsonify({
            "total_posts": total,
            "channels": channels,
            "top_tags": tags,
            "latest_post": latest.isoformat() if latest else None,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ API Error in /api/stats: {e}")
        return jsonify({"error": str(e)}), 500

# ========== Application Startup ==========
def startup_sequence():
    """Run startup initialization"""
    print("🚀 Starting 4UTODAY Bot Application...")
    
    # Step 1: Initialize database
    if init_database():
        print("✅ Database initialization complete")
    else:
        print("⚠️ Database initialization had issues")
    
    # Step 2: Setup webhook in background
    setup_webhook_in_background()
    
    print("✅ Startup sequence completed")

# Run startup sequence when module loads
startup_sequence()

# ========== Main Entry Point ==========
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
