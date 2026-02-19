import telebot
import os
import time
import traceback
from io import BytesIO
import undetected_chromedriver as uc
from pyvirtualdisplay import Display
from telebot.types import InputMediaPhoto

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

TARGET_URL = "https://www.skills.google/google_sso?fallback=https%3A%2F%2Faccounts.google.com%2FAddSession%3Fservice%3Daccountsettings%26sarp%3D1%26continue%3Dhttps%253A%252F%252Fconsole.cloud.google.com%252Fhome%252Fdashboard%253Fproject%253Dqwiklabs-gcp-00-1557cd67848d%2526walkthrough_id%253Dhttps%25253A%25252F%25252Fwww.skills.google%25252Fdisplay_in_context%25253Fdisplay_token%25253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8%23Email%3Dstudent-04-07815351e64b%40qwiklabs.net&relay=https%3A%2F%2Fconsole.cloud.google.com%2Fhome%2Fdashboard%3Fproject%3Dqwiklabs-gcp-00-1557cd67848d%26walkthrough_id%3Dhttps%253A%252F%252Fwww.skills.google%252Fdisplay_in_context%253Fdisplay_token%253D0seYTyegfp9dS1q8fDc7knKSCJST2qxJz3097rH8lO8&token=SoqLeEqqZa1uhh769bUBkXuw1c5Qq5dC9YRony0s1Bk"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "أهلاً بك! النظام جاهز بالكامل. أرسل /live للبدء 🚀")

@bot.message_handler(commands=['live'])
def start_livestream(message):
    msg = bot.reply_to(message, "⏳ [1/6] جاري تهيئة الشاشة الوهمية (Xvfb)...")
    
    display = None
    driver = None
    
    try:
        display = Display(visible=0, size=(1280, 720))
        display.start()
        
        bot.edit_message_text("⏳ [2/6] جاري تشغيل المتصفح بأمان...", chat_id=message.chat.id, message_id=msg.message_id)
        
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--incognito")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        
        # التوجيه الصارم للمسارات لمنع التجمد أثناء البحث عن المتصفح
        driver = uc.Chrome(
            options=options,
            browser_executable_path="/usr/bin/chromium",
            driver_executable_path="/usr/bin/chromedriver",
            use_subprocess=True
        )
        
        # وضع حد زمني للتحميل حتى لا يعلق البوت للأبد
        driver.set_page_load_timeout(30)
        
        bot.edit_message_text("⏳ [3/6] تم تشغيل المحرك! جاري خداع جوجل...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get("https://accounts.google.com")
        time.sleep(3) 
        
        bot.edit_message_text("⏳ [4/6] جاري الدخول للرابط الهدف...", chat_id=message.chat.id, message_id=msg.message_id)
        driver.get(TARGET_URL)
        time.sleep(5) # انتظار أولي لتحميل الصفحة
        
        bot.edit_message_text("⏳ [5/6] جاري اختراق وتخطي صفحة الشروط...", chat_id=message.chat.id, message_id=msg.message_id)
        
        # ---------------------------------------------------------
        # كود الجافاسكريبت النهائي للبحث والضغط (مقاوم للفشل)
        # ---------------------------------------------------------
        js_click_code = """
        let clicked = false;
        let elements = document.querySelectorAll('button, div, span, a');
        for (let i = 0; i < elements.length; i++) {
            let text = elements[i].innerText || elements[i].textContent;
            if (text && text.toLowerCase().includes('i understand')) {
                elements[i].style.border = "5px solid red"; // تلوين الزر لتأكيد إيجاده
                elements[i].click();
                clicked = true;
                break;
            }
        }
        return clicked;
        """
        
        # محاولة الضغط 3 مرات متتالية لضمان النتيجة
        for attempt in range(3):
            result = driver.execute_script(js_click_code)
            if result:
                print("تم الضغط بنجاح بواسطة JS!")
                time.sleep(5) # انتظار الانتقال للوحة التحكم بعد الضغط
                break
            time.sleep(2) # إذا لم يجده، ينتظر ثانيتين ويحاول مجدداً
            
        bot.edit_message_text("✅ [6/6] تمت العملية! جاري بدء البث المباشر...", chat_id=message.chat.id, message_id=msg.message_id)
        time.sleep(2)

        # التقاط أول صورة وبدء البث
        screenshot = driver.get_screenshot_as_png()
        photo = BytesIO(screenshot)
        photo.name = 'screen.png'
        
        bot.delete_message(message.chat.id, msg.message_id)
        live_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر للشاشة... (يتم التحديث تلقائياً)")
        
        # حلقة البث المباشر
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
        bot.send_message(message.chat.id, f"❌ حدث خطأ غير متوقع:\n{e}\n\nالتفاصيل:\n{error_details[-800:]}")
    finally:
        try:
            if driver is not None:
                driver.quit()
        except:
            pass
        try:
            if display is not None:
                display.stop()
        except:
            pass

print("البوت الاحترافي يعمل الآن ومستعد للبث المستمر...")
bot.infinity_polling()
