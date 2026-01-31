# telegram_bot.py
import asyncio
import logging
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import config
from database import db

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = config.TOKEN
        self.bot = None
        self.application = None
    
    async def setup(self):
        """Bot ကို setup လုပ်မယ်"""
        if not self.token:
            logger.error("❌ Bot token not found!")
            return False
        
        try:
            # Application create လုပ်မယ်
            self.application = Application.builder().token(self.token).build()
            
            # Handlers တွေ ထည့်မယ်
            self._add_handlers()
            
            logger.info("✅ Telegram bot setup completed")
            return True
        except Exception as e:
            logger.error(f"❌ Bot setup error: {e}")
            return False
    
    def _add_handlers(self):
        """Command handlers တွေ ထည့်မယ်"""
        # Start command
        self.application.add_handler(CommandHandler("start", self._start_command))
        
        # Help command
        self.application.add_handler(CommandHandler("help", self._help_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("stats", self._stats_command))
        
        # Message handler
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
    
    async def _start_command(self, update: Update, context):
        """/start command handler"""
        user = update.effective_user
        welcome_text = f"""
👋 မင်္ဂလာပါ {user.first_name}!

🤖 **4UTODAY Bot** မှ ကြိုဆိုပါတယ်။

📢 ဤ bot သည် 4UTODAY သတင်းများကို ဖြန့်ချိပေးမည့် bot ဖြစ်ပါသည်။

🔧 Available Commands:
/start - Bot စတင်ရန်
/help - အကူအညီရယူရန်
/stats - စာရင်းဇယားများ (Admin only)
        """
        await update.message.reply_text(welcome_text)
    
    async def _help_command(self, update: Update, context):
        """/help command handler"""
        help_text = """
📖 **Help Guide**

🔹 Admin Commands:
/stats - Bot statistics ကြည့်ရန်

🔹 Features:
• Channel posts များကို လက်ခံရယူခြင်း
• Database ထဲတွင် သိမ်းဆည်းခြင်း
• Webhook မှတဆင့် အလုပ်လုပ်ခြင်း

📞 Support: @your_support_contact
        """
        await update.message.reply_text(help_text)
    
    async def _stats_command(self, update: Update, context):
        """/stats command handler - Admin only"""
        user_id = update.effective_user.id
        
        # Admin check (ဒီနေရာမှာ ကိုယ့် admin ID ကို ထည့်ပါ)
        if str(user_id) not in config.ADMIN_IDS:
            await update.message.reply_text("⛔ ဤ command ကို သုံးခွင့်မရှိပါ။")
            return
        
        # Database ကနေ statistics ယူမယ်
        try:
            with db.conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as total_posts FROM posts")
                post_count = cur.fetchone()[0]
                
                cur.execute("SELECT COUNT(*) as total_users FROM users")
                user_count = cur.fetchone()[0]
            
            stats_text = f"""
📊 **Bot Statistics**

📝 Total Posts: {post_count}
👥 Total Users: {user_count}
🔗 Webhook: {config.WEBHOOK_URL}
🌐 Server: {config.RENDER_URL}
            """
            await update.message.reply_text(stats_text)
        except Exception as e:
            logger.error(f"Stats error: {e}")
            await update.message.reply_text(f"❌ Statistics ရယူရာတွင် error: {e}")
    
    async def _handle_message(self, update: Update, context):
        """Regular message handler"""
        # ဒီမှာ message process လုပ်မယ်
        message = update.message.text
        user = update.effective_user
        
        # Database ထဲမှာ user ကို save/update လုပ်မယ်
        try:
            with db.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (user_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE
                    SET username = EXCLUDED.username,
                        first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name
                """, (user.id, user.username, user.first_name, user.last_name))
                db.conn.commit()
        except Exception as e:
            logger.error(f"User save error: {e}")
        
        # Echo message (ဥပမာအားဖြင့်)
        await update.message.reply_text(f"📩 Message received: {message[:50]}...")
    
    async def setup_webhook(self):
        """Webhook setup လုပ်မယ်"""
        try:
            bot = Bot(token=self.token)
            
            # Delete existing webhook
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("✅ Webhook deleted")
            
            # Set new webhook
            await bot.set_webhook(url=config.WEBHOOK_URL)
            logger.info(f"✅ Webhook set to: {config.WEBHOOK_URL}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Webhook setup error: {e}")
            return False
    
    async def process_update(self, update_data):
        """Webhook ကနေ ရလာတဲ့ update ကို process လုပ်မယ်"""
        if not self.application:
            await self.setup()
        
        update = Update.de_json(update_data, self.application.bot)
        await self.application.process_update(update)

# Global bot instance
telegram_bot = TelegramBot()

# Sync functions for Flask (async ကို sync လုပ်ဖို့)
def setup_webhook_sync():
    """Flask ထဲကနေ async function ကို ခေါ်သုံးဖို့"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(telegram_bot.setup_webhook())
    finally:
        loop.close()

async def setup_bot_async():
    """Bot setup async function"""
    return await telegram_bot.setup()
