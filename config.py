# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # .env file ရှိရင် load လုပ်မယ်

# Configuration settings
class Config:
    # Telegram Bot
    TOKEN = os.environ.get('TOKEN')
    BOT_USERNAME = os.environ.get('BOT_USERNAME', '4UTODAY_bot')
    
    # Database
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Server/Webhook
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://fourutoday.onrender.com')
    WEBHOOK_PATH = '/tg-hook-85379794'
    WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"
    
    # App settings
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 10000))
    
    # Channel/Group IDs
    CHANNEL_ID = os.environ.get('CHANNEL_ID', '')
    ADMIN_IDS = os.environ.get('ADMIN_IDS', '').split(',') if os.environ.get('ADMIN_IDS') else []
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')

# Config instance
config = Config()
