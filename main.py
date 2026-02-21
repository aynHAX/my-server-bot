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
# 🖥️ شاشة وهمية بدقة عالية واقعية
# ─────────────────────────────────────────────────
display = None
try:
    display = Display(visible=0, size=(1920, 1080), color_depth=24)
    display.start()
    print("✅ الشاشة الوهمية تعمل (1920x1080, 24bit)")
except Exception as e:
    print(f"⚠️ فشل الشاشة الوهمية: {e}")

# ─────────────────────────────────────────────────
# 🛡️ سكربت التخفي الشامل - كل بصمات المتصفح
# ─────────────────────────────────────────────────
STEALTH_JS = '''
// ========== 1. إخفاء webdriver ==========
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});

// ========== 2. Plugins واقعية ==========
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
        arr.item = function(i){return arr[i];};
        arr.namedItem = function(n){return arr.find(function(p){return p.name===n;});};
        return arr;
    }
});

// ========== 3. MimeTypes ==========
Object.defineProperty(navigator, 'mimeTypes', {
    get: function() {
        var arr = [
            {type:'application/pdf', suffixes:'pdf', description:'Portable Document Format'},
            {type:'text/pdf', suffixes:'pdf', description:'Portable Document Format'}
        ];
        arr.refresh = function(){};
        arr.item = function(i){return arr[i];};
        arr.namedItem = function(n){return arr.find(function(m){return m.type===n;});};
        return arr;
    }
});

// ========== 4. اللغات والمنصة ==========
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});
Object.defineProperty(navigator, 'vendor', {get: () => 'Google Inc.'});
Object.defineProperty(navigator, 'appVersion', {
    get: () => navigator.userAgent.replace('Mozilla/', '')
});

// ========== 5. Connection API ==========
if (!navigator.connection) {
    Object.defineProperty(navigator, 'connection', {
        get: () => ({
            downlink: 10, effectiveType: '4g', rtt: 50,
            saveData: false, onchange: null,
            addEventListener: function(){}, removeEventListener: function(){}
        })
    });
}

// ========== 6. Battery API ==========
navigator.getBattery = function() {
    return Promise.resolve({
        charging: true, chargingTime: 0,
        dischargingTime: Infinity, level: 0.97,
        addEventListener: function(){}, removeEventListener: function(){},
        onchargingchange: null, onchargingtimechange: null,
        ondischargingtimechange: null, onlevelchange: null
    });
};

// ========== 7. Chrome Runtime كامل ==========
window.chrome = window.chrome || {};
window.chrome.runtime = {
    onMessage: {addListener:function(){}, removeListener:function(){}},
    onConnect: {addListener:function(){}, removeListener:function(){}},
    sendMessage: function(){},
    connect: function(){return {onMessage:{addListener:function(){}},
        postMessage:function(){}, disconnect:function(){}};}
};
window.chrome.loadTimes = function() {
    return {
        commitLoadTime: Date.now()/1000, connectionInfo:'http/1.1',
        finishDocumentLoadTime: Date.now()/1000, finishLoadTime: Date.now()/1000,
        firstPaintAfterLoadTime: 0, firstPaintTime: Date.now()/1000,
        navigationType:'Other', npnNegotiatedProtocol:'unknown',
        requestTime: Date.now()/1000 - 0.16, startLoadTime: Date.now()/1000,
        wasAlternateProtocolAvailable:false, wasFetchedViaSpdy:false,
        wasNpnNegotiated:false
    };
};
window.chrome.csi = function() {
    return {onloadT:Date.now(), pageT:Date.now()/1000, startE:Date.now(), tran:15};
};

// ========== 8. Permissions API ==========
if (navigator.permissions) {
    var origQuery = navigator.permissions.query;
    navigator.permissions.query = function(params) {
        if (params.name === 'notifications')
            return Promise.resolve({state:'prompt', onchange:null,
                addEventListener:function(){}, removeEventListener:function(){}});
        return origQuery.call(navigator.permissions, params);
    };
}

// ========== 9. WebGL واقعي ==========
try {
    var origGetParam = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(p) {
        if(p===37445) return 'Intel Inc.';
        if(p===37446) return 'Intel Iris OpenGL Engine';
        if(p===7937) return 'WebKit WebGL';
        if(p===7936) return 'WebKit';
        return origGetParam.call(this, p);
    };
} catch(e){}
try {
    var origGetParam2 = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(p) {
        if(p===37445) return 'Intel Inc.';
        if(p===37446) return 'Intel Iris OpenGL Engine';
        if(p===7937) return 'WebKit WebGL';
        if(p===7936) return 'WebKit';
        return origGetParam2.call(this, p);
    };
} catch(e){}

// ========== 10. Canvas Fingerprint حماية ==========
var origToDataURL = HTMLCanvasElement.prototype.toDataURL;
HTMLCanvasElement.prototype.toDataURL = function(type) {
    if(this.width === 0 && this.height === 0) return origToDataURL.apply(this, arguments);
    var ctx = this.getContext('2d');
    if(ctx) {
        var imgData = ctx.getImageData(0, 0, Math.min(this.width,4), Math.min(this.height,4));
        for(var i = 0; i < imgData.data.length; i += 4) {
            imgData.data[i] = imgData.data[i] ^ 1;
        }
        ctx.putImageData(imgData, 0, 0);
    }
    return origToDataURL.apply(this, arguments);
};

// ========== 11. AudioContext ==========
try {
    var origCreateOsc = AudioContext.prototype.createOscillator;
    AudioContext.prototype.createOscillator = function() {
        var osc = origCreateOsc.apply(this, arguments);
        osc.__proto__.frequency.value = osc.__proto__.frequency.value + Math.random() * 0.0001;
        return osc;
    };
} catch(e){}

// ========== 12. Iframe contentWindow ==========
try {
    Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
        get: function() {
            return window;
        }
    });
} catch(e){}

// ========== 13. حذف متغيرات cdc ==========
for (var prop in window) {
    if (prop.match(/^cdc_/)) { try { delete window[prop]; } catch(e){} }
}
for (var prop in document) {
    if (prop.match(/^cdc_|\\$cdc_/)) { try { delete document[prop]; } catch(e){} }
}

// ========== 14. Screen واقعي ==========
Object.defineProperty(screen, 'width', {get: () => 1920});
Object.defineProperty(screen, 'height', {get: () => 1080});
Object.defineProperty(screen, 'availWidth', {get: () => 1920});
Object.defineProperty(screen, 'availHeight', {get: () => 1040});
Object.defineProperty(screen, 'colorDepth', {get: () => 24});
Object.defineProperty(screen, 'pixelDepth', {get: () => 24});

// ========== 15. إصلاح toString ==========
var nativeToString = Function.prototype.toString;
var customFunctions = new Set();
var originalToString = Function.prototype.toString;
Function.prototype.toString = function() {
    if (this === Function.prototype.toString) return 'function toString() { [native code] }';
    if (this === navigator.permissions.query) return 'function query() { [native code] }';
    if (this === navigator.getBattery) return 'function getBattery() { [native code] }';
    return originalToString.call(this);
};
'''

# ─────────────────────────────────────────────────
# 🌐 إنشاء متصفح متخفي بالكامل
# ─────────────────────────────────────────────────
def get_driver():
    """إنشاء Google Chrome متخفي مع جميع طبقات الحماية"""

    # ✅ بروفايل مستمر (ليس فارغاً في كل مرة)
    profile_dir = os.path.join(os.path.expanduser('~'), 'chrome-profile')
    os.makedirs(profile_dir, exist_ok=True)

    # تنظيف ملفات القفل من جلسات سابقة متعطلة
    for lock_file in ['SingletonLock', 'SingletonSocket', 'SingletonCookie']:
        lock_path = os.path.join(profile_dir, lock_file)
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except Exception:
                pass

    options = uc.ChromeOptions()

    # ✅ بروفايل مستمر (أهم تغيير - يحفظ الكوكيز)
    options.add_argument(f'--user-data-dir={profile_dir}')
    options.add_argument('--profile-directory=Default')

    # ✅ خيارات ضرورية لـ Docker فقط (أقل عدد ممكن)
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    # ✅ إعدادات واقعية
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--start-maximized')
    options.add_argument('--lang=en-US,en')

    # ✅ إخفاء بصمات الأوتوميشن
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-ipc-flooding-protection')

    # ⚠️ لا نضيف هذه (تكشف البوت):
    # --incognito, --headless, --disable-gpu, --disable-extensions, --disable-infobars

    options.page_load_strategy = 'normal'  # ✅ normal بدل eager (أكثر واقعية)

    print("🚀 جاري إنشاء المتصفح...")

    # ✅ لا نحدد مسار الدرايفر - نترك UC يتولى التصحيح تلقائياً
    driver = uc.Chrome(
        options=options,
        headless=False,
        use_subprocess=True,
    )

    # ─── طبقة 1: selenium-stealth ───
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
            print("🛡️ [طبقة 1] selenium-stealth ✓")
        except Exception as e:
            print(f"⚠️ فشل stealth: {e}")

    # ─── طبقة 2: سكربت التخفي الشامل ───
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': STEALTH_JS
        })
        print("🛡️ [طبقة 2] Stealth JS ✓")
    except Exception as e:
        print(f"⚠️ فشل حقن JS: {e}")

    # ─── طبقة 3: تنظيف User-Agent ───
    try:
        ua = driver.execute_script("return navigator.userAgent")
        clean_ua = ua.replace("Headless", "").replace("headless", "")
        if "HeadlessChrome" in ua or "headless" in ua.lower():
            clean_ua = clean_ua.replace("HeadlessChrome", "Chrome")
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
        print(f"🛡️ [طبقة 3] UA: {clean_ua[:60]}...")
    except Exception as e:
        print(f"⚠️ فشل UA: {e}")

    # ─── طبقة 4: إخفاء webdriver عبر CDP ───
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                    configurable: true
                });
            '''
        })
        print("🛡️ [طبقة 4] navigator.webdriver = undefined ✓")
    except Exception:
        pass

    driver.set_page_load_timeout(60)
    print("✅ المتصفح جاهز بجميع طبقات التخفي.")
    return driver


# ─────────────────────────────────────────────────
# 🔥 تسخين المتصفح (الخطوة الأهم لتجاوز Google)
# ─────────────────────────────────────────────────
def human_like_mouse_move(driver):
    """حركة ماوس بشرية عشوائية"""
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
    """تمرير بشري عشوائي"""
    try:
        scroll_amount = random.randint(100, 400)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
        time.sleep(random.uniform(0.3, 0.8))
        driver.execute_script(f"window.scrollBy(0, -{scroll_amount // 2})")
    except Exception:
        pass


def pre_warm_browser(driver, chat_id=None):
    """
    تسخين المتصفح بزيارة مواقع Google أولاً
    هذا يُنشئ كوكيز طبيعية ويجعل المتصفح يبدو حقيقياً
    """
    if chat_id:
        try:
            bot.send_message(chat_id, "🔥 جاري تسخين المتصفح (زيارة Google لبناء الثقة)...")
        except Exception:
            pass

    try:
        # ─── الخطوة 1: زيارة google.com ───
        print("🔥 [تسخين 1/3] زيارة google.com...")
        driver.get("https://www.google.com")
        time.sleep(random.uniform(3, 5))

        # حركة ماوس طبيعية
        human_like_mouse_move(driver)

        # قبول الكوكيز إن ظهرت
        try:
            cookie_btns = driver.find_elements(By.XPATH,
                "//button[contains(., 'Accept') or contains(., 'I agree') or contains(., 'Accept all')]")
            if cookie_btns:
                time.sleep(random.uniform(0.5, 1.5))
                cookie_btns[0].click()
                time.sleep(random.uniform(1, 2))
                print("   ✓ تم قبول الكوكيز")
        except Exception:
            pass

        # كتابة بحث وهمي (يُنشئ سجل تصفح)
        try:
            search_box = driver.find_element(By.NAME, "q")
            search_box.click()
            time.sleep(random.uniform(0.5, 1.0))
            search_text = "google cloud console login"
            for char in search_text:
                search_box.send_keys(char)
                time.sleep(random.uniform(0.03, 0.12))
            time.sleep(random.uniform(1, 2))
            search_box.send_keys(Keys.RETURN)
            time.sleep(random.uniform(2, 4))
            human_like_scroll(driver)
            print("   ✓ تم البحث الوهمي")
        except Exception:
            pass

        # ─── الخطوة 2: زيارة accounts.google.com ───
        print("🔥 [تسخين 2/3] زيارة accounts.google.com...")
        time.sleep(random.uniform(1, 2))
        driver.get("https://accounts.google.com")
        time.sleep(random.uniform(3, 5))
        human_like_mouse_move(driver)
        human_like_scroll(driver)

        # ─── الخطوة 3: زيارة myaccount.google.com ───
        print("🔥 [تسخين 3/3] زيارة myaccount.google.com...")
        time.sleep(random.uniform(1, 2))
        driver.get("https://myaccount.google.com")
        time.sleep(random.uniform(2, 4))
        human_like_mouse_move(driver)

        print("✅ التسخين اكتمل - المتصفح يملك كوكيز Google الآن")

        if chat_id:
            try:
                bot.send_message(chat_id, "✅ تم التسخين بنجاح! جاري فتح الرابط الآن...")
            except Exception:
                pass

    except Exception as e:
        print(f"⚠️ خطأ في التسخين: {e}")


# ─────────────────────────────────────────────────
# 🧹 إدارة الجلسات والتنظيف
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
# 🎬 حلقة البث المستمر
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

            # ─── 🤖 نظام الطيار الآلي ───
            if not session.get('shell_opened'):
                # الضغط على I understand
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

                # القفز إلى Cloud Shell
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

                # ✅ كشف خطأ "Couldn't sign you in" وإعادة المحاولة
                try:
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    if "Couldn't sign you in" in page_text or "couldn't sign you in" in page_text.lower():
                        status_msg = "⚠️ Google رفض الدخول - جاري إعادة المحاولة..."
                        time.sleep(random.uniform(3, 5))
                        driver.delete_all_cookies()
                        pre_warm_browser(driver)
                        time.sleep(random.uniform(2, 3))
                        driver.get(session.get('url', 'about:blank'))
                        time.sleep(random.uniform(4, 6))
                except Exception:
                    pass

            else:
                # Authorize
                if not session.get('authorized'):
                    try:
                        auth_btns = driver.find_elements(By.XPATH,
                            "//button[contains(., 'Authorize') or contains(., 'AUTHORIZE')]")
                        for btn in auth_btns:
                            if btn.is_displayed():
                                time.sleep(random.uniform(0.5, 1.5))
                                btn.click()
                                session['authorized'] = True
                                status_msg = "تم التوثيق (Authorize) 🛡️"
                                time.sleep(2)
                                break
                    except Exception:
                        pass

                if session.get('authorized'):
                    status_msg = "✅ الشل جاهز"
                elif "جاري" not in status_msg:
                    status_msg = "✅ Cloud Shell يعمل"

            # حركة ماوس عشوائية كل فترة (سلوك بشري)
            if random.random() < 0.3:
                human_like_mouse_move(driver)

            # ─── 📸 التقاط الصورة ───
            png_data = driver.get_screenshot_as_png()
            bio = io.BytesIO(png_data)
            bio.name = f'live_{int(time.time())}_{random.randint(1000, 9999)}.png'

            flash_state = not flash_state
            live_icon = "🔴" if flash_state else "⭕"
            now = datetime.now().strftime("%H:%M:%S")

            proj_text = f"📁 {session.get('project_id')}" if session.get('project_id') else ""
            caption_text = f"{live_icon} بث مباشر\n{proj_text}\n📌 {status_msg}\n⏱ {now}"

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
                        pre_warm_browser(new_driver, chat_id)
                        session['driver'] = new_driver
                        driver = new_driver
                        driver.get(session.get('url', 'about:blank'))
                        session['shell_opened'] = False
                        session['authorized'] = False
                        driver_error_count = 0
                        error_count = 0
                        time.sleep(3)
                    except Exception as restart_err:
                        try:
                            bot.send_message(chat_id, f"❌ فشل:\n`{str(restart_err)[:200]}`", parse_mode="Markdown")
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
    # إيقاف بث قديم
    old_driver = None
    with sessions_lock:
        if chat_id in user_sessions:
            old_session = user_sessions[chat_id]
            old_session['running'] = False
            old_session['generation'] = old_session.get('generation', 0) + 1
            old_driver = old_session.get('driver')

    bot.send_message(chat_id,
        "⚡ جاري التجهيز...\n"
        "🛡️ Google Chrome + Anti-Detection\n"
        "🔥 تسخين المتصفح لتجاوز حماية Google"
    )

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

    # ✅ تسخين المتصفح أولاً (الخطوة الأهم!)
    pre_warm_browser(driver, chat_id)

    # ✅ تأخير بشري قبل فتح الرابط الحقيقي
    time.sleep(random.uniform(2, 4))

    try:
        print(f"🌐 فتح الرابط: {url[:80]}...")
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"⚠️ خطأ تحميل: {e}")

    # انتظار تحميل الصفحة + التوجيهات
    time.sleep(random.uniform(5, 8))

    # حركة ماوس بعد التحميل
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
        "🚀 مرحباً! البوت يعمل بنظام التخفي الكامل:\n\n"
        "🛡️ Google Chrome حقيقي\n"
        "🛡️ undetected-chromedriver\n"
        "🛡️ selenium-stealth\n"
        "🛡️ سكربت تخفي شامل (15 طبقة)\n"
        "🔥 تسخين مسبق لبناء ثقة Google\n"
        "🖱️ سلوك بشري (ماوس + تمرير)\n\n"
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
# 🏁 تشغيل البوت
# ─────────────────────────────────────────────────
def run_bot():
    print("=" * 55)
    print("✅ البوت يعمل بنظام التخفي الكامل ضد Google")
    print("🛡️ Chrome + UC + Stealth + CDP + Pre-Warming")
    print("🖱️ سلوك بشري (ماوس + تمرير + تأخيرات)")
    print("📁 بروفايل مستمر لحفظ الكوكيز")
    print("=" * 55)
    while True:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ خطأ: {e}")
            time.sleep(5)


if __name__ == '__main__':
    run_bot()
