# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if exists

class Config:
    # Telegram Bot Configuration
    TOKEN = os.environ.get('TOKEN', '')
    BOT_USERNAME = os.environ.get('BOT_USERNAME', '')
    
    # Database Configuration
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Server/Webhook Configuration
    RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://fourutoday.onrender.com')
    WEBHOOK_PATH = '/tg-hook-85379794'
    WEBHOOK_URL = f"{RENDER_URL}{WEBHOOK_PATH}"
    
    # App Settings
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'
    PORT = int(os.environ.get('PORT', 10000))
    
    # Channel/Group IDs
    CHANNEL_ID = os.environ.get('CHANNEL_ID', '-1003798327086')
    ADMIN_IDS = os.environ.get('ADMIN_IDS', '').split(',') if os.environ.get('ADMIN_IDS') else []
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    
    # CORS Settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With']

# Create config instance
config = Config()
