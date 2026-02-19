import os
import telebot

# جلب التوكن من متغيرات البيئة (سنقوم بإضافته في Koyeb لاحقاً)
BOT_TOKEN = os.environ.get('BOT_TOKEN')

# التحقق من وجود التوكن
if not BOT_TOKEN:
    raise ValueError("لم يتم العثور على BOT_TOKEN. تأكد من إضافته في إعدادات Koyeb.")

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أنا بوت تيليغرام يعمل بنجاح على استضافة Koyeb 🚀")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    # يقوم البوت بالرد بنفس الرسالة التي أرسلها المستخدم
    bot.reply_to(message, message.text)

if __name__ == "__main__":
    print("جاري تشغيل البوت...")
    bot.infinity_polling()
