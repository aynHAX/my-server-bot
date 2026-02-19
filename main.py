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

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# الرابط الجديد الذي طلبته
TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-00-1557cd67848d%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8%23Email%3Dstudent-04-07815351e64b%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-00-1557cd67848d%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8&token=SoqLeEqqZa1uhh769bUBkXuw1c5Qq5dC9YRony0s1Bk"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث بالطريقة الخارقة 🚀")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ جاري تهيئة النظام وبدء الشاشة الوهمية...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    
    try:
        options = uc.ChromeOptions()
        options.binary_location = "/usr/bin/chromium"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        
        bot.edit_message_text("⏳ جاري تشغيل المتصفح والدخول للموقع...", chat_id=message.chat.id, message_id=msg.message_id)
        driver = uc.Chrome(options=options, use_subprocess=True, driver_executable_path="/usr/bin/chromedriver")
        
        driver.get("https://accounts.google.com")
        time.sleep(3) 
        
        driver.get(TARGET_URL)
        
        bot.edit_message_text("⏳ تم الوصول! جاري اختراق زر 'I understand' وإجباره على الضغط...", chat_id=message.chat.id, message_id=msg.message_id)
        time.sleep(6) 
        
        try:
            # حقن سكربت جافاسكريبت للبحث عن الزر مهما كان مخفياً والضغط عليه
            js_click_code = """
            var elements = document.querySelectorAll('span, button, div, a');
            for (var i = 0; i < elements.length; i++) {
                var text = elements[i].innerText || elements[i].textContent;
                if (text && (text.trim().toLowerCase() === 'i understand' || text.trim() === 'أفهم' || text.trim() === 'أوافق')) {
                    elements[i].click();
                    return true;
                }
            }
            return false;
            """
            is_clicked = driver.execute_script(js_click_code)
            
            if not is_clicked:
                btn = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//*[contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'i understand')]"))
                )
                driver.execute_script("arguments[0].click();", btn)
                
            time.sleep(7) 
        except Exception as e:
            print("لم يتم العثور على الزر: ", e)

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

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر...")
bot.infinity_polling()
