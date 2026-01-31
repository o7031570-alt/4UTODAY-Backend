# app.py - Complete Telegram Bot for Render
from flask import Flask, request
import os
import json
import gspread
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from google.oauth2.service_account import Credentials
import threading
import asyncio
import logging

# Flask App စတင်ပါ
app = Flask(__name__)

# ====== 1. GOOGLE SHEETS SETUP ======
def get_google_sheet():
    """Google Sheets နဲ့ ချိတ်ဆက်ပြီး worksheet object ပြန်ပေးမယ်"""
    try:
        # Render Environment Variable ကနေ JSON string ကိုဖတ်မယ်
        creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json_str:
            raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable မတွေ့ပါ")
        
        # JSON string ကို dictionary အဖြစ် ပြောင်းမယ်
        service_account_info = json.loads(creds_json_str)
        
        # Credentials object ဖန်တီးပြီး gspread ကို authorize လုပ်မယ်
        credentials = Credentials.from_service_account_info(service_account_info)
        gc = gspread.authorize(credentials)
        
        # Google Sheet ID ကိုယူမယ်
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        if not sheet_id:
            raise ValueError("GOOGLE_SHEET_ID environment variable မတွေ့ပါ")
            
        # Sheet ကိုဖွင့်ပြီး ပထမဆုံး worksheet ကိုရမယ်
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
        
        # Column headers ရှိမရှိ စစ်မယ်၊ မရှိရင် ထည့်မယ်
        if worksheet.row_count == 0:
            headers = ["Timestamp", "Title", "Description", "File URL", "Tags"]
            worksheet.append_row(headers)
            
        print("✅ Google Sheets နှင့် ချိတ်ဆက်ပြီးပါပြီ")
        return worksheet
        
    except json.JSONDecodeError as e:
        print(f"❌ GOOGLE_CREDENTIALS_JSON ကို ဖတ်ရာတွင် အမှာ့အယွင်း: {e}")
        return None
    except Exception as e:
        print(f"❌ Google Sheets ချိတ်ဆက်ရာတွင် အမှာ့အယွင်း: {e}")
        return None

# ====== 2. TELEGRAM BOT HANDLER ======
async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram channel ကနေ post အသစ်တစ်ခု ရောက်လာရင် ဒီ function ကို ခေါ်မယ်"""
    try:
        message = update.channel_post
        
        # Post မရှိရင် ထွက်မယ်
        if not message:
            return
            
        print(f"📨 Channel post received: {message.message_id}")
        
        # 1. Google Sheet ကို ချိတ်ဆက်မယ်
        worksheet = get_google_sheet()
        if not worksheet:
            print("❌ Google Sheet နဲ့ ချိတ်ဆက်လို့မရပါ")
            return
            
        # 2. Post ကနေ အချက်အလက်တွေ ထုတ်ယူမယ်
        # Title (caption or text ရဲ့ ပထမစာကြောင်း 100 လုံး)
        if message.caption:
            title = message.caption[:100] + "..." if len(message.caption) > 100 else message.caption
            description = message.caption
        elif message.text:
            title = message.text[:100] + "..." if len(message.text) > 100 else message.text
            description = message.text
        else:
            title = "Media Post"
            description = "No text content"
            
        # File URL ရှာမယ်
        file_url = ""
        if message.photo:
            # အကြီးဆုံး photo ကို ယူမယ်
            file_id = message.photo[-1].file_id
            file = await context.bot.get_file(file_id)
            file_url = file.file_path
        elif message.video:
            file = await context.bot.get_file(message.video.file_id)
            file_url = file.file_path
        elif message.document:
            file = await context.bot.get_file(message.document.file_id)
            file_url = file.file_path
            
        # Hashtags စုစည်းမယ်
        tags = []
        if message.caption:
            words = message.caption.split()
            tags = [word for word in words if word.startswith("#")]
        elif message.text:
            words = message.text.split()
            tags = [word for word in words if word.startswith("#")]
            
        tags_str = ", ".join(tags) if tags else "#telegram"
        
        # 3. Google Sheet ထဲကို data တန်ဖိုးတွေ ထည့်မယ်
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_row = [timestamp, title, description, file_url, tags_str]
        worksheet.append_row(new_row)
        
        print(f"✅ Data written to Google Sheet: {title}")
        print(f"   📊 Row added: {new_row}")
        
    except Exception as e:
        print(f"❌ Error processing channel post: {e}")

# ====== 3. BOT MANAGER & BACKGROUND THREAD ======
class BotManager:
    """Bot ကို background မှာ စီမံခန့်ခွဲဖို့ class"""
    def __init__(self):
        self.application = None
        self.is_running = False
        
    def start_bot(self):
        """Bot ကို background thread ပေါ်မှာ စတင်မယ်"""
        if self.is_running:
            return
            
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN environment variable မတွေ့ပါ")
            return
            
        try:
            # 1. Google Sheets ကို test connection
            print("🔧 Testing Google Sheets connection...")
            sheet_test = get_google_sheet()
            if sheet_test:
                print("✅ Google Sheets connection test successful")
            else:
                print("⚠️ Google Sheets connection failed, but continuing...")
            
            # 2. Telegram Bot Application ဖန်တီးမယ်
            print("🤖 Creating Telegram Bot Application...")
            self.application = Application.builder().token(token).build()
            
            # 3. Channel post handler ကို ထည့်သွင်းမယ်
            self.application.add_handler(
                MessageHandler(filters.ChatType.CHANNEL, handle_channel_post)
            )
            
            # 4. Bot ကို background thread ပေါ်မှာ စတင်မယ်
            self.is_running = True
            bot_thread = threading.Thread(target=self.run_bot_polling, daemon=True)
            bot_thread.start()
            
            print("✅ Telegram Bot started successfully in background")
            print("📱 Bot is now listening for channel posts...")
            
        except Exception as e:
            print(f"❌ Failed to start Telegram Bot: {e}")
            self.is_running = False
    
    def run_bot_polling(self):
        """Bot ကို polling mode နဲ့ run မယ် (background thread)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print("🔄 Starting bot polling...")
            self.application.run_polling()
        except Exception as e:
            print(f"❌ Bot polling error: {e}")
            self.is_running = False

# BotManager instance ဖန်တီးပါ
bot_manager = BotManager()

# ====== 4. FLASK ROUTES ======
@app.route('/')
def home():
    """Root endpoint - Bot status ကို ပြမယ်"""
    status = "running" if bot_manager.is_running else "not running"
    return f"""
    <h1>🚀 Telegram Auto-Poster Bot</h1>
    <p>Status: <strong>{status}</strong></p>
    <p>This bot listens to your Telegram channel and saves posts to Google Sheets.</p>
    <hr>
    <h3>Environment Check:</h3>
    <ul>
        <li>TELEGRAM_BOT_TOKEN: {'✅ Set' if os.environ.get('TELEGRAM_BOT_TOKEN') else '❌ Missing'}</li>
        <li>GOOGLE_SHEET_ID: {'✅ Set' if os.environ.get('GOOGLE_SHEET_ID') else '❌ Missing'}</li>
        <li>GOOGLE_CREDENTIALS_JSON: {'✅ Set' if os.environ.get('GOOGLE_CREDENTIALS_JSON') else '❌ Missing'}</li>
    </ul>
    <p>Check Render logs for detailed operation.</p>
    """

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    if bot_manager.is_running:
        return "✅ Bot is healthy and running", 200
    else:
        return "⚠️ Bot is not running", 503

@app.route('/start-bot', methods=['POST'])
def start_bot_manual():
    """Manual bot start endpoint (if needed)"""
    if not bot_manager.is_running:
        bot_manager.start_bot()
        return "🔄 Bot starting... Check logs for details.", 200
    else:
        return "✅ Bot is already running", 200

# ====== 5. APPLICATION STARTUP ======
if __name__ == '__main__':
    # App စဖွင့်တာနဲ့ bot ကို auto-start လုပ်မယ်
    print("🚀 Starting Flask application and Telegram Bot...")
    bot_manager.start_bot()
    
    # Flask app ကို start မယ်
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)    
