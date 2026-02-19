import os
import telebot
import threading
import time
import signal
import sys
from telebot.types import InputMediaPhoto
from flask import Flask
from playwright.sync_api import sync_playwright
from telebot.apihelper import ApiTelegramException

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("خطأ: يرجى التأكد من إضافة BOT_TOKEN في Koyeb")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# قفل لمنع استنزاف موارد الخادم
browser_lock = threading.Lock()

@app.route('/')
def health_check():
    return "Bot is running perfectly with Firefox!"

def run_flask():
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أرسل لي رابط Google Skills وسأقوم بفتحه متجاوزاً حماية جوجل 🔴")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    # التأكد من أن الرابط يخص منصة مهارات جوجل
    if "skills.google" not in text:
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يخص منصة Google Skills 🔗")
        return
        
    if browser_lock.locked():
        bot.reply_to(message, "⚠️ عذراً، البوت مشغول حالياً. يرجى الانتظار قليلاً ثم المحاولة.")
        return

    with browser_lock:
        wait_msg = bot.reply_to(message, "جاري الدخول باستخدام محرك Firefox لتجاوز فحص جوجل... 🦊")
        screenshot_path = f"screenshot_{message.chat.id}.jpg" 
        
        try:
            with sync_playwright() as p:
                # إطلاق متصفح Firefox بدلاً من Chromium
                browser = p.firefox.launch(
                    headless=True
                )
                
                # إعداد User-Agent واقعي لمتصفح فايرفوكس
                firefox_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
                
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent=firefox_user_agent
                )
                
                page = context.new_page()
                
                # التوجه للرابط
                page.goto(text, timeout=60000)
                
                # التقاط الصورة الأولى
                page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                
                with open(screenshot_path, 'rb') as photo:
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر (Firefox Mode)...")
                    
                try:
                    bot.delete_message(message.chat.id, wait_msg.message_id)
                except ApiTelegramException:
                    pass
                
                # البث المباشر
                for _ in range(15): 
                    time.sleep(2.5) 
                    
                    page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                    
                    try:
                        with open(screenshot_path, 'rb') as photo:
                            media = InputMediaPhoto(photo, caption="🔴 بث مباشر (Firefox Mode)...")
                            bot.edit_message_media(chat_id=message.chat.id, message_id=stream_msg.message_id, media=media)
                    
                    except ApiTelegramException as e:
                        if "message is not modified" in str(e):
                            continue
                        elif "message to edit not found" in str(e):
                            break
                            
                try:
                    bot.edit_message_caption(chat_id=message.chat.id, message_id=stream_msg.message_id, caption="✅ انتهى البث المباشر.")
                except ApiTelegramException:
                    pass
                    
                context.close()
                browser.close()
                
        except Exception as e:
            try:
                bot.edit_message_text(f"❌ حدث خطأ داخلي:\n{str(e)}", message.chat.id, wait_msg.message_id)
            except ApiTelegramException:
                bot.send_message(message.chat.id, f"❌ حدث خطأ داخلي:\n{str(e)}")
            
        finally:
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)

# إغلاق آمن لتجنب تعليق Koyeb
def signal_handler(signum, frame):
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot.infinity_polling(skip_pending=True)
