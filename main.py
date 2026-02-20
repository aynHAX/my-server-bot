import telebot
import os
import time
import traceback
import urllib.parse
import re
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

# --- الخادم الوهمي لتخطي فحص Koyeb (Port 8000) ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is Healthy and Running on Koyeb!")
    
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# -------------------------------------------------

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
    bot.reply_to(message, "أهلاً بك! البوت يعمل الآن بقوة على خوادم Koyeb ☁️. أرسل /live للبدء 🚀")

@bot.message_handler(commands=['live'])
def ask_for_sso_url(message):
    msg = bot.reply_to(message, "🔗 الرجاء إرسال **رابط تسجيل الدخول** الطويل:")
    bot.register_next_step_handler(msg, start_livestream)

def start_livestream(message):
    sso_url = message.text
    if not sso_url.startswith("http"):
        bot.reply_to(message, "❌ الرابط غير صالح. أرسل /live للمحاولة مجدداً.")
        return

    # --- استخراج بيانات المشروع بذكاء ---
    try:
        parsed_url = urllib.parse.urlparse(sso_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        project_id = None
        walkthrough_id = ""
        
        if 'relay' in query_params:
            relay_url = query_params['relay'][0]
            relay_parsed = urllib.parse.urlparse(relay_url)
            relay_params = urllib.parse.parse_qs(relay_parsed.query)
            if 'project' in relay_params:
                project_id = relay_params['project'][0]
            if 'walkthrough_id' in relay_params:
                walkthrough_id = relay_params['walkthrough_id'][0]
        
        if not project_id:
            match = re.search(r'project(?:%3D|=)(qwiklabs-gcp-[a-zA-Z0-9-]+)', sso_url)
            if match:
                project_id = match.group(1)
                
        if not project_id:
            bot.reply_to(message, "❌ لم أتمكن من العثور على اسم المشروع. تأكد من الرابط.")
            return
        
        # صناعة رابط الكلاود شيل لفتح التيرمينال مباشرة
        shell_url = f"https://shell.cloud.google.com/?project={project_id}&show=terminal"
        if walkthrough_id:
            shell_url += f"&walkthrough_id={urllib.parse.quote(walkthrough_id, safe='')}"
            
        bot.send_message(message.chat.id, f"✅ تم اكتشاف المشروع: `{project_id}`\n🚀 سيتم الانتقال للـ Shell تلقائياً!", parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ حدث خطأ أثناء تحليل الرابط:\n{e}")
        return

    msg = bot.reply_to(message, "⏳ [1/7] جاري بناء الشاشة الوهمية (Xvfb) على سيرفر Koyeb...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    time.sleep(2)
    
    try:
        bot.edit_message_text("⏳ [2/7] جاري تشغيل المتصفح الخفي (Incognito)...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        options.page_load_strategy = 'eager'
        options.add_argument("--incognito")
        options.add_argument("--disable-site-isolation-trials")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        
        # مسارات الكروم الخاصة ببيئة Docker على Koyeb
        driver = uc.Chrome(
            options=options, 
            use_subprocess=True,
            driver_executable_path="/usr/bin/chromedriver",
            browser_executable_path="/usr/bin/chromium"
        )
        driver.set_page_load_timeout(30)
        
        bot.edit_message_text("⏳ [3/7] تم تشغيل المحرك! بدء البث المباشر...", chat_id=message.chat.id, message_id=msg.message_id)
        
        photo = get_light_jpg_screenshot(driver)
        live_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر (جاري التهيئة)...")
        
        # --- الدخول لرابط الموافقة المباشر ---
        try: driver.get(sso_url)
        except Exception: pass 
            
        time.sleep(3)
        try:
            photo = get_light_jpg_screenshot(driver)
            bot.edit_message_media(chat_id=message.chat.id, message_id=live_msg.message_id, media=InputMediaPhoto(photo, caption="🔴 بث مباشر (جاري البحث عن زر الموافقة الأول)..."))
        except: pass
        
        # --- الضغط على موافقة الحساب الأولى ---
        bot.edit_message_text("⏳ [4/7] جاري الضغط على موافقة الحساب...", chat_id=message.chat.id, message_id=msg.message_id)
        try:
            js_script = "var btn = document.getElementById('confirm'); if(btn) { btn.click(); return true; } return false;"
            clicked = driver.execute_script(js_script)
            if not clicked:
                understand_btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.ID, "confirm")))
                understand_btn.click()
        except Exception as e:
            print("لم يتم العثور على زر الموافقة الأول.")

        time.sleep(3) 
        
        # --- الانتقال لـ Cloud Shell ---
        bot.edit_message_text("⏳ [5/7] جاري فتح واجهة Cloud Shell...", chat_id=message.chat.id, message_id=msg.message_id)
        try: driver.get(shell_url) 
        except Exception: pass 

        # --- انتظار واجهة Cloud Shell والضغط على زر Authorize ---
        bot.edit_message_text("⏳ [6/7] جاري انتظار ظهور زر التخويل (Authorize)...", chat_id=message.chat.id, message_id=msg.message_id)
        time.sleep(12) 
        try:
            js_auth_script = """
            var btns = document.querySelectorAll('button, span, div');
            for(var i=0; i<btns.length; i++){
                if(btns[i].innerText && btns[i].innerText.trim().toLowerCase() === 'authorize'){
                    btns[i].click();
                    return true;
                }
            }
            return false;
            """
            clicked_auth = driver.execute_script(js_auth_script)
            if not clicked_auth:
                auth_btn = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'AUTHORIZE', 'authorize'), 'authorize')] | //button[contains(., 'Authorize')]"))
                )
                auth_btn.click()
        except Exception as e:
            print("لم يظهر زر Authorize.")

        time.sleep(4)

        # --- إغلاق المحرر (Editor) وترك الـ Terminal فقط ---
        bot.edit_message_text("⏳ [7/7] جاري تنظيف الشاشة وترك الـ Terminal فقط...", chat_id=message.chat.id, message_id=msg.message_id)
        try:
            js_close_editor = """
            var btns = document.querySelectorAll('button, a');
            for(var i=0; i<btns.length; i++){
                var title = btns[i].getAttribute('title') || btns[i].getAttribute('aria-label') || '';
                if(title.toLowerCase().includes('close editor') || title.toLowerCase().includes('toggle editor')){
                    btns[i].click();
                    return true;
                }
            }
            return false;
            """
            driver.execute_script(js_close_editor)
        except Exception:
            pass
            
        bot.delete_message(message.chat.id, msg.message_id)

        # --- حلقة البث المباشر المستمرة ---
        while True:
            time.sleep(3) 
            try:
                photo = get_light_jpg_screenshot(driver)
                bot.edit_message_media(
                    chat_id=message.chat.id,
                    message_id=live_msg.message_id,
                    media=InputMediaPhoto(photo, caption=f"🔴 بث مباشر للـ Terminal: {project_id}")
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

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر...")

# حماية الاتصال من الانقطاع
while True:
    try:
        bot.polling(non_stop=True, timeout=60)
    except Exception as e:
        print(f"⚠️ انقطع الاتصال، جاري إعادة المحاولة... ({e})")
        time.sleep(5)
