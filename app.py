# app.py - Main Flask Application
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
from datetime import datetime
import threading
import json

# Import our modules
from config import config
from database import db
from telegram_bot import telegram_bot, setup_webhook_sync, process_update_sync

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, 
     origins=config.CORS_ORIGINS,
     methods=config.CORS_METHODS,
     allow_headers=config.CORS_ALLOW_HEADERS)

# Global flag to track initialization
_initialized = False
_init_lock = threading.Lock()

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

# Middleware to ensure initialization
@app.before_request
def before_request_handler():
    """Ensure app is initialized before first request"""
    if not _initialized:
        initialize_app()

# ==================== API ENDPOINTS ====================

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

# ==================== CHANNEL POSTS API ====================

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

# ==================== WEBHOOK MANAGEMENT ====================

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

# ==================== DEBUG & ADMIN ENDPOINTS ====================

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

# ==================== STATIC FILES (for frontend) ====================

@app.route('/dashboard')
def dashboard():
    """Serve dashboard HTML"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>4UTODAY Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            h1 { color: #333; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 10px 0; border-radius: 5px; }
            .stat { font-size: 24px; font-weight: bold; color: #4CAF50; }
        </style>
    </head>
    <body>
        <h1>4UTODAY Dashboard</h1>
        <div class="card">
            <h3>API Endpoints:</h3>
            <ul>
                <li><a href="/health">Health Check</a></li>
                <li><a href="/api/channel/stats">Channel Stats</a></li>
                <li><a href="/api/channel/posts">Channel Posts</a></li>
                <li><a href="/api/debug">Debug Info</a></li>
                <li><a href="/api/setup-webhook">Setup Webhook</a></li>
                <li><a href="/api/webhook-info">Webhook Info</a></li>
            </ul>
        </div>
        <div class="card">
            <h3>Quick Stats:</h3>
            <div id="stats">Loading...</div>
        </div>
        <script>
            fetch('/api/channel/stats')
                .then(r => r.json())
                .then(data => {
                    if(data.status === 'success') {
                        document.getElementById('stats').innerHTML = `
                            <div>Total Posts: <span class="stat">${data.data.total_posts}</span></div>
                            <div>Latest Post: ${data.data.latest_post || 'N/A'}</div>
                        `;
                    }
                });
        </script>
    </body>
    </html>
    """

# ==================== APPLICATION SHUTDOWN ====================

@app.teardown_appcontext
def shutdown(exception=None):
    """Application shutdown cleanup"""
    if exception:
        logger.error(f"App shutdown with error: {exception}")
    
    # Database connection will be closed automatically when app exits

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
