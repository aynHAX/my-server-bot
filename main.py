import os
import time
import threading
import queue
import io
import http.server
import socketserver
import subprocess
import uuid
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
        print("✅ [DB] MongoDB Connected.")
    except Exception as e:
        users_col, servers_col, ram_vips = {}, {}, set()
        USE_MONGO = False
        print(f"⚠️ [DB] MongoDB Failed: {e}")
else:
    users_col, servers_col, ram_vips = {}, {}, set()
    USE_MONGO = False
    print("⚠️ [DB] No MONGO_URI. RAM mode.")

task_queue = queue.Queue()
driver_lock = threading.Lock()
worker_thread = None

if ADMIN_ID and not USE_MONGO:
    ram_vips.add(str(ADMIN_ID))

# ==========================================
# ☠️ قاتل Chrome + إعداد Swap
# ==========================================
def nuke_all_chrome():
    for p in ['chrome', 'chromium', 'chromedriver', 'google-chrome']:
        try: subprocess.run(['pkill', '-9', '-f', p], timeout=5, capture_output=True)
        except: pass
    try: subprocess.run('rm -rf /tmp/.com.google.Chrome* /tmp/chrome_crashpad* /tmp/.org.chromium* /tmp/Temp-*', shell=True, timeout=5, capture_output=True)
    except: pass
    time.sleep(1)

def setup_swap():
    try:
        r = subprocess.run(['swapon', '--show'], capture_output=True, text=True, timeout=5)
        if r.stdout.strip():
            print("✅ Swap already active")
            return
        subprocess.run('fallocate -l 512M /swapfile 2>/dev/null && chmod 600 /swapfile && mkswap /swapfile >/dev/null 2>&1 && swapon /swapfile 2>/dev/null', shell=True, timeout=60)
        print("✅ 512MB Swap created")
    except:
        print("⚠️ Swap not available (container limits)")

setup_swap()
nuke_all_chrome()

# ==========================================
# 🧹 محرك تنظيف الكوكيز
# ==========================================
def cookie_cleanup_worker():
    while True:
        time.sleep(12 * 60 * 60)
        try:
            if USE_MONGO:
                servers_col.update_many({}, {"$set": {"cookies": []}})
            else:
                for url in servers_col: servers_col[url]['cookies'] = []
        except: pass

threading.Thread(target=cookie_cleanup_worker, daemon=True).start()

# ==========================================
# 🐕 حارس الجلسات المعلقة
# ==========================================
def session_watchdog():
    while True:
        time.sleep(300)
        try:
            if USE_MONGO:
                for s in users_col.find({"active": True}):
                    lt = s.get('interaction_time', 0)
                    if lt and (time.time() - lt > 900):
                        cid = s.get('chat_id')
                        clear_session(cid)
                        try: bot.send_message(cid, "⏳ **انتهت الجلسة تلقائياً (عدم نشاط 15 دقيقة).**\nأعد إرسال الرابط.", parse_mode="Markdown")
                        except: pass
            else:
                for cid, s in list(users_col.items()):
                    if s.get('active'):
                        lt = s.get('interaction_time', 0)
                        if lt and (time.time() - lt > 900):
                            clear_session(cid)
        except: pass

threading.Thread(target=session_watchdog, daemon=True).start()

# ==========================================
# 🛡️ نظام VIP
# ==========================================
def is_vip(user_id):
    str_id = str(user_id)
    if str_id == str(ADMIN_ID): return True
    if USE_MONGO: return vips_col.find_one({"user_id": str_id}) is not None
    return str_id in ram_vips

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
    return list(ram_vips)

def send_unauthorized_msg(chat_id):
    try:
        m = bot.send_message(chat_id, ".", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.delete_message(chat_id, m.message_id)
    except: pass
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 التواصل لشراء البوت", url="https://t.me/aynX1"))
    msg = bot.send_message(chat_id, "⛔️ **عذراً، أنت غير مشترك في هذا البوت.**\n\nللاشتراك، يرجى التواصل مع الإدارة.", reply_markup=markup, parse_mode="Markdown")
    update_session(chat_id, {'unauth_msg_id': msg.message_id})

# ==========================================
# ⚙️ إدارة الجلسات (مع Task ID)
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
        "interaction_time": 0, "old_server_name": None,
        "task_id": None
    })

def generate_task_id():
    return str(uuid.uuid4())[:8]

def is_task_current(chat_id, task_id):
    """هل هذه المهمة لا تزال هي النشطة؟ (حل مشكلة Race Condition)"""
    s = get_session(chat_id)
    return s.get('active', False) and s.get('task_id') == task_id

def get_server_by_url(url):
    try:
        if USE_MONGO: return servers_col.find_one({"url": url})
        return servers_col.get(url)
    except: return None

def save_successful_server(chat_id, url, server_name, region, protocol, project_id, cookies=None):
    data = {"chat_id": str(chat_id), "url": url, "server_name": server_name, "region": region, "protocol": protocol, "project_id": project_id, "cookies": cookies or [], "timestamp": time.time()}
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
    echo "Retrying with Safe Mode..."
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
          --arg text "❌ **فشل البناء النهائي:**

حساب Qwiklabs محظور أو ممتلئ في منطقة \`${REGION}\`.

💡 **الحل:** /cancel وجرب منطقة مختلفة أو حساب جديد." \
          '{chat_id: $chat_id, text: $text, parse_mode: "Markdown"}')
        curl -s -X POST "https://api.telegram.org/bot<BOT_TOKEN_PLACEHOLDER>/sendMessage" \
          -H "Content-Type: application/json" -d "$ERROR_PAYLOAD" > /dev/null
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
  --arg text "✅ **تم بناء السيرفر بنجاح!** 🚀🔥

🛡️ **البروتوكول:** \`${PROTOCOL}\`
📍 **المنطقـــة:** \`${REGION}\`
🆔 **UUID:** \`${UUID}\`

🔗 **رابط الاتصال:**
\`\`\`
${VPN_LINK}
\`\`\`

*💎 OCX PRO System*" \
  '{chat_id: $chat_id, text: $text, parse_mode: "Markdown"}')

curl -s -X POST "https://api.telegram.org/bot<BOT_TOKEN_PLACEHOLDER>/sendMessage" \
  -H "Content-Type: application/json" -d "$JSON_PAYLOAD" > /dev/null
echo "SUCCESS_OCX_FINISH"
"""

def translate_region(name):
    translations = {'Netherlands': 'هولندا 🇳🇱', 'South Carolina': 'ساوث كارولينا 🇺🇸', 'Oregon': 'أوريغون 🇺🇸', 'Iowa': 'آيوا 🇺🇸', 'Belgium': 'بلجيكا 🇧🇪', 'London': 'لندن 🇬🇧', 'Frankfurt': 'فرانكفورت 🇩🇪', 'Taiwan': 'تايوان 🇹🇼', 'Tokyo': 'طوكيو 🇯🇵', 'Singapore': 'سنغافورة 🇸🇬', 'Sydney': 'سيدني 🇦🇺', 'Mumbai': 'مومباي 🇮🇳', 'Oslo': 'أوسلو 🇳🇴', 'Finland': 'فنلندا 🇫🇮', 'Montreal': 'مونتريال 🇨🇦', 'Toronto': 'تورونتو 🇨🇦', 'Sao Paulo': 'ساو باولو 🇧🇷', 'Jakarta': 'جاكرتا 🇮🇩', 'Las Vegas': 'لاس فيغاس 🇺🇸', 'Los Angeles': 'لوس أنجلوس 🇺🇸', 'Northern Virginia': 'فرجينيا 🇺🇸', 'Salt Lake City': 'سولت ليك 🇺🇸', 'Seoul': 'سيول 🇰🇷', 'Zurich': 'زيورخ 🇨🇭', 'Milan': 'ميلانو 🇮🇹', 'Madrid': 'مدريد 🇪🇸', 'Paris': 'باريس 🇫🇷', 'Warsaw': 'وارسو 🇵🇱'}
    for key, val in translations.items():
        if key.lower() in name.lower(): return val
    return f"{name} 🏳️"

# ==========================================
# 🌐 Health Check Server
# ==========================================
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == '/health' else 404)
        self.send_header('Content-type', 'text/plain'); self.end_headers()
        if self.path == '/health': self.wfile.write(b"OK")
    def log_message(self, *a): pass

def run_health_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", int(os.environ.get("PORT", 8080))), HealthCheckHandler) as h: h.serve_forever()
threading.Thread(target=run_health_server, daemon=True).start()

# ==========================================
# 🚀 محرك Chrome (V5 - Stable)
# ==========================================
display = Display(visible=0, size=(800, 600))
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
    options.add_argument('--no-first-run')
    options.add_argument('--incognito')
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
    options.page_load_strategy = 'eager'
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_experimental_option("prefs", {"profile.default_content_setting_values.notifications": 2})
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    service = Service(log_output=os.devnull)
    driver = webdriver.Chrome(options=options, service=service)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"})
    driver.set_page_load_timeout(150)
    driver.set_script_timeout(30)
    driver.implicitly_wait(3)
    return driver

def get_driver_safe():
    last_err = None
    for i in range(1, 4):
        try:
            print(f"🔧 [Chrome] Attempt {i}/3...")
            d = create_driver()
            d.get("about:blank")
            print(f"✅ [Chrome] OK on attempt {i}")
            return d
        except Exception as e:
            last_err = e
            print(f"❌ [Chrome] Attempt {i} failed: {e}")
            nuke_all_chrome()
            time.sleep(5)
    raise Exception(f"DRIVER_FAILED: {last_err}")

# === دوال الأمان ===
def alive(d):
    if not d: return False
    try: _ = d.title; return True
    except: return False

def safe_get(d, url):
    try: d.get(url); return True
    except TimeoutException:
        try: d.execute_script("window.stop();")
        except: pass
        return True
    except Exception as e:
        if any(k in str(e).lower() for k in ['crash','not reachable','session','disconnected','target closed']):
            return False
        return True

def safe_exec(d, s, *a):
    try: return d.execute_script(s, *a)
    except: return None

def safe_find(d, by, val):
    try: return d.find_elements(by, val)
    except: return []

def safe_screenshot(d):
    try: return d.get_screenshot_as_png()
    except: return None

def safe_source(d):
    try: return d.page_source
    except: return ""

def safe_url(d):
    try: return d.current_url
    except: return ""

def safe_cookies(d):
    try: return d.get_cookies()
    except: return []

def destroy_driver(d):
    if d:
        try: d.quit()
        except: pass
    nuke_all_chrome()

def safe_delete_msg(cid, mid):
    if mid:
        try: bot.delete_message(cid, mid)
        except: pass

def inject_cookies_safely(d, cookies):
    if not cookies: return
    try:
        safe_get(d, "https://google.com/robots.txt"); time.sleep(1)
        for c in cookies:
            if 'google.com' in c.get('domain', ''):
                try: d.add_cookie(c)
                except: pass
        safe_get(d, "https://console.cloud.google.com/robots.txt"); time.sleep(1)
        for c in cookies:
            if 'cloud.google.com' in c.get('domain', ''):
                try: d.add_cookie(c)
                except: pass
    except: pass

def update_live_stream(cid, mid, text, logs=None, driver=None, is_photo=False):
    if not mid: return
    ft = f"🟢 *نظام OCX | التتبع المباشر*\n━━━━━━━━━━━━━━━━━\n**العملية:** {text}\n```bash\n> {logs}\n```\n━━━━━━━━━━━━━━━━━" if logs else text
    try:
        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
        if is_photo:
            if driver and alive(driver):
                ss = safe_screenshot(driver)
                if ss:
                    try: bot.edit_message_media(chat_id=cid, message_id=mid, media=InputMediaPhoto(ss, caption=ft, parse_mode="Markdown"), reply_markup=mk); return
                    except: pass
            try: bot.edit_message_caption(chat_id=cid, message_id=mid, caption=ft, parse_mode="Markdown", reply_markup=mk)
            except: pass
        else:
            try: bot.edit_message_text(chat_id=cid, message_id=mid, text=ft, parse_mode="Markdown", reply_markup=mk)
            except: pass
    except: pass

# ==========================================
# ⚙️ محرك المهام (V5 - مع حل Race Condition)
# ==========================================
RESULT_SUCCESS = "SUCCESS"
RESULT_RETRY = "RETRY"
RESULT_ABORT = "ABORT"

def run_single_task(chat_id, url, task_id, attempt_num):
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

        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
        retry_note = f"\n🔄 *(المحاولة {attempt_num})*" if attempt_num > 1 else ""
        ss = safe_screenshot(driver)
        if ss:
            try: msg = bot.send_photo(chat_id, photo=ss, caption=f"🟢 **سجل العمليات المباشر:**\n⚡ جاري تهيئة الاتصال...{retry_note}", parse_mode="Markdown", reply_markup=mk); is_status_photo = True
            except: msg = bot.send_message(chat_id, f"🟢 **سجل العمليات:**\n⚡ جاري التهيئة...{retry_note}", parse_mode="Markdown", reply_markup=mk)
        else:
            msg = bot.send_message(chat_id, f"🟢 **سجل العمليات:**\n⚡ جاري التهيئة...{retry_note}", parse_mode="Markdown", reply_markup=mk)
        status_msg_id = msg.message_id

        loop_count = 0
        project_id = saved_project_id or ""
        dead_checks = 0

        while loop_count < 300:
            loop_count += 1
            time.sleep(3)

            # === فحص Task ID (حل Race Condition) ===
            if not is_task_current(chat_id, task_id):
                safe_delete_msg(chat_id, status_msg_id)
                return RESULT_ABORT

            if not alive(driver):
                dead_checks += 1
                if dead_checks >= 3:
                    safe_delete_msg(chat_id, status_msg_id)
                    return RESULT_RETRY
                time.sleep(2); continue
            dead_checks = 0

            if loop_count % 20 == 0:
                safe_exec(driver, "try{performance.clearResourceTimings();}catch(e){}")

            current_url = safe_url(driver)
            if not current_url: continue

            current_session = get_session(chat_id)
            update_session(chat_id, {'interaction_time': time.time()})

            # === صفحة تسجيل الدخول ===
            if 'accounts.google.com' in current_url:
                page_lower = safe_source(driver).lower()
                if "couldn't sign you in" in page_lower or "domain admin" in page_lower or "admin for help" in page_lower:
                    safe_delete_msg(chat_id, status_msg_id)
                    bot.send_message(chat_id, "❌ **حساب Qwiklabs محظور.**\n💡 أغلق اللاب وابدأ جديد.", parse_mode="Markdown")
                    return RESULT_ABORT

                email_inputs = safe_find(driver, By.XPATH, "//input[@type='email']")
                pass_inputs = safe_find(driver, By.XPATH, "//input[@type='password']")

                if email_inputs and email_inputs[0].is_displayed() and not (pass_inputs and pass_inputs[0].is_displayed()):
                    if not sso_tried:
                        update_live_stream(chat_id, status_msg_id, "🔄 **التحويل عبر SSO...**", driver=driver, is_photo=is_status_photo)
                        sso_tried = True
                        if not safe_get(driver, url): safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                        state = "INIT"; time.sleep(2); continue
                    elif not cookies_tried and saved_cookies:
                        update_live_stream(chat_id, status_msg_id, "⚡ **حقن الكوكيز...**", driver=driver, is_photo=is_status_photo)
                        inject_cookies_safely(driver, saved_cookies); cookies_tried = True
                        if not safe_get(driver, target_url_to_load): safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                        state = initial_state; time.sleep(2); continue
                    elif current_session.get('status') != 'waiting_credentials' and not current_session.get('email'):
                        safe_delete_msg(chat_id, status_msg_id)
                        msg = bot.send_message(chat_id, "⚠️ **مطلوب بيانات الدخول.**\n\nأرسل الإيميل والباسورد:\n`student-02-xxx@qwiklabs.net Password123`", parse_mode="Markdown")
                        update_session(chat_id, {'status': 'waiting_credentials', 'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
                        status_msg_id = msg.message_id; continue

                if current_session.get('email') and current_session.get('password'):
                    try:
                        if email_inputs and email_inputs[0].is_displayed():
                            update_live_stream(chat_id, status_msg_id, "مصادقة", f"إدخال البريد: {current_session['email']}", driver=driver, is_photo=is_status_photo)
                            email_inputs[0].clear(); email_inputs[0].send_keys(current_session['email']); email_inputs[0].send_keys(Keys.ENTER)
                            time.sleep(2); continue
                        elif pass_inputs and pass_inputs[0].is_displayed():
                            update_live_stream(chat_id, status_msg_id, "مصادقة", "إدخال كلمة المرور... ***", driver=driver, is_photo=is_status_photo)
                            pass_inputs[0].clear(); pass_inputs[0].send_keys(current_session['password']); pass_inputs[0].send_keys(Keys.ENTER)
                            time.sleep(3); update_session(chat_id, {'email': None, 'password': None}); state = "INIT"
                            safe_delete_msg(chat_id, status_msg_id)
                            mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
                            ss = safe_screenshot(driver)
                            try: msg = bot.send_photo(chat_id, photo=ss, caption="🟢 ✅ تمت المصادقة...", parse_mode="Markdown", reply_markup=mk); is_status_photo = True
                            except: msg = bot.send_message(chat_id, "🟢 ✅ تمت المصادقة...", parse_mode="Markdown", reply_markup=mk); is_status_photo = False
                            status_msg_id = msg.message_id; continue
                    except Exception as e: print(f"Login Error: {e}")

                if current_session.get('status') == 'waiting_credentials': continue

            # === حالات الآلة ===
            if state == "WAIT_USER_SELECTION":
                if current_session.get('selected_region') and current_session.get('protocol'):
                    if project_id:
                        if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={project_id}&pli=1&show=terminal"):
                            safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                        state = "AUTHORIZE_SHELL"
                continue

            elif state == "SILENT_BUILD":
                ps = safe_source(driver)
                if not ps and not alive(driver): safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                if "ERROR_DEPLOYMENT_FAILED_OCX_CATCH" in ps: safe_delete_msg(chat_id, status_msg_id); return RESULT_ABORT
                sm = re.search(r'OCX_DATA_SYNC:\s*(.*?)\|(.*?)\|(.*?)\|(.*?)(?:\n|<)', ps)
                if sm: save_successful_server(chat_id, url, sm.group(1), sm.group(2), sm.group(3), project_id, safe_cookies(driver))
                if "SUCCESS_OCX_FINISH" in ps: safe_delete_msg(chat_id, status_msg_id); return RESULT_SUCCESS
                update_live_stream(chat_id, status_msg_id, f"🟢 **بناء الحاوية...**\n⏳ {loop_count*3} ثانية", driver=driver, is_photo=is_status_photo)
                continue
            else:
                ar_map = {"INIT": "التهيئة", "WAIT_DEPLOY": "واجهة البناء", "WAIT_REGION": "خريطة السيرفرات", "EXTRACT_REGIONS": "استخراج البيانات", "AUTHORIZE_SHELL": "تفويض الطرفية", "WAIT_TERMINAL_BOOT": "تشغيل Linux", "INJECT_PAYLOAD": "حقن السكربت"}
                update_live_stream(chat_id, status_msg_id, f"🟢 المرحلة: `{ar_map.get(state, state)}`", driver=driver, is_photo=is_status_photo)

            # === أزرار الموافقة ===
            try:
                for btn in safe_find(driver, By.XPATH, "//button[contains(., 'Agree and continue') or contains(., 'موافق ومتابعة') or contains(., 'Akkoord en doorgaan')]"):
                    if btn.is_displayed():
                        for cb in safe_find(driver, By.XPATH, "//*[@role='checkbox'] | //mat-checkbox | //input[@type='checkbox']"):
                            safe_exec(driver, "arguments[0].click();", cb)
                        time.sleep(1); safe_exec(driver, "arguments[0].click();", btn); break
            except: pass

            if state == "INIT":
                if 'accounts.google.com' in current_url:
                    try:
                        for el in safe_find(driver, By.XPATH, "//*[@id='confirm'] | //input[@type='submit'] | //button | //div[@role='button'] | //span"):
                            t = ((el.text or el.get_attribute('value') or '')).lower()
                            eid = el.get_attribute('id') or ''
                            if any(k in t for k in ['understand','begrijp','accept','أفهم','موافق','continue','متابعة']) or eid == 'confirm':
                                safe_exec(driver, "arguments[0].click();", el); break
                    except: pass
                elif 'console.cloud.google.com' in current_url:
                    m = re.search(r'project=([^&#]+)', current_url)
                    if m:
                        project_id = saved_project_id if (saved_project_id and (current_session.get('replace_mode') or current_session.get('add_new_mode'))) else m.group(1)
                        fc = safe_cookies(driver)
                        if fc: update_server_cookies(url, fc)
                        update_live_stream(chat_id, status_msg_id, "🟢 🔐 تم الوصول بنجاح.", driver=driver, is_photo=is_status_photo)
                        time.sleep(1)
                        if current_session.get('replace_mode'):
                            if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={project_id}&pli=1&show=terminal"): safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                            state = "AUTHORIZE_SHELL"
                        else:
                            if not safe_get(driver, f"https://console.cloud.google.com/run/services?project={project_id}"): safe_delete_msg(chat_id, status_msg_id); return RESULT_RETRY
                            state = "WAIT_DEPLOY"

            elif state == "WAIT_DEPLOY":
                for btn in safe_find(driver, By.XPATH, "//*[contains(text(), 'Deploy container')]"):
                    try:
                        if btn.is_displayed(): safe_exec(driver, "arguments[0].click();", btn); state = "WAIT_REGION"; break
                    except: pass

            elif state == "WAIT_REGION":
                safe_exec(driver, "document.querySelectorAll('button').forEach(b=>{if(b.innerText.includes('OK, got it')||b.innerText.includes('Accept'))b.click()})")
                for re_el in safe_find(driver, By.XPATH, "//*[contains(text(), 'Region') and not(contains(text(), 'Regions'))]"):
                    try:
                        if re_el.is_displayed():
                            safe_exec(driver, "arguments[0].scrollIntoView({block:'center'});", re_el); time.sleep(1)
                            safe_exec(driver, "arguments[0].click();", re_el); state = "EXTRACT_REGIONS"; break
                    except: pass
                else: safe_exec(driver, "window.scrollBy(0,300);")

            elif state == "EXTRACT_REGIONS":
                if current_session.get('replace_mode'): state = "WAIT_USER_SELECTION"; continue
                time.sleep(1)
                regions_list = []
                for opt in safe_find(driver, By.XPATH, "//*[@role='option'] | //mat-option | //*[contains(@class, 'mat-option-text')]"):
                    try:
                        t = " ".join((opt.get_attribute('textContent') or opt.text or '').split()).strip()
                        if len(t) > 3 and "Select" not in t and t not in [r['raw'] for r in regions_list]:
                            m2 = re.search(r'^([a-z0-9-]+)\s*\(([^)]+)\)', t)
                            rid, rn = (m2.group(1), m2.group(2)) if m2 else (t.split()[0], t)
                            if rid.startswith(('us-','northamerica-','southamerica-')): ct = 'أمريكا 🌎'
                            elif rid.startswith('europe-'): ct = 'أوروبا 🌍'
                            elif rid.startswith('asia-'): ct = 'آسيا 🌏'
                            elif rid.startswith('australia-'): ct = 'أستراليا 🦘'
                            elif rid.startswith(('me-','africa-')): ct = 'الشرق الأوسط 🐪'
                            else: ct = 'أخرى 🗺️'
                            regions_list.append({'id': rid, 'name': rn, 'continent': ct, 'raw': t})
                    except: pass
                if regions_list:
                    gr = {}
                    for r in regions_list: gr.setdefault(r['continent'], []).append(r)
                    update_session(chat_id, {'available_regions': gr, 'project_id': project_id})
                    safe_delete_msg(chat_id, status_msg_id); status_msg_id = None
                    mk = InlineKeyboardMarkup(row_width=2)
                    mk.add(*[InlineKeyboardButton(text=c, callback_data=f"cont_{c}") for c in gr.keys()])
                    msg = bot.send_message(chat_id, "📍 **تم جلب السيرفرات!**\n\n👇 اختر القارة:", reply_markup=mk, parse_mode="Markdown")
                    update_session(chat_id, {'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
                    state = "WAIT_USER_SELECTION"
                else:
                    safe_exec(driver, "document.body.click();"); time.sleep(1)
                    try:
                        cv = driver.find_element(By.XPATH, "//*[contains(text(),'Region')]/following::*[@role='combobox'][1]")
                        ActionChains(driver).move_to_element(cv).click().perform()
                    except: pass

            elif state == "AUTHORIZE_SHELL":
                if status_msg_id is None:
                    safe_delete_msg(chat_id, current_session.get('ui_msg_id'))
                    mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
                    ss = safe_screenshot(driver)
                    try: msg = bot.send_photo(chat_id, photo=ss, caption="🟢 🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=mk); is_status_photo = True
                    except: msg = bot.send_message(chat_id, "🟢 🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=mk); is_status_photo = False
                    status_msg_id = msg.message_id

                js_click = """
                function ac(r){if(!r)return false;let els=r.querySelectorAll('button,span.mdc-button__label,modal-action button,a,[role="button"]');
                for(let e of els){let t=(e.innerText||e.textContent||'').trim();
                if(['Continue','Doorgaan','متابعة','Continuer'].includes(t)){try{e.click()}catch(x){}}
                if(['Authorize','Autoriser','تخويل','Autoriseren'].includes(t)||(t.includes('Authorize')&&t.length<=15)){try{e.click()}catch(x){}
                e.querySelectorAll('span').forEach(s=>{try{s.click()}catch(x){}});return true}}
                for(let e of r.querySelectorAll('*')){if(e.shadowRoot&&ac(e.shadowRoot))return true}return false}
                if(ac(document))return true;for(let f of document.querySelectorAll('iframe')){try{if(ac(f.contentDocument))return true}catch(x){}}return false;"""
                if safe_exec(driver, js_click): state = "WAIT_TERMINAL_BOOT"

            elif state == "WAIT_TERMINAL_BOOT":
                jc = "function c(r){if(r.querySelector('textarea.xterm-helper-textarea'))return true;for(let f of r.querySelectorAll('iframe')){try{if(c(f.contentDocument))return true}catch(e){}}return false}return c(document);"
                if safe_exec(driver, jc): time.sleep(1); state = "INJECT_PAYLOAD"

            elif state == "INJECT_PAYLOAD":
                update_live_stream(chat_id, status_msg_id, "حقن النواة", "جاري حقن كود OCX...", driver=driver, is_photo=is_status_photo)
                cs = get_session(chat_id)
                sr = cs.get('selected_region', 'europe-west4')
                pr = cs.get('protocol', 'vless')
                rm = cs.get('replace_mode', False)
                osn = cs.get('old_server_name', '')
                pn = pr.upper()

                if pr == 'vmess':
                    ic = r"""{"log":{"loglevel":"none"},"inbounds":[{"listen":"0.0.0.0","port":${PORT},"protocol":"vmess","settings":{"clients":[{"id":"${UUID}","alterId":0}]},"streamSettings":{"network":"ws","wsSettings":{"path":"${WS_PATH}","maxEarlyData":1024,"earlyDataHeaderName":"Sec-WebSocket-Protocol"}},"sniffing":{"enabled":false}}],"outbounds":[{"protocol":"freedom","settings":{"domainStrategy":"AsIs"}}],"policy":{"levels":{"0":{"handshake":1,"connIdle":600,"uplinkOnly":1,"downlinkOnly":1}}}}"""
                    lg = r"""VMESS_JSON="{\"v\":\"2\",\"ps\":\"𝗢 𝗖 𝗫 ⚡️\",\"add\":\"vpn.googleapis.com\",\"port\":\"443\",\"id\":\"${UUID}\",\"aid\":\"0\",\"net\":\"ws\",\"type\":\"none\",\"host\":\"${SERVICE_HOST}\",\"path\":\"/%40O_C_X7\",\"tls\":\"tls\",\"sni\":\"yt.be\"}" && VPN_LINK="vmess://$(echo -n "$VMESS_JSON" | base64 -w 0)" """
                elif pr == 'trojan':
                    ic = r"""{"log":{"loglevel":"none"},"inbounds":[{"listen":"0.0.0.0","port":${PORT},"protocol":"trojan","settings":{"clients":[{"password":"${UUID}"}]},"streamSettings":{"network":"ws","wsSettings":{"path":"${WS_PATH}","maxEarlyData":1024,"earlyDataHeaderName":"Sec-WebSocket-Protocol"}},"sniffing":{"enabled":false}}],"outbounds":[{"protocol":"freedom","settings":{"domainStrategy":"AsIs"}}],"policy":{"levels":{"0":{"handshake":1,"connIdle":600,"uplinkOnly":1,"downlinkOnly":1}}}}"""
                    lg = r"""VPN_LINK="trojan://${UUID}@vpn.googleapis.com:443?path=/%40O_C_X7&security=tls&host=${SERVICE_HOST}&type=ws&sni=yt.be#𝗢 𝗖 𝗫 ⚡️" """
                else:
                    ic = r"""{"log":{"loglevel":"none"},"inbounds":[{"listen":"0.0.0.0","port":${PORT},"protocol":"vless","settings":{"clients":[{"id":"${UUID}","level":0}],"decryption":"none"},"streamSettings":{"network":"ws","wsSettings":{"path":"${WS_PATH}","maxEarlyData":1024,"earlyDataHeaderName":"Sec-WebSocket-Protocol"}},"sniffing":{"enabled":false}}],"outbounds":[{"protocol":"freedom","settings":{"domainStrategy":"AsIs"}}],"policy":{"levels":{"0":{"handshake":1,"connIdle":600,"uplinkOnly":1,"downlinkOnly":1}}}}"""
                    lg = r"""VPN_LINK="vless://${UUID}@vpn.googleapis.com:443?path=/%40O_C_X7&security=tls&encryption=none&host=${SERVICE_HOST}&type=ws&sni=yt.be#𝗢 𝗖 𝗫 ⚡️" """

                fs = VPN_SCRIPT_TEMPLATE.replace("<INBOUND_CONFIG_PLACEHOLDER>", ic).replace("<LINK_GENERATION_PLACEHOLDER>", lg).replace("TARGET_REGION_PLACEHOLDER", sr).replace("PROTOCOL_NAME_PLACEHOLDER", pn).replace("<BOT_TOKEN_PLACEHOLDER>", BOT_TOKEN).replace("<CHAT_ID_PLACEHOLDER>", str(chat_id))
                if rm and osn: fs = fs.replace("REPLACE_MODE_PLACEHOLDER", "True").replace("OLD_SERVER_NAME_PLACEHOLDER", osn)
                else: fs = fs.replace("REPLACE_MODE_PLACEHOLDER", "False")

                b64 = base64.b64encode(fs.encode('utf-8')).decode('utf-8')
                cmd = f"clear && echo '{b64}' | base64 -d > deploy.sh && chmod +x deploy.sh && ./deploy.sh\n"

                ji = """function p(r,t){let a=r.querySelectorAll('textarea.xterm-helper-textarea');for(let x of a){x.focus();const d=new DataTransfer();d.setData('text/plain',t);x.dispatchEvent(new ClipboardEvent('paste',{clipboardData:d,bubbles:true,cancelable:true}));setTimeout(()=>{x.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,cancelable:true,keyCode:13,key:'Enter'}))},500);return true}for(let f of r.querySelectorAll('iframe')){try{if(p(f.contentDocument,t))return true}catch(e){}}return false}return p(document,arguments[0]);"""
                s = safe_exec(driver, ji, cmd)
                if s:
                    time.sleep(1)
                    try: ActionChains(driver).send_keys(Keys.ENTER).perform()
                    except: pass
                else:
                    try: ActionChains(driver).send_keys(cmd).send_keys(Keys.ENTER).perform()
                    except: pass
                state = "SILENT_BUILD"

        safe_delete_msg(chat_id, status_msg_id)
        return RESULT_ABORT

    except Exception as e:
        safe_delete_msg(chat_id, status_msg_id)
        err = str(e).lower()
        print(f"❌ [Task] Chat {chat_id}, Attempt {attempt_num}: {e}")
        if any(k in err for k in ['crash','renderer','timeout','session','disconnected','not reachable','target closed','chrome','driver']):
            return RESULT_RETRY
        return RESULT_ABORT
    finally:
        destroy_driver(driver)

# ==========================================
# 🔄 Worker Loop (محمي من الموت + Race Condition Fix)
# ==========================================
def worker_loop():
    while True:
        task = None
        try:
            task = task_queue.get(timeout=30)
        except queue.Empty:
            continue
        except:
            continue

        try:
            chat_id = task['chat_id']
            url = task['url']
            task_id = task['task_id']

            # === فحص: هل المهمة لا تزال صالحة؟ ===
            if not is_task_current(chat_id, task_id):
                print(f"⏭️ [Worker] Skipping stale task {task_id} for {chat_id}")
                continue

            update_session(chat_id, {'status': 'processing', 'interaction_time': time.time()})
            safe_delete_msg(chat_id, get_session(chat_id).get('ui_msg_id'))

            MAX_RETRIES = 3
            for attempt in range(1, MAX_RETRIES + 1):
                # فحص قبل كل محاولة
                if not is_task_current(chat_id, task_id):
                    print(f"⏭️ [Worker] Task {task_id} cancelled before attempt {attempt}")
                    break

                if attempt > 1:
                    try:
                        rm = bot.send_message(chat_id, f"🔄 **إعادة محاولة تلقائية ({attempt}/{MAX_RETRIES})...**", parse_mode="Markdown")
                        time.sleep(2)
                        safe_delete_msg(chat_id, rm.message_id)
                    except: pass
                    nuke_all_chrome()
                    time.sleep(5)
                    # تأكد من أن المهمة لا تزال نشطة بعد الانتظار
                    if not is_task_current(chat_id, task_id): break
                    update_session(chat_id, {'status': 'processing', 'interaction_time': time.time()})

                print(f"🚀 [Worker] Task {task_id} for {chat_id} - Attempt {attempt}")
                result = run_single_task(chat_id, url, task_id, attempt)

                if result == RESULT_SUCCESS:
                    print(f"✅ [Worker] SUCCESS for {chat_id}")
                    break
                elif result == RESULT_ABORT:
                    print(f"🛑 [Worker] ABORT for {chat_id}")
                    break
                elif result == RESULT_RETRY:
                    print(f"🔄 [Worker] RETRY {attempt}/{MAX_RETRIES} for {chat_id}")
                    if attempt >= MAX_RETRIES:
                        try: bot.send_message(chat_id, "❌ **فشلت جميع المحاولات.**\n\n💡 انتظر 30 ثانية ثم أعد إرسال الرابط.", parse_mode="Markdown")
                        except: pass

        except Exception as e:
            print(f"❌ [Worker FATAL] {e}")
            if task:
                try: bot.send_message(task['chat_id'], "⚠️ **خطأ غير متوقع.** أعد إرسال الرابط.", parse_mode="Markdown")
                except: pass
        finally:
            # === حل Race Condition: فقط نظف إذا المهمة لا تزال هي النشطة ===
            if task:
                try:
                    current = get_session(task['chat_id'])
                    if current.get('task_id') == task['task_id']:
                        clear_session(task['chat_id'])
                    # else: مهمة جديدة أرسلت، لا تمسح الجلسة الجديدة
                except: pass
                try: task_queue.task_done()
                except: pass

def start_worker():
    global worker_thread
    worker_thread = threading.Thread(target=worker_loop, daemon=True, name="OCX-Worker")
    worker_thread.start()
    print("✅ [Worker] Thread started")

def ensure_worker():
    """تأكد أن الـ Worker حي - أعد تشغيله إذا مات"""
    global worker_thread
    if worker_thread is None or not worker_thread.is_alive():
        print("🔄 [Worker] Thread was dead! Restarting...")
        nuke_all_chrome()
        start_worker()

start_worker()

# ==========================================
# 🎛️ إدارة واجهة المستخدم
# ==========================================
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    cid = message.chat.id
    try: bot.delete_message(cid, message.message_id)
    except: pass
    if not is_vip(cid): send_unauthorized_msg(cid); return
    text = "💎 **مرحباً بك في نظام OCX PRO** 💎\n\n⚡ أسرع نظام لإنشاء سيرفرات Qwiklabs.\n🔗 **أرسل رابط الدخول المباشر لبدء العملية.**"
    if str(cid) == str(ADMIN_ID):
        mk = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1); mk.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.send_message(cid, text, reply_markup=mk, parse_mode="Markdown")
    else:
        bot.send_message(cid, text, reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="Markdown")

@bot.message_handler(commands=['cancel', 'stop'])
def force_cancel(message):
    cid = message.chat.id
    if not is_vip(cid): return
    try: bot.delete_message(cid, message.message_id)
    except: pass
    clear_session(cid)
    bot.send_message(cid, "🛑 **تم إلغاء المهمة وتفريغ الجلسة.**\nيمكنك إرسال رابط جديد.", parse_mode="Markdown")

def process_add_vip(message):
    nid = message.text.strip()
    if nid.isdigit():
        add_vip_user(nid)
        bot.reply_to(message, f"✅ تم إضافة `{nid}`.", parse_mode="Markdown")
        try:
            s = get_session(nid)
            if s.get('unauth_msg_id'): safe_delete_msg(nid, s['unauth_msg_id']); update_session(nid, {'unauth_msg_id': None})
            bot.send_message(nid, "🎉 **تم تفعيل اشتراكك!**\n💎 أرسل رابط الدخول لبدء العملية.", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(message, "❌ معرف خاطئ.")

def process_del_vip(message):
    did = message.text.strip()
    if did.isdigit():
        remove_vip_user(did)
        bot.reply_to(message, f"🗑️ تم حذف `{did}`.", parse_mode="Markdown")
        try: bot.send_message(did, "⛔️ **تم سحب صلاحياتك.**", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(message, "❌ معرف خاطئ.")

def process_broadcast(message):
    t = message.text
    if t in ["👥 قائمة الـ VIP","📊 حالة النظام","➕ إضافة عميل","➖ إزالة عميل","📢 إذاعة رسالة","🔙 القائمة الرئيسية"]:
        bot.reply_to(message, "❌ تم إلغاء الإذاعة."); return
    vips = get_all_vips(); sc = 0
    for uid in vips:
        try: bot.send_message(uid, f"📢 **إشعار:**\n\n{t}", parse_mode="Markdown"); sc += 1
        except: pass
    bot.send_message(message.chat.id, f"✅ تم الإرسال لـ `{sc}` مشترك.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👑 لوحة الإدارة")
def handle_admin_panel(message):
    if str(message.chat.id) != str(ADMIN_ID): return
    mk = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(KeyboardButton("👥 قائمة الـ VIP"), KeyboardButton("📊 حالة النظام"))
    mk.add(KeyboardButton("➕ إضافة عميل"), KeyboardButton("➖ إزالة عميل"))
    mk.add(KeyboardButton("📢 إذاعة رسالة"), KeyboardButton("🔙 القائمة الرئيسية"))
    bot.reply_to(message, "👑 **لوحة الإدارة** 👑", reply_markup=mk, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["👥 قائمة الـ VIP","📊 حالة النظام","➕ إضافة عميل","➖ إزالة عميل","📢 إذاعة رسالة","🔙 القائمة الرئيسية"])
def handle_admin_keyboard(message):
    cid = message.chat.id
    if str(cid) != str(ADMIN_ID): return
    t = message.text
    if t == "👥 قائمة الـ VIP":
        v = get_all_vips()
        bot.reply_to(message, "👥 **VIPs:**\n\n" + ("\n".join([f"🔹 `{u}`" for u in v]) if v else "فارغة."), parse_mode="Markdown")
    elif t == "📊 حالة النظام":
        wa = "✅ حي" if (worker_thread and worker_thread.is_alive()) else "❌ ميت"
        bot.reply_to(message, f"📊 **النظام:**\n📦 طابور: `{task_queue.qsize()}`\n💾 تخزين: `{'MongoDB 🟢' if USE_MONGO else 'RAM 🟡'}`\n👷 Worker: `{wa}`\n🌐 متصفح: `V5 Stable ⚡`", parse_mode="Markdown")
    elif t == "➕ إضافة عميل":
        msg = bot.send_message(cid, "✏️ **أرسل ID:**", parse_mode="Markdown"); bot.register_next_step_handler(msg, process_add_vip)
    elif t == "➖ إزالة عميل":
        msg = bot.send_message(cid, "✏️ **أرسل ID:**", parse_mode="Markdown"); bot.register_next_step_handler(msg, process_del_vip)
    elif t == "📢 إذاعة رسالة":
        msg = bot.send_message(cid, "📢 **أرسل الرسالة:**", parse_mode="Markdown"); bot.register_next_step_handler(msg, process_broadcast)
    elif t == "🔙 القائمة الرئيسية":
        mk = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1); mk.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.reply_to(message, "🔙 تم.", reply_markup=mk)

@bot.message_handler(func=lambda m: get_session(m.chat.id).get('status') == 'waiting_credentials')
def handle_credentials(message):
    cid = message.chat.id; t = message.text.strip()
    em = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', t)
    if em:
        email = em.group(0); pw = t.replace(email, '').strip()
        if pw:
            update_session(cid, {'email': email, 'password': pw, 'status': 'processing', 'interaction_time': time.time()})
            try: bot.delete_message(cid, message.message_id)
            except: pass
            bot.send_message(cid, "✅ **تم استلام البيانات!** جاري المصادقة...", parse_mode="Markdown"); return
    bot.send_message(cid, "⚠️ **تنسيق خاطئ!**\n`student-02-xxx@qwiklabs.net Password123`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    cid = call.message.chat.id; data = call.data
    if not is_vip(cid):
        try: bot.answer_callback_query(call.id, "❌ ليس لديك صلاحية.")
        except: pass; return
    session = get_session(cid)
    update_session(cid, {'interaction_time': time.time()})

    if data == "cancel_ui":
        clear_session(cid)
        try: bot.edit_message_text("🛑 تم الإلغاء.", chat_id=cid, message_id=call.message.message_id)
        except: pass; return

    if data == "abort_mission":
        clear_session(cid)
        try: bot.answer_callback_query(call.id, "تم الإلغاء!")
        except: pass
        safe_delete_msg(cid, call.message.message_id)
        bot.send_message(cid, "🛑 **تم إلغاء المهمة.** جاهز لرابط جديد.", parse_mode="Markdown"); return

    if data in ["replace_server", "add_new_server"]:
        url = session.get('target_url')
        if not url: return
        tid = generate_task_id()
        ud = {'active': True, 'status': 'queued', 'interaction_time': time.time(), 'task_id': tid}
        if data == "replace_server":
            os_data = get_server_by_url(url)
            if os_data: ud.update({'replace_mode': True, 'old_server_name': os_data.get('server_name', ''), 'selected_region': os_data.get('region', ''), 'protocol': os_data.get('protocol', 'vless')})
            try: bot.edit_message_text("🔄 **استبدال السيرفر...**", chat_id=cid, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        else:
            ud.update({'replace_mode': False, 'add_new_mode': True})
            try: bot.edit_message_text("➕ **إضافة سيرفر جديد...**", chat_id=cid, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        update_session(cid, ud)
        ensure_worker()
        task_queue.put({'chat_id': cid, 'url': url, 'task_id': tid}); return

    if not session.get('active'):
        try: bot.answer_callback_query(call.id, "❌ الجلسة منتهية.")
        except: pass; return

    if data.startswith("cont_"):
        ct = data[5:]; regs = session.get('available_regions', {}).get(ct, [])
        mk = InlineKeyboardMarkup(row_width=1)
        for r in regs: mk.add(InlineKeyboardButton(text=f"{translate_region(r['name'])} ({r['id']})", callback_data=f"reg_{r['id']}"))
        mk.add(InlineKeyboardButton(text="🔙 العودة", callback_data="back_to_conts"))
        try: bot.edit_message_text(f"📍 سيرفرات {ct}:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk)
        except: pass
    elif data.startswith("reg_"):
        rid = data[4:]; update_session(cid, {'selected_region': rid})
        mk = InlineKeyboardMarkup(row_width=3)
        mk.add(InlineKeyboardButton("⚡ VLESS", callback_data="proto_vless"), InlineKeyboardButton("🛡️ VMESS", callback_data="proto_vmess"), InlineKeyboardButton("🐎 TROJAN", callback_data="proto_trojan"))
        try: bot.edit_message_text(f"✅ المنطقة: `{rid}`\n\n👇 اختر البروتوكول:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except: pass
    elif data.startswith("proto_"):
        update_session(cid, {'protocol': data[6:]}); safe_delete_msg(cid, call.message.message_id)
    elif data == "back_to_conts":
        gr = session.get('available_regions', {}); mk = InlineKeyboardMarkup(row_width=2)
        mk.add(*[InlineKeyboardButton(text=c, callback_data=f"cont_{c}") for c in gr.keys()])
        try: bot.edit_message_text("👇 اختر القارة:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk)
        except: pass

@bot.message_handler(func=lambda m: m.text and m.text.startswith('http'))
def handle_url(message):
    cid = message.chat.id; url = message.text
    try: bot.delete_message(cid, message.message_id)
    except: pass
    if not is_vip(cid): send_unauthorized_msg(cid); return
    if not url.startswith("https://www.skills.google/google_sso"): return

    session = get_session(cid)
    if session.get('active'):
        msg = bot.send_message(cid, "⚠️ **لديك مهمة قيد التنفيذ!**\nأرسل /cancel أولاً.", parse_mode="Markdown")
        threading.Timer(15.0, lambda m=msg.message_id: safe_delete_msg(cid, m)).start(); return

    existing = get_server_by_url(url)
    if existing and existing.get('project_id'):
        tid = generate_task_id()
        update_session(cid, {'target_url': url, 'task_id': tid})
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🔄 استبدال السيرفر القديم", callback_data="replace_server"),
               InlineKeyboardButton("➕ بناء سيرفر جديد", callback_data="add_new_server"),
               InlineKeyboardButton("🛑 إلغاء", callback_data="cancel_ui"))
        msg = bot.send_message(cid, "⚠️ **رابط مستخدم سابقاً!** كيف تفضل؟", reply_markup=mk, parse_mode="Markdown")
        update_session(cid, {'ui_msg_id': msg.message_id}); return

    tid = generate_task_id()
    msg = bot.send_message(cid, "⏳ **تمت الإضافة للطابور...**", parse_mode="Markdown")
    update_session(cid, {'active': True, 'status': 'queued', 'target_url': url, 'ui_msg_id': msg.message_id, 'interaction_time': time.time(), 'task_id': tid})
    ensure_worker()
    task_queue.put({'chat_id': cid, 'url': url, 'task_id': tid})

@bot.message_handler(func=lambda m: True, content_types=['text','photo','video','document','audio','sticker','voice'])
def delete_spam(message):
    try: bot.delete_message(message.chat.id, message.message_id)
    except: pass

if __name__ == "__main__":
    print("💎 OCX PRO V5 (STABLE) ACTIVE...")
    nuke_all_chrome()
    try: bot.remove_webhook()
    except: pass
    while True:
        try:
            ensure_worker()
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"❌ [Polling] {e}")
            time.sleep(3)
