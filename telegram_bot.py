#!/usr/bin/env python3
"""
Telegram Bot to Auto-Post Channel Content to Google Sheets
Run this script 24/7 on a free server to automate the process
"""

import os
import logging
import asyncio
from datetime import datetime
import gspread
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError

# ==================== CONFIGURATION ====================
# REPLACE THESE WITH YOUR VALUES
TELEGRAM_BOT_TOKEN = "8537979478:AAEaj5NWtKyGQoKNkcl_X6qMOX1JMr6RJvc"  # From @BotFather
TELEGRAM_CHANNEL_ID = "@foru_today"  # Your public channel (e.g., "@MyContentFeed")
GOOGLE_SHEET_ID = "https://2PACX-1vQKLow94aPoADie7dT1HaUUb0X8jimzDTk1H4jqMDiS6G2-53MjvW97dMvpjmgbvc9X6W4CAMDmHcRT"  # From your sheet URL
GOOGLE_CREDENTIALS_FILE = "credentials.json"  # Google API credentials
# =======================================================

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Google Sheets
try:
    gc = gspread.service_account(filename=GOOGLE_CREDENTIALS_FILE)
    sh = gc.open_by_key(GOOGLE_SHEET_ID)
    worksheet = sh.sheet1
    logger.info("✅ Connected to Google Sheets")
except Exception as e:
    logger.error(f"❌ Failed to connect to Google Sheets: {e}")
    exit(1)

def get_google_drive_direct_link(file_id: str) -> str:
    """Convert Google Drive file ID to direct download link"""
    return f"https://drive.google.com/uc?export=download&id={file_id}"

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process new posts in the Telegram channel"""
    try:
        message = update.channel_post
        
        # Skip if message is None
        if not message:
            return
        
        # Extract post details
        title = ""
        description = ""
        tags = ""
        file_url = ""
        
        # Get text/caption (use as title and description)
        if message.caption:
            title = message.caption[:100] + "..." if len(message.caption) > 100 else message.caption
            description = message.caption
        elif message.text:
            title = message.text[:100] + "..." if len(message.text) > 100 else message.text
            description = message.text
        
        # Extract hashtags from text/caption
        if message.caption:
            tags = " ".join([word for word in message.caption.split() if word.startswith("#")])
        elif message.text:
            tags = " ".join([word for word in message.text.split() if word.startswith("#")])
        
        # If no hashtags found, use default
        if not tags:
            tags = "#telegram #bot"
        
        # Handle different media types
        if message.photo:
            # Get the largest photo (last in the array)
            file_id = message.photo[-1].file_id
            file = await context.bot.get_file(file_id)
            file_url = file.file_path
            logger.info(f"📸 Photo detected: {file_url}")
            
        elif message.video:
            file = await context.bot.get_file(message.video.file_id)
            file_url = file.file_path
            logger.info(f"🎥 Video detected: {file_url}")
            
        elif message.document:
            file = await context.bot.get_file(message.document.file_id)
            file_url = file.file_path
            logger.info(f"📄 Document detected: {file_url}")
            
        elif message.audio:
            file = await context.bot.get_file(message.audio.file_id)
            file_url = file.file_path
            logger.info(f"🎵 Audio detected: {file_url}")
            
        elif message.voice:
            file = await context.bot.get_file(message.voice.file_id)
            file_url = file.file_path
            logger.info(f"🎤 Voice message detected: {file_url}")
        
        # Append to Google Sheet
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        worksheet.append_row([
            title,
            description,
            file_url,
            tags,
            timestamp  # Optional: add timestamp column
        ])
        
        logger.info(f"✅ Added to Google Sheet: {title[:50]}...")
        
    except Exception as e:
        logger.error(f"❌ Error processing post: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Start the bot"""
    try:
        # Create application
        app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        
        # Add handler for channel posts
        app.add_handler(
            MessageHandler(
                filters.Chat(username=TELEGRAM_CHANNEL_ID.lstrip('@')) | 
                filters.Chat(chat_id=TELEGRAM_CHANNEL_ID) if TELEGRAM_CHANNEL_ID.startswith('-') else 
                filters.Chat(username=TELEGRAM_CHANNEL_ID.lstrip('@')),
                handle_channel_post
            )
        )
        
        # Add error handler
        app.add_error_handler(error_handler)
        
        logger.info(f"🤖 Bot started. Listening to channel: {TELEGRAM_CHANNEL_ID}")
        logger.info("📊 Posts will be automatically added to Google Sheets")
        logger.info("🔄 Bot is running. Press Ctrl+C to stop.")
        
        # Start polling
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except TelegramError as e:
        logger.error(f"❌ Telegram API error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()