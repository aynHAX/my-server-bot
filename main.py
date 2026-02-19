import telebot
import os
import time
import traceback
from io import BytesIO
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth # استيراد مكتبة التمويه

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-03-3bc2ceea09ce%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c%23Email%3Dstudent-04-f7e00356523c%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-03-3bc2ceea09ce%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c&token=G4lne3KeVX2ubqrjqo_yagH22FyVmEqCPcujPxLnxjA"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء تشغيل متصفح Brave وبث الشاشة.")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ [1/4] جاري تجهيز إعدادات التمويه (Stealth) لتخطي حماية جوجل...")
    
    options = Options()
    options.binary_location = "/usr/bin/brave-browser"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito") 
    
    # --- إعدادات تخطي الحماية (Anti-Bot) ---
    # 1. إخفاء حقيقة أننا نستخدم نظام آلي
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    # 2. تزييف هوية المتصفح ليبدو كأنه يعمل من كمبيوتر ويندوز عادي وليس سيرفر لينكس
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # --- إعدادات توفير الذاكرة (RAM) الإجبارية ---
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=1280,720") 
    options.add_argument("--js-flags=--expose-gc") 
    
    try:
        bot.edit_message_text("⏳ [2/4] جاري تشغيل محرك Brave مع التمويه...", chat_id=message.chat.id, message_id=msg.message_id)
        driver = webdriver.Chrome(options=options)
        
        # --- تطبيق مكتبة Stealth ---
        # هذا الجزء يغير بصمة الـ JavaScript للمتصفح ليخدع جوجل تماماً
        stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        
        bot.edit_message_text("⏳ [3/4] تم تشغيل المحرك! جاري الاتصال بالرابط...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(TARGET_URL)
        
        bot.edit_message_text("✅ [4/4] تم فتح الرابط بنجاح! جاري بدء البث المباشر 📸...", chat_id=message.chat.id, message_id=msg.message_id)
        
        while True:
            screenshot = driver.get_screenshot_as_png()
            photo = BytesIO(screenshot)
            photo.name = 'screen.png'
            
            bot.send_photo(message.chat.id, photo)
            time.sleep(3) 
            
    except Exception as e:
        error_details = traceback.format_exc()
        bot.send_message(message.chat.id, f"❌ حدث خطأ:\n{e}\n\nالتفاصيل:\n{error_details[-800:]}")
    finally:
        if 'driver' in locals() and driver is not None:
            driver.quit()

print("البوت يعمل الآن ومستعد للبث...")
bot.infinity_polling()
