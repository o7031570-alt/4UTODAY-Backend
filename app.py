# app.py - CORRECT ORDER

# ===== IMPORTS =====
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import logging
from datetime import datetime
import threading
import json

# Import our modules
from config import config
from database import db
from telegram_bot import telegram_bot, setup_webhook_sync, process_update_sync

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== FLASK APP INITIALIZATION =====
# အရင်ဆုံး app ကို create လုပ်ပါ
app = Flask(__name__)
CORS(app, 
     origins=config.CORS_ORIGINS,
     methods=config.CORS_METHODS,
     allow_headers=config.CORS_ALLOW_HEADERS)

# ===== GLOBAL VARIABLES =====
_initialized = False
_init_lock = threading.Lock()

# ===== HELPER FUNCTIONS =====
# ဒီနေရာမှာ helper functions တွေ define လုပ်ပါ
# ဒါပေမယ့် app.route() decorator မသုံးရသေးဘူး

def initialize_app():
    """Application initialization"""
    global _initialized
    
    with _init_lock:
        if _initialized:
            return
        
        logger.info("🚀 Starting 4UTODAY Bot...")
        
        # Configuration check
        logger.info("🔧 Configuration Check:")
        logger.info(f"   - TOKEN: {'✅ SET' if config.TOKEN else '❌ NOT SET'}")
        logger.info(f"   - DATABASE_URL: {'✅ SET' if config.DATABASE_URL else '❌ NOT SET'}")
        logger.info(f"   - RENDER_URL: {config.RENDER_URL}")
        logger.info(f"   - WEBHOOK_URL: {config.WEBHOOK_URL}")
        
        # Database check
        if db.conn:
            logger.info("✅ Database connected")
        else:
            logger.error("❌ Database connection failed")
        
        # Setup webhook in background thread if token exists
        if config.TOKEN:
            def setup_webhook_background():
                logger.info("🔄 Setting up webhook...")
                if setup_webhook_sync():
                    logger.info("✅ Webhook setup completed")
                else:
                    logger.error("❌ Webhook setup failed")
            
            # Start webhook setup in background
            webhook_thread = threading.Thread(target=setup_webhook_background, daemon=True)
            webhook_thread.start()
        else:
            logger.warning("⚠️ TOKEN not set, skipping webhook setup")
        
        logger.info("✅ Application initialized")
        _initialized = True

def process_channel_post(channel_post):
    """Process channel post data"""
    try:
        post_id = channel_post.get('message_id')
        chat = channel_post.get('chat', {})
        channel_id = chat.get('id')
        
        # Determine message type
        message_type = 'unknown'
        content = ''
        caption = ''
        media_url = None
        file_id = None
        file_size = None
        width = None
        height = None
        
        if 'text' in channel_post:
            content = channel_post['text']
            message_type = 'text'
        elif 'caption' in channel_post:
            caption = channel_post['caption']
            message_type = 'photo'
            content = caption
        
        if 'photo' in channel_post:
            # Get the best quality photo (last one is highest quality)
            photos = channel_post['photo']
            if photos:
                best_photo = photos[-1]
                file_id = best_photo.get('file_id')
                file_size = best_photo.get('file_size')
                width = best_photo.get('width')
                height = best_photo.get('height')
                message_type = 'photo'
        
        elif 'document' in channel_post:
            document = channel_post['document']
            file_id = document.get('file_id')
            file_size = document.get('file_size')
            message_type = 'document'
        
        elif 'video' in channel_post:
            video = channel_post['video']
            file_id = video.get('file_id')
            file_size = video.get('file_size')
            width = video.get('width')
            height = video.get('height')
            message_type = 'video'
        
        return {
            'message_id': post_id,
            'channel_id': channel_id,
            'message_type': message_type,
            'content': content,
            'caption': caption,
            'media_url': media_url,
            'file_id': file_id,
            'file_size': file_size,
            'width': width,
            'height': height,
            'date': channel_post.get('date')
        }
    except Exception as e:
        logger.error(f"❌ Process channel post error: {e}")
        return None

# ===== MIDDLEWARE =====
@app.before_request
def before_request_handler():
    """Ensure app is initialized before first request"""
    if not _initialized:
        initialize_app()

# ===== ROUTES START HERE =====
# ဒီနေရာကနေ စပြီး app.route() decorator သုံးလို့ရပါပြီ

@app.route('/')
def home():
    """Root endpoint - health check"""
    return jsonify({
        "status": "online",
        "service": "4UTODAY Bot API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "webhook": config.WEBHOOK_PATH,
            "channel_posts": "/api/channel/posts",
            "channel_stats": "/api/channel/stats",
            "frontend_posts": "/api/posts",
            "frontend_stats": "/api/stats",
            "setup_webhook": "/api/setup-webhook"
        }
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Database health check
        with db.conn.cursor() as cur:
            cur.execute("SELECT 1")
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "token_set": bool(config.TOKEN),
            "timestamp": datetime.now().isoformat()
        }), 200
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }), 500

@app.route(config.WEBHOOK_PATH, methods=['POST'])
def telegram_webhook():
    """Telegram webhook endpoint"""
    try:
        data = request.get_json()
        logger.info(f"📩 Webhook received")
        
        # Process channel posts
        if 'channel_post' in data:
            channel_post = data['channel_post']
            post_data = process_channel_post(channel_post)
            
            if post_data:
                db.save_channel_post(post_data)
                logger.info(f"✅ Channel post saved: {post_data.get('message_id')}")
        
        # Process user messages (async)
        if 'message' in data or 'edited_message' in data:
            # Process in background thread
            threading.Thread(
                target=process_update_sync,
                args=(data,),
                daemon=True
            ).start()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== CHANNEL POSTS API =====
@app.route('/api/channel/posts', methods=['GET'])
def get_channel_posts():
    """Get all channel posts for frontend"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        offset = (page - 1) * limit
        
        posts = db.get_channel_posts(limit=limit, offset=offset)
        total = db.get_post_count()
        
        return jsonify({
            "status": "success",
            "data": {
                "posts": posts,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "pages": (total + limit - 1) // limit if limit > 0 else 0
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"Get channel posts error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/channel/posts/<int:post_id>', methods=['GET'])
def get_channel_post(post_id):
    """Get single channel post"""
    try:
        post = db.get_channel_post_by_id(post_id)
        
        if post:
            return jsonify({"status": "success", "data": post}), 200
        else:
            return jsonify({"status": "error", "message": "Post not found"}), 404
    except Exception as e:
        logger.error(f"Get channel post error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/channel/stats', methods=['GET'])
def get_channel_stats():
    """Get channel statistics"""
    try:
        stats = db.get_stats()
        
        return jsonify({
            "status": "success",
            "data": {
                "total_posts": stats['total_posts'],
                "type_counts": stats['type_counts'],
                "latest_post": stats['latest_post'].isoformat() if stats['latest_post'] else None
            }
        }), 200
    except Exception as e:
        logger.error(f"Get channel stats error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== FRONTEND API ENDPOINTS =====
# မင်း frontend အတွက် endpoints တွေ
@app.route('/api/posts', methods=['GET'])
def get_posts_for_frontend():
    """Frontend အတွက် posts endpoint"""
    try:
        limit = request.args.get('limit', 50, type=int)
        tag = request.args.get('tag', None)
        
        # Channel posts ကို ယူမယ်
        posts = db.get_channel_posts(limit=limit, offset=0)
        
        # Frontend နဲ့ ကိုက်ညီအောင် format ပြောင်းမယ်
        formatted_posts = []
        for post in posts:
            # Title အတွက် content ကို သုံးမယ်
            content = post.get('content', '') or post.get('caption', '')
            title = content[:100] + '...' if len(content) > 100 else content or 'No title'
            
            # Tags ကို message_type ကနေ ယူမယ်
            tags = post.get('message_type', 'telegram')
            
            formatted_post = {
                'id': post.get('id'),
                'telegram_message_id': post.get('post_id'),
                'post_title': title,
                'post_description': content or 'No description available',
                'tags': tags,
                'file_url': post.get('media_url'),
                'created_at': post.get('date').isoformat() if post.get('date') else datetime.now().isoformat()
            }
            formatted_posts.append(formatted_post)
        
        return jsonify({
            "posts": formatted_posts
        }), 200
    except Exception as e:
        logger.error(f"Get posts for frontend error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats_for_frontend():
    """Frontend အတွက် stats endpoint"""
    try:
        stats = db.get_stats()
        
        # Frontend နဲ့ ကိုက်ညီအောင် format ပြောင်းမယ်
        return jsonify({
            "total_posts": stats['total_posts'],
            "total_tags": len(stats['type_counts']),  # Message type ကိုပဲ tag အဖြစ် သုံးမယ်
            "today_posts": 0  # ဒီ feature ကို နောက်မှ ထည့်မယ်
        }), 200
    except Exception as e:
        logger.error(f"Get stats for frontend error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/test', methods=['GET'])
def test_frontend_connection():
    """Frontend နဲ့ connection test"""
    return jsonify({
        "status": "success",
        "message": "Backend is connected and working",
        "endpoints": {
            "posts": "/api/posts",
            "stats": "/api/stats",
            "channel_posts": "/api/channel/posts",
            "channel_stats": "/api/channel/stats"
        }
    }), 200

# ===== WEBHOOK MANAGEMENT =====
@app.route('/api/setup-webhook', methods=['GET'])
def setup_webhook_manual():
    """Manual webhook setup endpoint"""
    import requests
    
    if not config.TOKEN:
        return jsonify({"status": "error", "message": "TOKEN not set in environment"}), 400
    
    try:
        # Delete old webhook
        delete_response = requests.get(
            f"https://api.telegram.org/bot{config.TOKEN}/deleteWebhook",
            timeout=10
        )
        
        # Set new webhook
        set_response = requests.get(
            f"https://api.telegram.org/bot{config.TOKEN}/setWebhook?url={config.WEBHOOK_URL}",
            timeout=10
        )
        
        return jsonify({
            "status": "success",
            "delete_response": delete_response.json(),
            "set_response": set_response.json(),
            "webhook_url": config.WEBHOOK_URL
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/webhook-info', methods=['GET'])
def get_webhook_info():
    """Get webhook information from Telegram"""
    import requests
    
    if not config.TOKEN:
        return jsonify({"status": "error", "message": "TOKEN not set in environment"}), 400
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{config.TOKEN}/getWebhookInfo",
            timeout=10
        )
        
        return jsonify({
            "status": "success",
            "data": response.json()
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== DEBUG & ADMIN ENDPOINTS =====
@app.route('/api/debug', methods=['GET'])
def debug_info():
    """Debug information endpoint"""
    import socket
    
    return jsonify({
        "status": "success",
        "data": {
            "hostname": socket.gethostname(),
            "initialized": _initialized,
            "token_set": bool(config.TOKEN),
            "token_length": len(config.TOKEN) if config.TOKEN else 0,
            "database_connected": db.conn is not None,
            "webhook_url": config.WEBHOOK_URL,
            "environment": "production"
        }
    }), 200

@app.route('/api/test-db', methods=['GET'])
def test_db():
    """Test database connection"""
    try:
        with db.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM channel_posts")
            count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as count FROM posts")
            posts_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as count FROM users")
            users_count = cur.fetchone()[0]
        
        return jsonify({
            "status": "success",
            "data": {
                "channel_posts": count,
                "posts": posts_count,
                "users": users_count,
                "database": "working"
            }
        }), 200
    except Exception as e:
        logger.error(f"Test DB error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== FRONTEND DASHBOARD =====
@app.route('/frontend')
def serve_frontend():
    """Serve the frontend HTML"""
    # မင်း frontend HTML ကို ဒီမှာ ကူးထည့်ပါ
    # ဒါမှမဟုတ် သပ်သပ် file လုပ်ပြီး ဖတ်ပါ
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>4UTODAY - Telegram Content Hub</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
        <style>
            /* မင်း CSS ကို ဒီမှာ paste လုပ်ပါ */
            :root {
                --primary: #4361ee;
                /* ... ဆက်ရေးပါ ... */
            }
        </style>
    </head>
    <body>
        <!-- မင်း HTML body ကို ဒီမှာ paste လုပ်ပါ -->
        <header class="main-header">
            <!-- ... rest of your HTML ... -->
        </header>
        
        <script>
            // မင်း JavaScript ကို ဒီမှာ paste လုပ်ပါ
            // ဒီမှာ API_BASE_URL ကို ပြင်ရမယ်
            const API_BASE_URL = "https://fourutoday.onrender.com";
            // ... rest of your JavaScript ...
        </script>
    </body>
    </html>
    """
    return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}

# ===== APPLICATION SHUTDOWN =====
@app.teardown_appcontext
def shutdown(exception=None):
    """Application shutdown cleanup"""
    if exception:
        logger.error(f"App shutdown with error: {exception}")
    
    # Database connection will be closed automatically when app exits

# ===== INITIALIZE APP =====
# Initialize app on import (for gunicorn)
initialize_app()

if __name__ == '__main__':
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False
)
