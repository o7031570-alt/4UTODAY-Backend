# app.py - Telegram Bot for Render
from flask import Flask, request, Response
import os
import gspread
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
import threading
import logging
import asyncio

# Flask App စတင်ပါ
app = Flask(__name__)

# ====== သင့်ရဲ့ မူရင်း Bot Logic ကို ဒီမှာ ထည့်ပါ ======
# မူရင်း telegram_bot.py ထဲက handle_channel_post function ကို ဒီနေရာမှာ ကူးထည့်ပါ
# function ရဲ့ အမည်ကို အတိအကျ ကူးထည့်ပါ (ဥပမာ - async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE): )
# ====================================================

# Google Sheets ချိတ်ဆက်ခြင်း (မူရင်း ကုဒ်အတိုင်းပါ)
def init_google_sheets():
    try:
        # Render ပေါ်က Environment Variable ထဲက JSON ကို ယူသုံးမယ်
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            raise ValueError("GOOGLE_CREDENTIALS_JSON environment variable မတွေ့ပါ")
        
        # JSON string ကို file အဖြစ်ယူမယ်
        import json
        creds_dict = json.loads(creds_json)
        import google.auth
        from google.oauth2.service_account import Credentials
        
        credentials = Credentials.from_service_account_info(creds_dict)
        gc = gspread.authorize(credentials)
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        sh = gc.open_by_key(sheet_id)
        worksheet = sh.sheet1
        print("✅ Google Sheets နှင့် ချိတ်ဆက်ပြီးပါပြီ")
        return worksheet
    except Exception as e:
        print(f"❌ Google Sheets ချိတ်ဆက်ရာတွင် အမှာ့အယွင်း: {e}")
        return None

# Bot ကို စတင် စီမံခန့်ခွဲဖို့
class BotManager:
    def __init__(self):
        self.app = None
        self.worksheet = None
        self.is_running = False
        
    def start(self):
        """Bot ကို စတင်ပါ"""
        if self.is_running:
            return
            
        token = os.environ.get('TELEGRAM_BOT_TOKEN')
        if not token:
            print("❌ TELEGRAM_BOT_TOKEN မထည့်သွင်းရသေးပါ")
            return
            
        try:
            # Google Sheets ချိတ်ဆက်ပါ
            self.worksheet = init_google_sheets()
            
            # Telegram Bot Application ဖန်တီးပါ
            self.app = Application.builder().token(token).build()
            
            # Channel post handler ကို ထည့်သွင်းပါ
            # မှတ်ချက်: handle_channel_post ဆိုတဲ့ function အမည်ကို သင့်ကုဒ်နဲ့ ကိုက်ညီအောင် ပြောင်းပေးပါ
            self.app.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
            
            # Webhook အတွက် စီမံပါ (Render ပေါ်တွင် port 10000 ကို သုံးပါမည်)
            port = int(os.environ.get("PORT", 10000))
            webhook_url = f"https://{os.environ.get('RENDER_SERVICE_NAME', 'your-service')}.onrender.com"
            
            # Bot ကို background thread ပေါ်တွင် စတင်ပါ
            self.is_running = True
            bot_thread = threading.Thread(target=self.run_bot, daemon=True)
            bot_thread.start()
            
            print(f"🤖 Telegram Bot စတင်ပြီးပါပြီ")
            print(f"🌐 Webhook URL: {webhook_url}")
            
        except Exception as e:
            print(f"❌ Bot စတင်ရာတွင် အမှားတစ်ခုဖြစ်နေပါသည်: {e}")
            self.is_running = False
    
    def run_bot(self):
        """Bot ကို background တွင် run ပါ"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.app.run_polling()
        except Exception as e:
            print(f"❌ Bot run ရာတွင် အမှာ့အယွင်း: {e}")
            self.is_running = False

# BotManager instance ဖန်တီးပါ
bot_manager = BotManager()

# ====== Flask Routes ======
@app.route('/')
def home():
    return "🚀 Telegram Bot is Running on Render!"

@app.route('/health')
def health_check():
    if bot_manager.is_running:
        return Response("✅ Bot is healthy and running", status=200)
    else:
        return Response("⚠️ Bot is not running", status=503)

@app.route('/start-bot', methods=['POST'])
def start_bot():
    """Bot ကို စတင်ဖို့ route"""
    bot_manager.start()
    return "Bot starting... Check logs for details."

# ====== App ကို စတင်ဖို့ ======
if __name__ == '__main__':
    # App စတင်တာနဲ့ bot ကိုပါ auto start လုပ်မယ်
    bot_manager.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)