import telebot
import os
import time
import threading
import io
import re
import random
import shutil
import gc
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from pyvirtualdisplay import Display

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("لم يتم العثور على التوكن!")

bot = telebot.TeleBot(TOKEN)
user_sessions = {}
sessions_lock = threading.Lock()

# ─────────────────────────────────────────────
# 🌐 Health Check (بدون Flask - خفيف)
# ─────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.getenv('PORT', 8000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Health Check: port {port}")
    server.serve_forever()


# ─────────────────────────────────────────────
# 🖥️ شاشة وهمية خفيفة (بدل headless)
# ─────────────────────────────────────────────
display = None
try:
    # ✅ 800x600 + 8bit = ~10MB RAM فقط (بدل 1920x1080 24bit = 50MB)
    display = Display(visible=0, size=(800, 600), color_depth=8)
    display.start()
    print("✅ Xvfb يعمل (800x600, 8bit) - خفيف جداً")
except Exception as e:
    print(f"⚠️ فشل Xvfb: {e}")
    # محاولة ثانية بإعدادات أبسط
    try:
        display = Display(visible=0, size=(800, 600))
        display.start()
        print("✅ Xvfb يعمل (800x600)")
    except Exception as e2:
        print(f"❌ Xvfb فشل نهائياً: {e2}")


# ─────────────────────────────────────────────
# 🛡️ سكربت تخفي مختصر
# ─────────────────────────────────────────────
STEALTH_JS = '''
Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']});
Object.defineProperty(navigator,'platform',{get:()=>'Win32'});
Object.defineProperty(navigator,'vendor',{get:()=>'Google Inc.'});
Object.defineProperty(navigator,'hardwareConcurrency',{get:()=>4});
Object.defineProperty(navigator,'deviceMemory',{get:()=>8});
Object.defineProperty(navigator,'maxTouchPoints',{get:()=>0});

window.chrome={runtime:{onMessage:{addListener:function(){}},sendMessage:function(){},
connect:function(){return{onMessage:{addListener:function(){}},postMessage:function(){}}}}};
window.chrome.loadTimes=function(){return{commitLoadTime:Date.now()/1000,
connectionInfo:'http/1.1',finishLoadTime:Date.now()/1000,navigationType:'Other',
requestTime:Date.now()/1000-0.16,startLoadTime:Date.now()/1000}};
window.chrome.csi=function(){return{onloadT:Date.now(),pageT:Date.now()/1000,startE:Date.now(),tran:15}};

if(navigator.permissions){
    var o=navigator.permissions.query;
    navigator.permissions.query=function(p){
        if(p.name==='notifications')return Promise.resolve({state:'prompt'});
        return o.call(navigator.permissions,p);
    };
}

try{var g=WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter=function(p){
if(p===37445)return'Intel Inc.';if(p===37446)return'Intel Iris OpenGL Engine';
return g.call(this,p);};}catch(e){}

Object.defineProperty(screen,'width',{get:()=>1920});
Object.defineProperty(screen,'height',{get:()=>1080});
Object.defineProperty(screen,'colorDepth',{get:()=>24});
Object.defineProperty(screen,'pixelDepth',{get:()=>24});
Object.defineProperty(screen,'availWidth',{get:()=>1920});
Object.defineProperty(screen,'availHeight',{get:()=>1040});

for(var p in window){if(p.match(/^cdc_/)){try{delete window[p]}catch(e){}}}
for(var p in document){if(p.match(/^cdc_|\\$cdc_/)){try{delete document[p]}catch(e){}}}
'''

# ─────────────────────────────────────────────
# 🔍 البحث عن المتصفح
# ─────────────────────────────────────────────
def find_path(names, extras=None):
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    for p in (extras or []):
        if os.path.isfile(p):
            return p
    return None


# ─────────────────────────────────────────────
# 🌐 متصفح محسّن (Xvfb + تخفي + خفيف)
# ─────────────────────────────────────────────
def get_driver():
    browser = find_path(
        ['chromium', 'chromium-browser'],
        ['/usr/bin/chromium', '/usr/bin/chromium-browser']
    )
    drv = find_path(
        ['chromedriver'],
        ['/usr/bin/chromedriver', '/usr/lib/chromium/chromedriver']
    )

    if not browser:
        raise Exception("❌ المتصفح غير موجود!")
    if not drv:
        raise Exception("❌ ChromeDriver غير موجود!")

    options = Options()
    options.binary_location = browser

    # ═══════════════════════════════════════════
    # ✅ بدون --headless (Xvfb يعمل كشاشة)
    # هذا هو السر - Google لا يكتشف Xvfb
    # ═══════════════════════════════════════════

    # 🛡️ تخفي
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    # ⚡ توفير موارد
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--single-process')
    options.add_argument('--no-zygote')
    options.add_argument('--renderer-process-limit=1')
    options.add_argument('--window-size=800,600')

    # 🔇 تعطيل غير ضروري
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-sync')
    options.add_argument('--disable-translate')
    options.add_argument('--disable-features=TranslateUI')
    options.add_argument('--disable-hang-monitor')
    options.add_argument('--disable-domain-reliability')
    options.add_argument('--disable-component-update')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--no-first-run')
    options.add_argument('--no-default-browser-check')
    options.add_argument('--metrics-recording-only')
    options.add_argument('--mute-audio')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--lang=en-US')

    # حد ذاكرة JS
    options.add_argument('--js-flags=--max-old-space-size=128')

    # تعطيل تحميل الصور (توفير RAM)
    prefs = {
        'profile.managed_default_content_settings.images': 2,
        'profile.default_content_setting_values.notifications': 2,
        'disk-cache-size': 1,
    }
    options.add_experimental_option('prefs', prefs)

    options.page_load_strategy = 'eager'

    print("🚀 إنشاء المتصفح (Xvfb + تخفي)...")

    service = Service(executable_path=drv)
    driver = webdriver.Chrome(service=service, options=options)

    # حقن سكربت التخفي
    try:
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': STEALTH_JS
        })
        print("🛡️ تخفي JS ✓")
    except Exception as e:
        print(f"⚠️ فشل JS: {e}")

    # تنظيف User-Agent
    try:
        driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "platform": "Win32",
            "acceptLanguage": "en-US,en;q=0.9"
        })
        print("🛡️ User-Agent ✓")
    except Exception:
        pass

    driver.set_page_load_timeout(25)

    # ✅ فحص التخفي
    try:
        driver.get("about:blank")
        wd = driver.execute_script("return navigator.webdriver")
        print(f"🔍 navigator.webdriver = {wd} {'✅' if wd is None or wd == False else '❌'}")
    except Exception:
        pass

    print("✅ المتصفح جاهز!")
    return driver


# ─────────────────────────────────────────────
# 🧹 تنظيف
# ─────────────────────────────────────────────
def safe_quit(driver):
    if driver:
        try:
            driver.quit()
        except Exception:
            pass
        gc.collect()


def cleanup_session(chat_id):
    with sessions_lock:
        if chat_id in user_sessions:
            s = user_sessions[chat_id]
            s['running'] = False
            safe_quit(s.get('driver'))
            del user_sessions[chat_id]
            gc.collect()


def driver_alive(driver):
    try:
        _ = driver.title
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────
# 🎛️ لوحة التحكم
# ─────────────────────────────────────────────
def panel():
    mk = InlineKeyboardMarkup()
    mk.row(
        InlineKeyboardButton("⏹ إيقاف", callback_data="stop"),
        InlineKeyboardButton("🔄 تحديث", callback_data="refresh")
    )
    return mk


# ─────────────────────────────────────────────
# 🎬 حلقة البث
# ─────────────────────────────────────────────
def stream_loop(chat_id, gen):
    with sessions_lock:
        if chat_id not in user_sessions:
            return
        session = user_sessions[chat_id]

    driver = session['driver']
    flash = True
    err_count = 0
    drv_err = 0
    cycle = 0

    while session['running'] and session.get('gen') == gen:
        time.sleep(random.uniform(8, 12))

        if not session['running'] or session.get('gen') != gen:
            break

        cycle += 1

        try:
            handles = driver.window_handles
            if handles:
                driver.switch_to.window(handles[-1])

            url = driver.current_url
            status = "مراقبة..."

            # ─── الطيار الآلي (كل دورتين) ───
            if cycle % 2 == 0:
                if not session.get('shell_opened'):
                    # I understand
                    try:
                        btns = driver.find_elements(By.XPATH, "//*[contains(text(), 'I understand')]")
                        if btns and btns[0].is_displayed():
                            time.sleep(1)
                            btns[0].click()
                            status = "I understand ✔️"
                            time.sleep(2)
                    except Exception:
                        pass

                    # القفز للشل
                    if "console.cloud.google.com" in url or "myaccount.google.com" in url:
                        pid = session.get('project_id')
                        if pid:
                            status = "🚀 Cloud Shell..."
                            try:
                                driver.get(f"https://shell.cloud.google.com/?project={pid}&pli=1&show=terminal")
                                session['shell_opened'] = True
                                time.sleep(5)
                            except Exception:
                                pass

                    # كشف رفض الدخول
                    try:
                        body = driver.find_element(By.TAG_NAME, "body").text.lower()
                        if "couldn't sign you in" in body:
                            status = "⚠️ Google رفض الدخول"
                    except Exception:
                        pass
                else:
                    if not session.get('auth'):
                        try:
                            a_btns = driver.find_elements(By.XPATH,
                                "//button[contains(., 'Authorize') or contains(., 'AUTHORIZE')]")
                            for b in a_btns:
                                if b.is_displayed():
                                    b.click()
                                    session['auth'] = True
                                    status = "توثيق ✔️"
                                    time.sleep(2)
                                    break
                        except Exception:
                            pass

                    if session.get('auth'):
                        status = "✅ جاهز"
                    else:
                        status = "✅ يعمل"

            # ─── 📸 لقطة ───
            png = driver.get_screenshot_as_png()
            bio = io.BytesIO(png)
            bio.name = f'l_{int(time.time())}.png'

            flash = not flash
            icon = "🔴" if flash else "⭕"
            now = datetime.now().strftime("%H:%M:%S")
            proj = f"📁 {session.get('project_id')}" if session.get('project_id') else ""
            cap = f"{icon} بث مباشر\n{proj}\n📌 {status}\n⏱ {now}"

            bot.edit_message_media(
                media=InputMediaPhoto(bio, caption=cap),
                chat_id=chat_id,
                message_id=session['msg_id'],
                reply_markup=panel()
            )

            err_count = 0
            drv_err = 0

            if cycle % 10 == 0:
                gc.collect()

        except Exception as e:
            em = str(e).lower()

            if "message is not modified" in em:
                continue

            err_count += 1

            if "too many requests" in em or "retry after" in em:
                w = re.search(r'retry after (\d+)', em)
                time.sleep(int(w.group(1)) if w else 5)

            elif any(k in em for k in ['session', 'disconnected', 'crashed', 'not reachable']):
                drv_err += 1
                if drv_err >= 3:
                    try:
                        bot.send_message(chat_id, "⚠️ المتصفح تعطل! إعادة تشغيل...")
                    except Exception:
                        pass
                    try:
                        safe_quit(driver)
                        new_drv = get_driver()
                        session['driver'] = new_drv
                        driver = new_drv
                        driver.get(session.get('url', 'about:blank'))
                        session['shell_opened'] = False
                        session['auth'] = False
                        drv_err = 0
                        err_count = 0
                        time.sleep(5)
                    except Exception:
                        session['running'] = False
                        break

            elif err_count >= 5:
                try:
                    driver.refresh()
                    err_count = 0
                except Exception:
                    drv_err += 1

    print(f"🛑 انتهى: {chat_id}")
    gc.collect()


# ─────────────────────────────────────────────
# ▶️ بدء البث
# ─────────────────────────────────────────────
def start_stream(chat_id, url):
    old_drv = None
    with sessions_lock:
        if chat_id in user_sessions:
            old = user_sessions[chat_id]
            old['running'] = False
            old['gen'] = old.get('gen', 0) + 1
            old_drv = old.get('driver')

    bot.send_message(chat_id, "⚡ جاري التجهيز...")

    if old_drv:
        safe_quit(old_drv)
        time.sleep(2)

    project_match = re.search(r'(qwiklabs-gcp-[\w-]+)', url)
    project_id = project_match.group(1) if project_match else None

    try:
        driver = get_driver()
        bot.send_message(chat_id, "✅ المتصفح جاهز (Xvfb + تخفي)")
    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل:\n`{str(e)[:300]}`", parse_mode="Markdown")
        return

    gen = int(time.time())

    with sessions_lock:
        user_sessions[chat_id] = {
            'driver': driver, 'running': False,
            'msg_id': None, 'url': url,
            'project_id': project_id,
            'shell_opened': False, 'auth': False,
            'gen': gen
        }

    session = user_sessions[chat_id]

    # فتح الرابط مباشرة
    bot.send_message(chat_id, "🌐 فتح الرابط...")

    try:
        driver.get(url)
    except Exception as e:
        if "timeout" not in str(e).lower():
            print(f"⚠️ {e}")

    time.sleep(5)

    try:
        handles = driver.window_handles
        if handles:
            driver.switch_to.window(handles[-1])

        png = driver.get_screenshot_as_png()
        bio = io.BytesIO(png)
        bio.name = f's_{int(time.time())}.png'

        msg = bot.send_photo(
            chat_id, bio,
            caption="🔴 بث مباشر\n📌 بدء...",
            reply_markup=panel()
        )

        session['msg_id'] = msg.message_id
        session['running'] = True

        t = threading.Thread(target=stream_loop, args=(chat_id, gen), daemon=True)
        t.start()

        bot.send_message(chat_id, "✅ البث يعمل! (تحديث كل ~10 ثوانٍ)")

    except Exception as e:
        bot.send_message(chat_id, f"❌ فشل:\n`{str(e)[:200]}`", parse_mode="Markdown")
        cleanup_session(chat_id)


# ─────────────────────────────────────────────
# 📨 أوامر
# ─────────────────────────────────────────────
@bot.message_handler(commands=['start'])
def cmd_start(message):
    bot.reply_to(message,
        "🚀 مرحباً!\n\n"
        "أرسل رابط يبدأ بـ:\n"
        "`https://www.skills.google/google_sso`",
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text and m.text.startswith('https://www.skills.google/google_sso'))
def handle_url(message):
    threading.Thread(target=start_stream, args=(message.chat.id, message.text), daemon=True).start()


@bot.message_handler(func=lambda m: m.text and m.text.startswith('http'))
def handle_bad(message):
    bot.reply_to(message, "❌ الرابط يجب أن يبدأ بـ:\n`https://www.skills.google/google_sso`", parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: True)
def on_cb(call):
    cid = call.message.chat.id
    try:
        with sessions_lock:
            if cid not in user_sessions:
                bot.answer_callback_query(call.id, "لا توجد جلسة.")
                return
            s = user_sessions[cid]

        if call.data == "stop":
            s['running'] = False
            s['gen'] = s.get('gen', 0) + 1
            bot.answer_callback_query(call.id, "تم الإيقاف.")
            try:
                bot.edit_message_caption("🛑 توقف.", chat_id=cid, message_id=s['msg_id'])
            except Exception:
                pass
            safe_quit(s.get('driver'))
            with sessions_lock:
                if cid in user_sessions:
                    del user_sessions[cid]
            gc.collect()

        elif call.data == "refresh":
            bot.answer_callback_query(call.id, "تحديث...")
            try:
                s['driver'].refresh()
            except Exception:
                pass
    except Exception:
        pass


# ─────────────────────────────────────────────
# 🏁 التشغيل
# ─────────────────────────────────────────────
def run_bot():
    print("✅ البوت يعمل...")
    while True:
        try:
            bot.polling(non_stop=True, timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ {e}")
            time.sleep(5)


if __name__ == '__main__':
    print("=" * 45)
    print("⚡ Xvfb + تخفي + خفيف (512MB)")
    print(f"🌐 بورت: {os.getenv('PORT', 8000)}")
    print("=" * 45)

    threading.Thread(target=start_health_server, daemon=True).start()
    run_bot()
