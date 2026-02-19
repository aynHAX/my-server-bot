import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# إعداد الـ Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# قراءة التوكن من متغيرات البيئة
TOKEN = os.environ.get('TOKEN')
PORT = os.environ.get('PORT')

# خادم الفحص الصحي الوهمي
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        return

def run_health_server():
    port = int(PORT) if PORT else 8000
    server = HTTPServer(('', port), HealthCheckHandler)
    logging.info(f"Health check server running on port {port}")
    server.serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحباً! أنا بوت يعمل على Koyeb.')

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"قلت: {update.message.text}")

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f'Update {update} caused error {context.error}')

def main():
    if not TOKEN:
        logging.error("لم يتم العثور على التوكن!")
        return

    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    application.add_error_handler(error)

    # تشغيل خادم الفحص الصحي في الخلفية إذا كان PORT محدداً
    if PORT:
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        logging.info("Health check thread started")
    
    # تشغيل البوت
    logging.info("Bot is starting...")
    
    # استخدام Webhook إذا كان PORT محدداً، وإلا استخدم Polling
    if PORT:
        # استخدام Webhook مع Koyeb
        application.run_webhook(
            listen="0.0.0.0",
            port=int(PORT),
            url_path=TOKEN,
            webhook_url=f"https://your-app-name.koyeb.app/{TOKEN}"
        )
    else:
        # استخدام Long Polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
