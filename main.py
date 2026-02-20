import telebot
import os
import time
import traceback
from io import BytesIO
import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from telebot.types import InputMediaPhoto

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is Healthy and Running!")
    
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث، وسأطلب منك الرابط 🚀")

@bot.message_handler(commands=['live'])
def ask_for_url(message):
    # نطلب من المستخدم إرسال الرابط أولاً
    msg = bot.reply_to(message, "🔗 الرجاء إرسال الرابط الذي تريد الدخول إليه وبثه:")
    # نخبر البوت أن الخطوة القادمة هي استلام الرابط وتمريره لدالة التشغيل
    bot.register_next_step_handler(msg, start_livestream)

def start_livestream(message):
    target_url = message.text
    
    # تحقق بسيط للتأكد من أن النص المرسل هو رابط فعلي
    if not target_url.startswith("http"):
        bot.reply_to(message, "❌ الرابط غير صالح. الرجاء إرسال رابط يبدأ بـ http أو https. أرسل /live للمحاولة مجدداً.")
        return

    msg = bot.reply_to(message, "⏳ [1/5] جاري بناء الشاشة الوهمية (Xvfb) داخل السيرفر...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    
    time.sleep(2)
    
    try:
        bot.edit_message_text("⏳ [2/5] جاري تجهيز المتصفح المضاد للاكتشاف...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        
        driver = uc.Chrome(
            options=options, 
            use_subprocess=True, 
            driver_executable_path="/usr/bin/chromedriver",
            browser_executable_path="/usr/bin/chromium"
        )
        
        bot.edit_message_text("⏳ [3/5] تم تشغيل المحرك! جاري خداع أنظمة جوجل...", chat_id=message.chat.id, message_id=msg.message_id)
        
        driver.get("https://accounts.google.com")
        time.sleep(3) 
        
        bot.edit_message_text("⏳ [4/5] جاري الدخول للرابط الخاص بك...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(target_url) # هنا نستخدم الرابط الذي أرسلته في المحادثة
        
        bot.edit_message_text("⏳ [5/5] جاري الضغط على زر الموافقة...", chat_id=message.chat.id, message_id=msg.message_id)
        
        try:
            time.sleep(5) 
            
            js_script = """
            var btn = document.getElementById('confirm');
            if(btn) {
                btn.click();
                return true;
            }
            return false;
            """
            clicked = driver.execute_script(js_script)
            
            if not clicked:
                understand_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "confirm"))
                )
                understand_btn.click()
                
            time.sleep(6) 
        except Exception as e:
            print("لم يتمكن من الضغط على الزر: ", e)

        screenshot = driver.get_screenshot_as_png()
        photo = BytesIO(screenshot)
        photo.name = 'screen.png'
        
        bot.delete_message(message.chat.id, msg.message_id)
        live_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر للشاشة... (يتم التحديث تلقائياً)")
        
        while True:
            time.sleep(3) 
            screenshot = driver.get_screenshot_as_png()
            photo = BytesIO(screenshot)
            photo.name = 'screen.png'
            
            try:
                bot.edit_message_media(
                    chat_id=message.chat.id,
                    message_id=live_msg.message_id,
                    media=InputMediaPhoto(photo, caption="🔴 بث مباشر للشاشة... (يتم التحديث تلقائياً)")
                )
            except Exception as update_error:
                if "is not modified" in str(update_error).lower():
                    continue
                else:
                    pass
            
    except Exception as e:
        error_details = traceback.format_exc()
        bot.send_message(message.chat.id, f"❌ حدث خطأ:\n{e}\n\nالتفاصيل:\n{error_details[-800:]}")
    finally:
        if 'driver' in locals() and driver is not None:
            driver.quit()
        if 'display' in locals():
            display.stop()

print("جاري تشغيل خادم الويب الوهمي لتخطي فحص Koyeb...")
threading.Thread(target=run_dummy_server, daemon=True).start()

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر...")
bot.infinity_polling()
