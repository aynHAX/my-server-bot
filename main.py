import os
import telebot

# جلب توكن البوت من متغيرات البيئة في Koyeb
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("الرجاء التأكد من إضافة BOT_TOKEN في إعدادات Koyeb")

bot = telebot.TeleBot(BOT_TOKEN)

# الرد على أمر /start و /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أنا بوت تيليجرام أعمل بنجاح على استضافة Koyeb 🚀")

# الرد على أي رسالة نصية أخرى (إعادة إرسال نفس النص)
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, f"لقد قلت: {message.text}")

if __name__ == "__main__":
    print("جاري تشغيل البوت...")
    bot.infinity_polling()
