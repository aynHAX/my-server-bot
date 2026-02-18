import os
import telebot
import threading
import time
from telebot.types import InputMediaPhoto
from flask import Flask
from playwright.sync_api import sync_playwright

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# خادم Flask لتجاوز فحص الصحة في Koyeb
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8000)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! أرسل لي رابط Google Skills الخاص بك وسأقوم بزيارته وعمل بث مباشر له 🔴")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    # التعديل هنا: الشرط يقبل فقط الروابط التي تبدأ بالمسار المطلوب
    if text.startswith("https://www.skills.google/google_sso"):
        wait_msg = bot.reply_to(message, "جاري فتح الرابط المخصص في المتصفح المخفي... 🕵️‍♂️")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                context = browser.new_context()
                page = context.new_page()
                
                # الدخول للرابط
                page.goto(text, timeout=60000)
                
                screenshot_path = "screenshot.jpg"
                
                # التقاط الصورة الأولى
                page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                
                with open(screenshot_path, 'rb') as photo:
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر لصفحة الدخول (يتم التحديث)...")
                    
                bot.delete_message(message.chat.id, wait_msg.message_id)
                
                # التحديث المستمر كبث مباشر
                for _ in range(15): 
                    time.sleep(2.5) 
                    
                    page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                    
                    with open(screenshot_path, 'rb') as photo:
                        media = InputMediaPhoto(photo, caption="🔴 بث مباشر لصفحة الدخول (يتم التحديث)...")
                        bot.edit_message_media(chat_id=message.chat.id, message_id=stream_msg.message_id, media=media)
                        
                bot.edit_message_caption(chat_id=message.chat.id, message_id=stream_msg.message_id, caption="✅ انتهى البث المباشر وتم إغلاق المتصفح.")
                context.close()
                browser.close()
            
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                
        except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ:\n{str(e)}", message.chat.id, wait_msg.message_id)
    else:
        # رسالة الخطأ عند إرسال رابط غير مدعوم
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يخص منصة Google Skills ويبدأ بـ:\nhttps://www.skills.google/google_sso 🔗")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    print("جاري تشغيل بوت التليجرام...")
    bot.infinity_polling()
