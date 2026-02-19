import os
import telebot
from flask import Flask
import threading

# 1. إعداد البوت
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    raise ValueError("لم يتم العثور على BOT_TOKEN. تأكد من إضافته في إعدادات Koyeb.")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أنا يعمل الآن بنجاح كـ Web Service على Koyeb 🚀")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, message.text)

# 2. إعداد خادم الويب الوهمي لإرضاء فحص Koyeb
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running perfectly!"

def run_bot():
    print("جاري تشغيل البوت...")
    bot.infinity_polling()

if __name__ == "__main__":
    # تشغيل البوت في مسار (Thread) منفصل حتى لا يتداخل مع خادم الويب
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    
    # تشغيل خادم الويب الوهمي على البورت الذي يطلبه Koyeb (الافتراضي 8000)
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port)
