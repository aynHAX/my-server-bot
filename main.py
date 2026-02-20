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

# ---- المكتبات الجديدة لإنشاء الخادم الوهمي ----
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

# إعداد خادم الويب الوهمي للرد على فحوصات Koyeb
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is Healthy and Running!")
    
    # إخفاء سجلات الخادم حتى لا تزعجنا في الـ Logs
    def log_message(self, format, *args):
        pass

def run_dummy_server():
    # Koyeb تستخدم المنفذ 8000 بشكل افتراضي
    port = int(os.environ.get("PORT", 8000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# ------------------------------------------------

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-04-7870bd398a02%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253D79l45xKEQwWJhKBuRX2Hw9ozw-4rRZFXpDmVU17TSC8%23Email%3Dstudent-04-07815351e64b%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-04-7870bd398a02%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253D79l45xKEQwWJhKBuRX2Hw9ozw-4rRZFXpDmVU17TSC8&token=7DjJMBeGTVygdCnV89AwF39SW97qgSJPj_-4nldLsLk"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث بالطريقة الخارقة 🚀")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ [1/5] جاري بناء الشاشة الوهمية (Xvfb) داخل السيرفر...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    
    try:
        bot.edit_message_text("⏳ [2/5] جاري تجهيز المتصفح المضاد للاكتشاف...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        options.binary_location = "/usr/bin/chromium"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        
        driver = uc.Chrome(options=options, use_subprocess=True, driver_executable_path="/usr/bin/chromedriver")
        
        bot.edit_message_text("⏳ [3/5] تم تشغيل المحرك! جاري خداع أنظمة جوجل...", chat_id=message.chat.id, message_id=msg.message_id)
        
        driver.get("https://accounts.google.com")
        time.sleep(3) 
        
        bot.edit_message_text("⏳ [4/5] جاري الدخول للرابط الهدف...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(TARGET_URL)
        
        bot.edit_message_text("⏳ [5/5] جاري الضغط على زر الموافقة...", chat_id=message.chat.id, message_id=msg.message_id)
        
        try:
            time.sleep(5) 
            
            # استهداف زر confirm مباشرة كما اكتشفنا
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


# ---- تشغيل الخادم الوهمي في الخلفية قبل تشغيل البوت ----
print("جاري تشغيل خادم الويب الوهمي لتخطي فحص Koyeb...")
threading.Thread(target=run_dummy_server, daemon=True).start()

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر...")
bot.infinity_polling()
