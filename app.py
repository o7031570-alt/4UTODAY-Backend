# app.py ရဲ့ အဆုံးမှာ ဒီ endpoints တွေ ထပ်ထည့်ပါ

# ===== FRONTEND ENDPOINTS =====
@app.route('/api/posts', methods=['GET'])
def get_posts_frontend():
    """Endpoint for frontend"""
    try:
        limit = request.args.get('limit', 50, type=int)
        posts = db.get_channel_posts(limit=limit, offset=0)
        
        formatted_posts = []
        for post in posts:
            content = post.get('content', '') or post.get('caption', '')
            title = content[:100] + '...' if len(content) > 100 else content or 'No title'
            
            formatted_posts.append({
                'id': post.get('id'),
                'telegram_message_id': post.get('post_id'),
                'post_title': title,
                'post_description': content or 'No description',
                'tags': post.get('message_type', 'telegram'),
                'file_url': post.get('media_url'),
                'created_at': post.get('date').isoformat() if post.get('date') else datetime.now().isoformat()
            })
        
        return jsonify({"posts": formatted_posts}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats_frontend():
    """Stats for frontend"""
    try:
        stats = db.get_stats()
        return jsonify({
            "total_posts": stats['total_posts'],
            "total_tags": len(stats['type_counts']),
            "today_posts": stats['total_posts']  # ရိုးရိုးပဲ ပြမယ်
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/frontend')
def frontend_dashboard():
    """Serve the frontend dashboard"""
    # ဒီမှာ မင်း HTML ကို ဒီအတိုင်း return ပြန်ပါ
    # ဒီလိုမျိုး:
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
            /* မင်း CSS အကုန်လုံး ဒီမှာ */
            :root {
                --primary: #4361ee;
                --primary-dark: #3a56d4;
                /* ... ဆက်ရေးပါ ... */
            }
        </style>
    </head>
    <body>
        <!-- မင်း HTML အကုန်လုံး ဒီမှာ -->
        
        <script>
            // ဒီမှာ API_BASE_URL ကို ပြင်ပါ
            const API_BASE_URL = "https://fourutoday.onrender.com";
            
            // မင်း JavaScript အကုန်လုံး ဒီမှာ
            // ...
        </script>
    </body>
    </html>
    """
    return html_content, 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/')
def home():
    """Redirect to frontend"""
    return redirect('/frontend')
