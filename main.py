import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد الـ Logging لمعرفة الأخطاء في كونيب
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# قراءة التوكن من متغيرات البيئة
TOKEN = os.environ.get('TOKEN')

# دالة البدء
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('مرحباً! أنا بوت يعمل على Koyeb. كيف يمكنني مساعدتك؟')

# دالة للرد على الرسائل (يقوم بتكرار الرسالة)
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"قلت: {update.message.text}")

# دالة للتعامل مع الأخطاء
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f'Update {update} caused error {context.error}')

def main():
    # التأكد من وجود التوكن
    if not TOKEN:
        logging.error("لم يتم العثور على التوكن! تأكد من ضبط متغير البيئة TOKEN")
        return

    # إنشاء التطبيق
    application = Application.builder().token(TOKEN).build()

    # إضافة معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    
    # معالج الرسائل النصية (باستثناء الأوامر)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # معالج الأخطاء
    application.add_error_handler(error)

    # تشغيل البوت
    logging.info("Bot is starting...")
    # نستخدم run_polling لأن نوع الخدمة worker لا يتطلب بورت محدد
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
