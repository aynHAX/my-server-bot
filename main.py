import telebot
import os
import time
import traceback
from io import BytesIO
import undetected_chromedriver as uc
from pyvirtualdisplay import Display

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-03-3bc2ceea09ce%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c%23Email%3Dstudent-04-f7e00356523c%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-03-3bc2ceea09ce%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253Dx5Iil4oqpybj7DB7nyQW5uSxLmt-_bzs1rTvA19Nu_c&token=G4lne3KeVX2ubqrjqo_yagH22FyVmEqCPcujPxLnxjA"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! أرسل الأمر /live لبدء البث بالطريقة الخارقة 🚀")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ [1/4] جاري بناء الشاشة الوهمية (Xvfb) داخل السيرفر...")
    
    # 1. تشغيل الشاشة الوهمية
    # هذا يجعل المتصفح يظن أنه يعمل على بي سي حقيقي تماماً!
    display = Display(visible=0, size=(1280, 720))
    display.start()
    
    bot.edit_message_text("⏳ [2/4] جاري تجهيز المتصفح المضاد للاكتشاف (Undetected-Chromedriver)...", chat_id=message.chat.id, message_id=msg.message_id)
    
    options = uc.ChromeOptions()
    options.binary_location = "/usr/bin/brave-browser"
    
    # تحذير: لا تضف أمر headless أبداً! المتصفح سيعمل كأنه مرئي
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    options.add_argument("--disable-gpu")
    
    # تكتيك إضافي: فتح موقع جوجل الرئيسي أولاً لبناء سجل تصفح نظيف قبل الدخول لرابط تسجيل الدخول المعقد
    
    try:
        # تشغيل المحرك
        driver = uc.Chrome(options=options, use_subprocess=True)
        
        bot.edit_message_text("⏳ [3/4] تم تشغيل المحرك! جاري خداع أنظمة جوجل...", chat_id=message.chat.id, message_id=msg.message_id)
        
        # التكتيك: الدخول لجوجل العادي أولاً
        driver.get("https://accounts.google.com")
        time.sleep(3) # ننتظر قليلاً لتبادل ملفات الارتباط (Cookies)
        
        # الآن ننتقل للرابط الهدف
        bot.edit_message_text("⏳ [4/4] جاري الدخول للرابط الهدف وبدء البث...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(TARGET_URL)
        
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
        # إيقاف الشاشة الوهمية لتوفير الذاكرة
        if 'display' in locals():
            display.stop()

print("البوت الاحترافي يعمل الآن ومستعد للبث...")
bot.infinity_polling()
