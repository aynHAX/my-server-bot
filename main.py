import telebot
import os
import time
import threading
import io
import shutil
import re
from datetime import datetime
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 🔥 السر الجديد: تشغيل شاشة وهمية لخداع جوجل بأننا متصفح حقيقي!
from pyvirtualdisplay import Display

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن! تأكد من إضافة BOT_TOKEN في إعدادات Koyeb.")

bot = telebot.TeleBot(TOKEN)
user_sessions = {}

# تشغيل الشاشة الوهمية على السيرفر بشكل دائم
try:
    display = Display(visible=0, size=(1280, 720))
    display.start()
except Exception as e:
    print(f"تنبيه: فشل تشغيل الشاشة الوهمية: {e}")

def get_driver():
    browser_path = shutil.which('google-chrome') or shutil.which('chromium') or shutil.which('chromium-browser')
    if not browser_path:
        raise Exception("BROWSER_MISSING")

    options = Options()
    options.page_load_strategy = 'eager' 
    
    # ❌ قمنا بحذف خيار --headless لكي يفتح المتصفح بشكله الحقيقي على الشاشة الوهمية
    options.add_argument('--incognito')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--disable-features=Translate') 
    
    # خيارات التمويه
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    options.binary_location = browser_path
    driver = webdriver.Chrome(options=options)
    
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = {runtime: {}};
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        """
    })
    
    driver.set_page_load_timeout(45) 
    return driver

def create_control_panel():
    markup = InlineKeyboardMarkup()
    btn_stop = InlineKeyboardButton("⏹ إيقاف البث", callback_data="stop_stream")
    btn_refresh = InlineKeyboardButton("🔄 تحديث الصفحة يدوياً", callback_data="refresh_page")
    markup.row(btn_stop, btn_refresh)
    return markup

def stream_loop(chat_id):
    session = user_sessions[chat_id]
    driver = session['driver']
    flash_state = True 
    error_count = 0 
    
    while session['running']:
        time.sleep(4) 
        if not session['running']:
            break
            
        try:
            if len(driver.window_handles) > 0:
                driver.switch_to.window(driver.window_handles[-1])
            
            current_url = driver.current_url
            status_msg = "جاري المراقبة والمعالجة..."

            # ---------------------------------------------------------
            # 🤖 الطيار الآلي
            # ---------------------------------------------------------
            if not session.get('shell_opened'):
                try:
                    btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'I understand')]")
                    if btns and btns[0].is_displayed():
                        btns[0].click()
                        status_msg = "تم الضغط على I understand ✔️"
                        time.sleep(2)
                except:
                    pass

                if "console.cloud.google.com" in current_url or "myaccount.google.com" in current_url:
                    project_id = session.get('project_id')
                    if project_id:
                        status_msg = f"🚀 جاري القفز إلى الشاشة السوداء..."
                        shell_url = f"https://shell.cloud.google.com/?project={project_id}&pli=1&show=terminal"
                        try:
                            driver.get(shell_url)
                            session['shell_opened'] = True
                            time.sleep(4)
                        except:
                            pass
            else:
                if not session.get('authorized'):
                    try:
                        auth_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Authorize') or contains(., 'AUTHORIZE')]")
                        for btn in auth_btns:
                            if btn.is_displayed():
                                btn.click()
                                session['authorized'] = True
                                status_msg = "تم تخطي رسالة التوثيق (Authorize) 🛡️"
                                time.sleep(2)
                                break
                    except:
                        pass
                
                if session.get('authorized'):
                    status_msg = "✅ الشل جاهز للأوامر الآن"
                elif "جاري" not in status_msg:
                    status_msg = "✅ Cloud Shell يعمل الآن (بانتظار التوثيق إن وُجد)"
            # ---------------------------------------------------------

            # أخذ الصورة وتحديثها باسم جديد لتخطي حماية تيليغرام
            png_data = driver.get_screenshot_as_png()
            bio = io.BytesIO(png_data)
            bio.name = f'image_{int(time.time())}.png'
            
            flash_state = not flash_state
            live_icon = "🔴" if flash_state else "⭕"
            now = datetime.now().strftime("%H:%M:%S")
            
            proj_text = f"📁 المشروع: {session.get('project_id')}" if session.get('project_id') else ""
            caption_text = f"{live_icon} بث حي ومستمر...\n{proj_text}\n📌 الحالة: {status_msg}\n⏱ {now}"
            
            bot.edit_message_media(
                media=InputMediaPhoto(bio, caption=caption_text),
                chat_id=chat_id,
                message_id=session['message_id'],
                reply_markup=create_control_panel()
            )
            
            error_count = 0 
            
        except Exception as e:
            err_msg = str(e).lower()
            if "message is not modified" in err_msg:
                continue
                
            error_count += 1
            if "too many requests" in err_msg or "retry after" in err_msg:
                time.sleep(2)
            elif error_count >= 3: 
                try:
                    driver.refresh()
                    error_count = 0
                except:
                    pass

def start_stream(chat_id, url):
    bot.send_message(chat_id, "⚡ جاري تشغيل المتصفح كإنسان حقيقي على استضافة Koyeb...")
    
    project_match = re.search(r'(qwiklabs-gcp-[\w-]+)', url)
    project_id = project_match.group(1) if project_match else None
    
    try:
        if chat_id not in user_sessions:
            user_sessions[chat_id] = {
                'driver': get_driver(), 
                'running': False, 
                'message_id': None, 
                'url': url,
                'project_id': project_id,
                'shell_opened': False,
                'authorized': False 
            }
        else:
            user_sessions[chat_id]['url'] = url
            user_sessions[chat_id]['project_id'] = project_id
            user_sessions[chat_id]['shell_opened'] = False
            user_sessions[chat_id]['authorized'] = False
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ المتصفح واجه مشكلة في الإقلاع:\n`{str(e)}`", parse_mode="Markdown")
        return
        
    session = user_sessions[chat_id]
    driver = session['driver']
    session['running'] = False 
    time.sleep(1) 
    
    try:
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            pass 
        
    time.sleep(2) 
    
    try:
        if len(driver.window_handles) > 0:
            driver.switch_to.window(driver.window_handles[-1])
        png_data = driver.get_screenshot_as_png()
        bio = io.BytesIO(png_data)
        bio.name = f'image_{int(time.time())}.png'
        
        msg = bot.send_photo(
            chat_id, 
            bio, 
            caption=f"🔴 بث حي ومستمر...\n📌 الحالة: بدء المراقبة التلقائية...\n⏱ جاري الاتصال...",
            reply_markup=create_control_panel()
        )
        
        session['message_id'] = msg.message_id
        session['running'] = True
        
        threading.Thread(target=stream_loop, args=(chat_id,)).start()
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ محاولة الاتصال الأولى متعثرة، لكن البوت سيستمر في المحاولة.")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! وضع 'الشاشة الوهمية' مفعل لتخطي حماية تسجيل الدخول 🛡️. أرسل رابط Qwiklabs الآن.")

@bot.message_handler(func=lambda message: message.text.startswith('https://www.skills.google/google_sso'))
def handle_qwiklabs_url(message):
    threading.Thread(target=start_stream, args=(message.chat.id, message.text)).start()

@bot.message_handler(func=lambda message: message.text.startswith('http') and not message.text.startswith('https://www.skills.google/google_sso'))
def handle_invalid_url(message):
    bot.reply_to(message, "❌ عذراً، يجب أن يبدأ الرابط بـ:\n`https://www.skills.google/google_sso`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    try:
        if chat_id not in user_sessions:
            bot.answer_callback_query(call.id, "لا توجد جلسة نشطة.")
            return
            
        session = user_sessions[chat_id]
        
        if call.data == "stop_stream":
            session['running'] = False
            bot.answer_callback_query(call.id, "تم إيقاف البث.")
            bot.edit_message_caption("🛑 تم إيقاف البث.", chat_id=chat_id, message_id=session['message_id'])
            try:
                session['driver'].get("about:blank")
            except: pass
            
        elif call.data == "refresh_page":
            bot.answer_callback_query(call.id, "جاري الإنعاش يدوياً...")
            try:
                session['driver'].refresh()
            except: pass
    except:
        pass

print("البوت يعمل الآن بكفاءة (تم تفعيل الشاشة الوهمية Xvfb للعمل على Koyeb)...")
bot.polling()
