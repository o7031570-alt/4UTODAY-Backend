# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from datetime import datetime
import threading

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
CORS(app)

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
        logger.info(f"   - TOKEN: {'✅ Set' if config.TOKEN else '❌ Missing'}")
        logger.info(f"   - DATABASE_URL: {'✅ Set' if config.DATABASE_URL else '❌ Missing'}")
        logger.info(f"   - RENDER_URL: {config.RENDER_URL}")
        logger.info(f"   - WEBHOOK_URL: {config.WEBHOOK_URL}")
        
        # Database check
        if db.conn:
            logger.info("✅ Database connected")
        else:
            logger.error("❌ Database connection failed")
        
        # Setup webhook in background thread
        def setup_webhook_background():
            logger.info("🔄 Setting up webhook...")
            if setup_webhook_sync():
                logger.info("✅ Webhook setup completed")
            else:
                logger.error("❌ Webhook setup failed")
        
        # Start webhook setup in background
        webhook_thread = threading.Thread(target=setup_webhook_background, daemon=True)
        webhook_thread.start()
        
        logger.info("✅ Application initialized")
        _initialized = True

@app.before_request
def before_request_handler():
    """Ensure app is initialized before first request"""
    if not _initialized:
        initialize_app()

@app.route('/')
def home():
    """Root endpoint - health check"""
    return jsonify({
        "status": "online",
        "service": "4UTODAY Bot API",
        "version": "1.0.0",
        "webhook": config.WEBHOOK_URL,
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "webhook": config.WEBHOOK_PATH,
            "posts": "/api/posts",
            "stats": "/api/stats"
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
        update_data = request.get_json()
        logger.info(f"📩 Webhook received")
        
        # Process the update synchronously
        process_update_sync(update_data)
        
        # Log to database
        db.add_log("INFO", "Webhook processed", "telegram_webhook")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        db.add_log("ERROR", f"Webhook error: {e}", "telegram_webhook")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Get all posts from database"""
    try:
        limit = request.args.get('limit', 100, type=int)
        posts = db.get_all_posts(limit=limit)
        
        return jsonify({
            "status": "success",
            "count": len(posts),
            "posts": posts
        }), 200
    except Exception as e:
        logger.error(f"Get posts error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """Get a specific post"""
    try:
        post = db.get_post(post_id)
        if post:
            return jsonify({"status": "success", "post": post}), 200
        else:
            return jsonify({"status": "error", "message": "Post not found"}), 404
    except Exception as e:
        logger.error(f"Get post error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get system statistics"""
    try:
        with db.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total_posts FROM posts")
            post_count = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) as total_users FROM users")
            user_count = cur.fetchone()[0]
            
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN level = 'ERROR' THEN 1 END) as error_logs,
                    COUNT(CASE WHEN level = 'INFO' THEN 1 END) as info_logs
                FROM logs
            """)
            log_counts = cur.fetchone()
        
        return jsonify({
            "status": "success",
            "stats": {
                "posts": post_count,
                "users": user_count,
                "logs": {
                    "errors": log_counts[0],
                    "info": log_counts[1]
                },
                "webhook": config.WEBHOOK_URL,
                "server": config.RENDER_URL
            }
        }), 200
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Initialize on import (for gunicorn)
initialize_app()

if __name__ == '__main__':
    # Start Flask app
    app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG,
        use_reloader=False
    )
