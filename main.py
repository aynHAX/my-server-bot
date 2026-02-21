import telebot
import os
import time
import threading
import io
import re
import random
import atexit
from datetime import datetime
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

# ✅ مكتبة التخفي المتقدمة (تعمل مع Google Chrome فقط)
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from pyvirtualdisplay import Display

# محاولة تحميل selenium-stealth للتخفي الإضافي
try:
    from selenium_stealth import stealth
    STEALTH_AVAILABLE = True
    print("✅ مكتبة selenium-stealth متاحة.")
except ImportError:
    STEALTH_AVAILABLE = False
    print("⚠️ selenium-stealth غير متاحة، سيتم استخدام التخفي اليدوي فقط.")

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن! تأكد من إضافته في إعدادات Koyeb.")

bot = telebot.TeleBot(TOKEN)
user_sessions = {}
sessions_lock = threading.Lock()

# ─────────────────────────────────────────────────────────
# 🖥️ تشغيل الشاشة الوهمية بدقة واقعية (بدل headless)
# ─────────────────────────────────────────────────────────
display = None
try:
    display = Display(visible=0, size=(1920, 1080), color_depth=24)
    display.start()
    print("✅ تم تشغيل الشاشة الوهمية (1920x1080, 24bit).")
except Exception as e:
    print(f"⚠️ فشل تشغيل الشاشة الوهمية: {e}")

# ─────────────────────────────────────────────────────────
# 🛡️ سكربت التخفي الشامل (يُحقن في كل صفحة جديدة)
# ─────────────────────────────────────────────────────────
STEALTH_JS = '''
// ===== 1. إخفاء navigator.webdriver =====
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});

// ===== 2. إضافة Plugins وهمية واقعية =====
Object.defineProperty(navigator, 'plugins', {
    get: function() {
        var plugins = [
            { name: 'Chrome PDF Plugin', description: 'Portable Document Format', filename: 'internal-pdf-viewer', length: 1 },
            { name: 'Chrome PDF Viewer', description: '', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', length: 1 },
            { name: 'Native Client', description: '', filename: 'internal-nacl-plugin', length: 2 }
        ];
        plugins.refresh = function() {};
        return plugins;
    }
});

// ===== 3. إخفاء اللغات =====
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en']
});

// ===== 4. تزوير المنصة =====
Object.defineProperty(navigator, 'platform', {
    get: () => 'Win32'
});

// ===== 5. أنوية المعالج والذاكرة =====
Object.defineProperty(navigator, 'hardwareConcurrency', {
    get: () => 8
});
Object.defineProperty(navigator, 'deviceMemory', {
    get: () => 8
});

// ===== 6. إخفاء اللمس (ليس جهاز لمس) =====
Object.defineProperty(navigator, 'maxTouchPoints', {
    get: () => 0
});

// ===== 7. محاكاة chrome runtime كاملة =====
window.chrome = {
    runtime: {
        onMessage: { addListener: function(){}, removeListener: function(){} },
        sendMessage: function(){},
        connect: function() {
            return { onMessage: { addListener: function(){} }, postMessage: function(){}, disconnect: function(){} };
        }
    },
    loadTimes: function() {
        return {
            commitLoadTime: Date.now() / 1000,
            connectionInfo: 'http/1.1',
            finishDocumentLoadTime: Date.now() / 1000,
            finishLoadTime: Date.now() / 1000,
            firstPaintAfterLoadTime: 0,
            firstPaintTime: Date.now() / 1000,
            navigationType: 'Other',
            npnNegotiatedProtocol: 'unknown',
            requestTime: Date.now() / 1000 - 0.16,
            startLoadTime: Date.now() / 1000,
            wasAlternateProtocolAvailable: false,
            wasFetchedViaSpdy: false,
            wasNpnNegotiated: false
        };
    },
    csi: function() {
        return { onloadT: Date.now(), pageT: Date.now() / 1000, startE: Date.now(), tran: 15 };
    }
};

// ===== 8. تصحيح Permissions API =====
if (window.navigator.permissions) {
    var originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = function(parameters) {
        if (parameters.name === 'notifications') {
            return Promise.resolve({ state: 'prompt' });
        }
        return originalQuery(parameters);
    };
}

// ===== 9. تزوير WebGL (بصمة كرت الشاشة) =====
try {
    var getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, arguments);
    };
} catch(e) {}

try {
    var getParameter2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter2.apply(this, arguments);
    };
} catch(e) {}

// ===== 10. إخفاء أوتوميشن من window =====
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;

// ===== 11. تصحيح toString لكل الدوال المزورة =====
var nativeToString = Function.prototype.toString;
var fakeToString = function() {
    if (this === window.navigator.permissions.query) {
        return 'function query() { [native code] }';
    }
    return nativeToString.call(this);
};
Function.prototype.toString = fakeToString;
'''


# ─────────────────────────────────────────────────────────
# 🌐 إنشاء متصفح خفي غير قابل للاكتشاف
# ─────────────────────────────────────────────────────────
def get_driver():
    """إنشاء متصفح Google Chrome متخفي بالكامل"""
    
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    
    # ✅ خيارات ضرورية لـ Docker
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # ✅ إعدادات واقعية (شاشة حقيقية، بدون علامات أوتوميشن)
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--lang=en-US')
    options.add_argument('--disable-features=Translate')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-extensions')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--ignore-certificate-errors')
    
    # ⚠️ لا نستخدم --incognito لأن Google يكشفه بسهولة
    # ⚠️ لا نستخدم --headless لأن Google يكشفه - نعتمد على Xvfb بدلاً منه
    
    print("🚀 جاري إنشاء المتصفح المتخفي...")
    
    driver = uc.Chrome(
        options=options,
        headless=False,       # ✅ False لأن Xvfb يعمل كشاشة وهمية
        use_subprocess=True,  # ✅ أكثر استقراراً في Docker
    )
    
    # ✅ تطبيق selenium-stealth (طبقة تخفي إضافية)
    if STEALTH_AVAILABLE:
        try:
            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )
            print("🛡️ تم تطبيق selenium-stealth بنجاح.")
        except Exception as e:
            print(f"⚠️ فشل تطبيق selenium-stealth: {e}")
    
    # ✅ حقن سكربت التخفي الشامل في كل صفحة
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': STEALTH_JS
        })
        print("🛡️ تم حقن سكربت التخفي في المتصفح.")
    except Exception as e:
        print(f"⚠️ فشل حقن سكربت التخفي: {e}")
    
    # ✅ تزوير User-Agent (إزالة أي أثر لـ Headless)
    try:
        ua = driver.execute_script("return navigator.userAgent")
        clean_ua = ua.replace("Headless", "").replace("headless", "")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": clean_ua,
            "platform": "Win32",
            "acceptLanguage": "en-US,en;q=0.9"
        })
        print(f"🌐 User-Agent: {clean_ua[:80]}...")
    except Exception as e:
        print(f"⚠️ فشل تعديل User-Agent: {e}")
    
    driver.set_page_load_timeout(60)
    print("✅ المتصفح جاهز ومتخفي بالكامل.")
    return driver


# ─────────────────────────────────────────────────────────
# 🧹 دوال التنظيف وإدارة الجلسات
# ─────────────────────────────────────────────────────────
def safe_quit_driver(driver):
    """إغلاق المتصفح بأمان"""
    if driver:
        try:
            driver.quit()
        except Exception:
            pass


def cleanup_session(chat_id):
    """تنظيف جلسة مستخدم"""
    with sessions_lock:
        if chat_id in user_sessions:
            session = user_sessions[chat_id]
            session['running'] = False
            safe_quit_driver(session.get('driver'))
            del user_sessions[chat_id]


def cleanup_all():
    """تنظيف جميع الجلسات عند إغلاق البوت"""
    print("🧹 جاري تنظيف جميع الجلسات...")
    with sessions_lock:
        for cid in list(user_sessions.keys()):
            user_sessions[cid]['running'] = False
            safe_quit_driver(user_sessions[cid].get('driver'))
        user_sessions.clear()
    if display:
        try:
            display.stop()
        except Exception:
            pass
    print("✅ تم التنظيف.")


atexit.register(cleanup_all)


def is_driver_alive(driver):
    """فحص هل المتصفح لا يزال يعمل"""
    try:
        _ = driver.title
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────
# 🎛️ لوحة التحكم
# ─────────────────────────────────────────────────────────
def create_control_panel():
    markup = InlineKeyboardMarkup()
    btn_stop = InlineKeyboardButton("⏹ إيقاف البث", callback_data="stop_stream")
    btn_refresh = InlineKeyboardButton("🔄 تحديث الصفحة يدوياً", callback_data="refresh_page")
    markup.row(btn_stop, btn_refresh)
    return markup


# ─────────────────────────────────────────────────────────
# 🎬 حلقة البث المستمر
# ─────────────────────────────────────────────────────────
def stream_loop(chat_id, generation):
    """حلقة البث المستمر مع حماية الجيل"""
    with sessions_lock:
        if chat_id not in user_sessions:
            return
        session = user_sessions[chat_id]

    driver = session['driver']
    flash_state = True
    error_count = 0
    driver_error_count = 0

    while session['running'] and session.get('generation') == generation:
        # ✅ تأخير عشوائي بسيط لمحاكاة سلوك بشري
        time.sleep(random.uniform(3.5, 5.0))

        if not session['running'] or session.get('generation') != generation:
            break

        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])

            current_url = driver.current_url
            status_msg = "جاري المراقبة والمعالجة..."

            # ─── 🤖 نظام الطيار الآلي ───
            if not session.get('shell_opened'):
                # 1. الضغط على I understand
                try:
                    btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'I understand')]")
                    if btns and btns[0].is_displayed():
                        # تأخير بشري قبل الضغط
                        time.sleep(random.uniform(0.5, 1.5))
                        btns[0].click()
                        status_msg = "تم الضغط على I understand ✔️"
                        time.sleep(random.uniform(1.5, 3.0))
                except Exception:
                    pass

                # 2. القفز إلى Cloud Shell
                if "console.cloud.google.com" in current_url or "myaccount.google.com" in current_url:
                    project_id = session.get('project_id')
                    if project_id:
                        status_msg = "🚀 جاري القفز إلى الشاشة السوداء..."
                        shell_url = f"https://shell.cloud.google.com/?project={project_id}&pli=1&show=terminal"
                        try:
                            time.sleep(random.uniform(1.0, 2.0))
                            driver.get(shell_url)
                            session['shell_opened'] = True
                            time.sleep(4)
                        except Exception:
                            pass
            else:
                # 3. توثيق Authorize
                if not session.get('authorized'):
                    try:
                        auth_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Authorize') or contains(., 'AUTHORIZE')]")
                        for btn in auth_btns:
                            if btn.is_displayed():
                                time.sleep(random.uniform(0.5, 1.5))
                                btn.click()
                                session['authorized'] = True
                                status_msg = "تم تخطي التوثيق (Authorize) 🛡️"
                                time.sleep(2)
                                break
                    except Exception:
                        pass

                if session.get('authorized'):
                    status_msg = "✅ الشل جاهز للأوامر الآن"
                elif "جاري" not in status_msg:
                    status_msg = "✅ Cloud Shell يعمل الآن"

            # ─── 📸 التقاط الصورة ───
            png_data = driver.get_screenshot_as_png()
            bio = io.BytesIO(png_data)
            bio.name = f'live_{int(time.time())}_{random.randint(1000,9999)}.png'

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

            if "message is not modified" in err_msg:
                continue

            error_count += 1

            if "too many requests" in err_msg or "retry after" in err_msg:
                wait_match = re.search(r'retry after (\d+)', err_msg)
                wait_time = int(wait_match.group(1)) if wait_match else 3
                time.sleep(wait_time)

            elif any(kw in err_msg for kw in ['session', 'disconnected', 'crashed', 'not reachable']):
                driver_error_count += 1
                if driver_error_count >= 3:
                    try:
                        bot.send_message(chat_id, "⚠️ المتصفح تعطل! جاري إعادة التشغيل...")
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
                            bot.send_message(chat_id, "✅ تم إعادة تشغيل المتصفح!")
                        except Exception:
                            pass
                    except Exception as restart_err:
                        try:
                            bot.send_message(chat_id, f"❌ فشل إعادة التشغيل:\n`{str(restart_err)[:200]}`", parse_mode="Markdown")
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


# ─────────────────────────────────────────────────────────
# ▶️ بدء البث
# ─────────────────────────────────────────────────────────
def start_stream(chat_id, url):
    # إيقاف أي بث قديم
    old_driver = None
    with sessions_lock:
        if chat_id in user_sessions:
            old_session = user_sessions[chat_id]
            old_session['running'] = False
            old_session['generation'] = old_session.get('generation', 0) + 1
            old_driver = old_session.get('driver')

    bot.send_message(chat_id, "⚡ جاري تجهيز المتصفح المتخفي (Google Chrome + Anti-Detection)...")

    if old_driver:
        time.sleep(5)

    project_match = re.search(r'(qwiklabs-gcp-[\w-]+)', url)
    project_id = project_match.group(1) if project_match else None

    try:
        driver = None
        if old_driver and is_driver_alive(old_driver):
            driver = old_driver
        else:
            safe_quit_driver(old_driver)
            driver = get_driver()
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

    # ✅ تأخير بشري قبل فتح الرابط
    time.sleep(random.uniform(1.0, 2.0))

    try:
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"⚠️ خطأ تحميل الرابط: {e}")

    # ✅ انتظار تحميل الصفحة
    time.sleep(random.uniform(3.0, 5.0))

    try:
        handles = driver.window_handles
        if handles:
            driver.switch_to.window(handles[-1])

        png_data = driver.get_screenshot_as_png()
        bio = io.BytesIO(png_data)
        bio.name = f'start_{int(time.time())}.png'

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
        bot.send_message(chat_id, f"⚠️ فشل اللقطة الأولى:\n`{str(e)[:200]}`", parse_mode="Markdown")
        cleanup_session(chat_id)


# ─────────────────────────────────────────────────────────
# 📨 معالجة رسائل تيليغرام
# ─────────────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, 
        "مرحباً! 🚀\n\n"
        "البوت يعمل بنظام التخفي المتقدم:\n"
        "🛡️ Google Chrome حقيقي\n"
        "🛡️ undetected-chromedriver\n"
        "🛡️ selenium-stealth\n"
        "🛡️ سكربت تخفي شامل\n\n"
        "أرسل الرابط للبدء."
    )


@bot.message_handler(func=lambda message: message.text and message.text.startswith('https://www.skills.google/google_sso'))
def handle_qwiklabs_url(message):
    threading.Thread(target=start_stream, args=(message.chat.id, message.text), daemon=True).start()


@bot.message_handler(func=lambda message: message.text and message.text.startswith('http') and not message.text.startswith('https://www.skills.google/google_sso'))
def handle_invalid_url(message):
    bot.reply_to(message, "❌ يجب أن يبدأ الرابط بـ:\n`https://www.skills.google/google_sso`", parse_mode="Markdown")


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
                bot.edit_message_caption("🛑 تم إيقاف البث.", chat_id=chat_id, message_id=session['message_id'])
            except Exception:
                pass
            try:
                session['driver'].get("about:blank")
            except Exception:
                pass

        elif call.data == "refresh_page":
            bot.answer_callback_query(call.id, "جاري التحديث...")
            try:
                session['driver'].refresh()
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────────────────
# 🏁 تشغيل البوت مع إعادة الاتصال التلقائي
# ─────────────────────────────────────────────────────────
def run_bot():
    print("=" * 50)
    print("✅ البوت يعمل بنظام التخفي الكامل")
    print("🛡️ Google Chrome + UC + Stealth + CDP Scripts")
    print("=" * 50)
    while True:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ خطأ اتصال: {e}")
            print("🔄 إعادة الاتصال بعد 5 ثوانٍ...")
            time.sleep(5)


if __name__ == '__main__':
    run_bot()
