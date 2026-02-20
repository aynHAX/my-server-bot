import telebot
import os
import time
import traceback
from io import BytesIO
import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from telebot.types import InputMediaPhoto
from PIL import Image

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

def get_light_jpg_screenshot(driver):
    png_data = driver.get_screenshot_as_png()
    img = Image.open(BytesIO(png_data))
    img = img.convert('RGB')
    img.thumbnail((800, 600)) 
    output = BytesIO()
    img.save(output, format='JPEG', quality=40, optimize=True)
    output.seek(0)
    output.name = 'screen.jpg'
    return output

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث والأتمتة 🚀")

@bot.message_handler(commands=['live'])
def ask_for_sso_url(message):
    # الخطوة 1: طلب رابط تسجيل الدخول
    msg = bot.reply_to(message, "🔗 1. الرجاء إرسال **رابط تسجيل الدخول الأول** (skills.google...):")
    bot.register_next_step_handler(msg, ask_for_shell_url)

def ask_for_shell_url(message):
    sso_url = message.text
    if not sso_url.startswith("http"):
        bot.reply_to(message, "❌ الرابط غير صالح. أرسل /live للمحاولة مجدداً.")
        return
        
    # الخطوة 2: طلب رابط الشيل المخصص
    msg = bot.reply_to(message, "💻 2. ممتاز! الآن أرسل **رابط الـ Cloud Shell** الخاص بالمشروع (shell.cloud.google.com/?project=...):")
    bot.register_next_step_handler(msg, start_livestream, sso_url)

def start_livestream(message, sso_url):
    shell_url = message.text
    if not shell_url.startswith("http"):
        bot.reply_to(message, "❌ الرابط غير صالح. أرسل /live للمحاولة مجدداً.")
        return

    msg = bot.reply_to(message, "⏳ [1/5] جاري بناء الشاشة الوهمية (Xvfb)...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    time.sleep(2)
    
    try:
        bot.edit_message_text("⏳ [2/5] جاري تشغيل المتصفح...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'
        options.add_argument("--disable-site-isolation-trials")
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
        driver.set_page_load_timeout(30)
        
        bot.edit_message_text("⏳ [3/5] تم تشغيل المحرك! بدء البث المباشر...", chat_id=message.chat.id, message_id=msg.message_id)
        
        driver.get("https://accounts.google.com")
        
        time.sleep(2)
        bot.delete_message(message.chat.id, msg.message_id)
        
        photo = get_light_jpg_screenshot(driver)
        live_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر (جاري التهيئة وتجهيز المتصفح)...")
        
        # --- الدخول لرابط الموافقة ---
        try:
            driver.get(sso_url)
        except Exception:
            pass 
            
        time.sleep(3)
        try:
            photo = get_light_jpg_screenshot(driver)
            bot.edit_message_media(chat_id=message.chat.id, message_id=live_msg.message_id, media=InputMediaPhoto(photo, caption="🔴 بث مباشر (تم فتح رابط التسجيل، جاري البحث عن الزر)..."))
        except: pass
        
        # --- الضغط على الزر ---
        try:
            js_script = "var btn = document.getElementById('confirm'); if(btn) { btn.click(); return true; } return false;"
            clicked = driver.execute_script(js_script)
            if not clicked:
                understand_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "confirm")))
                understand_btn.click()
        except Exception as e:
            print("لم يتم العثور على الزر أو تم تجاوزه.")

        time.sleep(3) # انتظار قصير لقبول جوجل لتسجيل الدخول
        
        # --- الانتقال المباشر لـ Cloud Shell المخصص ---
        try:
            photo = get_light_jpg_screenshot(driver)
            bot.edit_message_media(chat_id=message.chat.id, message_id=live_msg.message_id, media=InputMediaPhoto(photo, caption="🔴 بث مباشر (تمت الموافقة! جاري فتح الـ Cloud Shell)..."))
        except: pass
        
        try:
            driver.get(shell_url) # سيتم فتح الرابط المخصص الذي أدخلته هنا
        except Exception:
            pass # نتجاهل خطأ انتهاء وقت التحميل إذا كان الـ Shell ثقيلاً

        # --- حلقة البث المباشر المستمرة ---
        while True:
            time.sleep(3) 
            try:
                photo = get_light_jpg_screenshot(driver)
                bot.edit_message_media(
                    chat_id=message.chat.id,
                    message_id=live_msg.message_id,
                    media=InputMediaPhoto(photo, caption="🔴 بث مباشر لـ Cloud Shell... (يتم التحديث تلقائياً)")
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
            try: driver.quit()
            except: pass
        if 'display' in locals():
            try: display.stop()
            except: pass

print("جاري تشغيل خادم الويب الوهمي لتخطي فحص Koyeb...")
threading.Thread(target=run_dummy_server, daemon=True).start()

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر بصور خفيفة...")
bot.infinity_polling()
