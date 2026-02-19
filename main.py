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

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-00-1557cd67848d%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8%23Email%3Dstudent-04-07815351e64b%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-00-1557cd67848d%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8&token=SoqLeEqqZa1uhh769bUBkXuw1c5Qq5dC9YRony0s1Bk"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث بالطريقة الخارقة 🚀")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ [1/5] جاري بناء الشاشة الوهمية (Xvfb) داخل السيرفر...")
    
    display = Display(visible=0, size=(1280, 720))
    display.start()
    
    try:
        bot.edit_message_text("⏳ [2/5] جاري تجهيز المتصفح المضاد للاكتشاف (بدون تحميل خارجي)...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        # توجيه المكتبة للمتصفح المثبت في النظام
        options.binary_location = "/usr/bin/chromium"
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        
        # إجبار المكتبة على استخدام الدرايفر المثبت مسبقاً لمنع أخطاء فك الضغط
        driver = uc.Chrome(options=options, use_subprocess=True, driver_executable_path="/usr/bin/chromedriver")
        
        bot.edit_message_text("⏳ [3/5] تم تشغيل المحرك! جاري خداع أنظمة جوجل...", chat_id=message.chat.id, message_id=msg.message_id)
        
        driver.get("https://accounts.google.com")
        time.sleep(3) 
        
        bot.edit_message_text("⏳ [4/5] جاري الدخول للرابط الهدف...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(TARGET_URL)
        
        bot.edit_message_text("⏳ [5/5] جاري البحث عن زر 'I understand' والضغط عليه...", chat_id=message.chat.id, message_id=msg.message_id)
        try:
            understand_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//*[contains(translate(text(), 'I UNDERSTAND', 'i understand'), 'i understand') or contains(text(), 'أفهم') or contains(text(), 'أوافق')]"))
            )
            understand_btn.click()
            time.sleep(5) 
        except Exception as e:
            print("لم يظهر زر 'I understand' أو تم تجاوزه بالفعل.")

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
                    print(f"Ignored minor error: {update_error}")
            
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
