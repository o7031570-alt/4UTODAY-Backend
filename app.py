# app.py - Updated with Frontend Serving
from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import logging
from datetime import datetime
import os

# ===== LOGGING SETUP =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== FLASK APP INITIALIZATION =====
app = Flask(__name__, 
           static_folder='static',
           template_folder='templates')
CORS(app, resources={r"/*": {"origins": "*"}})

# ===== CONFIGURATION =====
TOKEN = os.environ.get('TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://fourutoday.onrender.com')
WEBHOOK_URL = f"{RENDER_URL}/tg-hook-85379794"

logger.info(f"🚀 Initializing 4UTODAY Bot...")

# ===== SIMPLE STORAGE =====
# We'll use in-memory storage for now
posts_storage = []
channel_posts_storage = []

# ===== HELPER FUNCTIONS =====
def add_channel_post(post_data):
    """Add a channel post to storage"""
    channel_posts_storage.append({
        'id': len(channel_posts_storage) + 1,
        **post_data,
        'created_at': datetime.now().isoformat()
    })
    logger.info(f"✅ Added channel post: {post_data.get('message_id')}")

def get_all_channel_posts():
    """Get all channel posts"""
    return channel_posts_storage

def get_channel_stats():
    """Get channel statistics"""
    return {
        'total_posts': len(channel_posts_storage),
        'type_counts': {'telegram': len(channel_posts_storage)},
        'latest_post': channel_posts_storage[-1]['created_at'] if channel_posts_storage else None
    }

# ===== ROUTES =====

@app.route('/')
def index():
    """Serve the frontend"""
    return render_template('index.html')

@app.route('/api')
def api_home():
    """API home endpoint"""
    return jsonify({
        "status": "online",
        "service": "4UTODAY Bot API",
        "timestamp": datetime.now().isoformat(),
        "endpoints": {
            "health": "/health",
            "posts": "/api/posts",
            "stats": "/api/stats",
            "channel_posts": "/api/channel/posts",
            "channel_stats": "/api/channel/stats"
        }
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "database": "in-memory",
        "posts_count": len(channel_posts_storage),
        "timestamp": datetime.now().isoformat()
    })

# ===== TELEGRAM WEBHOOK =====
@app.route('/tg-hook-85379794', methods=['POST'])
def telegram_webhook():
    """Telegram webhook endpoint"""
    try:
        data = request.get_json()
        logger.info(f"📩 Webhook received")
        
        # Process channel posts
        if 'channel_post' in data:
            channel_post = data['channel_post']
            
            # Extract post data
            post_id = channel_post.get('message_id')
            chat = channel_post.get('chat', {})
            channel_id = chat.get('id')
            
            # Get content
            content = ''
            if 'text' in channel_post:
                content = channel_post['text']
            elif 'caption' in channel_post:
                content = channel_post['caption']
            
            # Save to storage
            post_data = {
                'post_id': post_id,
                'channel_id': channel_id,
                'message_type': 'telegram',
                'content': content,
                'date': datetime.fromtimestamp(channel_post.get('date')).isoformat() if channel_post.get('date') else datetime.now().isoformat()
            }
            
            add_channel_post(post_data)
            logger.info(f"✅ Channel post saved: {post_id}")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== CHANNEL API =====
@app.route('/api/channel/posts', methods=['GET'])
def get_channel_posts():
    """Get all channel posts"""
    try:
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        # Simple pagination
        start = (page - 1) * limit
        end = start + limit
        posts = get_all_channel_posts()[start:end]
        
        return jsonify({
            "status": "success",
            "data": {
                "posts": posts,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": len(channel_posts_storage),
                    "pages": (len(channel_posts_storage) + limit - 1) // limit if limit > 0 else 0
                }
            }
        }), 200
    except Exception as e:
        logger.error(f"Get channel posts error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/channel/stats', methods=['GET'])
def get_channel_stats_api():
    """Get channel statistics"""
    try:
        stats = get_channel_stats()
        return jsonify({
            "status": "success",
            "data": stats
        }), 200
    except Exception as e:
        logger.error(f"Get channel stats error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== FRONTEND API =====
@app.route('/api/posts', methods=['GET'])
def get_posts_frontend():
    """Frontend posts endpoint"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        # Get posts and format for frontend
        all_posts = get_all_channel_posts()
        posts = all_posts[:limit]
        
        formatted_posts = []
        for post in posts:
            content = post.get('content', '')
            title = content[:100] + '...' if len(content) > 100 else content or 'No title'
            
            formatted_posts.append({
                'id': post.get('id'),
                'telegram_message_id': post.get('post_id'),
                'post_title': title,
                'post_description': content or 'No description available',
                'content': content,
                'tags': 'telegram',
                'file_url': None,
                'created_at': post.get('created_at')
            })
        
        return jsonify({
            "posts": formatted_posts
        }), 200
    except Exception as e:
        logger.error(f"Get posts frontend error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats_frontend():
    """Frontend stats endpoint"""
    try:
        stats = get_channel_stats()
        return jsonify({
            "total_posts": stats['total_posts'],
            "total_tags": 1,
            "today_posts": stats['total_posts']
        }), 200
    except Exception as e:
        logger.error(f"Get stats frontend error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# ===== STATIC FILES =====
@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

# ===== START APPLICATION =====
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
