import os
import threading
import asyncio
import datetime
from telegram import Update, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from extensions import db
from models.device_info import DeviceInfo
import logging

# Configure logging for the bot
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

class TelegramService:
    def __init__(self, app):
         self.app = app
         self.bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None

    async def send_error_log(self, message):
        if self.bot and TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"🚨 ERROR: {message}")
            except Exception as e:
                print(f"Failed to send Telegram log: {e}")

    async def set_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
             # /setstatus <sn> <status>
             args = context.args
             if len(args) != 2:
                 await update.message.reply_text("Usage: /setstatus <SN> <STATUS>")
                 return
             
             sn = args[0]
             new_status = args[1]
             
             # Need app context to access DB
             with self.app.app_context():
                 device = DeviceInfo.query.get(sn)
                 if device:
                     device.status = new_status
                     db.session.commit()
                     await update.message.reply_text(f"✅ Status of {sn} updated to {new_status}")
                 else:
                     await update.message.reply_text(f"❌ Device {sn} not found.")
                     
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error updating status: {str(e)}")

    async def send_message(self, message):
        if self.bot and TELEGRAM_CHAT_ID:
            try:
                await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            except Exception as e:
                print(f"Failed to send Telegram message: {e}")

    async def set_env_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
             # /set_env <key> <value>
             args = context.args
             if len(args) != 2:
                 await update.message.reply_text("Usage: /set_env <KEY> <VALUE>")
                 return
             

             key = args[0]
             value = args[1]
             print(f"Old env {key}={os.environ.get(key)}")
             print(f"Setting env {key}={value}")
             os.environ[key] = value
             await update.message.reply_text(f"✅ Set env {key}={value}")
                      
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error setting env: {str(e)}")

    async def remove_device_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # /remove <sn>
            args = context.args
            if len(args) != 1:
                await update.message.reply_text("Usage: /remove <SN>")
                return

            sn = args[0]
            with self.app.app_context():
                device = DeviceInfo.query.get(sn)
                if device:
                    db.session.delete(device)
                    db.session.commit()
                    await update.message.reply_text(f"✅ Removed device {sn}")
                else:
                    await update.message.reply_text(f"❌ Device {sn} not found.")
        except Exception as e:
            await update.message.reply_text(f"⚠️ Error removing device: {str(e)}")

    async def startup_notification(self):
         if self.bot and TELEGRAM_CHAT_ID:
             try:
                 start_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                 await self.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=f"🚀 Application Started at {start_time}")
             except Exception as e:
                 print(f"Failed to send startup notification: {e}")

    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("pong")

    async def uptime_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Calculate uptime (simple approximation)
        # In a real scenario, track start time globally
        current_time = datetime.datetime.now()
        await update.message.reply_text(f"🕒 Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

def run_telegram_bot(app):
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram Token not found. Bot will not start.")
        return

    # Define post_init hook to run startup notification
    async def on_startup(application):
        telegram_service = TelegramService(app)
        # We can update the service's bot to match the application's bot if desired, 
        # but the service initialized its own. 
        # Let's just call the notification method.
        # Since startup_notification uses self.bot, checking if it's initialized is enough.
        await telegram_service.startup_notification()

    # Create telegram service instance once for handlers
    telegram_service = TelegramService(app)

    # Use post_init to schedule startup tasks safely within the bot's loop
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(on_startup).build()
    
    # Register handlers
    application.add_handler(CommandHandler("setstatus", telegram_service.set_status_command))
    application.add_handler(CommandHandler("set_env", telegram_service.set_env_command))
    application.add_handler(CommandHandler("remove", telegram_service.remove_device_command))
    application.add_handler(CommandHandler("ping", telegram_service.ping_command))
    application.add_handler(CommandHandler("uptime", telegram_service.uptime_command))
    
    print("Telegram Bot Service Started...")
    # allowed_updates=Update.ALL_TYPES makes sure we get everything, but defaults are usually fine
    # stop_signals=None is REQUIRED when running in a background thread to avoid "set_wakeup_fd" errors
    application.run_polling(stop_signals=None)

def start_bot_thread(app):
    thread = threading.Thread(target=run_telegram_bot, args=(app,))
    thread.daemon = True
    thread.start()

# Helper for logging errors from other parts of the app
def log_error_to_telegram(app, message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
             # Basic implementation: using a temporary loop or blocking call might be tricky in Flask request context
             # For production, use an async task queue (Celery) or a background thread queue.
             # Here we will just fire and forget via a thread to avoid blocking response
             def _send():
                 asyncio.run(TelegramService(app).send_error_log(message))
             
             threading.Thread(target=_send).start()
        except Exception as e:
            print(f"Error dispatching telegram log: {e}")

def send_telegram_notification(app, message):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
             def _send():
                 asyncio.run(TelegramService(app).send_message(message))
             
             threading.Thread(target=_send).start()
        except Exception as e:
            print(f"Error dispatching telegram notification: {e}")
