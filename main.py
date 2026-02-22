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

# ✅ خادم ويب بسيط لحل مشكلة Koyeb Health Check
from flask import Flask

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from pyvirtualdisplay import Display

try:
    from selenium_stealth import stealth
    STEALTH_AVAILABLE = True
    print("✅ selenium-stealth متاحة")
except ImportError:
    STEALTH_AVAILABLE = False
    print("⚠️ selenium-stealth غير متاحة")

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن!")

bot = telebot.TeleBot(TOKEN)
user_sessions = {}
sessions_lock = threading.Lock()

# ─────────────────────────────────────────────────
# 🌐 خادم ويب لـ Koyeb Health Check (حل المشكلة الأولى)
# ─────────────────────────────────────────────────
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/status')
def status():
    with sessions_lock:
        active = len(user_sessions)
    return f"Active sessions: {active}", 200

def start_web_server():
    """تشغيل خادم الويب في خيط منفصل"""
    port = int(os.getenv('PORT', 8000))
    print(f"🌐 خادم Health Check يعمل على البورت {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ─────────────────────────────────────────────────
# 🖥️ الشاشة الوهمية
# ─────────────────────────────────────────────────
display = None
try:
    display = Display(visible=0, size=(1920, 1080), color_depth=24)
    display.start()
    print("✅ الشاشة الوهمية تعمل (1920x1080)")
except Exception as e:
    print(f"⚠️ فشل الشاشة الوهمية: {e}")

# ─────────────────────────────────────────────────
# 🛡️ سكربت التخفي الشامل
# ─────────────────────────────────────────────────
STEALTH_JS = '''
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

Object.defineProperty(navigator, 'plugins', {
    get: function() {
        var arr = [
            {name:'Chrome PDF Plugin', description:'Portable Document Format',
             filename:'internal-pdf-viewer', length:1,
             item: function(i){return this;}, namedItem: function(n){return this;}},
            {name:'Chrome PDF Viewer', description:'',
             filename:'mhjfbmdgcfjbbpaeojofohoefgiehjai', length:1,
             item: function(i){return this;}, namedItem: function(n){return this;}},
            {name:'Native Client', description:'',
             filename:'internal-nacl-plugin', length:2,
             item: function(i){return this;}, namedItem: function(n){return this;}}
        ];
        arr.refresh = function(){};
        return arr;
    }
});

Object.defineProperty(navigator, 'mimeTypes', {
    get: function() {
        var arr = [
            {type:'application/pdf', suffixes:'pdf', description:'Portable Document Format'},
            {type:'text/pdf', suffixes:'pdf', description:'Portable Document Format'}
        ];
        arr.refresh = function(){};
        return arr;
    }
});

Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});

if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            downlink: 10, effectiveType: '4g', rtt: 50,
            saveData: false, onchange: null
        })
    });
}

navigator.getBattery = function() {
    return Promise.resolve({
        charging: true, chargingTime: 0,
        dischargingTime: Infinity, level: 0.97
    });
};

window.chrome = window.chrome || {};
window.chrome.runtime = {
    onMessage: {addListener:function(){}, removeListener:function(){}},
    onConnect: {addListener:function(){}, removeListener:function(){}},
    sendMessage: function(){},
    connect: function(){return {onMessage:{addListener:function(){}},
        postMessage:function(){}, disconnect:function(){}};}
};
window.chrome.loadTimes = function() {
    return {commitLoadTime: Date.now()/1000, connectionInfo:'http/1.1',
        finishDocumentLoadTime: Date.now()/1000, finishLoadTime: Date.now()/1000,
        firstPaintTime: Date.now()/1000, navigationType:'Other',
        requestTime: Date.now()/1000 - 0.16, startLoadTime: Date.now()/1000};
};
window.chrome.csi = function() {
    return {onloadT:Date.now(), pageT:Date.now()/1000, startE:Date.now(), tran:15};
};

if (navigator.permissions) {
    var origQuery = navigator.permissions.query;
    navigator.permissions.query = function(params) {
        if (params.name === 'notifications')
            return Promise.resolve({state:'prompt'});
        return origQuery.call(navigator.permissions, params);
    };
}

try {
    var origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if(p===37445) return 'Intel Inc.';
        if(p===37446) return 'Intel Iris OpenGL Engine';
        return origGetParam.call(this, p);
    };
} catch(e){}

try {
    var origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(p) {
        if(p===37445) return 'Intel Inc.';
        if(p===37446) return 'Intel Iris OpenGL Engine';
        return origGetParam2.call(this, p);
    };
} catch(e){}

Object.defineProperty(screen, 'width', {get: () => 1920});
Object.defineProperty(screen, 'height', {get: () => 1080});
Object.defineProperty(screen, 'availWidth', {get: () => 1920});
Object.defineProperty(screen, 'availHeight', {get: () => 1040});
Object.defineProperty(screen, 'colorDepth', {get: () => 24});
Object.defineProperty(screen, 'pixelDepth', {get: () => 24});

for (var prop in window) {
    if (prop.match(/^cdc_/)) { try { delete window[prop]; } catch(e){} }
}
for (var prop in document) {
    if (prop.match(/^cdc_|\\$cdc_/)) { try { delete document[prop]; } catch(e){} }
}
'''

# ─────────────────────────────────────────────────
# 🌐 إنشاء المتصفح المتخفي
# ─────────────────────────────────────────────────
def get_driver():
    profile_dir = os.path.join(os.path.expanduser('~'), 'chrome-profile')
    os.makedirs(profile_dir, exist_ok=True)

    for lock_file in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        lock_path = os.path.join(profile_dir, lock_file)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass

    options = uc.ChromeOptions()
    options.add_argument(f'--user-data-dir={profile_dir}')
    options.add_argument('--profile-directory=Default')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--lang=en-US,en')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-ipc-flooding-protection')
    options.page_load_strategy = 'normal'

    print("🚀 جاري إنشاء المتصفح...")

    driver = uc.Chrome(
        options=options,
        headless=False,
        use_subprocess=True,
    )

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
            print("🛡️ selenium-stealth ✓")
        except Exception as e:
            print(f"⚠️ فشل stealth: {e}")

    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': STEALTH_JS
        })
        print("🛡️ Stealth JS ✓")
    except Exception as e:
        print(f"⚠️ فشل JS: {e}")

    try:
        ua = driver.execute_script("return navigator.userAgent")
        clean_ua = ua.replace("Headless", "").replace("headless", "").replace("HeadlessChrome", "Chrome")
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": clean_ua,
            "platform": "Win32",
            "acceptLanguage": "en-US,en;q=0.9",
            "userAgentMetadata": {
                "brands": [
                    {"brand": "Google Chrome", "version": "120"},
                    {"brand": "Chromium", "version": "120"},
                    {"brand": "Not_A Brand", "version": "24"}
                ],
                "fullVersion": "120.0.6099.109",
                "platform": "Windows",
                "platformVersion": "10.0.0",
                "architecture": "x86",
                "model": "",
                "mobile": False,
                "bitness": "64",
                "wow64": False
            }
        })
        print(f"🛡️ UA: {clean_ua[:60]}...")
    except Exception as e:
        print(f"⚠️ فشل UA: {e}")

    driver.set_page_load_timeout(60)
    print("✅ المتصفح جاهز.")
    return driver


# ─────────────────────────────────────────────────
# 🖱️ سلوك بشري
# ─────────────────────────────────────────────────
def human_like_mouse_move(driver):
    try:
        actions = ActionChains(driver)
        for _ in range(random.randint(2, 5)):
            x = random.randint(-200, 200)
            y = random.randint(-150, 150)
            actions.move_by_offset(x, y)
            actions.pause(random.uniform(0.1, 0.4))
        actions.perform()
    except Exception:
        pass


def human_like_scroll(driver):
    try:
        scroll = random.randint(100, 400)
        driver.execute_script(f"window.scrollBy(0, {scroll})")
        time.sleep(random.uniform(0.3, 0.8))
        driver.execute_script(f"window.scrollBy(0, -{scroll // 2})")
    except Exception:
        pass


# ─────────────────────────────────────────────────
# 🔥 تسخين المتصفح
# ─────────────────────────────────────────────────
def pre_warm_browser(driver, chat_id=None):
    if chat_id:
        try:
            bot.send_message(chat_id, "🔥 تسخين المتصفح (زيارة Google لبناء الثقة)...")
        except Exception:
            pass

    try:
        print("🔥 [1/3] google.com...")
        driver.get("https://www.google.com")
        time.sleep(random.uniform(3, 5))
        human_like_mouse_move(driver)

        try:
            btns = driver.find_elements(By.XPATH,
                "//button[contains(., 'Accept') or contains(., 'I agree') or contains(., 'Accept all')]")
            if btns:
                time.sleep(random.uniform(0.5, 1.5))
                btns[0].click()
                time.sleep(random.uniform(1, 2))
        except Exception:
            pass

        try:
            search = driver.find_element(By.NAME, "q")
            search.click()
            time.sleep(random.uniform(0.5, 1.0))
            for char in "google cloud console":
                search.send_keys(char)
                time.sleep(random.uniform(0.03, 0.12))
            time.sleep(random.uniform(1, 2))
            search.send_keys(Keys.RETURN)
            time.sleep(random.uniform(2, 4))
            human_like_scroll(driver)
        except Exception:
            pass

        print("🔥 [2/3] accounts.google.com...")
        time.sleep(random.uniform(1, 2))
        driver.get("https://accounts.google.com")
        time.sleep(random.uniform(3, 5))
        human_like_mouse_move(driver)

        print("🔥 [3/3] myaccount.google.com...")
        time.sleep(random.uniform(1, 2))
        driver.get("https://myaccount.google.com")
        time.sleep(random.uniform(2, 4))
        human_like_mouse_move(driver)

        print("✅ التسخين اكتمل")

        if chat_id:
            try:
                bot.send_message(chat_id, "✅ تم التسخين! جاري فتح الرابط...")
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ خطأ تسخين: {e}")


# ─────────────────────────────────────────────────
# 🧹 تنظيف
# ─────────────────────────────────────────────────
def safe_quit_driver(driver):
    if driver:
        try:
            driver.quit()
        except Exception:
            pass


def cleanup_session(chat_id):
    with sessions_lock:
        if chat_id in user_sessions:
            session = user_sessions[chat_id]
            session['running'] = False
            safe_quit_driver(session.get('driver'))
            del user_sessions[chat_id]


def cleanup_all():
    print("🧹 تنظيف شامل...")
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


atexit.register(cleanup_all)


def is_driver_alive(driver):
    try:
        _ = driver.title
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────
# 🎛️ لوحة التحكم
# ─────────────────────────────────────────────────
def create_control_panel():
    markup = InlineKeyboardMarkup()
    btn_stop = InlineKeyboardButton("⏹ إيقاف", callback_data="stop_stream")
    btn_refresh = InlineKeyboardButton("🔄 تحديث", callback_data="refresh_page")
    markup.row(btn_stop, btn_refresh)
    return markup


# ─────────────────────────────────────────────────
# 🎬 حلقة البث
# ─────────────────────────────────────────────────
def stream_loop(chat_id, generation):
    with sessions_lock:
        if chat_id not in user_sessions:
            return
        session = user_sessions[chat_id]

    driver = session['driver']
    flash_state = True
    error_count = 0
    driver_error_count = 0

    while session['running'] and session.get('generation') == generation:
        time.sleep(random.uniform(3.5, 5.5))

        if not session['running'] or session.get('generation') != generation:
            break

        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])

            current_url = driver.current_url
            status_msg = "جاري المراقبة..."

            if not session.get('shell_opened'):
                try:
                    btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'I understand')]")
                    if btns and btns[0].is_displayed():
                        time.sleep(random.uniform(0.8, 2.0))
                        human_like_mouse_move(driver)
                        btns[0].click()
                        status_msg = "تم الضغط على I understand ✔️"
                        time.sleep(random.uniform(2, 3))
                except Exception:
                    pass

                if "console.cloud.google.com" in current_url or "myaccount.google.com" in current_url:
                    project_id = session.get('project_id')
                    if project_id:
                        status_msg = "🚀 جاري القفز إلى Cloud Shell..."
                        shell_url = f"https://shell.cloud.google.com/?project={project_id}&pli=1&show=terminal"
                        try:
                            time.sleep(random.uniform(1.5, 3.0))
                            driver.get(shell_url)
                            session['shell_opened'] = True
                            time.sleep(random.uniform(4, 6))
                        except Exception:
                            pass

                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    if "couldn't sign you in" in page_text.lower():
                        status_msg = "⚠️ Google رفض - إعادة محاولة..."
                        time.sleep(random.uniform(3, 5))
                        driver.delete_all_cookies()
                        pre_warm_browser(driver)
                        time.sleep(random.uniform(2, 3))
                        driver.get(session.get('url', 'about:blank'))
                        time.sleep(random.uniform(4, 6))
                except Exception:
                    pass
            else:
                if not session.get('authorized'):
                    try:
                        auth_btns = driver.find_elements(By.XPATH,
                            "//button[contains(., 'Authorize') or contains(., 'AUTHORIZE')]")
                        for btn in auth_btns:
                            if btn.is_displayed():
                                time.sleep(random.uniform(0.5, 1.5))
                                btn.click()
                                session['authorized'] = True
                                status_msg = "تم التوثيق 🛡️"
                                time.sleep(2)
                                break
                    except Exception:
                        pass

                if session.get('authorized'):
                    status_msg = "✅ الشل جاهز"
                elif "جاري" not in status_msg:
                    status_msg = "✅ Cloud Shell يعمل"

            if random.random() < 0.3:
                human_like_mouse_move(driver)

            png_data = driver.get_screenshot_as_png()
            bio = io.BytesIO(png_data)
            bio.name = f'live_{int(time.time())}_{random.randint(1000, 9999)}.png'

            flash_state = not flash_state
            live_icon = "🔴" if flash_state else "⭕"
            now = datetime.now().strftime("%H:%M:%S")

            proj_text = f"📁 {session.get('project_id')}" if session.get('project_id') else ""
            caption = f"{live_icon} بث مباشر\n{proj_text}\n📌 {status_msg}\n⏱ {now}"

            bot.edit_message_media(
                media=InputMediaPhoto(bio, caption=caption),
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
                        bot.send_message(chat_id, "⚠️ المتصفح تعطل! إعادة تشغيل...")
                    except Exception:
                        pass
                    try:
                        safe_quit_driver(driver)
                        new_driver = get_driver()
                        pre_warm_browser(new_driver, chat_id)
                        session['driver'] = new_driver
                        driver = new_driver
                        driver.get(session.get('url', 'about:blank'))
                        session['shell_opened'] = False
                        session['authorized'] = False
                        driver_error_count = 0
                        error_count = 0
                        time.sleep(3)
                    except Exception as err:
                        try:
                            bot.send_message(chat_id, f"❌ فشل:\n`{str(err)[:200]}`", parse_mode="Markdown")
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

    print(f"🛑 انتهى البث: {chat_id}")


# ─────────────────────────────────────────────────
# ▶️ بدء البث
# ─────────────────────────────────────────────────
def start_stream(chat_id, url):
    old_driver = None
    with sessions_lock:
        if chat_id in user_sessions:
            old_session = user_sessions[chat_id]
            old_session['running'] = False
            old_session['generation'] = old_session.get('generation', 0) + 1
            old_driver = old_session.get('driver')

    bot.send_message(chat_id, "⚡ جاري التجهيز + التسخين...")

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
        bot.send_message(chat_id, f"⚠️ خطأ المتصفح:\n`{str(e)[:300]}`", parse_mode="Markdown")
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

    pre_warm_browser(driver, chat_id)
    time.sleep(random.uniform(2, 4))

    try:
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"⚠️ خطأ تحميل: {e}")

    time.sleep(random.uniform(5, 8))
    human_like_mouse_move(driver)

    try:
        handles = driver.window_handles
        if handles:
            driver.switch_to.window(handles[-1])

        png_data = driver.get_screenshot_as_png()
        bio = io.BytesIO(png_data)
        bio.name = f'start_{int(time.time())}.png'

        msg = bot.send_photo(
            chat_id, bio,
            caption="🔴 بث مباشر\n📌 بدء البث...\n⏱ جاري الاتصال...",
            reply_markup=create_control_panel()
        )

        session['message_id'] = msg.message_id
        session['running'] = True

        t = threading.Thread(target=stream_loop, args=(chat_id, generation), daemon=True)
        t.start()

    except Exception as e:
        bot.send_message(chat_id, f"⚠️ فشل اللقطة:\n`{str(e)[:200]}`", parse_mode="Markdown")
        cleanup_session(chat_id)


# ─────────────────────────────────────────────────
# 📨 أوامر تيليغرام
# ─────────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message,
        "🚀 مرحباً!\n\n"
        "🛡️ Google Chrome + Anti-Detection\n"
        "🔥 تسخين مسبق لتجاوز Google\n"
        "🖱️ سلوك بشري واقعي\n\n"
        "أرسل الرابط للبدء."
    )


@bot.message_handler(func=lambda m: m.text and m.text.startswith('https://www.skills.google/google_sso'))
def handle_qwiklabs_url(message):
    threading.Thread(target=start_stream, args=(message.chat.id, message.text), daemon=True).start()


@bot.message_handler(func=lambda m: m.text and m.text.startswith('http') and not m.text.startswith('https://www.skills.google/google_sso'))
def handle_invalid_url(message):
    bot.reply_to(message, "❌ يجب أن يبدأ الرابط بـ:\n`https://www.skills.google/google_sso`", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    chat_id = call.message.chat.id
    try:
        with sessions_lock:
            if chat_id not in user_sessions:
                bot.answer_callback_query(call.id, "لا توجد جلسة.")
                return
            session = user_sessions[chat_id]

        if call.data == "stop_stream":
            session['running'] = False
            session['generation'] = session.get('generation', 0) + 1
            bot.answer_callback_query(call.id, "تم الإيقاف.")
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


# ─────────────────────────────────────────────────
# 🏁 التشغيل الرئيسي
# ─────────────────────────────────────────────────
def run_bot():
    """تشغيل بوت تيليغرام مع إعادة الاتصال التلقائي"""
    print("✅ بوت تيليغرام يعمل...")
    while True:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ خطأ اتصال: {e}")
            time.sleep(5)


if __name__ == '__main__':
    print("=" * 55)
    print("✅ البوت + خادم Health Check")
    print("🌐 البورت: " + str(os.getenv('PORT', 8000)))
    print("=" * 55)

    # ✅ تشغيل خادم الويب في خيط منفصل (لـ Koyeb Health Check)
    web_thread = threading.Thread(target=start_web_server, daemon=True)
    web_thread.start()

    # ✅ تشغيل البوت في الخيط الرئيسي
    run_bot()
