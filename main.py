import os
import time
import threading
import queue
import io
import http.server
import socketserver
import subprocess
import telebot
from telebot.types import InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import re
import base64
import pymongo
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import *
from pyvirtualdisplay import Display
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# ==========================================
# 💀 إعدادات النظام الأساسية
# ==========================================
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')
MONGO_URI = os.environ.get('MONGO_URI', '')

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 💾 إعدادات قاعدة البيانات MongoDB
# ==========================================
if MONGO_URI:
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.server_info()
        db = mongo_client['ocx_server_db']
        users_col = db['users']
        vips_col = db['vips']
        servers_col = db['servers']
        users_col.update_many({}, {"$set": {"active": False, "status": "idle"}})
        USE_MONGO = True
        print("✅ [DB] MongoDB Connected Successfully.")
    except Exception as e:
        users_col, servers_col, ram_vips = {}, {}, set()
        USE_MONGO = False
        print(f"⚠️ [DB] MongoDB Connection Failed: {e}. Using RAM mode.")
else:
    users_col, servers_col, ram_vips = {}, {}, set()
    USE_MONGO = False
    print("⚠️ [DB] No MONGO_URI provided. Using RAM mode.")

task_queue = queue.Queue()
driver_lock = threading.Lock()

if ADMIN_ID and not USE_MONGO:
    ram_vips.add(str(ADMIN_ID))

# ==========================================
# ☠️ قاتل Chrome الجذري
# ==========================================
def nuke_all_chrome():
    for proc in ['chrome', 'chromium', 'chromedriver', 'google-chrome']:
        try: subprocess.run(['pkill', '-9', '-f', proc], timeout=5, capture_output=True)
        except: pass
    try: subprocess.run(['killall', '-9', 'chrome', 'chromedriver'], timeout=5, capture_output=True)
    except: pass
    try: subprocess.run('rm -rf /tmp/.com.google.Chrome* /tmp/chrome_crashpad* /tmp/.org.chromium* /tmp/Temp-*', shell=True, timeout=5, capture_output=True)
    except: pass
    time.sleep(1)

nuke_all_chrome()

# ==========================================
# 🧹 محرك تنظيف الكوكيز
# ==========================================
def cookie_cleanup_worker():
    while True:
        time.sleep(12 * 60 * 60)
        try:
            if USE_MONGO:
                result = servers_col.update_many({}, {"$set": {"cookies": []}})
                print(f"🧹 [Cleanup] Cleared cookies from {result.modified_count} servers.")
            else:
                for url in servers_col: servers_col[url]['cookies'] = []
        except: pass

threading.Thread(target=cookie_cleanup_worker, daemon=True).start()

# ==========================================
# 🐕 حارس الجلسات المعلقة
# ==========================================
def session_watchdog():
    while True:
        time.sleep(180)
        try:
            if USE_MONGO:
                for s in users_col.find({"active": True}):
                    lt = s.get('interaction_time', 0)
                    if lt and (time.time() - lt > 600):
                        cid = s.get('chat_id')
                        clear_session(cid)
                        try: bot.send_message(cid, "⏳ **انتهت الجلسة تلقائياً.**\nأعد إرسال الرابط.", parse_mode="Markdown")
                        except: pass
            else:
                for cid, s in list(users_col.items()):
                    if s.get('active'):
                        lt = s.get('interaction_time', 0)
                        if lt and (time.time() - lt > 600):
                            clear_session(cid)
                            try: bot.send_message(cid, "⏳ **انتهت الجلسة تلقائياً.**\nأعد إرسال الرابط.", parse_mode="Markdown")
                            except: pass
        except: pass

threading.Thread(target=session_watchdog, daemon=True).start()

# ==========================================
# 🛡️ نظام الحماية (VIP System)
# ==========================================
def is_vip(user_id):
    str_id = str(user_id)
    if str_id == str(ADMIN_ID): return True
    if USE_MONGO: return vips_col.find_one({"user_id": str_id}) is not None
    else: return str_id in ram_vips

def add_vip_user(user_id):
    str_id = str(user_id)
    if USE_MONGO: vips_col.update_one({"user_id": str_id}, {"$set": {"user_id": str_id}}, upsert=True)
    else: ram_vips.add(str_id)

def remove_vip_user(user_id):
    str_id = str(user_id)
    if USE_MONGO: vips_col.delete_one({"user_id": str_id})
    else: ram_vips.discard(str_id)

def get_all_vips():
    if USE_MONGO: return [doc['user_id'] for doc in vips_col.find()]
    else: return list(ram_vips)

def send_unauthorized_msg(chat_id):
    try:
        m = bot.send_message(chat_id, "...", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.delete_message(chat_id, m.message_id)
    except: pass
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 التواصل لشراء البوت", url="https://t.me/aynX1"))
    msg = bot.send_message(chat_id, "⛔️ **عذراً، أنت غير مشترك في هذا البوت.**\n\nللاشتراك والحصول على الصلاحيات، يرجى التواصل مع الإدارة.", reply_markup=markup, parse_mode="Markdown")
    update_session(chat_id, {'unauth_msg_id': msg.message_id})

# ==========================================
# ⚙️ إدارة الجلسات
# ==========================================
def get_session(chat_id):
    try:
        if USE_MONGO:
            res = users_col.find_one({"chat_id": str(chat_id)})
            return res if res else {}
        return users_col.get(str(chat_id), {})
    except: return {}

def update_session(chat_id, data):
    try:
        if USE_MONGO:
            users_col.update_one({"chat_id": str(chat_id)}, {"$set": data}, upsert=True)
        else:
            if str(chat_id) not in users_col: users_col[str(chat_id)] = {"chat_id": str(chat_id)}
            users_col[str(chat_id)].update(data)
    except: pass

def clear_session(chat_id):
    update_session(chat_id, {
        "active": False, "status": "idle", "selected_region": None,
        "protocol": None, "target_url": None, "available_regions": {},
        "replace_mode": False, "add_new_mode": False,
        "ui_msg_id": None, "email": None, "password": None,
        "interaction_time": 0, "old_server_name": None
    })

def get_server_by_url(url):
    try:
        if USE_MONGO: return servers_col.find_one({"url": url})
        return servers_col.get(url)
    except: return None

def save_successful_server(chat_id, url, server_name, region, protocol, project_id, cookies=None):
    data = {
        "chat_id": str(chat_id), "url": url, "server_name": server_name,
        "region": region, "protocol": protocol, "project_id": project_id,
        "cookies": cookies or [], "timestamp": time.time()
    }
    try:
        if USE_MONGO: servers_col.update_one({"url": url}, {"$set": data}, upsert=True)
        else: servers_col[url] = data
    except: pass

def update_server_cookies(url, cookies):
    try:
        if USE_MONGO: servers_col.update_one({"url": url}, {"$set": {"cookies": cookies}}, upsert=True)
        else:
            if url not in servers_col: servers_col[url] = {}
            servers_col[url]['cookies'] = cookies
    except: pass

# ==========================================
# 💀 السكربت المولد
# ==========================================
VPN_SCRIPT_TEMPLATE = r"""#!/bin/bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --quiet 2>/dev/null || true

UUID=$(cat /proc/sys/kernel/random/uuid)
if [ "REPLACE_MODE_PLACEHOLDER" == "True" ]; then
    SERVICE_NAME="OLD_SERVER_NAME_PLACEHOLDER"
else
    SERVICE_NAME="ocx-server-max"
fi

REGION="TARGET_REGION_PLACEHOLDER"
PORT=8080
WS_PATH="/@O_C_X7"
PROTOCOL="PROTOCOL_NAME_PLACEHOLDER"

rm -rf ~/ultra-v4 && mkdir -p ~/ultra-v4 && cd ~/ultra-v4

cat > Dockerfile << 'DEOF'
FROM alpine:3.19
RUN apk add --no-cache wget unzip ca-certificates bash curl jq
RUN wget -qO /tmp/xray.zip "https://github.com/XTLS/Xray-core/releases/download/v1.8.7/Xray-linux-64.zip" && \
    mkdir -p /opt/xray && unzip /tmp/xray.zip -d /opt/xray && chmod +x /opt/xray/xray && \
    rm -f /tmp/xray.zip && apk del wget unzip && rm -rf /var/cache/apk/*
COPY config.json /opt/xray/config.json
COPY start.sh /start.sh
RUN chmod +x /start.sh
ENV XRAY_LOCATION_ASSET=/opt/xray
ENV GOMAXPROCS=2
ENV GOMEMLIMIT=1500MiB
EXPOSE 8080
CMD ["/start.sh"]
DEOF

cat > config.json << XEOF
<INBOUND_CONFIG_PLACEHOLDER>
XEOF

cat > start.sh << 'EEOF'
#!/bin/bash
sysctl -w net.ipv4.tcp_congestion_control=bbr 2>/dev/null
sysctl -w net.core.default_qdisc=fq 2>/dev/null
exec /opt/xray/xray run -config /opt/xray/config.json
EEOF

cat > .dockerignore << 'EOF'
.git
*.md
EOF

echo "Attempting Ultimate Gaming Deployment..."
gcloud run deploy ${SERVICE_NAME} \
  --source . \
  --region=${REGION} \
  --platform=managed \
  --allow-unauthenticated \
  --cpu=2 \
  --memory=2048Mi \
  --min-instances=1 \
  --max-instances=4 \
  --concurrency=250 \
  --timeout=3600 \
  --port=${PORT} \
  --session-affinity \
  --no-cpu-throttling \
  --quiet

if [ $? -ne 0 ]; then
    echo "First attempt rejected. Retrying with Safe Mode..."
    gcloud run deploy ${SERVICE_NAME} \
      --source . \
      --region=${REGION} \
      --platform=managed \
      --allow-unauthenticated \
      --cpu=2 \
      --memory=2048Mi \
      --min-instances=1 \
      --max-instances=4 \
      --concurrency=250 \
      --timeout=3600 \
      --port=${PORT} \
      --session-affinity \
      --quiet

    if [ $? -ne 0 ]; then
        ERROR_PAYLOAD=$(jq -n \
          --arg chat_id "<CHAT_ID_PLACEHOLDER>" \
          --arg text "❌ **فشل البناء النهائي (Deployment Failed):**

حساب Qwiklabs هذا محظور كلياً أو مساحته ممتلئة ولا يقبل إنشاء أي خوادم جديدة في منطقة \`${REGION}\`.

💡 **الحل:** استخدم أمر /cancel ، وجرب منطقة مختلفة تماماً (مثل us-central1)، أو قم بتسجيل الدخول بحساب Qwiklabs جديد ونظيف." \
          '{chat_id: $chat_id, text: $text, parse_mode: "Markdown"}')

        curl -s -X POST "https://api.telegram.org/bot<BOT_TOKEN_PLACEHOLDER>/sendMessage" \
          -H "Content-Type: application/json" \
          -d "$ERROR_PAYLOAD" > /dev/null

        echo "ERROR_DEPLOYMENT_FAILED_OCX_CATCH"
        exit 1
    fi
fi

SERVICE_HOST="${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

<LINK_GENERATION_PLACEHOLDER>

echo "OCX_DATA_SYNC: ${SERVICE_NAME}|${REGION}|${PROTOCOL}|${UUID}"
sleep 2

JSON_PAYLOAD=$(jq -n \
  --arg chat_id "<CHAT_ID_PLACEHOLDER>" \
  --arg text "✅ **تم بناء السيرفر بنجاح واحترافية!** 🚀🔥

🛡️ **البروتوكول:** \`${PROTOCOL}\`
📍 **المنطقـــة:** \`${REGION}\`
🆔 **المعرف (UUID):** \`${UUID}\`

🔗 **رابط الاتصال المباشر (اضغط للنسخ):**
\`\`\`
${VPN_LINK}
\`\`\`

*تمت العملية بواسطة 💎 OCX PRO System.*" \
  '{chat_id: $chat_id, text: $text, parse_mode: "Markdown"}')

curl -s -X POST "https://api.telegram.org/bot<BOT_TOKEN_PLACEHOLDER>/sendMessage" \
  -H "Content-Type: application/json" \
  -d "$JSON_PAYLOAD" > /dev/null

echo "SUCCESS_OCX_FINISH"
"""

def translate_region(name):
    translations = {'Netherlands': 'هولندا 🇳🇱', 'South Carolina': 'ساوث كارولينا 🇺🇸', 'Oregon': 'أوريغون 🇺🇸', 'Iowa': 'آيوا 🇺🇸', 'Belgium': 'بلجيكا 🇧🇪', 'London': 'لندن 🇬🇧', 'Frankfurt': 'فرانكفورت 🇩🇪', 'Taiwan': 'تايوان 🇹🇼', 'Tokyo': 'طوكيو 🇯🇵', 'Singapore': 'سنغافورة 🇸🇬', 'Sydney': 'سيدني 🇦🇺', 'Mumbai': 'مومباي 🇮🇳', 'Oslo': 'أوسلو 🇳🇴', 'Finland': 'فنلندا 🇫🇮', 'Montreal': 'مونتريال 🇨🇦', 'Toronto': 'تورونتو 🇨🇦', 'Sao Paulo': 'ساو باولو 🇧🇷', 'Jakarta': 'جاكرتا 🇮🇩', 'Las Vegas': 'لاس فيغاس 🇺🇸', 'لوس أنجلوس': 'لوس أنجلوس 🇺🇸', 'Los Angeles': 'لوس أنجلوس 🇺🇸', 'Northern Virginia': 'فرجينيا 🇺🇸', 'Salt Lake City': 'سولت ليك 🇺🇸', 'Seoul': 'سيول 🇰🇷', 'Zurich': 'زيورخ 🇨🇭', 'Milan': 'ميلانو 🇮🇹', 'Madrid': 'مدريد 🇪🇸', 'Paris': 'باريس 🇫🇷', 'Warsaw': 'وارسو 🇵🇱'}
    for key, val in translations.items():
        if key.lower() in name.lower(): return val
    return f"{name} 🏳️"

class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200); self.send_header('Content-type', 'text/plain'); self.end_headers(); self.wfile.write(b"OK")
        else: self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass

def run_health_server():
    socketserver.TCPServer.allow_reuse_address = True
    port = int(os.environ.get("PORT", 8080))
    with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd: httpd.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

# ==========================================
# 🚀 محرك المتصفح (BULLETPROOF V4 - Auto Retry)
# ==========================================
display = Display(visible=0, size=(1280, 800))
display.start()

def create_driver():
    nuke_all_chrome()
    time.sleep(2)

    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-background-networking')
    options.add_argument('--disable-default-apps')
    options.add_argument('--disable-sync')
    options.add_argument('--disable-translate')
    options.add_argument('--disable-hang-monitor')
    options.add_argument('--disable-component-update')
    options.add_argument('--disable-backgrounding-occluded-windows')
    options.add_argument('--disable-renderer-backgrounding')
    options.add_argument('--disable-background-timer-throttling')
    options.add_argument('--disable-ipc-flooding-protection')
    options.add_argument('--disable-client-side-phishing-detection')
    options.add_argument('--disable-popup-blocking')
    options.add_argument('--disable-prompt-on-repost')
    options.add_argument('--no-first-run')
    options.add_argument('--incognito')
    # === الفرق الجذري: لا --single-process ولا --no-zygote ===
    # هذا يسمح لـ Chrome بالتعافي إذا انهار الـ renderer
    options.add_argument('--renderer-process-limit=1')
    options.add_argument('--disable-features=site-per-process,VizDisplayCompositor,TranslateUI')
    options.add_argument('--js-flags=--max-old-space-size=256')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disk-cache-size=0')
    options.add_argument('--media-cache-size=0')
    options.add_argument('--aggressive-cache-discard')
    options.add_argument('--disable-cache')
    options.add_argument('--disable-application-cache')
    options.add_argument('--crash-dumps-dir=/tmp/chrome-crashes')
    options.page_load_strategy = 'eager'
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,
    })
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')

    service = Service(log_output=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    driver.set_page_load_timeout(150)
    driver.set_script_timeout(30)
    driver.implicitly_wait(3)
    return driver

def get_driver_safe():
    last_error = None
    for attempt in range(1, 4):
        try:
            print(f"🔧 [Chrome] Creating driver (attempt {attempt}/3)...")
            d = create_driver()
            # اختبار سريع: هل يعمل فعلاً؟
            d.get("about:blank")
            print(f"✅ [Chrome] Driver OK on attempt {attempt}")
            return d
        except Exception as e:
            last_error = e
            print(f"❌ [Chrome] Attempt {attempt} failed: {e}")
            nuke_all_chrome()
            time.sleep(5)
    raise Exception(f"DRIVER_CREATION_FAILED: {last_error}")

def alive(driver):
    if not driver: return False
    try:
        _ = driver.title
        return True
    except: return False

def safe_get(driver, url):
    try:
        driver.get(url)
        return True
    except TimeoutException:
        try: driver.execute_script("window.stop();")
        except: pass
        return True
    except Exception as e:
        err = str(e).lower()
        if any(k in err for k in ['crash', 'not reachable', 'session', 'disconnected', 'no such window', 'target closed']):
            return False
        try: driver.execute_script("window.stop();")
        except: pass
        return True

def safe_exec(driver, script, *args):
    try: return driver.execute_script(script, *args)
    except: return None

def safe_find(driver, by, value):
    try: return driver.find_elements(by, value)
    except: return []

def safe_screenshot(driver):
    try: return driver.get_screenshot_as_png()
    except: return None

def safe_source(driver):
    try: return driver.page_source
    except: return ""

def safe_url(driver):
    try: return driver.current_url
    except: return ""

def safe_cookies(driver):
    try: return driver.get_cookies()
    except: return []

def destroy_driver(driver):
    if driver:
        try: driver.quit()
        except: pass
    nuke_all_chrome()

def safe_delete_msg(chat_id, msg_id):
    if msg_id:
        try: bot.delete_message(chat_id, msg_id)
        except: pass

def inject_cookies_safely(driver, cookies):
    if not cookies: return
    try:
        safe_get(driver, "https://google.com/robots.txt")
        time.sleep(1)
        for c in cookies:
            if 'google.com' in c.get('domain', ''):
                try: driver.add_cookie(c)
                except: pass
        safe_get(driver, "https://console.cloud.google.com/robots.txt")
        time.sleep(1)
        for c in cookies:
            if 'cloud.google.com' in c.get('domain', ''):
                try: driver.add_cookie(c)
                except: pass
    except: pass

def cleanup_browser_memory(driver):
    """تنظيف ذاكرة المتصفح أثناء التشغيل"""
    safe_exec(driver, """
        if(window.gc) window.gc();
        if(window.performance && window.performance.memory) {
            try { window.performance.clearResourceTimings(); } catch(e){}
        }
        try {
            var highResEntries = performance.getEntriesByType("resource");
            if(highResEntries.length > 100) performance.clearResourceTimings();
        } catch(e) {}
    """)

def update_live_stream(chat_id, msg_id, status_text, logs=None, driver=None, is_photo=False):
    if not msg_id: return
    if logs is not None:
        final_text = f"🟢 *نظام OCX | التتبع المباشر*\n━━━━━━━━━━━━━━━━━\n**العملية:** {status_text}\n```bash\n> {logs}\n```\n━━━━━━━━━━━━━━━━━"
    else:
        final_text = status_text
    try:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
        if is_photo:
            if driver and alive(driver):
                ss = safe_screenshot(driver)
                if ss:
                    try:
                        media = InputMediaPhoto(ss, caption=final_text, parse_mode="Markdown")
                        bot.edit_message_media(chat_id=chat_id, message_id=msg_id, media=media, reply_markup=markup)
                        return
                    except: pass
            try: bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=final_text, parse_mode="Markdown", reply_markup=markup)
            except: pass
        else:
            try: bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=final_text, parse_mode="Markdown", reply_markup=markup)
            except: pass
    except: pass

# ==========================================
# ⚙️ محرك المهام (مع إعادة محاولة تلقائية)
# ==========================================
RESULT_SUCCESS = "SUCCESS"
RESULT_RETRY = "RETRY"
RESULT_ABORT = "ABORT"

def run_single_task(chat_id, url, attempt_num):
    """
    تنفيذ مهمة واحدة.
    يرجع: RESULT_SUCCESS, RESULT_RETRY, أو RESULT_ABORT
    """
    driver = None
    status_msg_id = None
    is_status_photo = False

    try:
        with driver_lock:
            driver = get_driver_safe()

        current_session = get_session(chat_id)
        existing_server = get_server_by_url(url)
        saved_project_id = existing_server.get('project_id', '') if existing_server else ''
        saved_cookies = existing_server.get('cookies', []) if existing_server else []

        target_url_to_load = url
        initial_state = "INIT"
        sso_tried = True

        if saved_project_id and (current_session.get('replace_mode') or current_session.get('add_new_mode')):
            if current_session.get('replace_mode'):
                target_url_to_load = f"https://shell.cloud.google.com/?enableapi=true&project={saved_project_id}&pli=1&show=terminal"
                initial_state = "AUTHORIZE_SHELL"
            else:
                target_url_to_load = f"https://console.cloud.google.com/run/services?project={saved_project_id}"
                initial_state = "WAIT_DEPLOY"
            sso_tried = False

        if not safe_get(driver, target_url_to_load):
            raise Exception("CHROME_CRASH_ON_LOAD")

        state = initial_state
        cookies_tried = False
        time.sleep(3)

        # رسالة البث المباشر
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
        retry_note = f"\n🔄 *(المحاولة {attempt_num})*" if attempt_num > 1 else ""

        ss = safe_screenshot(driver)
        if ss:
            try:
                msg = bot.send_photo(chat_id, photo=ss, caption=f"🟢 **سجل العمليات المباشر:**\n⚡ جاري تهيئة الاتصال المشفر...{retry_note}", parse_mode="Markdown", reply_markup=markup)
                is_status_photo = True
            except:
                msg = bot.send_message(chat_id, f"🟢 **سجل العمليات المباشر:**\n⚡ جاري تهيئة الاتصال المشفر...{retry_note}", parse_mode="Markdown", reply_markup=markup)
        else:
            msg = bot.send_message(chat_id, f"🟢 **سجل العمليات المباشر:**\n⚡ جاري تهيئة الاتصال المشفر...{retry_note}", parse_mode="Markdown", reply_markup=markup)
        status_msg_id = msg.message_id

        loop_count = 0
        project_id = saved_project_id or ""
        dead_checks = 0

        while get_session(chat_id).get('active') and loop_count < 250:
            loop_count += 1
            time.sleep(3)

            if not get_session(chat_id).get('active'):
                safe_delete_msg(chat_id, status_msg_id)
                return RESULT_ABORT

            # === فحص حياة المتصفح ===
            if not alive(driver):
                dead_checks += 1
                if dead_checks >= 3:
                    print(f"☠️ [Chrome] Dead for {dead_checks} checks, triggering retry")
                    safe_delete_msg(chat_id, status_msg_id)
                    return RESULT_RETRY
                time.sleep(2)
                continue
            dead_checks = 0

            # === تنظيف الذاكرة كل 15 دورة ===
            if loop_count % 15 == 0:
                cleanup_browser_memory(driver)

            current_url = safe_url(driver)
            if not current_url:
                continue

            current_session = get_session(chat_id)
            update_session(chat_id, {'interaction_time': time.time()})

            # === مهلة الانتظار ===
            if current_session.get('status') == 'waiting_credentials' or state == "WAIT_USER_SELECTION":
                last_interaction = current_session.get('interaction_time', time.time())
                if time.time() - last_interaction > 90:
                    safe_delete_msg(chat_id, status_msg_id)
                    safe_delete_msg(chat_id, current_session.get('ui_msg_id'))
                    msg_to = bot.send_message(chat_id, "⏳ **تم إنهاء الجلسة تلقائياً!**\n\nتجاوزت مهلة الاستجابة.\nيرجى إرسال الرابط مرة أخرى.", parse_mode="Markdown")
                    threading.Timer(300.0, lambda m=msg_to.message_id: safe_delete_msg(chat_id, m)).start()
                    return RESULT_ABORT

            # === صفحة تسجيل الدخول ===
            if 'accounts.google.com' in current_url:
                page_lower = safe_source(driver).lower()

                if "couldn't sign you in" in page_lower or "domain admin" in page_lower or "admin for help" in page_lower:
                    safe_delete_msg(chat_id, status_msg_id)
                    bot.send_message(chat_id, "❌ **تم حظر تسجيل الدخول بواسطة Google.**\n\n💡 أغلق اللاب الحالي وابدأ لاب جديد.", parse_mode="Markdown")
                    return RESULT_ABORT

                email_inputs = safe_find(driver, By.XPATH, "//input[@type='email']")
                pass_inputs = safe_find(driver, By.XPATH, "//input[@type='password']")

                if email_inputs and email_inputs[0].is_displayed() and not (pass_inputs and pass_inputs[0].is_displayed()):
                    if not sso_tried:
                        update_live_stream(chat_id, status_msg_id, "🔄 **جاري التحويل عبر SSO...**", driver=driver, is_photo=is_status_photo)
                        sso_tried = True
                        if not safe_get(driver, url):
                            safe_delete_msg(chat_id, status_msg_id)
                            return RESULT_RETRY
                        state = "INIT"
                        time.sleep(2)
                        continue
                    elif not cookies_tried and saved_cookies:
                        update_live_stream(chat_id, status_msg_id, "⚡ **استعادة ذكية: حقن الكوكيز...**", driver=driver, is_photo=is_status_photo)
                        inject_cookies_safely(driver, saved_cookies)
                        cookies_tried = True
                        if not safe_get(driver, target_url_to_load):
                            safe_delete_msg(chat_id, status_msg_id)
                            return RESULT_RETRY
                        state = initial_state
                        time.sleep(2)
                        continue
                    elif current_session.get('status') != 'waiting_credentials' and not current_session.get('email'):
                        safe_delete_msg(chat_id, status_msg_id)
                        msg = bot.send_message(chat_id, "⚠️ **توقف - مطلوب بيانات الدخول.**\n\nالرجاء إرسال **الإيميل** و **الباسورد** الخاصين بـ Qwiklabs.\n\nمثال:\n`student-02-xxx@qwiklabs.net Password123`", parse_mode="Markdown")
                        update_session(chat_id, {'status': 'waiting_credentials', 'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
                        status_msg_id = msg.message_id
                        continue

                if current_session.get('email') and current_session.get('password'):
                    try:
                        if email_inputs and email_inputs[0].is_displayed():
                            update_live_stream(chat_id, status_msg_id, "مصادقة الحساب", f"[المصادقة] إدخال البريد: {current_session.get('email')}", driver=driver, is_photo=is_status_photo)
                            email_inputs[0].clear()
                            email_inputs[0].send_keys(current_session.get('email'))
                            email_inputs[0].send_keys(Keys.ENTER)
                            time.sleep(2)
                            continue
                        elif pass_inputs and pass_inputs[0].is_displayed():
                            update_live_stream(chat_id, status_msg_id, "مصادقة الحساب", "[المصادقة] إدخال كلمة المرور... ***", driver=driver, is_photo=is_status_photo)
                            pass_inputs[0].clear()
                            pass_inputs[0].send_keys(current_session.get('password'))
                            pass_inputs[0].send_keys(Keys.ENTER)
                            time.sleep(3)
                            update_session(chat_id, {'email': None, 'password': None})
                            state = "INIT"
                            safe_delete_msg(chat_id, status_msg_id)
                            markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
                            ss = safe_screenshot(driver)
                            if ss:
                                try:
                                    msg = bot.send_photo(chat_id, photo=ss, caption="🟢 **سجل العمليات:**\n✅ تمت المصادقة بنجاح...", parse_mode="Markdown", reply_markup=markup)
                                    is_status_photo = True
                                except:
                                    msg = bot.send_message(chat_id, "🟢 **سجل العمليات:**\n✅ تمت المصادقة بنجاح...", parse_mode="Markdown", reply_markup=markup)
                                    is_status_photo = False
                            else:
                                msg = bot.send_message(chat_id, "🟢 **سجل العمليات:**\n✅ تمت المصادقة بنجاح...", parse_mode="Markdown", reply_markup=markup)
                                is_status_photo = False
                            status_msg_id = msg.message_id
                            continue
                    except Exception as e:
                        print(f"Login Error: {e}")

            if current_session.get('status') == 'waiting_credentials':
                continue

            # === حالات الآلة ===
            if state == "WAIT_USER_SELECTION":
                if current_session.get('selected_region') and current_session.get('protocol'):
                    if project_id:
                        if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={project_id}&pli=1&show=terminal"):
                            safe_delete_msg(chat_id, status_msg_id)
                            return RESULT_RETRY
                        state = "AUTHORIZE_SHELL"
                continue

            elif state == "SILENT_BUILD":
                page_source = safe_source(driver)
                if not page_source and not alive(driver):
                    safe_delete_msg(chat_id, status_msg_id)
                    return RESULT_RETRY

                if "ERROR_DEPLOYMENT_FAILED_OCX_CATCH" in page_source:
                    safe_delete_msg(chat_id, status_msg_id)
                    return RESULT_ABORT

                sync_match = re.search(r'OCX_DATA_SYNC:\s*(.*?)\|(.*?)\|(.*?)\|(.*?)(?:\n|<)', page_source)
                if sync_match:
                    s_name, s_reg, s_proto, _ = sync_match.groups()
                    save_successful_server(chat_id, url, s_name, s_reg, s_proto, project_id, safe_cookies(driver))

                if "SUCCESS_OCX_FINISH" in page_source:
                    safe_delete_msg(chat_id, status_msg_id)
                    return RESULT_SUCCESS
                else:
                    update_live_stream(chat_id, status_msg_id, f"🟢 **سجل العمليات المباشر:**\n⚙️ يتم بناء الحاوية...\n⏳ الوقت المنقضي: {loop_count*3} ثانية", driver=driver, is_photo=is_status_photo)
                    continue
            else:
                ar_map = {"INIT": "التهيئة واجتياز الشروط", "WAIT_DEPLOY": "البحث عن واجهة البناء", "WAIT_REGION": "تحميل خريطة السيرفرات", "EXTRACT_REGIONS": "استخراج البيانات المعمارية", "AUTHORIZE_SHELL": "تفويض صلاحيات الطرفية", "WAIT_TERMINAL_BOOT": "تشغيل بيئة Linux", "INJECT_PAYLOAD": "حقن السكربت الرئيسي"}
                ar_state = ar_map.get(state, state)
                update_live_stream(chat_id, status_msg_id, f"🟢 **سجل العمليات المباشر:**\n🌐 المرحلة: `{ar_state}`", driver=driver, is_photo=is_status_photo)

            # === أزرار الموافقة ===
            try:
                agree_btns = safe_find(driver, By.XPATH, "//button[contains(., 'Agree and continue') or contains(., 'موافق ومتابعة') or contains(., 'Akkoord en doorgaan')]")
                visible_btn = next((b for b in agree_btns if b.is_displayed()), None)
                if visible_btn:
                    for cb in safe_find(driver, By.XPATH, "//*[@role='checkbox'] | //mat-checkbox | //input[@type='checkbox']"):
                        safe_exec(driver, "arguments[0].click();", cb)
                    time.sleep(1)
                    safe_exec(driver, "arguments[0].click();", visible_btn)
            except: pass

            if state == "INIT":
                if 'accounts.google.com' in current_url:
                    try:
                        elements = safe_find(driver, By.XPATH, "//*[@id='confirm'] | //input[@type='submit'] | //button | //div[@role='button'] | //span")
                        for el in elements:
                            text = ((el.text or el.get_attribute('value') or '') if el else '').lower()
                            el_id = (el.get_attribute('id') or '') if el else ''
                            if any(k in text for k in ['understand', 'begrijp', 'accept', 'أفهم', 'موافق', 'continue', 'متابعة']) or el_id == 'confirm':
                                safe_exec(driver, "arguments[0].click();", el)
                                break
                    except: pass
                elif 'console.cloud.google.com' in current_url:
                    match = re.search(r'project=([^&#]+)', current_url)
                    if match:
                        extracted_project_id = match.group(1)
                        project_id = saved_project_id if (saved_project_id and (current_session.get('replace_mode') or current_session.get('add_new_mode'))) else extracted_project_id
                        fresh_cookies = safe_cookies(driver)
                        if fresh_cookies: update_server_cookies(url, fresh_cookies)
                        update_live_stream(chat_id, status_msg_id, "🟢 **سجل العمليات:**\n🔐 تم الوصول بنجاح.", driver=driver, is_photo=is_status_photo)
                        time.sleep(1)
                        if current_session.get('replace_mode'):
                            if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={project_id}&pli=1&show=terminal"):
                                safe_delete_msg(chat_id, status_msg_id)
                                return RESULT_RETRY
                            state = "AUTHORIZE_SHELL"
                        else:
                            if not safe_get(driver, f"https://console.cloud.google.com/run/services?project={project_id}"):
                                safe_delete_msg(chat_id, status_msg_id)
                                return RESULT_RETRY
                            state = "WAIT_DEPLOY"

            elif state == "WAIT_DEPLOY":
                for btn in safe_find(driver, By.XPATH, "//*[contains(text(), 'Deploy container')]"):
                    try:
                        if btn.is_displayed():
                            safe_exec(driver, "arguments[0].click();", btn)
                            state = "WAIT_REGION"
                            break
                    except: pass

            elif state == "WAIT_REGION":
                safe_exec(driver, "document.querySelectorAll('button').forEach(b => { if(b.innerText.includes('OK, got it') || b.innerText.includes('Accept')) b.click() })")
                for re_elem in safe_find(driver, By.XPATH, "//*[contains(text(), 'Region') and not(contains(text(), 'Regions'))]"):
                    try:
                        if re_elem.is_displayed():
                            safe_exec(driver, "arguments[0].scrollIntoView({block: 'center'});", re_elem)
                            time.sleep(1)
                            safe_exec(driver, "arguments[0].click();", re_elem)
                            state = "EXTRACT_REGIONS"
                            break
                    except: pass
                else:
                    safe_exec(driver, "window.scrollBy(0, 300);")

            elif state == "EXTRACT_REGIONS":
                if current_session.get('replace_mode'):
                    state = "WAIT_USER_SELECTION"
                    continue
                time.sleep(1)
                regions_list = []
                for opt in safe_find(driver, By.XPATH, "//*[@role='option'] | //mat-option | //*[contains(@class, 'mat-option-text')]"):
                    try:
                        text = (opt.get_attribute('textContent') or opt.text or '').strip()
                        if len(text) > 3 and "Select" not in text and text not in [r['raw'] for r in regions_list]:
                            text = " ".join(text.split())
                            match = re.search(r'^([a-z0-9-]+)\s*\(([^)]+)\)', text)
                            if match: reg_id, reg_name = match.group(1), match.group(2)
                            else: reg_id, reg_name = text.split()[0], text
                            if reg_id.startswith('us-') or reg_id.startswith('northamerica-') or reg_id.startswith('southamerica-'): continent = 'أمريكا 🌎'
                            elif reg_id.startswith('europe-'): continent = 'أوروبا 🌍'
                            elif reg_id.startswith('asia-'): continent = 'آسيا 🌏'
                            elif reg_id.startswith('australia-'): continent = 'أستراليا 🦘'
                            elif reg_id.startswith('me-') or reg_id.startswith('africa-'): continent = 'الشرق الأوسط وأفريقيا 🐪'
                            else: continent = 'أخرى 🗺️'
                            regions_list.append({'id': reg_id, 'name': reg_name, 'continent': continent, 'raw': text})
                    except: pass

                if regions_list:
                    grouped_regions = {}
                    for r in regions_list: grouped_regions.setdefault(r['continent'], []).append(r)
                    update_session(chat_id, {'available_regions': grouped_regions, 'project_id': project_id})
                    safe_delete_msg(chat_id, status_msg_id)
                    status_msg_id = None
                    markup = InlineKeyboardMarkup(row_width=2)
                    markup.add(*[InlineKeyboardButton(text=c, callback_data=f"cont_{c}") for c in grouped_regions.keys()])
                    msg = bot.send_message(chat_id, "📍 **تم جلب السيرفرات المتاحة بنجاح.**\n\n👇 اختر القارة:", reply_markup=markup, parse_mode="Markdown")
                    update_session(chat_id, {'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
                    state = "WAIT_USER_SELECTION"
                else:
                    safe_exec(driver, "document.body.click();")
                    time.sleep(1)
                    try:
                        cv = driver.find_element(By.XPATH, "//*[contains(text(), 'Region')]/following::*[@role='combobox'][1]")
                        ActionChains(driver).move_to_element(cv).click().perform()
                    except: pass

            elif state == "AUTHORIZE_SHELL":
                if status_msg_id is None:
                    safe_delete_msg(chat_id, current_session.get('ui_msg_id'))
                    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
                    ss = safe_screenshot(driver)
                    if ss:
                        try:
                            msg = bot.send_photo(chat_id, photo=ss, caption="🟢 **سجل العمليات:**\n🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=markup)
                            is_status_photo = True
                        except:
                            msg = bot.send_message(chat_id, "🟢 **سجل العمليات:**\n🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=markup)
                            is_status_photo = False
                    else:
                        msg = bot.send_message(chat_id, "🟢 **سجل العمليات:**\n🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=markup)
                        is_status_photo = False
                    status_msg_id = msg.message_id

                js_fast_click = """
                function attemptClick(rootDoc) {
                    if (!rootDoc) return false;
                    let elements = rootDoc.querySelectorAll('button, span.mdc-button__label, modal-action button, a, [role="button"]');
                    for (let el of elements) {
                        let text = (el.innerText || el.textContent || '').trim();
                        if (['Continue', 'Doorgaan', 'متابعة', 'Continuer'].includes(text)) { try { el.click(); } catch(e) {} }
                        if (['Authorize', 'Autoriser', 'تخويل', 'Autoriseren'].includes(text) || (text.includes('Authorize') && text.length <= 15)) {
                            try { el.click(); } catch(e) {}
                            el.querySelectorAll('span').forEach(s => { try{ s.click() } catch(e){} });
                            return true;
                        }
                    }
                    for (let el of rootDoc.querySelectorAll('*')) {
                        if (el.shadowRoot && attemptClick(el.shadowRoot)) return true;
                    }
                    return false;
                }
                if (attemptClick(document)) return true;
                for (let f of document.querySelectorAll('iframe')) {
                    try { if (attemptClick(f.contentDocument)) return true; } catch(e) {}
                }
                return false;
                """
                if safe_exec(driver, js_fast_click):
                    state = "WAIT_TERMINAL_BOOT"

            elif state == "WAIT_TERMINAL_BOOT":
                js_check = "function checkTerm(root){if(root.querySelector('textarea.xterm-helper-textarea'))return true;for(let f of root.querySelectorAll('iframe')){try{if(checkTerm(f.contentDocument))return true;}catch(e){}}return false;} return checkTerm(document);"
                if safe_exec(driver, js_check):
                    time.sleep(1)
                    state = "INJECT_PAYLOAD"

            elif state == "INJECT_PAYLOAD":
                update_live_stream(chat_id, status_msg_id, "تثبيت النواة", "[الأنظمة] حقن كود OCX...", driver=driver, is_photo=is_status_photo)
                current_session = get_session(chat_id)
                selected_reg = current_session.get('selected_region', 'europe-west4')
                protocol = current_session.get('protocol', 'vless')
                replace_mode = current_session.get('replace_mode', False)
                old_server_name = current_session.get('old_server_name', '')
                proto_name = protocol.upper()

                if protocol == 'vmess':
                    inbound_cfg = r"""{"log": {"loglevel": "none"},"inbounds": [{"listen": "0.0.0.0", "port": ${PORT}, "protocol": "vmess","settings": {"clients": [{"id": "${UUID}", "alterId": 0}]},"streamSettings": {"network": "ws", "wsSettings": {"path": "${WS_PATH}", "maxEarlyData": 1024, "earlyDataHeaderName": "Sec-WebSocket-Protocol"}},"sniffing": {"enabled": false}}],"outbounds": [{"protocol": "freedom", "settings": {"domainStrategy": "AsIs"}}],"policy": {"levels": {"0": {"handshake": 1, "connIdle": 600, "uplinkOnly": 1, "downlinkOnly": 1}}}}"""
                    link_gen = r"""VMESS_JSON="{\"v\":\"2\",\"ps\":\"𝗢 𝗖 𝗫 ⚡️\",\"add\":\"vpn.googleapis.com\",\"port\":\"443\",\"id\":\"${UUID}\",\"aid\":\"0\",\"net\":\"ws\",\"type\":\"none\",\"host\":\"${SERVICE_HOST}\",\"path\":\"/%40O_C_X7\",\"tls\":\"tls\",\"sni\":\"yt.be\"}" && VPN_LINK="vmess://$(echo -n "$VMESS_JSON" | base64 -w 0)" """
                elif protocol == 'trojan':
                    inbound_cfg = r"""{"log": {"loglevel": "none"},"inbounds": [{"listen": "0.0.0.0", "port": ${PORT}, "protocol": "trojan","settings": {"clients": [{"password": "${UUID}"}]},"streamSettings": {"network": "ws", "wsSettings": {"path": "${WS_PATH}", "maxEarlyData": 1024, "earlyDataHeaderName": "Sec-WebSocket-Protocol"}},"sniffing": {"enabled": false}}],"outbounds": [{"protocol": "freedom", "settings": {"domainStrategy": "AsIs"}}],"policy": {"levels": {"0": {"handshake": 1, "connIdle": 600, "uplinkOnly": 1, "downlinkOnly": 1}}}}"""
                    link_gen = r"""VPN_LINK="trojan://${UUID}@vpn.googleapis.com:443?path=/%40O_C_X7&security=tls&host=${SERVICE_HOST}&type=ws&sni=yt.be#𝗢 𝗖 𝗫 ⚡️" """
                else:
                    inbound_cfg = r"""{"log": {"loglevel": "none"},"inbounds": [{"listen": "0.0.0.0", "port": ${PORT}, "protocol": "vless","settings": {"clients": [{"id": "${UUID}", "level": 0}], "decryption": "none"},"streamSettings": {"network": "ws", "wsSettings": {"path": "${WS_PATH}", "maxEarlyData": 1024, "earlyDataHeaderName": "Sec-WebSocket-Protocol"}},"sniffing": {"enabled": false}}],"outbounds": [{"protocol": "freedom", "settings": {"domainStrategy": "AsIs"}}],"policy": {"levels": {"0": {"handshake": 1, "connIdle": 600, "uplinkOnly": 1, "downlinkOnly": 1}}}}"""
                    link_gen = r"""VPN_LINK="vless://${UUID}@vpn.googleapis.com:443?path=/%40O_C_X7&security=tls&encryption=none&host=${SERVICE_HOST}&type=ws&sni=yt.be#𝗢 𝗖 𝗫 ⚡️" """

                final_script = VPN_SCRIPT_TEMPLATE.replace("<INBOUND_CONFIG_PLACEHOLDER>", inbound_cfg).replace("<LINK_GENERATION_PLACEHOLDER>", link_gen).replace("TARGET_REGION_PLACEHOLDER", selected_reg).replace("PROTOCOL_NAME_PLACEHOLDER", proto_name).replace("<BOT_TOKEN_PLACEHOLDER>", BOT_TOKEN).replace("<CHAT_ID_PLACEHOLDER>", str(chat_id))
                if replace_mode and old_server_name:
                    final_script = final_script.replace("REPLACE_MODE_PLACEHOLDER", "True").replace("OLD_SERVER_NAME_PLACEHOLDER", old_server_name)
                else:
                    final_script = final_script.replace("REPLACE_MODE_PLACEHOLDER", "False")

                b64_script = base64.b64encode(final_script.encode('utf-8')).decode('utf-8')
                cmd_payload = f"clear && echo '{b64_script}' | base64 -d > deploy.sh && chmod +x deploy.sh && ./deploy.sh\n"

                js_inject = """
                function pasteToTerminal(root, text) {
                    let textareas = root.querySelectorAll('textarea.xterm-helper-textarea');
                    for (let ta of textareas) {
                        ta.focus();
                        const dt = new DataTransfer();
                        dt.setData('text/plain', text);
                        ta.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
                        setTimeout(() => { ta.dispatchEvent(new KeyboardEvent('keydown', {bubbles: true, cancelable: true, keyCode: 13, key: 'Enter'})); }, 500);
                        return true;
                    }
                    for (let f of root.querySelectorAll('iframe')) { try { if (pasteToTerminal(f.contentDocument, text)) return true; } catch(e) {} }
                    return false;
                }
                return pasteToTerminal(document, arguments[0]);
                """
                success = safe_exec(driver, js_inject, cmd_payload)
                if success:
                    time.sleep(1)
                    try: ActionChains(driver).send_keys(Keys.ENTER).perform()
                    except: pass
                else:
                    try: ActionChains(driver).send_keys(cmd_payload).send_keys(Keys.ENTER).perform()
                    except: pass
                state = "SILENT_BUILD"

        # وصلنا لنهاية الـ while loop بدون نتيجة واضحة
        safe_delete_msg(chat_id, status_msg_id)
        return RESULT_ABORT

    except Exception as e:
        safe_delete_msg(chat_id, status_msg_id)
        err_str = str(e).lower()
        print(f"❌ [Task Error] Chat {chat_id}, Attempt {attempt_num}: {e}")

        # هل الخطأ قابل لإعادة المحاولة؟
        retryable_keywords = ['crash', 'renderer', 'timeout', 'session', 'disconnected',
                              'not reachable', 'target closed', 'no such window',
                              'chrome_crash', 'chrome not reachable', 'unable to receive',
                              'timed out receiving', 'chrome_dead', 'driver_creation']
        if any(k in err_str for k in retryable_keywords):
            return RESULT_RETRY
        return RESULT_ABORT

    finally:
        destroy_driver(driver)
        driver = None


def worker_loop():
    """المحرك الرئيسي مع نظام إعادة المحاولة التلقائي"""
    while True:
        task = task_queue.get()
        chat_id, url = task['chat_id'], task['url']

        session = get_session(chat_id)
        if not session.get('active') or session.get('status') != 'queued':
            task_queue.task_done()
            continue

        update_session(chat_id, {'status': 'processing', 'interaction_time': time.time()})

        ui_msg_id = get_session(chat_id).get('ui_msg_id')
        safe_delete_msg(chat_id, ui_msg_id)

        MAX_RETRIES = 3
        final_result = RESULT_ABORT

        for attempt in range(1, MAX_RETRIES + 1):
            if not get_session(chat_id).get('active'):
                break

            if attempt > 1:
                retry_msg = bot.send_message(chat_id,
                    f"🔄 **إعادة محاولة تلقائية ({attempt}/{MAX_RETRIES})...**\n"
                    f"⚙️ جاري إعادة تشغيل المتصفح والاتصال...",
                    parse_mode="Markdown")
                nuke_all_chrome()
                time.sleep(8)
                safe_delete_msg(chat_id, retry_msg.message_id)

                # تحديث حالة الجلسة للمحاولة الجديدة
                update_session(chat_id, {'active': True, 'status': 'processing', 'interaction_time': time.time()})

            print(f"🚀 [Worker] Task for {chat_id} - Attempt {attempt}/{MAX_RETRIES}")
            result = run_single_task(chat_id, url, attempt)
            final_result = result

            if result == RESULT_SUCCESS:
                print(f"✅ [Worker] Task SUCCESS for {chat_id} on attempt {attempt}")
                break
            elif result == RESULT_ABORT:
                print(f"🛑 [Worker] Task ABORT for {chat_id} on attempt {attempt}")
                break
            elif result == RESULT_RETRY:
                print(f"🔄 [Worker] Task RETRY for {chat_id} (attempt {attempt}/{MAX_RETRIES})")
                if attempt >= MAX_RETRIES:
                    bot.send_message(chat_id,
                        "❌ **فشلت جميع المحاولات.**\n\n"
                        "💡 السيرفر يعاني من ضغط كبير في الذاكرة حالياً.\n"
                        "⏳ انتظر دقيقة واحدة ثم أعد إرسال الرابط.",
                        parse_mode="Markdown")

        clear_session(chat_id)
        task_queue.task_done()

threading.Thread(target=worker_loop, daemon=True).start()

# ==========================================
# 🎛️ إدارة واجهة المستخدم
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    chat_id = message.chat.id
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    if not is_vip(chat_id):
        send_unauthorized_msg(chat_id)
        return
    text = (
        "💎 **مرحباً بك في نظام OCX PRO** 💎\n\n"
        "⚡ أسرع نظام لإنشاء سيرفرات Qwiklabs المخصصة للألعاب والتصفح.\n"
        "🔗 **فقط قم بإرسال رابط الدخول المباشر لبدء العملية.**"
    )
    if str(chat_id) == str(ADMIN_ID):
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.send_message(chat_id, text, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="Markdown")

@bot.message_handler(commands=['cancel', 'stop'])
def force_cancel(message):
    chat_id = message.chat.id
    if not is_vip(chat_id): return
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    clear_session(chat_id)
    bot.send_message(chat_id, "🛑 **تم إلغاء أي مهام قيد التنفيذ وتفريغ الجلسة بنجاح.**\nيمكنك الآن إرسال رابط جديد بحرية.", parse_mode="Markdown")

def process_add_vip(message):
    new_id = message.text.strip()
    if new_id.isdigit():
        add_vip_user(new_id)
        bot.reply_to(message, f"✅ تم إضافة العميل `{new_id}` بنجاح.", parse_mode="Markdown")
        try:
            session = get_session(new_id)
            unauth_msg_id = session.get('unauth_msg_id')
            if unauth_msg_id:
                safe_delete_msg(new_id, unauth_msg_id)
                update_session(new_id, {'unauth_msg_id': None})
            bot.send_message(new_id, "🎉 **تم تفعيل اشتراكك بنجاح!**\n\n💎 **مرحباً بك في نظام OCX PRO** 💎\n🔗 **أرسل رابط الدخول المباشر لبدء العملية.**", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(message, "❌ معرف خاطئ.")

def process_del_vip(message):
    del_id = message.text.strip()
    if del_id.isdigit():
        remove_vip_user(del_id)
        bot.reply_to(message, f"🗑️ تم حذف العميل `{del_id}` بنجاح.", parse_mode="Markdown")
        try: bot.send_message(del_id, "⛔️ **تم سحب صلاحياتك من البوت.**", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(message, "❌ معرف خاطئ.")

def process_broadcast(message):
    text = message.text
    if text in ["👥 قائمة الـ VIP", "📊 حالة النظام", "➕ إضافة عميل", "➖ إزالة عميل", "📢 إذاعة رسالة", "🔙 القائمة الرئيسية"]:
        bot.reply_to(message, "❌ تم إلغاء الإذاعة."); return
    vips = get_all_vips()
    success_count = 0
    bot.reply_to(message, "⏳ جاري الإرسال...")
    for uid in vips:
        try: bot.send_message(uid, f"📢 **إشعار من الإدارة:**\n\n{text}", parse_mode="Markdown"); success_count += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ تم الإرسال لـ `{success_count}` مشترك.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text == "👑 لوحة الإدارة")
def handle_admin_panel(message):
    chat_id = message.chat.id
    if str(chat_id) != str(ADMIN_ID): return
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("👥 قائمة الـ VIP"), KeyboardButton("📊 حالة النظام"))
    markup.add(KeyboardButton("➕ إضافة عميل"), KeyboardButton("➖ إزالة عميل"))
    markup.add(KeyboardButton("📢 إذاعة رسالة"), KeyboardButton("🔙 القائمة الرئيسية"))
    bot.reply_to(message, "👑 **لوحة تحكم الإدارة** 👑", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in ["👥 قائمة الـ VIP", "📊 حالة النظام", "➕ إضافة عميل", "➖ إزالة عميل", "📢 إذاعة رسالة", "🔙 القائمة الرئيسية"])
def handle_admin_keyboard(message):
    chat_id = message.chat.id
    if str(chat_id) != str(ADMIN_ID): return
    text = message.text
    if text == "👥 قائمة الـ VIP":
        vips = get_all_vips()
        bot.reply_to(message, "👥 **VIPs:**\n\n" + ("\n".join([f"🔹 `{uid}`" for uid in vips]) if vips else "فارغة."), parse_mode="Markdown")
    elif text == "📊 حالة النظام":
        bot.reply_to(message, f"📊 **النظام:**\n📦 طابور: `{task_queue.qsize()}`\n💾 تخزين: `{'MongoDB 🟢' if USE_MONGO else 'RAM 🟡'}`\n🌐 متصفح: `Bulletproof V4 ⚡`", parse_mode="Markdown")
    elif text == "➕ إضافة عميل":
        msg = bot.send_message(chat_id, "✏️ **أرسل ID العميل:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_add_vip)
    elif text == "➖ إزالة عميل":
        msg = bot.send_message(chat_id, "✏️ **أرسل ID العميل:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_del_vip)
    elif text == "📢 إذاعة رسالة":
        msg = bot.send_message(chat_id, "📢 **أرسل الرسالة:**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_broadcast)
    elif text == "🔙 القائمة الرئيسية":
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        markup.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.reply_to(message, "🔙 تم الرجوع.", reply_markup=markup)

@bot.message_handler(func=lambda message: get_session(message.chat.id).get('status') == 'waiting_credentials')
def handle_credentials(message):
    chat_id = message.chat.id
    text = message.text.strip()
    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
    if email_match:
        email = email_match.group(0)
        password = text.replace(email, '').strip()
        if password:
            update_session(chat_id, {'email': email, 'password': password, 'status': 'processing', 'interaction_time': time.time()})
            try: bot.delete_message(chat_id, message.message_id)
            except: pass
            bot.send_message(chat_id, "✅ **تم استلام البيانات!** جاري المصادقة...", parse_mode="Markdown")
            return
    bot.send_message(chat_id, "⚠️ **تنسيق خاطئ!**\n\nمثال:\n`student-02-xxx@qwiklabs.net Password123`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    data = call.data
    if not is_vip(chat_id):
        try: bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")
        except: pass
        return
    session = get_session(chat_id)
    update_session(chat_id, {'interaction_time': time.time()})

    if data == "cancel_ui":
        clear_session(chat_id)
        try: bot.edit_message_text("🛑 تم الإلغاء.", chat_id=chat_id, message_id=call.message.message_id)
        except: pass
        threading.Timer(300.0, lambda m=call.message.message_id: safe_delete_msg(chat_id, m)).start()
        return
    if data == "abort_mission":
        clear_session(chat_id)
        try: bot.answer_callback_query(call.id, "تم الإلغاء!")
        except: pass
        safe_delete_msg(chat_id, call.message.message_id)
        msg = bot.send_message(chat_id, "🛑 **تم إلغاء المهمة.**\nجاهز لرابط جديد.", parse_mode="Markdown")
        threading.Timer(300.0, lambda m=msg.message_id: safe_delete_msg(chat_id, m)).start()
        return
    if data in ["replace_server", "add_new_server"]:
        url = session.get('target_url')
        if not url: return
        update_data = {'active': True, 'status': 'queued', 'interaction_time': time.time()}
        if data == "replace_server":
            old_server = get_server_by_url(url)
            if old_server:
                update_data.update({'replace_mode': True, 'old_server_name': old_server.get('server_name', ''), 'selected_region': old_server.get('region', ''), 'protocol': old_server.get('protocol', 'vless')})
            try: bot.edit_message_text("🔄 **استبدال السيرفر...**", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        else:
            update_data.update({'replace_mode': False, 'add_new_mode': True})
            try: bot.edit_message_text("➕ **إضافة سيرفر جديد...**", chat_id=chat_id, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        update_session(chat_id, update_data)
        task_queue.put({'chat_id': chat_id, 'url': url})
        return
    if not session.get('active'):
        try: bot.answer_callback_query(call.id, "❌ الجلسة منتهية.")
        except: pass
        return
    if data.startswith("cont_"):
        continent = data.split("cont_")[1]
        regions = session.get('available_regions', {}).get(continent, [])
        markup = InlineKeyboardMarkup(row_width=1)
        for r in regions:
            markup.add(InlineKeyboardButton(text=f"{translate_region(r['name'])} ({r['id']})", callback_data=f"reg_{r['id']}"))
        markup.add(InlineKeyboardButton(text="🔙 العودة للقارات", callback_data="back_to_conts"))
        try: bot.edit_message_text(f"📍 سيرفرات {continent}:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        except: pass
    elif data.startswith("reg_"):
        reg_id = data.split("reg_")[1]
        update_session(chat_id, {'selected_region': reg_id})
        markup = InlineKeyboardMarkup(row_width=3)
        markup.add(InlineKeyboardButton("⚡ VLESS", callback_data="proto_vless"), InlineKeyboardButton("🛡️ VMESS", callback_data="proto_vmess"), InlineKeyboardButton("🐎 TROJAN", callback_data="proto_trojan"))
        try: bot.edit_message_text(f"✅ المنطقة: `{reg_id}`\n\n👇 اختر البروتوكول:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except: pass
    elif data.startswith("proto_"):
        update_session(chat_id, {'protocol': data.split("_")[1]})
        safe_delete_msg(chat_id, call.message.message_id)
    elif data == "back_to_conts":
        grouped = session.get('available_regions', {})
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(*[InlineKeyboardButton(text=c, callback_data=f"cont_{c}") for c in grouped.keys()])
        try: bot.edit_message_text("👇 اختر القارة:", chat_id=chat_id, message_id=call.message.message_id, reply_markup=markup)
        except: pass

@bot.message_handler(func=lambda message: message.text and message.text.startswith('http'))
def handle_url(message):
    chat_id = message.chat.id
    url = message.text
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    if not is_vip(chat_id):
        send_unauthorized_msg(chat_id); return
    if not url.startswith("https://www.skills.google/google_sso"): return
    session = get_session(chat_id)
    if session.get('active'):
        msg = bot.send_message(chat_id, "⚠️ **لديك مهمة قيد التنفيذ!**\nأرسل /cancel أولاً.", parse_mode="Markdown")
        threading.Timer(15.0, lambda m=msg.message_id: safe_delete_msg(chat_id, m)).start()
        return
    existing_server = get_server_by_url(url)
    if existing_server and existing_server.get('project_id'):
        update_session(chat_id, {'target_url': url})
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🔄 استبدال السيرفر القديم", callback_data="replace_server"),
            InlineKeyboardButton("➕ بناء سيرفر جديد", callback_data="add_new_server"),
            InlineKeyboardButton("🛑 إلغاء", callback_data="cancel_ui")
        )
        msg = bot.send_message(chat_id, "⚠️ **رابط مستخدم سابقاً!**\nكيف تفضل؟", reply_markup=markup, parse_mode="Markdown")
        update_session(chat_id, {'ui_msg_id': msg.message_id})
        return
    msg = bot.send_message(chat_id, "⏳ **تمت الإضافة للطابور...**", parse_mode="Markdown")
    update_session(chat_id, {'active': True, 'status': 'queued', 'target_url': url, 'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
    task_queue.put({'chat_id': chat_id, 'url': url})

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'sticker', 'voice'])
def delete_spam(message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

if __name__ == "__main__":
    print("💎 OCX PRO V4 (AUTO-RETRY BULLETPROOF) ACTIVE...")
    nuke_all_chrome()
    try: bot.remove_webhook()
    except: pass
    while True:
        try: bot.polling(none_stop=True)
        except Exception as e:
            print(f"❌ [Polling] {e}")
            time.sleep(3)
