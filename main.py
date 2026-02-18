import os
import telebot
import threading
import re
from flask import Flask
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# إعداد خادم Flask بسيط لكي تتجاوز فحص الصحة (Health Check) في Koyeb
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot and Browser Automation are running!"

def run_flask():
    # تشغيل الخادم على المنفذ 8000
    app.run(host="0.0.0.0", port=8000)

# الرد على أمر البداية
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أرسل لي أي رابط يبدأ بـ http أو https وسأقوم بزيارته وأخذ لقطة شاشة له 📸")

# معالجة الروابط
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    # التحقق مما إذا كانت الرسالة عبارة عن رابط
    if re.match(r'^https?://', text):
        msg = bot.reply_to(message, "جاري فتح المتصفح والدخول للرابط، يرجى الانتظار قليلاً... ⏳")
        
        try:
            # تشغيل متصفح Playwright
            with sync_playwright() as p:
                # فتح متصفح كروميوم في الخلفية
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # الذهاب للرابط (مع مهلة 60 ثانية)
                page.goto(text, timeout=60000)
                
                # أخذ لقطة شاشة وحفظها مؤقتاً
                screenshot_path = "screenshot.png"
                page.screenshot(path=screenshot_path)
                browser.close()
            
            # إرسال الصورة للمستخدم
            with open(screenshot_path, 'rb') as photo:
                bot.send_photo(message.chat.id, photo, caption="ها هي لقطة الشاشة للموقع! 🌐")
            
            # حذف الصورة بعد إرسالها لتوفير المساحة
            os.remove(screenshot_path)
            
            # حذف رسالة "الانتظار"
            bot.delete_message(message.chat.id, msg.message_id)
            
        except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ أثناء فتح الرابط:\n{str(e)}", message.chat.id, msg.message_id)
    else:
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https:// 🔗")

if __name__ == "__main__":
    # تشغيل Flask في الخلفية لتلبية متطلبات Koyeb
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    print("جاري تشغيل بوت التليجرام...")
    bot.infinity_polling()
