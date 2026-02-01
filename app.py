# app.py - SIMPLE WORKING VERSION
from flask import Flask, request, jsonify, render_template, send_from_directory
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

# ===== SIMPLE STORAGE =====
channel_posts_storage = []

# ===== ROUTES =====

@app.route('/')
def index():
    """Serve the frontend"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "healthy",
        "posts_count": len(channel_posts_storage),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/posts', methods=['GET'])
def get_posts():
    """Get all posts"""
    try:
        limit = request.args.get('limit', 50, type=int)
        
        # Format posts for frontend
        formatted_posts = []
        for i, post in enumerate(channel_posts_storage[:limit]):
            content = post.get('content', '')
            title = content[:100] + '...' if len(content) > 100 else content or 'No title'
            
            formatted_posts.append({
                'id': i + 1,
                'telegram_message_id': post.get('post_id', i + 1),
                'post_title': title,
                'post_description': content or 'No description available',
                'tags': 'telegram',
                'file_url': post.get('media_url'),
                'created_at': post.get('created_at', datetime.now().isoformat())
            })
        
        return jsonify({
            "posts": formatted_posts
        }), 200
    except Exception as e:
        logger.error(f"Get posts error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    return jsonify({
        "total_posts": len(channel_posts_storage),
        "total_tags": 1,
        "today_posts": len(channel_posts_storage)
    }), 200

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
            
            # Get content
            content = ''
            if 'text' in channel_post:
                content = channel_post['text']
            elif 'caption' in channel_post:
                content = channel_post['caption']
            
            # Save to storage
            post_data = {
                'post_id': post_id,
                'message_type': 'telegram',
                'content': content,
                'created_at': datetime.now().isoformat()
            }
            
            channel_posts_storage.append(post_data)
            logger.info(f"✅ Channel post saved: {post_id}")
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"🚀 Starting server on port {port}")
    logger.info(f"📁 Template folder: {app.template_folder}")
    logger.info(f"📁 Static folder: {app.static_folder}")
    app.run(host='0.0.0.0', port=port, debug=False)
