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
from playwright_stealth import stealth_sync  # مكتبة التخفي الجديدة

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("خطأ: يرجى التأكد من إضافة BOT_TOKEN في Koyeb")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

browser_lock = threading.Lock()

@app.route('/')
def health_check():
    return "Bot is running perfectly with Stealth Mode!"

def run_flask():
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أرسل لي رابط Google Skills وسأقوم بفتحه متجاوزاً حماية جوجل 🔴")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    if "skills.google" not in text:
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يخص منصة Google Skills 🔗")
        return
        
    if browser_lock.locked():
        bot.reply_to(message, "⚠️ عذراً، البوت مشغول حالياً. يرجى الانتظار قليلاً ثم المحاولة.")
        return

    with browser_lock:
        wait_msg = bot.reply_to(message, "جاري الدخول بوضع التخفي العميق (Stealth Mode) لتجاوز حماية جوجل... 🕵️‍♂️")
        screenshot_path = f"screenshot_{message.chat.id}.jpg" 
        
        try:
            with sync_playwright() as p:
                # إعدادات إطلاق المتصفح
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-dev-shm-usage", 
                        "--no-sandbox", 
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                        "--start-maximized"
                    ]
                )
                
                # إضافة User-Agent واقعي جداً
                real_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
                
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent=real_user_agent
                )
                
                # حقن كود خفي لحذف أي أثر للبوت
                context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                
                page = context.new_page()
                
                # تفعيل وضع التخفي (Stealth) على الصفحة قبل فتح الرابط
                stealth_sync(page)
                
                # التوجه للرابط
                page.goto(text, timeout=60000)
                
                page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                
                with open(screenshot_path, 'rb') as photo:
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر (Stealth Mode)...")
                    
                try:
                    bot.delete_message(message.chat.id, wait_msg.message_id)
                except ApiTelegramException:
                    pass
                
                for _ in range(15): 
                    time.sleep(2.5) 
                    
                    page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                    
                    try:
                        with open(screenshot_path, 'rb') as photo:
                            media = InputMediaPhoto(photo, caption="🔴 بث مباشر (Stealth Mode)...")
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

def signal_handler(signum, frame):
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot.infinity_polling(skip_pending=True)
