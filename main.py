import telebot
import os
import time
import threading
import io
import shutil
import re
import atexit
from datetime import datetime
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

# ✅ إصلاح #1: استخدام selenium العادي بدل undetected_chromedriver (غير متوافق مع Chromium)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from pyvirtualdisplay import Display

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن! تأكد من إضافته في إعدادات Koyeb.")

bot = telebot.TeleBot(TOKEN)
user_sessions = {}

# ✅ إصلاح #3: إضافة قفل للخيوط لمنع التعارض
sessions_lock = threading.Lock()

# تشغيل الشاشة الوهمية (Xvfb)
display = None
try:
    display = Display(visible=0, size=(1280, 720))
    display.start()
    print("✅ تم تشغيل الشاشة الوهمية بنجاح.")
except Exception as e:
    print(f"⚠️ تنبيه: فشل تشغيل الشاشة الوهمية: {e}")


# ✅ إصلاح #7: بحث شامل عن مسارات المتصفح والدرايفر
def find_browser_path():
    """البحث عن مسار متصفح Chromium/Chrome"""
    candidates = [
        shutil.which('chromium'),
        shutil.which('chromium-browser'),
        shutil.which('google-chrome'),
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def find_driver_path():
    """البحث عن مسار ChromeDriver"""
    candidates = [
        shutil.which('chromedriver'),
        shutil.which('chromium-driver'),
        '/usr/bin/chromedriver',
        '/usr/lib/chromium/chromedriver',
        '/usr/lib/chromium-browser/chromedriver',
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def get_driver():
    browser_path = find_browser_path()
    driver_path = find_driver_path()

    if not browser_path:
        raise Exception("لم يتم العثور على متصفح Chromium! تأكد من تثبيته في Dockerfile.")
    if not driver_path:
        raise Exception("لم يتم العثور على ChromeDriver! تأكد من تثبيته في Dockerfile.")

    print(f"🌐 المتصفح: {browser_path}")
    print(f"🔧 الدرايفر: {driver_path}")

    options = Options()
    options.binary_location = browser_path
    options.page_load_strategy = 'eager'

    # ✅ إصلاح #1: أكواد تخفي يدوية بدل مكتبة uc
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # خيارات أساسية للتشغيل في Docker
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--incognito')
    options.add_argument('--disable-features=Translate')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    service = Service(executable_path=driver_path)
    driver = webdriver.Chrome(service=service, options=options)

    # حقن سكربت إخفاء بصمة Selenium
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = {runtime: {}};
            '''
        })
    except Exception:
        pass

    driver.set_page_load_timeout(45)
    return driver


# ✅ إصلاح #2: دوال تنظيف آمنة للمتصفح
def safe_quit_driver(driver):
    """إغلاق المتصفح بأمان"""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass


def cleanup_session(chat_id):
    """تنظيف جلسة مستخدم واحد"""
    with sessions_lock:
        if chat_id in user_sessions:
            session = user_sessions[chat_id]
            session['running'] = False
            safe_quit_driver(session.get('driver'))
            del user_sessions[chat_id]


# ✅ إصلاح #10: تنظيف شامل عند إغلاق البوت
def cleanup_all():
    """تنظيف جميع الجلسات عند إغلاق البوت"""
    print("🧹 جاري تنظيف جميع الجلسات...")
    with sessions_lock:
        for chat_id in list(user_sessions.keys()):
            session = user_sessions[chat_id]
            session['running'] = False
            safe_quit_driver(session.get('driver'))
        user_sessions.clear()
    if display:
        try:
            display.stop()
        except Exception:
            pass
    print("✅ تم التنظيف بنجاح.")


atexit.register(cleanup_all)


def is_driver_alive(driver):
    """فحص إذا كان المتصفح لا يزال يعمل"""
    try:
        _ = driver.title
        return True
    except Exception:
        return False


def create_control_panel():
    markup = InlineKeyboardMarkup()
    btn_stop = InlineKeyboardButton("⏹ إيقاف البث", callback_data="stop_stream")
    btn_refresh = InlineKeyboardButton("🔄 تحديث الصفحة يدوياً", callback_data="refresh_page")
    markup.row(btn_stop, btn_refresh)
    return markup


def stream_loop(chat_id, generation):
    """حلقة البث المستمر مع حماية بالـ generation"""
    with sessions_lock:
        if chat_id not in user_sessions:
            return
        session = user_sessions[chat_id]

    driver = session['driver']
    flash_state = True
    error_count = 0
    driver_error_count = 0

    while session['running'] and session.get('generation') == generation:
        time.sleep(4)

        # ✅ فحص مزدوج بعد النوم
        if not session['running'] or session.get('generation') != generation:
            break

        try:
            # التبديل لأحدث نافذة
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])

            current_url = driver.current_url
            status_msg = "جاري المراقبة والمعالجة..."

            # ---------------------------------------------------------
            # 🤖 نظام الطيار الآلي المتكامل
            # ---------------------------------------------------------
            if not session.get('shell_opened'):
                # 1. الضغط على زر I understand
                try:
                    btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'I understand')]")
                    if btns and btns[0].is_displayed():
                        btns[0].click()
                        status_msg = "تم الضغط على I understand ✔️"
                        time.sleep(2)
                except Exception:
                    pass

                # 2. القفز التلقائي إلى الشاشة السوداء
                if "console.cloud.google.com" in current_url or "myaccount.google.com" in current_url:
                    project_id = session.get('project_id')
                    if project_id:
                        status_msg = "🚀 جاري القفز إلى الشاشة السوداء..."
                        shell_url = f"https://shell.cloud.google.com/?project={project_id}&pli=1&show=terminal"
                        try:
                            driver.get(shell_url)
                            session['shell_opened'] = True
                            time.sleep(4)
                        except Exception:
                            pass
            else:
                # 3. توثيق الشل التلقائي (Authorize)
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
                    except Exception:
                        pass

                if session.get('authorized'):
                    status_msg = "✅ الشل جاهز للأوامر الآن"
                elif "جاري" not in status_msg:
                    status_msg = "✅ Cloud Shell يعمل الآن (بانتظار التوثيق إن وُجد)"

            # ---------------------------------------------------------

            # 📸 التقاط الصورة
            png_data = driver.get_screenshot_as_png()
            bio = io.BytesIO(png_data)
            bio.name = f'image_{int(time.time())}_{id(bio)}.png'

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
            driver_error_count = 0

        except Exception as e:
            err_msg = str(e).lower()

            # تجاهل خطأ "الرسالة لم تتغير"
            if "message is not modified" in err_msg:
                continue

            error_count += 1

            # ✅ إصلاح #9: استخراج وقت الانتظار الفعلي
            if "too many requests" in err_msg or "retry after" in err_msg:
                wait_match = re.search(r'retry after (\d+)', err_msg)
                wait_time = int(wait_match.group(1)) if wait_match else 3
                time.sleep(wait_time)

            # ✅ إصلاح #8: كشف تعطل المتصفح وإعادة تشغيله
            elif any(keyword in err_msg for keyword in [
                'session', 'disconnected', 'no such window',
                'crashed', 'not reachable', 'unable to evaluate'
            ]):
                driver_error_count += 1
                if driver_error_count >= 3:
                    try:
                        bot.send_message(chat_id, "⚠️ المتصفح تعطل! جاري إعادة التشغيل التلقائي...")
                    except Exception:
                        pass
                    try:
                        safe_quit_driver(driver)
                        new_driver = get_driver()
                        session['driver'] = new_driver
                        driver = new_driver
                        driver.get(session.get('url', 'about:blank'))
                        session['shell_opened'] = False
                        session['authorized'] = False
                        driver_error_count = 0
                        error_count = 0
                        time.sleep(3)
                        try:
                            bot.send_message(chat_id, "✅ تم إعادة تشغيل المتصفح بنجاح!")
                        except Exception:
                            pass
                    except Exception as restart_err:
                        try:
                            bot.send_message(chat_id, f"❌ فشل إعادة تشغيل المتصفح:\n`{str(restart_err)[:200]}`", parse_mode="Markdown")
                        except Exception:
                            pass
                        session['running'] = False
                        break

            elif error_count >= 5:
                try:
                    driver.refresh()
                    error_count = 0
                except Exception:
                    driver_error_count += 1

    print(f"🛑 انتهت حلقة البث للمستخدم {chat_id}")


def start_stream(chat_id, url):
    # ✅ إصلاح #5: إيقاف البث القديم أولاً
    old_driver = None
    with sessions_lock:
        if chat_id in user_sessions:
            old_session = user_sessions[chat_id]
            old_session['running'] = False
            old_session['generation'] = old_session.get('generation', 0) + 1
            old_driver = old_session.get('driver')

    bot.send_message(chat_id, "⚡ جاري تجهيز المتصفح (بث مستمر بدون توقف)...")

    # الانتظار حتى تتوقف الحلقة القديمة
    if old_driver:
        time.sleep(5)

    project_match = re.search(r'(qwiklabs-gcp-[\w-]+)', url)
    project_id = project_match.group(1) if project_match else None

    # إنشاء أو إعادة استخدام المتصفح
    try:
        driver = None
        if old_driver and is_driver_alive(old_driver):
            driver = old_driver
            print(f"♻️ إعادة استخدام المتصفح للمستخدم {chat_id}")
        else:
            safe_quit_driver(old_driver)
            driver = get_driver()
            print(f"🆕 متصفح جديد للمستخدم {chat_id}")
    except Exception as e:
        bot.send_message(chat_id, f"⚠️ خطأ في إقلاع المتصفح:\n`{str(e)[:300]}`", parse_mode="Markdown")
        return

    generation = int(time.time())

    with sessions_lock:
        user_sessions[chat_id] = {
            'driver': driver,
            'running': False,
            'message_id': None,
            'url': url,
            'project_id': project_id,
            'shell_opened': False,
            'authorized': False,
            'generation': generation
        }

    session = user_sessions[chat_id]

    try:
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"⚠️ خطأ في تحميل الرابط: {e}")

    time.sleep(3)

    try:
        handles = driver.window_handles
        if handles:
            driver.switch_to.window(handles[-1])

        png_data = driver.get_screenshot_as_png()
        bio = io.BytesIO(png_data)
        bio.name = f'image_{int(time.time())}.png'

        msg = bot.send_photo(
            chat_id,
            bio,
            caption="🔴 بث حي ومستمر...\n📌 الحالة: بدء البث...\n⏱ جاري الاتصال...",
            reply_markup=create_control_panel()
        )

        session['message_id'] = msg.message_id
        session['running'] = True

        t = threading.Thread(target=stream_loop, args=(chat_id, generation), daemon=True)
        t.start()

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ فشل في اللقطة الأولى:\n`{str(e)[:200]}`", parse_mode="Markdown")
        cleanup_session(chat_id)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! البوت يعمل الآن بالنسخة المُصلَحة. أرسل الرابط. 🚀")


# ✅ إصلاح #4: فحص message.text ضد None
@bot.message_handler(func=lambda message: message.text and message.text.startswith('https://www.skills.google/google_sso'))
def handle_qwiklabs_url(message):
    threading.Thread(target=start_stream, args=(message.chat.id, message.text), daemon=True).start()


@bot.message_handler(func=lambda message: message.text and message.text.startswith('http') and not message.text.startswith('https://www.skills.google/google_sso'))
def handle_invalid_url(message):
    bot.reply_to(message, "❌ عذراً، يجب أن يبدأ الرابط بـ:\n`https://www.skills.google/google_sso`", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    try:
        with sessions_lock:
            if chat_id not in user_sessions:
                bot.answer_callback_query(call.id, "لا توجد جلسة نشطة.")
                return
            session = user_sessions[chat_id]

        if call.data == "stop_stream":
            session['running'] = False
            session['generation'] = session.get('generation', 0) + 1
            bot.answer_callback_query(call.id, "تم إيقاف البث.")
            try:
                bot.edit_message_caption(
                    "🛑 تم إيقاف البث.",
                    chat_id=chat_id,
                    message_id=session['message_id']
                )
            except Exception:
                pass
            try:
                session['driver'].get("about:blank")
            except Exception:
                pass

        elif call.data == "refresh_page":
            bot.answer_callback_query(call.id, "جاري التحديث يدوياً...")
            try:
                session['driver'].refresh()
            except Exception:
                pass

    except Exception:
        pass


# ✅ إصلاح #6: إعادة تشغيل تلقائية عند فشل الاتصال
def run_bot():
    print("✅ البوت المُصلَح يعمل الآن...")
    while True:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ خطأ في الاتصال بتيليغرام: {e}")
            print("🔄 إعادة الاتصال بعد 5 ثوانٍ...")
            time.sleep(5)


if __name__ == '__main__':
    run_bot()
