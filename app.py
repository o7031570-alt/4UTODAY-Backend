# app.py (SIMPLE VERSION - ဒီဟာနဲ့ အစားထိုးပါ)
from flask import Flask, request, jsonify
import os
import logging
from datetime import datetime

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get('TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://fourutoday.onrender.com')
WEBHOOK_URL = f"{RENDER_URL}/tg-hook-85379794"

@app.route('/')
def home():
    """Root endpoint"""
    return jsonify({
        "status": "online",
        "service": "4UTODAY Bot",
        "webhook": WEBHOOK_URL,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "database": "connected" if DATABASE_URL else "disconnected",
        "token": "set" if TOKEN else "missing",
        "timestamp": datetime.now().isoformat()
    }), 200

@app.route('/tg-hook-85379794', methods=['POST'])
def telegram_webhook():
    """Telegram webhook endpoint"""
    try:
        data = request.get_json()
        logger.info(f"📩 Webhook received: {data}")
        
        # Simple response
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/setup-webhook', methods=['GET'])
def setup_webhook():
    """Setup webhook manually"""
    import requests
    
    if not TOKEN:
        return jsonify({"status": "error", "message": "TOKEN not set"}), 400
    
    try:
        # Delete old webhook
        delete_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
        delete_resp = requests.get(delete_url).json()
        
        # Set new webhook
        set_url = f"https://api.telegram.org/bot{TOKEN}/setWebhook?url={WEBHOOK_URL}"
        set_resp = requests.get(set_url).json()
        
        return jsonify({
            "status": "success",
            "delete_webhook": delete_resp,
            "set_webhook": set_resp,
            "webhook_url": WEBHOOK_URL
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"🚀 Starting 4UTODAY Bot...")
    logger.info(f"🔧 TOKEN: {'✅ Set' if TOKEN else '❌ Missing'}")
    logger.info(f"🔧 DATABASE_URL: {'✅ Set' if DATABASE_URL else '❌ Missing'}")
    logger.info(f"🔧 WEBHOOK_URL: {WEBHOOK_URL}")
    
    app.run(host='0.0.0.0', port=10000, debug=False)
