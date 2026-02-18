import os
import telebot
import threading
import time
import signal
import sys
from telebot.types import InputMediaPhoto
from flask import Flask
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("خطأ: يرجى التأكد من إضافة BOT_TOKEN في Koyeb")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# [التحسين 1] قفل لمنع استنزاف الرام وانهيار الخادم
browser_lock = threading.Lock()

@app.route('/')
def health_check():
    return "Bot and Browser Automation are running smoothly!"

def run_flask():
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أرسل لي رابط Google Skills وسأقوم بعمل بث مباشر له بأمان 🔴")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    if not text.startswith("https://www.skills.google/google_sso"):
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يخص منصة Google Skills ويبدأ بـ:\nhttps://www.skills.google/google_sso 🔗")
        return
        
    # التحقق مما إذا كان البوت مشغولاً برابط آخر
    if browser_lock.locked():
        bot.reply_to(message, "⚠️ عذراً، البوت مشغول حالياً بتصوير رابط آخر لحماية الخادم من التوقف. يرجى الانتظار قليلاً ثم المحاولة.")
        return

    # استخدام القفل لضمان معالجة عملية واحدة فقط في كل مرة
    with browser_lock:
        wait_msg = bot.reply_to(message, "جاري فتح الرابط المخصص بأمان تام... 🕵️‍♂️")
        
        # ربط اسم الصورة بمعرف المحادثة لتجنب أي تداخل
        screenshot_path = f"screenshot_{message.chat.id}.jpg" 
        
        try:
            with sync_playwright() as p:
                # [التحسين 2] تشغيل المتصفح بإعدادات مخصصة لبيئة Docker الخفيفة
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu", "--disable-setuid-sandbox"]
                )
                
                context = browser.new_context(viewport={'width': 1280, 'height': 720})
                page = context.new_page()
                
                page.goto(text, timeout=60000)
                
                # التقاط الصورة الأولى
                page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                
                with open(screenshot_path, 'rb') as photo:
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر لصفحة الدخول (يتم التحديث)...")
                    
                bot.delete_message(message.chat.id, wait_msg.message_id)
                
                # البث المباشر
                for _ in range(15): 
                    time.sleep(2.5) 
                    
                    page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                    
                    with open(screenshot_path, 'rb') as photo:
                        media = InputMediaPhoto(photo, caption="🔴 بث مباشر لصفحة الدخول (يتم التحديث)...")
                        bot.edit_message_media(chat_id=message.chat.id, message_id=stream_msg.message_id, media=media)
                        
                bot.edit_message_caption(chat_id=message.chat.id, message_id=stream_msg.message_id, caption="✅ انتهى البث المباشر وتم إغلاق المتصفح لترشيد الاستهلاك.")
                context.close()
                browser.close()
                
        except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ داخلي:\n{str(e)}", message.chat.id, wait_msg.message_id)
            
        finally:
            # [التحسين 5] هذا الكود سيعمل دائماً حتى لو حدث خطأ، لضمان حذف الصورة
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

# [التحسين 3] التقاط أمر الإغلاق من Koyeb لإيقاف البوت بسلاسة ومنع التعليق
def signal_handler(signum, frame):
    print("تم استلام أمر إيقاف من الاستضافة. جاري إغلاق البوت بأمان...")
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    # تشغيل Flask كـ Daemon لكي يتوقف تلقائياً مع توقف البوت
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("جاري تشغيل البوت الاحترافي...")
    
    # [التحسين 4] تجاهل الرسائل القديمة لتجنب الانهيار والتعارض عند التشغيل
    bot.infinity_polling(skip_pending=True)
