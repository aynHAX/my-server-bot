import os
import telebot
import threading
import re
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
    bot.reply_to(message, "مرحباً! أرسل لي أي رابط وسأقوم بزيارته في الوضع المخفي وعمل بث مباشر له 🔴")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    if re.match(r'^https?://', text):
        wait_msg = bot.reply_to(message, "جاري فتح المتصفح المخفي والدخول للرابط... 🕵️‍♂️")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                
                # فتح نافذة في الوضع المخفي (Incognito)
                context = browser.new_context()
                page = context.new_page()
                
                page.goto(text, timeout=60000)
                
                screenshot_path = "screenshot.jpg"
                
                # أخذ أول لقطة شاشة بصيغة JPEG بجودة 40% لتكون خفيفة جداً
                page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                
                with open(screenshot_path, 'rb') as photo:
                    # إرسال الصورة الأولى
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر للموقع (يتم التحديث)...")
                    
                # حذف رسالة الانتظار
                bot.delete_message(message.chat.id, wait_msg.message_id)
                
                # تحديث الصورة عدة مرات لعمل تأثير "البث المباشر"
                # سنلتقط 15 إطاراً (Frame)، يمكنك زيادة العدد إذا أردت بثاً أطول
                for _ in range(15): 
                    time.sleep(2.5) # الانتظار 2.5 ثانية لتجنب حظر تيليجرام (Rate Limit)
                    
                    # التقاط صورة جديدة خفيفة
                    page.screenshot(path=screenshot_path, type="jpeg", quality=40)
                    
                    with open(screenshot_path, 'rb') as photo:
                        # تحديث الصورة في نفس الرسالة
                        media = InputMediaPhoto(photo, caption="🔴 بث مباشر للموقع (يتم التحديث)...")
                        bot.edit_message_media(chat_id=message.chat.id, message_id=stream_msg.message_id, media=media)
                        
                # إغلاق المتصفح المخفي تماماً بعد الانتهاء
                bot.edit_message_caption(chat_id=message.chat.id, message_id=stream_msg.message_id, caption="✅ انتهى البث المباشر وتم إغلاق المتصفح.")
                context.close()
                browser.close()
            
            # تنظيف وحذف الصورة من مساحة التخزين
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
                
        except Exception as e:
            bot.edit_message_text(f"❌ حدث خطأ:\n{str(e)}", message.chat.id, wait_msg.message_id)
    else:
        bot.reply_to(message, "الرجاء إرسال رابط صحيح يبدأ بـ http:// أو https:// 🔗")

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    
    print("جاري تشغيل بوت التليجرام...")
    bot.infinity_polling()
