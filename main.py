import telebot
import os
import time
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-03-3bc2ceea09ce%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c%23Email%3Dstudent-04-f7e00356523c%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-03-3bc2ceea09ce%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c&token=G4lne3KeVX2ubqrjqo_yagH22FyVmEqCPcujPxLnxjA"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء تشغيل متصفح Brave وبث الشاشة.")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ جاري تهيئة متصفح Brave والاتصال بالرابط...")
    
    # إعدادات متصفح Brave
    options = Options()
    options.binary_location = "/usr/bin/brave-browser"
    options.add_argument("--headless") # إجباري لخوادم Koyeb
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    
    try:
        # تشغيل المتصفح باستخدام WebDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(TARGET_URL)
        
        bot.edit_message_text("✅ تم الدخول للرابط! جاري بدء البث المباشر...", chat_id=message.chat.id, message_id=msg.message_id)
        
        # حلقة البث المباشر
        while True:
            # التقاط صورة للشاشة
            screenshot = driver.get_screenshot_as_png()
            photo = BytesIO(screenshot)
            photo.name = 'screen.png'
            
            # إرسال الصورة للمستخدم
            bot.send_photo(message.chat.id, photo)
            
            # تأخير زمني لتجنب حظر تيليغرام
            time.sleep(2) 
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ حدث خطأ أثناء تشغيل المتصفح: {e}")
    finally:
        if 'driver' in locals():
            driver.quit()

print("البوت يعمل الآن ومستعد للبث...")
bot.infinity_polling()
