import os
import time
import threading
import queue
import io
import random
import shutil
import http.server
import socketserver
import subprocess
import uuid as uuid_module
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

# ── لا تزييف User-Agent — UA الحقيقي أأمن. تزييف UA = Windows على Linux = 100 mismatch (fonts, WebGL, platform).
# fake_useragent + --user-agent كانوا بيعمل mismatch detectable. Chromium على Linux ليه UA صحيح أصلاً.

# بنية تشفير بصمة المتصفح الموحدة (متزامنة JS + Python)
import hashlib
def _fp_seed(chat_id: str = "") -> int:
    """بذرة ثابتة لكل مستخدم = بصمة متماسكة عبر جلساته (مش عشوائية كل مرة)."""
    # تصحيح: chat_id من Telebot بيكون int، لازم str() الأول عشان .encode()
    cid = chat_id if chat_id else os.environ.get("ADMIN_ID", "ocx")
    base = str(cid).encode()
    return int(hashlib.md5(base).hexdigest(), 16)

BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = os.environ.get('ADMIN_ID', '')
MONGO_URI = os.environ.get('MONGO_URI', '')

bot = telebot.TeleBot(BOT_TOKEN)

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

task_queue = queue.Queue(maxsize=20)
worker_lock = threading.Lock()
workers = []

if ADMIN_ID and not USE_MONGO:
    ram_vips.add(str(ADMIN_ID))

def nuke_all_chrome():
    """قتل كل عمليات Chrome — يستخدم فقط عند الإقلاع وإيقاف الطوارئ."""
    for p in ['chrome', 'chromium', 'chromedriver', 'google-chrome']:
        try: subprocess.run(['pkill', '-9', '-f', p], timeout=5, capture_output=True)
        except: pass
    try: subprocess.run('rm -rf /tmp/.com.google.Chrome* /tmp/chrome_crashpad* /tmp/.org.chromium* /tmp/Temp-* /tmp/ocx_inc_* /tmp/ocx_task_* /tmp/ocx_profile_*', shell=True, timeout=5, capture_output=True)
    except: pass
    time.sleep(1)

def kill_driver_pid(d):
    """قتل Chrome خاص بمهمة واحدة فقط دون المساس بمهام أخرى."""
    if d is None: return
    pid = None
    try: pid = d.service.process.pid if hasattr(d, 'service') and d.service and hasattr(d.service, 'process') and d.service.process else None
    except: pass
    if not pid:
        try: pid = d.browser_pid if hasattr(d, 'browser_pid') else None
        except: pass
    if pid:
        try: subprocess.run(['kill', '-9', str(pid)], timeout=3, capture_output=True)
        except: pass

def setup_swap():
    try:
        r = subprocess.run(['swapon', '--show'], capture_output=True, text=True, timeout=5)
        if r.stdout.strip(): return
        subprocess.run('fallocate -l 512M /swapfile 2>/dev/null && chmod 600 /swapfile && mkswap /swapfile >/dev/null 2>&1 && swapon /swapfile 2>/dev/null', shell=True, timeout=60)
        print("✅ 512MB Swap created")
    except: pass

setup_swap()
nuke_all_chrome()

def cookie_cleanup_worker():
    while True:
        time.sleep(12 * 60 * 60)
        try:
            if USE_MONGO: servers_col.update_many({}, {"$set": {"cookies": []}})
            else:
                for url in servers_col: servers_col[url]['cookies'] = []
        except: pass

threading.Thread(target=cookie_cleanup_worker, daemon=True).start()

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
                        try: bot.send_message(cid, "⏳ **انتهت الجلسة تلقائياً (15 دقيقة).**\nأعد إرسال الرابط.", parse_mode="Markdown")
                        except: pass
            else:
                for cid, s in list(users_col.items()):
                    if s.get('active') and s.get('interaction_time', 0) and (time.time() - s['interaction_time'] > 900):
                        clear_session(cid)
        except: pass

threading.Thread(target=session_watchdog, daemon=True).start()

def is_vip(uid):
    sid = str(uid)
    if sid == str(ADMIN_ID): return True
    if USE_MONGO: return vips_col.find_one({"user_id": sid}) is not None
    return sid in ram_vips

def add_vip_user(uid):
    sid = str(uid)
    if USE_MONGO: vips_col.update_one({"user_id": sid}, {"$set": {"user_id": sid}}, upsert=True)
    else: ram_vips.add(sid)

def remove_vip_user(uid):
    sid = str(uid)
    if USE_MONGO: vips_col.delete_one({"user_id": sid})
    else: ram_vips.discard(sid)

def get_all_vips():
    if USE_MONGO: return [d['user_id'] for d in vips_col.find()]
    return list(ram_vips)

def send_unauthorized_msg(cid):
    try:
        m = bot.send_message(cid, ".", reply_markup=telebot.types.ReplyKeyboardRemove())
        bot.delete_message(cid, m.message_id)
    except: pass
    mk = InlineKeyboardMarkup().add(InlineKeyboardButton("📞 التواصل لشراء البوت", url="https://t.me/aynX1"))
    msg = bot.send_message(cid, "⛔️ **عذراً، أنت غير مشترك.**\n\nللاشتراك تواصل مع الإدارة.", reply_markup=mk, parse_mode="Markdown")
    update_session(cid, {'unauth_msg_id': msg.message_id})

def get_session(cid):
    try:
        if USE_MONGO:
            r = users_col.find_one({"chat_id": str(cid)})
            return r if r else {}
        return users_col.get(str(cid), {})
    except: return {}

def update_session(cid, data):
    try:
        if USE_MONGO: users_col.update_one({"chat_id": str(cid)}, {"$set": data}, upsert=True)
        else:
            if str(cid) not in users_col: users_col[str(cid)] = {"chat_id": str(cid)}
            users_col[str(cid)].update(data)
    except: pass

def clear_session(cid):
    update_session(cid, {
        "active": False, "status": "idle", "selected_region": None,
        "protocol": None, "target_url": None, "available_regions": {},
        "replace_mode": False, "add_new_mode": False,
        "ui_msg_id": None, "email": None, "password": None,
        "interaction_time": 0, "old_server_name": None, "task_id": None
    })

def gen_task_id():
    return str(uuid_module.uuid4())[:8]

def is_task_current(cid, tid):
    s = get_session(cid)
    return s.get('active', False) and s.get('task_id') == tid

def get_server_by_url(url):
    try:
        if USE_MONGO: return servers_col.find_one({"url": url})
        return servers_col.get(url)
    except: return None

def save_successful_server(cid, url, sname, region, proto, pid, cookies=None):
    d = {"chat_id": str(cid), "url": url, "server_name": sname, "region": region, "protocol": proto, "project_id": pid, "cookies": cookies or [], "timestamp": time.time()}
    try:
        if USE_MONGO: servers_col.update_one({"url": url}, {"$set": d}, upsert=True)
        else: servers_col[url] = d
    except: pass

def update_server_cookies(url, cookies):
    try:
        if USE_MONGO: servers_col.update_one({"url": url}, {"$set": {"cookies": cookies}}, upsert=True)
        else:
            if url not in servers_col: servers_col[url] = {}
            servers_col[url]['cookies'] = cookies
    except: pass

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
  --source . --region=${REGION} --platform=managed --allow-unauthenticated \
  --cpu=1 --memory=1024Mi --min-instances=1 --max-instances=16 \
  --concurrency=200 --timeout=3600 --port=${PORT} --execution-environment=gen2 \
  --session-affinity --no-cpu-throttling --quiet

if [ $? -ne 0 ]; then
    echo "Retrying Safe Mode..."
    gcloud run deploy ${SERVICE_NAME} \
      --source . --region=${REGION} --platform=managed --allow-unauthenticated \
      --cpu=1 --memory=1024Mi --min-instances=1 --max-instances=16 \
      --concurrency=200 --timeout=3600 --port=${PORT} --execution-environment=gen2 \
      --session-affinity --quiet
    if [ $? -ne 0 ]; then
        ERROR_PAYLOAD=$(jq -n --arg chat_id "<CHAT_ID_PLACEHOLDER>" \
          --arg text "❌ **فشل البناء النهائي:**
حساب Qwiklabs محظور أو ممتلئ في \`${REGION}\`.
💡 /cancel وجرب منطقة مختلفة أو حساب جديد." \
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
JSON_PAYLOAD=$(jq -n --arg chat_id "<CHAT_ID_PLACEHOLDER>" \
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
    translations = {
        'South Carolina': 'ساوث كارولينا 🇺🇸',
        'Moncks Corner': 'ساوث كارولينا 🇺🇸',
        'Oregon': 'أوريغون 🇺🇸',
        'The Dalles': 'أوريغون 🇺🇸',
        'Portland': 'بورتلاند 🇺🇸',
        'Iowa': 'آيوا 🇺🇸',
        'Council Bluffs': 'آيوا 🇺🇸',
        'Las Vegas': 'لاس فيغاس 🇺🇸',
        'Los Angeles': 'لوس أنجلوس 🇺🇸',
        'Northern Virginia': 'فرجينيا 🇺🇸',
        'Ashburn': 'فرجينيا 🇺🇸',
        'Salt Lake City': 'سولت ليك سيتي 🇺🇸',
        'Columbus': 'كولومبوس 🇺🇸',
        'Dallas': 'دالاس 🇺🇸',
        'Montreal': 'مونتريال 🇨🇦',
        'Toronto': 'تورونتو 🇨🇦',
        'Queretaro': 'كيريتارو 🇲🇽',
        'Querétaro': 'كيريتارو 🇲🇽',
        'Sao Paulo': 'ساو باولو 🇧🇷',
        'São Paulo': 'ساو باولو 🇧🇷',
        'Osasco': 'ساو باولو 🇧🇷',
        'Santiago': 'سانتياغو 🇨🇱',
        'Bogota': 'بوغوتا 🇨🇴',
        'Bogotá': 'بوغوتا 🇨🇴',
        'Buenos Aires': 'بوينس آيرس 🇦🇷',
        'London': 'لندن 🇬🇧',
        'Belgium': 'بلجيكا 🇧🇪',
        'St. Ghislain': 'بلجيكا 🇧🇪',
        'Netherlands': 'هولندا 🇳🇱',
        'Eemshaven': 'هولندا 🇳🇱',
        'Frankfurt': 'فرانكفورت 🇩🇪',
        'Berlin': 'برلين 🇩🇪',
        'Munich': 'ميونخ 🇩🇪',
        'Hanau': 'فرانكفورت 🇩🇪',
        'Paris': 'باريس 🇫🇷',
        'Marseille': 'مارسيليا 🇫🇷',
        'Madrid': 'مدريد 🇪🇸',
        'Milan': 'ميلانو 🇮🇹',
        'Turin': 'تورينو 🇮🇹',
        'Rome': 'روما 🇮🇹',
        'Warsaw': 'وارسو 🇵🇱',
        'Zurich': 'زيورخ 🇨🇭',
        'Zürich': 'زيورخ 🇨🇭',
        'Geneva': 'جنيف 🇨🇭',
        'Finland': 'فنلندا 🇫🇮',
        'Hamina': 'فنلندا 🇫🇮',
        'Helsinki': 'هلسنكي 🇫🇮',
        'Oslo': 'أوسلو 🇳🇴',
        'Stockholm': 'ستوكهولم 🇸🇪',
        'Copenhagen': 'كوبنهاغن 🇩🇰',
        'Dublin': 'دبلن 🇮🇪',
        'Bucharest': 'بوخارست 🇷🇴',
        'Vienna': 'فيينا 🇦🇹',
        'Prague': 'براغ 🇨🇿',
        'Budapest': 'بودابست 🇭🇺',
        'Lisbon': 'لشبونة 🇵🇹',
        'Athens': 'أثينا 🇬🇷',
        'Brussels': 'بروكسل 🇧🇪',
        'Amsterdam': 'أمستردام 🇳🇱',
        'Tokyo': 'طوكيو 🇯🇵',
        'Osaka': 'أوساكا 🇯🇵',
        'Singapore': 'سنغافورة 🇸🇬',
        'Jurong West': 'سنغافورة 🇸🇬',
        'Taiwan': 'تايوان 🇹🇼',
        'Changhua County': 'تايوان 🇹🇼',
        'Changhua': 'تايوان 🇹🇼',
        'Hong Kong': 'هونغ كونغ 🇭🇰',
        'Seoul': 'سيول 🇰🇷',
        'Mumbai': 'مومباي 🇮🇳',
        'Delhi': 'دلهي 🇮🇳',
        'Jakarta': 'جاكرتا 🇮🇩',
        'Kuala Lumpur': 'كوالالمبور 🇲🇾',
        'Bangkok': 'بانكوك 🇹🇭',
        'Tel Aviv': 'تل أبيب 🇮🇱',
        'Doha': 'الدوحة 🇶🇦',
        'Dammam': 'الدمام 🇸🇦',
        'Riyadh': 'الرياض 🇸🇦',
        'Jeddah': 'جدة 🇸🇦',
        'Dubai': 'دبي 🇦🇪',
        'Abu Dhabi': 'أبوظبي 🇦🇪',
        'Muscat': 'مسقط 🇴🇲',
        'Kuwait': 'الكويت 🇰🇼',
        'Bahrain': 'البحرين 🇧🇭',
        'Sydney': 'سيدني 🇦🇺',
        'Melbourne': 'ملبورن 🇦🇺',
        'Auckland': 'أوكلاند 🇳🇿',
        'Johannesburg': 'جوهانسبرغ 🇿🇦',
        'Cape Town': 'كيب تاون 🇿🇦',
        'Lagos': 'لاغوس 🇳🇬',
        'Nairobi': 'نيروبي 🇰🇪',
        'Cairo': 'القاهرة 🇪🇬',
        'Casablanca': 'الدار البيضاء 🇲🇦',
    }

    for key, val in translations.items():
        if key.lower() in name.lower():
            return val

    region_id_map = {
        'europe-north1': 'فنلندا 🇫🇮',
        'europe-north2': 'ستوكهولم 🇸🇪',
        'europe-west1': 'بلجيكا 🇧🇪',
        'europe-west2': 'لندن 🇬🇧',
        'europe-west3': 'فرانكفورت 🇩🇪',
        'europe-west4': 'هولندا 🇳🇱',
        'europe-west6': 'زيورخ 🇨🇭',
        'europe-west8': 'ميلانو 🇮🇹',
        'europe-west9': 'باريس 🇫🇷',
        'europe-west10': 'برلين 🇩🇪',
        'europe-west12': 'تورينو 🇮🇹',
        'europe-southwest1': 'مدريد 🇪🇸',
        'europe-central2': 'وارسو 🇵🇱',
        'us-central1': 'آيوا 🇺🇸',
        'us-east1': 'ساوث كارولينا 🇺🇸',
        'us-east4': 'فرجينيا 🇺🇸',
        'us-east5': 'كولومبوس 🇺🇸',
        'us-west1': 'أوريغون 🇺🇸',
        'us-west2': 'لوس أنجلوس 🇺🇸',
        'us-west3': 'سولت ليك سيتي 🇺🇸',
        'us-west4': 'لاس فيغاس 🇺🇸',
        'us-south1': 'دالاس 🇺🇸',
        'northamerica-northeast1': 'مونتريال 🇨🇦',
        'northamerica-northeast2': 'تورونتو 🇨🇦',
        'northamerica-south1': 'كيريتارو 🇲🇽',
        'southamerica-east1': 'ساو باولو 🇧🇷',
        'southamerica-west1': 'سانتياغو 🇨🇱',
        'asia-east1': 'تايوان 🇹🇼',
        'asia-east2': 'هونغ كونغ 🇭🇰',
        'asia-northeast1': 'طوكيو 🇯🇵',
        'asia-northeast2': 'أوساكا 🇯🇵',
        'asia-northeast3': 'سيول 🇰🇷',
        'asia-south1': 'مومباي 🇮🇳',
        'asia-south2': 'دلهي 🇮🇳',
        'asia-southeast1': 'سنغافورة 🇸🇬',
        'asia-southeast2': 'جاكرتا 🇮🇩',
        'australia-southeast1': 'سيدني 🇦🇺',
        'australia-southeast2': 'ملبورن 🇦🇺',
        'me-west1': 'تل أبيب 🇮🇱',
        'me-central1': 'الدوحة 🇶🇦',
        'me-central2': 'الدمام 🇸🇦',
        'africa-south1': 'جوهانسبرغ 🇿🇦',
    }

    for rid, val in region_id_map.items():
        if rid in name.lower():
            return val

    return f"{name} 🌍"

class HCHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200 if self.path == '/health' else 404)
        self.send_header('Content-type', 'text/plain'); self.end_headers()
        if self.path == '/health': self.wfile.write(b"OK")
    def log_message(self, *a): pass

def run_hc():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", int(os.environ.get("PORT", 8080))), HCHandler) as h: h.serve_forever()
threading.Thread(target=run_hc, daemon=True).start()

# ── Xvfb بحجم كبير = شاشة حقيقية 1920x1080 (مش 800x600 اللي بتكشف headless) ──
display = Display(visible=0, size=(1920, 1080), color_depth=24)
display.start()

# ── نهج جديد: "أحسن stealth = لا stealth" ──
# المتصفح الحقيقي عنده 0 overrides. كل override بـ Object.defineProperty بيترك trace
# قابل للكشف (Object.getOwnPropertyDescriptor بيكشف getter مخصص).
# الاعتماد على: --disable-blink-features=AutomationControlled (يخفي navigator.webdriver
# على مستوى Blink، مش JS) + binary patch للـ cdc_ في Dockerfile + excludeSwitches.
# الكود ده fallback أخير فقط — لو الـ blink flag مش شغّال على نسخة Chrome معينة.
STEALTH_JS = r"""
(() => {
// ── fallback وحيد: إخفاء navigator.webdriver لو لسه موجود (blink flag لم يخفيه) ──
try {
    if (navigator.webdriver) {
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    }
} catch(e){}

// ── تصفية console.warn من رسائل cdc_ (safety net للـ binary patch) ──
try {
    const _warn = console.warn;
    console.warn = function(...a) {
        const s = a.join(' ');
        if (/cdc_/i.test(s) || /chrome_driver/i.test(s)) return;
        return _warn.apply(console, a);
    };
} catch(e){}
})();
"""

def _detect_browser_paths():
    """يكتشف chromium + chromedriver على container Railway/Ubuntu.
    يعيد tuple (browser_path, driver_path) أو (None, None)."""
    import shutil
    browser = None
    for cand in ['chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable', '/usr/bin/chromium']:
        p = shutil.which(cand)
        if p: browser = p; break
    driver = None
    for cand in ['chromedriver', '/usr/bin/chromedriver']:
        p = shutil.which(cand)
        if p: driver = p; break
    # على Railway صورة python:3.11-slim + apt chromium:
    #   browser = /usr/bin/chromium, driver = /usr/bin/chromedriver
    return browser, driver

# نسخة Chrome الحالية المثبتة على container (لتجنب تحميل patcher خاطئ)
def _get_chrome_version():
    browser, _ = _detect_browser_paths()
    if not browser: return None
    try:
        r = subprocess.run([browser, '--version'], capture_output=True, text=True, timeout=10)
        m = re.search(r'(\d+)\.', r.stdout)
        return int(m.group(1)) if m else None
    except Exception: return None

def _build_options(use_exclude_switches: bool = True):
    """يبني ChromeOptions جديد بالكامل في كل مرة.

    use_exclude_switches=False للـ chromedriver 140+ الذي لا يعترف بـ:
      - excludeSwitches
      - useAutomationExtension
      - prefs (_profile_* experiments)
    في الحالة دي بنعتمد على: chromedriver binary patched (delete cdc_) +
    STEALTH_JS حقين عبر CDP + CLI flags فقط."""
    from selenium.webdriver.chrome.options import Options as _UCOptions
    opt = _UCOptions()
    # ⛔️ ممنوع --headless: جوجل بيكشفها بـ permissions query + null outerHeight.
    # احنا مش محتاجينها أصلاً لإن عندنا Xvfb 1920x1080.
    for a in ['--no-sandbox',
              '--disable-dev-shm-usage',
              '--disable-gpu',
              '--disable-software-rasterizer',
              '--disable-extensions',
              '--disable-background-networking',
              '--disable-default-apps',
              '--disable-sync',
              '--disable-translate',
              '--disable-hang-monitor',
              '--disable-component-update',
              '--disable-backgrounding-occluded-windows',
              '--disable-renderer-backgrounding',
              '--disable-background-timer-throttling',
              '--disable-ipc-flooding-protection',
              '--disable-client-side-phishing-detection',
              '--disable-popup-blocking',
              '--no-first-run',
              '--no-default-browser-check',
              '--disable-prompt-on-repost',
              '--renderer-process-limit=1',
              # مفيش site-per-process/IsolateOrigins/site-isolation-trial-opt-outs (بتكسر cross-origin redirects الـ SSO محتاجها)
              # مفيش VizDisplayCompositor (بيسبب rendering anomalies)
              '--disable-features=TranslateUI,AutofillServerCommunication',
              '--disable-blink-features=AutomationControlled',
              '--js-flags=--max-old-space-size=256',
              '--window-size=1920,1080',
              '--window-position=0,0',
              '--lang=en-US,en',
              '--accept-lang=en-US,en',
              '--disk-cache-size=0',
              '--media-cache-size=0',
              '--aggressive-cache-discard',
              '--disable-application-cache']:
        try: opt.add_argument(a)
        except Exception: pass
    # 'normal' = d.get() يستنى لحد ما الـ redirect chain كامل يتم (skills.google.com → accounts.google.com → console.cloud.google.com).
    # 'eager' بيرجع على DOMContentLoaded قبل ما الـ SSO redirect chain يخلص → بيقطع السلسلة.
    opt.page_load_strategy = 'normal'

    # للـ chromedriver القديم (<140) بس: نمّر excludeSwitches + useAutomationExtension + prefs.
    # للجديد (>=140): كل ده بيرفع "unrecognized chrome option" — نشيله نهائياً.
    if use_exclude_switches:
        try:
            opt.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        except Exception: pass
        try:
            opt.add_experimental_option('useAutomationExtension', False)
        except Exception: pass
        try:
            opt.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "safebrowsing.enabled": False,
                "profile.default_content_setting_values.geolocation": 2,
                "profile.default_content_setting_values.media_stream": 2,
            })
        except Exception: pass
    # للجديد: نعتمد على STEALTH_JS + CDP + chromedriver binary patched في الـ Dockerfile.
    return opt


def create_driver(chat_id: str = ""):
    # ⭐ لا nuke_all_chrome — يقتل مهام مستخدمين آخرين. تنظيف profile المؤقت فقط.
    time.sleep(0.5)

    # ⭐ لا UA تزييف — Chromium على Linux ليه UA صحيح (X11; Linux x86_64).
    # تزييف UA = Windows على Linux = 100 mismatch مكشوف (platform, WebGL, fonts, screen).

    # ── Qwiklabs REQUIRE incognito: profile فريش لكل مهمة + مسحه بعد المهمة ──
    # القواعد: "Run the lab in private browsing" + "Actions outside the lab scope will trigger
    # an automatic account block." → لازم temp dir جديد لكل مهمة عشان أي trace
    # متراكم يبقى "deviation" ويبلوك الحساب = "Couldn't sign you in / Contact your domain admin".
    udd = f"/tmp/ocx_task_{int(time.time())}_{random.randint(1000,9999)}"
    os.makedirs(udd, exist_ok=True)

    # ── تحديد مسار المتصفح + الـ driver على container + نسخة Chrome ──
    browser_path, driver_path = _detect_browser_paths()
    ver = os.environ.get("CHROME_VERSION_MAIN")
    if ver:
        try: ver = int(ver)
        except: ver = None
    if not ver:
        ver = _get_chrome_version()
    print(f"🔍 [UC] browser={browser_path} driver={driver_path} version={ver}")

    # كشف نسخة chromedriver عشان نعرف هل نمرّر excludeSwitches ولا لا
    # chromedriver >= 140 بيرفض excludeSwitches + useAutomationExtension + prefs القديمة
    exclude_sw = True
    if ver and ver >= 140:
        exclude_sw = False
        print("ℹ️ [UC] Chrome >=140 → تخطّي excludeSwitches + useAutomationExtension + prefs")

    # ════════════════════════════════════════════════════════════════
    #  المسار الأساسي: vanilla selenium + chromedriver binary patched (cdc_ → xxx_)
    #  + STEALTH_JS عبر CDP + INCognito (مطلوب من Qwiklabs)
    #  Incognito = مفيش persistent profile، تماماً زي ما Qwiklabs بتوصي به.
    #  STEALTH_JS بتفضل شغّالة = navigator.webdriver مخفي + سلاسل cdc_ ممسوحة.
    # ════════════════════════════════════════════════════════════════
    print("🚀 [Driver] vanilla selenium + stealth + INCognito (المسار الأساسي)")
    sopt = _build_options(use_exclude_switches=exclude_sw)
    if browser_path:
        sopt.binary_location = browser_path
    # ⭐ مفيش --incognito — incognito + automation إشارة bot أقوى. نعتمد على temp user-data-dir فريش لكل مهمة (نفس فايدة الـ private browsing اللي Qwiklabs بتطلبه) بدون إشارة incognito.
    # أضف user-data-dir مؤقت عشان نتجنّب "profile in use" line overlap
    # بس لازم يكون unique لكل instance:
    try:
        tmp_profile = f"/tmp/ocx_inc_{uuid_module.uuid4().hex[:8]}"
        os.makedirs(tmp_profile, exist_ok=True)
        sopt.add_argument(f'--user-data-dir={tmp_profile}')
    except Exception: pass
    svc = Service(executable_path=driver_path, log_output=os.devnull) if driver_path else Service(log_output=os.devnull)
    d = webdriver.Chrome(options=sopt, service=svc)
    # سجّل مسار الـ profile المؤقت على الـ driver عشان destroy_driver يمسحه بعد المهمة
    try:
        d._ocx_profile_dir = tmp_profile
    except Exception:
        pass
    print("✅ [Driver] selenium + chromedriver patched + incognito نشط")

    # ── حقن stealth JS للوثائق الجديدة (على مستوى CDP — يشتغل قبل أي DOM) ──
    try:
        d.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": STEALTH_JS})
    except Exception as e:
        print(f"⚠️ [Stealth CDP] {e}")

    # ⭐ لا CDP timezone/locale override — Emulation.setTimezoneOverride يترك trace قابل للكشف.
    # المتصفح الطبيعي ما عندهوش emulation. UTC هو التوقيت الطبيعي للحاوية → متناسق تلقائياً.

    d.set_page_load_timeout(60)
    d.set_script_timeout(15)
    d.implicitly_wait(1)
    return d

def get_driver_safe(chat_id: str = ""):
    for i in range(1, 4):
        try:
            print(f"🔧 [UC-Chrome] Attempt {i}/3 chat={chat_id}...")
            d = create_driver(chat_id); d.get("about:blank")
            print(f"✅ [UC-Chrome] OK chat={chat_id}"); return d
        except Exception as e:
            print(f"❌ [UC-Chrome] {i} failed chat={chat_id}: {e}")
            kill_driver_pid(d if 'd' in dir() else None); time.sleep(2)
    raise Exception("DRIVER_FAILED")

def alive(d):
    if not d: return False
    try: _ = d.title; return True
    except: return False

def safe_get(d, url):
    try: d.get(url); return True
    except TimeoutException:
        # ⭐ ما نعملش window.stop() — ده بيقتل الـ SSO redirect chain (skills.google.com → accounts.google.com → console.cloud.google.com).
        # الصفحة ممكن لسه بتعمل redirect؛ نرجع True ونسيب الـ main loop يكمّل.
        return True
    except Exception as e:
        if any(k in str(e).lower() for k in ['crash','not reachable','session','disconnected','target closed']): return False
        return True

def safe_exec(d, s, *a):
    try: return d.execute_script(s, *a)
    except: return None

def safe_find(d, by, v):
    try: return d.find_elements(by, v)
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

def destroy_driver(d, udd: str = None):
    # امسح temp profile dir عشان Qwiklabs incognito rule (لا persistent state بين المهام)
    profile_dir = udd
    if d is not None:
        try:
            profile_dir = profile_dir or getattr(d, '_ocx_profile_dir', None)
        except Exception:
            pass
        try: d.quit()
        except: pass
        # ⭐ اقتل Chrome خاص بهذه المهمة فقط — لا تمسّ مهام المستخدمين الآخرين
        kill_driver_pid(d)
    if profile_dir:
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception: pass

def sdm(cid, mid):
    if mid:
        try: bot.delete_message(cid, mid)
        except: pass

def inject_cookies_safely(d, cookies):
    if not cookies: return
    try:
        safe_get(d, "https://google.com/robots.txt"); time.sleep(0.5)
        for c in cookies:
            if 'google.com' in c.get('domain', ''):
                try: d.add_cookie(c)
                except: pass
        safe_get(d, "https://console.cloud.google.com/robots.txt"); time.sleep(0.5)
        for c in cookies:
            if 'cloud.google.com' in c.get('domain', ''):
                try: d.add_cookie(c)
                except: pass
    except: pass

def uls(cid, mid, text, logs=None, driver=None, is_photo=False):
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

R_OK = "SUCCESS"
R_RETRY = "RETRY"
R_ABORT = "ABORT"

def run_single_task(chat_id, url, task_id, attempt_num):
    driver = None
    status_msg_id = None
    is_photo = False

    try:
        driver = get_driver_safe(chat_id)

        cs = get_session(chat_id)
        ex = get_server_by_url(url)
        spid = ex.get('project_id', '') if ex else ''
        scook = ex.get('cookies', []) if ex else []

        turl = url
        istate = "INIT"
        sso_tried = True

        if spid and (cs.get('replace_mode') or cs.get('add_new_mode')):
            if cs.get('replace_mode'):
                turl = f"https://shell.cloud.google.com/?enableapi=true&project={spid}&pli=1&show=terminal"
                istate = "AUTHORIZE_SHELL"
            else:
                turl = f"https://console.cloud.google.com/run/services?project={spid}"
                istate = "WAIT_DEPLOY"
            sso_tried = False

        if not safe_get(driver, turl):
            raise Exception("CHROME_CRASH")

        state = istate
        cook_tried = False
        # ⭐ انتظار استقرار URL بعد SSO redirect chain
        prev_url = ''
        stable_count = 0
        for _ in range(10):  # max 15 ثانية بدل 60
            cur = safe_url(driver)
            if cur == prev_url:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                stable_count = 0
            prev_url = cur
            time.sleep(1)
        time.sleep(1)

        mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء فوري", callback_data="abort_mission"))
        rn = f"\n🔄 *(محاولة {attempt_num})*" if attempt_num > 1 else ""
        ss = safe_screenshot(driver)
        if ss:
            try: msg = bot.send_photo(chat_id, photo=ss, caption=f"🟢 **سجل العمليات:**\n⚡ جاري التهيئة...{rn}", parse_mode="Markdown", reply_markup=mk); is_photo = True
            except: msg = bot.send_message(chat_id, f"🟢 ⚡ جاري التهيئة...{rn}", parse_mode="Markdown", reply_markup=mk)
        else:
            msg = bot.send_message(chat_id, f"🟢 ⚡ جاري التهيئة...{rn}", parse_mode="Markdown", reply_markup=mk)
        status_msg_id = msg.message_id

        lc = 0
        pid = spid or ""
        dead = 0

        while lc < 500:
            lc += 1
            time.sleep(1)

            if not is_task_current(chat_id, task_id):
                sdm(chat_id, status_msg_id)
                return R_ABORT

            if not alive(driver):
                dead += 1
                if dead >= 3:
                    sdm(chat_id, status_msg_id)
                    return R_RETRY
                time.sleep(1); continue
            dead = 0

            if lc % 20 == 0:
                safe_exec(driver, "try{performance.clearResourceTimings();}catch(e){}")

            cur_url = safe_url(driver)
            if not cur_url: continue

            cs = get_session(chat_id)

            user_waiting = (state == "WAIT_USER_SELECTION" or cs.get('status') == 'waiting_credentials')

            if user_waiting:
                last_int = cs.get('interaction_time', 0)
                if last_int and (time.time() - last_int > 90):
                    sdm(chat_id, status_msg_id)
                    sdm(chat_id, cs.get('ui_msg_id'))
                    bot.send_message(chat_id,
                        "⏳ **تم إنهاء الجلسة تلقائياً!**\n\n"
                        "لم تقم بالاختيار خلال 90 ثانية.\n"
                        "تم إخلاء مكانك في الطابور.\n\n"
                        "💡 أرسل الرابط مرة أخرى عندما تكون جاهزاً.",
                        parse_mode="Markdown")
                    return R_ABORT

            if 'accounts.google.com' in cur_url:
                time.sleep(1)

                # ✅ FIX: استعمال innerText (النص المرئي فقط) بدل page_source
                visible_text = safe_exec(driver, "return document.body ? document.body.innerText : '';") or ""
                vt_lower = visible_text.lower()

                # ✅ صفحة "Verify it's you" / "تأكد من أنه أنت" — بتيجي بعد الـ login من IP جديد.
                # في صفحة فيها زر Continue + النص ده (مش حظر) = نضغط Continue
                if (("verify it's you" in vt_lower or
                     "confirm" in vt_lower and "account" in vt_lower or
                     "تأكد" in visible_text or
                     "للتأكد" in visible_text) and
                    "couldn't sign you in" not in vt_lower):
                    cont_btn = safe_find(driver, By.XPATH,
                        "//button[contains(translate(.,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'continue') or "
                        "contains(.,'متابعة') or contains(.,'Continue')]")
                    if cont_btn:
                        for b in cont_btn:
                            try:
                                if b.is_displayed() and b.is_enabled():
                                    uls(chat_id, status_msg_id, "🟡 **تأكيد الحساب...**", driver=driver, is_photo=is_photo)
                                    safe_exec(driver, "arguments[0].click();", b)
                                    time.sleep(3)
                                    sdm(chat_id, status_msg_id)
                                    status_msg_id = 0
                                    continue
                            except Exception: pass


                # ✅ فحص الحظر — "Couldn't sign you in / Contact your domain admin"
                # هذه شاشة حظر حساب من Qwiklabs (expired أو deviation).
                # ما ينفعش retry بنفس الحساب — لازم ABORT + طلب حساب/رابط جديد.
                if ("couldn't sign you in" in vt_lower or
                    ("domain admin" in vt_lower and "for help" in vt_lower) or
                    "admin for help" in vt_lower):

                    has_email_input = False
                    ei_check = safe_find(driver, By.XPATH, "//input[@type='email']")
                    if ei_check and ei_check[0].is_displayed():
                        has_email_input = True

                    has_pw_input = False
                    pi_check = safe_find(driver, By.XPATH, "//input[@type='password']")
                    if pi_check and pi_check[0].is_displayed():
                        has_pw_input = True

                    # ⭐ تأكيد الحظر: انتظر 3 ثواني وأعد الفحص (ممكن يكون transient أثناء SSO redirect)
                    time.sleep(3)
                    confirm_text = safe_exec(driver, "return document.body ? document.body.innerText : '';") or ""
                    confirm_lower = confirm_text.lower()
                    if "couldn't sign you in" not in confirm_lower and "domain admin" not in confirm_lower:
                        continue

                    # ✅ فقط لو ما في أي حقل دخول → صفحة حظر حقيقية (مش شاشة login عادية)
                    if not has_email_input and not has_pw_input:
                        sdm(chat_id, status_msg_id)
                        # امسح كل الـ storage عشان لو فيه أي trace
                        try:
                            safe_exec(driver, """
                                document.cookie.split(';').forEach(c=>{
                                    document.cookie=c.trim().split('=')[0]+'=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
                                });
                                try { localStorage.clear(); } catch(e){}
                                try { sessionStorage.clear(); } catch(e){}
                            """)
                        except Exception: pass
                        try:
                            bot.send_message(chat_id,
                                "⛔ **الحساب محظور من Qwiklabs.**\n\n"
                                "هذا الحساب إما انتهت صلاحيته أو تم حظره بسبب مخالفة شروط Qwiklabs.\n\n"
                                "💡 **الحل:** أرسل رابط دخول جديد بحساب `student-02-xxx@qwiklabs.net` آخر.",
                                parse_mode="Markdown")
                        except Exception: pass
                        return R_ABORT   # ⭐ مش retry — الحساب محظور، مفيش فايدة

                ei = safe_find(driver, By.XPATH, "//input[@type='email']")
                pi = safe_find(driver, By.XPATH, "//input[@type='password']")

                if ei and ei[0].is_displayed() and not (pi and pi[0].is_displayed()):
                    if not sso_tried:
                        uls(chat_id, status_msg_id, "🔄 **SSO...**", driver=driver, is_photo=is_photo)
                        sso_tried = True
                        if not safe_get(driver, url): sdm(chat_id, status_msg_id); return R_RETRY
                        state = "INIT"; time.sleep(1); continue
                    elif not cook_tried and scook:
                        uls(chat_id, status_msg_id, "⚡ **حقن كوكيز...**", driver=driver, is_photo=is_photo)
                        inject_cookies_safely(driver, scook); cook_tried = True
                        if not safe_get(driver, turl): sdm(chat_id, status_msg_id); return R_RETRY
                        state = istate; time.sleep(1); continue
                    elif cs.get('status') != 'waiting_credentials' and not cs.get('email'):
                        sdm(chat_id, status_msg_id)
                        msg = bot.send_message(chat_id, "⚠️ **مطلوب بيانات الدخول.**\n\n`student-02-xxx@qwiklabs.net Password123`", parse_mode="Markdown")
                        update_session(chat_id, {'status': 'waiting_credentials', 'ui_msg_id': msg.message_id, 'interaction_time': time.time()})
                        status_msg_id = msg.message_id; continue

                if cs.get('email') and cs.get('password'):
                    try:
                        if ei and ei[0].is_displayed():
                            uls(chat_id, status_msg_id, "مصادقة", f"بريد: {cs['email']}", driver=driver, is_photo=is_photo)
                            ei[0].click(); time.sleep(0.2)
                            ei[0].clear(); time.sleep(0.1)
                            for ch in cs['email']:
                                ei[0].send_keys(ch)
                                time.sleep(random.uniform(0.015, 0.04))
                            time.sleep(0.3); ei[0].send_keys(Keys.ENTER)
                            time.sleep(1); continue
                        elif pi and pi[0].is_displayed():
                            uls(chat_id, status_msg_id, "مصادقة", "كلمة مرور... ***", driver=driver, is_photo=is_photo)
                            pi[0].click(); time.sleep(0.2)
                            pi[0].clear(); time.sleep(0.1)
                            for ch in cs['password']:
                                pi[0].send_keys(ch)
                                time.sleep(random.uniform(0.015, 0.04))
                            time.sleep(0.3); pi[0].send_keys(Keys.ENTER)
                            time.sleep(1.5); update_session(chat_id, {'email': None, 'password': None}); state = "INIT"
                            sdm(chat_id, status_msg_id)
                            mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء", callback_data="abort_mission"))
                            ss = safe_screenshot(driver)
                            try: msg = bot.send_photo(chat_id, photo=ss, caption="🟢 ✅ تمت المصادقة...", parse_mode="Markdown", reply_markup=mk); is_photo = True
                            except: msg = bot.send_message(chat_id, "🟢 ✅ تمت المصادقة...", parse_mode="Markdown", reply_markup=mk); is_photo = False
                            status_msg_id = msg.message_id; continue
                    except Exception as e: print(f"Login: {e}")

                if cs.get('status') == 'waiting_credentials': continue

            if state == "WAIT_USER_SELECTION":
                if cs.get('selected_region') and cs.get('protocol'):
                    if pid:
                        if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={pid}&pli=1&show=terminal"):
                            sdm(chat_id, status_msg_id); return R_RETRY
                        state = "AUTHORIZE_SHELL"
                continue

            elif state == "SILENT_BUILD":
                ps = safe_source(driver)
                if not ps and not alive(driver): sdm(chat_id, status_msg_id); return R_RETRY
                if "ERROR_DEPLOYMENT_FAILED_OCX_CATCH" in ps: sdm(chat_id, status_msg_id); return R_ABORT
                sm = re.search(r'OCX_DATA_SYNC:\s*(.*?)\|(.*?)\|(.*?)\|(.*?)(?:\n|<)', ps)
                if sm: save_successful_server(chat_id, url, sm.group(1), sm.group(2), sm.group(3), pid, safe_cookies(driver))
                if "SUCCESS_OCX_FINISH" in ps: sdm(chat_id, status_msg_id); return R_OK
                uls(chat_id, status_msg_id, f"🟢 **بناء الحاوية...**\n⏳ {lc*3}s", driver=driver, is_photo=is_photo)
                continue
            else:
                am = {"INIT": "التهيئة", "WAIT_DEPLOY": "واجهة البناء", "WAIT_REGION": "خريطة السيرفرات", "EXTRACT_REGIONS": "استخراج البيانات", "AUTHORIZE_SHELL": "تفويض الطرفية", "WAIT_TERMINAL_BOOT": "تشغيل Linux", "INJECT_PAYLOAD": "حقن السكربت"}
                uls(chat_id, status_msg_id, f"🟢 المرحلة: `{am.get(state, state)}`", driver=driver, is_photo=is_photo)

            try:
                for btn in safe_find(driver, By.XPATH, "//button[contains(.,'Agree and continue') or contains(.,'موافق ومتابعة') or contains(.,'Akkoord en doorgaan')]"):
                    if btn.is_displayed():
                        for cb in safe_find(driver, By.XPATH, "//*[@role='checkbox'] | //mat-checkbox | //input[@type='checkbox']"):
                            safe_exec(driver, "arguments[0].click();", cb)
                        time.sleep(0.5); safe_exec(driver, "arguments[0].click();", btn); break
            except: pass

            if state == "INIT":
                if 'accounts.google.com' in cur_url:
                    try:
                        for el in safe_find(driver, By.XPATH, "//*[@id='confirm'] | //input[@type='submit'] | //button | //div[@role='button'] | //span"):
                            t = ((el.text or el.get_attribute('value') or '')).lower()
                            eid = el.get_attribute('id') or ''
                            if any(k in t for k in ['understand','begrijp','accept','أفهم','موافق','continue','متابعة']) or eid == 'confirm':
                                safe_exec(driver, "arguments[0].click();", el); break
                    except: pass
                elif 'console.cloud.google.com' in cur_url:
                    m = re.search(r'project=([^&#]+)', cur_url)
                    if m:
                        pid = spid if (spid and (cs.get('replace_mode') or cs.get('add_new_mode'))) else m.group(1)
                        fc = safe_cookies(driver)
                        if fc: update_server_cookies(url, fc)
                        uls(chat_id, status_msg_id, "🟢 🔐 تم الوصول.", driver=driver, is_photo=is_photo)
                        time.sleep(0.5)
                        if cs.get('replace_mode'):
                            if not safe_get(driver, f"https://shell.cloud.google.com/?enableapi=true&project={pid}&pli=1&show=terminal"): sdm(chat_id, status_msg_id); return R_RETRY
                            state = "AUTHORIZE_SHELL"
                        else:
                            if not safe_get(driver, f"https://console.cloud.google.com/run/services?project={pid}"): sdm(chat_id, status_msg_id); return R_RETRY
                            state = "WAIT_DEPLOY"

            elif state == "WAIT_DEPLOY":
                for btn in safe_find(driver, By.XPATH, "//*[contains(text(),'Deploy container')]"):
                    try:
                        if btn.is_displayed(): safe_exec(driver, "arguments[0].click();", btn); state = "WAIT_REGION"; break
                    except: pass

            elif state == "WAIT_REGION":
                safe_exec(driver, "document.querySelectorAll('button').forEach(b=>{if(b.innerText.includes('OK, got it')||b.innerText.includes('Accept'))b.click()})")
                for re_el in safe_find(driver, By.XPATH, "//*[contains(text(),'Region') and not(contains(text(),'Regions'))]"):
                    try:
                        if re_el.is_displayed():
                            safe_exec(driver, "arguments[0].scrollIntoView({block:'center'});", re_el)
                            time.sleep(0.5); safe_exec(driver, "arguments[0].click();", re_el)
                            state = "EXTRACT_REGIONS"; break
                    except: pass
                else: safe_exec(driver, "window.scrollBy(0,300);")

            elif state == "EXTRACT_REGIONS":
                if cs.get('replace_mode'): state = "WAIT_USER_SELECTION"; continue
                time.sleep(0.5)
                rlist = []
                for opt in safe_find(driver, By.XPATH, "//*[@role='option'] | //mat-option | //*[contains(@class,'mat-option-text')]"):
                    try:
                        t = " ".join((opt.get_attribute('textContent') or opt.text or '').split()).strip()
                        if len(t) > 3 and "Select" not in t and t not in [r['raw'] for r in rlist]:
                            m2 = re.search(r'^([a-z0-9-]+)\s*\(([^)]+)\)', t)
                            rid, rn = (m2.group(1), m2.group(2)) if m2 else (t.split()[0], t)
                            if rid.startswith(('us-','northamerica-','southamerica-')): ct = 'أمريكا 🌎'
                            elif rid.startswith('europe-'): ct = 'أوروبا 🌍'
                            elif rid.startswith('asia-'): ct = 'آسيا 🌏'
                            elif rid.startswith('australia-'): ct = 'أستراليا 🦘'
                            elif rid.startswith(('me-','africa-')): ct = 'الشرق الأوسط 🐪'
                            else: ct = 'أخرى 🗺️'
                            rlist.append({'id': rid, 'name': rn, 'continent': ct, 'raw': t})
                    except: pass

                if rlist:
                    gr = {}
                    for r in rlist: gr.setdefault(r['continent'], []).append(r)
                    update_session(chat_id, {'available_regions': gr, 'project_id': pid})
                    sdm(chat_id, status_msg_id); status_msg_id = None
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
                    sdm(chat_id, cs.get('ui_msg_id'))
                    mk = InlineKeyboardMarkup().add(InlineKeyboardButton("🛑 إلغاء", callback_data="abort_mission"))
                    ss = safe_screenshot(driver)
                    try: msg = bot.send_photo(chat_id, photo=ss, caption="🟢 🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=mk); is_photo = True
                    except: msg = bot.send_message(chat_id, "🟢 🚀 فتح الطرفية...", parse_mode="Markdown", reply_markup=mk); is_photo = False
                    status_msg_id = msg.message_id

                jc = """function ac(r){if(!r)return false;let els=r.querySelectorAll('button,span.mdc-button__label,modal-action button,a,[role="button"]');for(let e of els){let t=(e.innerText||e.textContent||'').trim();if(['Continue','Doorgaan','متابعة','Continuer'].includes(t)){try{e.click()}catch(x){}}if(['Authorize','Autoriser','تخويل','Autoriseren'].includes(t)||(t.includes('Authorize')&&t.length<=15)){try{e.click()}catch(x){}e.querySelectorAll('span').forEach(s=>{try{s.click()}catch(x){}});return true}}for(let e of r.querySelectorAll('*')){if(e.shadowRoot&&ac(e.shadowRoot))return true}return false}if(ac(document))return true;for(let f of document.querySelectorAll('iframe')){try{if(ac(f.contentDocument))return true}catch(x){}}return false;"""
                if safe_exec(driver, jc): state = "WAIT_TERMINAL_BOOT"

            elif state == "WAIT_TERMINAL_BOOT":
                jt = "function c(r){if(r.querySelector('textarea.xterm-helper-textarea'))return true;for(let f of r.querySelectorAll('iframe')){try{if(c(f.contentDocument))return true}catch(e){}}return false}return c(document);"
                if safe_exec(driver, jt): time.sleep(0.5); state = "INJECT_PAYLOAD"

            elif state == "INJECT_PAYLOAD":
                uls(chat_id, status_msg_id, "حقن النواة", "جاري حقن OCX...", driver=driver, is_photo=is_photo)
                cs2 = get_session(chat_id)
                sr = cs2.get('selected_region', 'europe-west4')
                pr = cs2.get('protocol', 'vless')
                rm = cs2.get('replace_mode', False)
                osn = cs2.get('old_server_name', '')
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

        sdm(chat_id, status_msg_id)
        return R_ABORT

    except Exception as e:
        sdm(chat_id, status_msg_id)
        err = str(e).lower()
        print(f"❌ [Task] {chat_id} A{attempt_num}: {e}")
        if any(k in err for k in ['crash','renderer','timeout','session','disconnected','not reachable','target closed','chrome','driver']):
            return R_RETRY
        return R_ABORT
    finally:
        destroy_driver(driver)

MAX_WORKERS = 3
USER_COOLDOWN = {}  # chat_id → expiry timestamp
COOLDOWN_SECONDS = 30

def worker_loop(worker_id: int):
    """كل worker يستهلك مهام من نفس الطابور بشكل مستقل."""
    while True:
        task = None
        try: task = task_queue.get(timeout=30)
        except queue.Empty: continue
        except: continue

        try:
            cid = task['chat_id']; url = task['url']; tid = task['task_id']
            if not is_task_current(cid, tid): continue

            update_session(cid, {'status': 'processing', 'interaction_time': time.time()})
            sdm(cid, get_session(cid).get('ui_msg_id'))

            for att in range(1, 4):
                if not is_task_current(cid, tid): break
                if att > 1:
                    try:
                        rm = bot.send_message(cid, f"🔄 **إعادة محاولة ({att}/3)...**", parse_mode="Markdown")
                        time.sleep(2); sdm(cid, rm.message_id)
                    except: pass
                    time.sleep(2)
                    if not is_task_current(cid, tid): break
                    update_session(cid, {'status': 'processing', 'interaction_time': time.time()})

                r = run_single_task(cid, url, tid, att)
                if r == R_OK: break
                elif r == R_ABORT: break
                elif r == R_RETRY and att >= 3:
                    try: bot.send_message(cid, "❌ **فشلت 3 محاولات.**\n💡 انتظر 30 ثانية وأعد الرابط.", parse_mode="Markdown")
                    except: pass

        except Exception as e:
            print(f"❌ [Worker-{worker_id} FATAL] {e}")
            if task:
                try: bot.send_message(task['chat_id'], "⚠️ خطأ. أعد الرابط.", parse_mode="Markdown")
                except: pass
        finally:
            if task:
                try:
                    cur = get_session(task['chat_id'])
                    if cur.get('task_id') == task['task_id']: clear_session(task['chat_id'])
                except: pass
                try: task_queue.task_done()
                except: pass

def start_workers():
    """ينشئ MAX_WORKERS عمال متوازين."""
    with worker_lock:
        for i in range(MAX_WORKERS):
            t = threading.Thread(target=worker_loop, args=(i,), daemon=True, name=f"OCX-Worker-{i}")
            t.start()
            workers.append(t)
        print(f"✅ [Workers] {MAX_WORKERS} workers started")

def ensure_workers():
    """يتأكد أن كل العمال أحياء، ويعيد تشغيل أي عامل ميت."""
    with worker_lock:
        alive_count = sum(1 for w in workers if w.is_alive())
        if alive_count < MAX_WORKERS:
            needed = MAX_WORKERS - alive_count
            for i in range(needed):
                idx = len(workers)
                t = threading.Thread(target=worker_loop, args=(idx,), daemon=True, name=f"OCX-Worker-{idx}")
                t.start()
                workers.append(t)
            print(f"⚠️ [Workers] restarted {needed} dead workers")

start_workers()

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    cid = message.chat.id
    try: bot.delete_message(cid, message.message_id)
    except: pass
    if not is_vip(cid): send_unauthorized_msg(cid); return
    t = "💎 **مرحباً بك في نظام OCX PRO** 💎\n\n⚡ أسرع نظام لإنشاء سيرفرات Qwiklabs.\n🔗 **أرسل رابط الدخول لبدء العملية.**"
    if str(cid) == str(ADMIN_ID):
        mk = ReplyKeyboardMarkup(resize_keyboard=True); mk.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.send_message(cid, t, reply_markup=mk, parse_mode="Markdown")
    else:
        bot.send_message(cid, t, reply_markup=telebot.types.ReplyKeyboardRemove(), parse_mode="Markdown")

@bot.message_handler(commands=['cancel', 'stop'])
def force_cancel(message):
    cid = message.chat.id
    if not is_vip(cid): return
    try: bot.delete_message(cid, message.message_id)
    except: pass
    clear_session(cid)
    bot.send_message(cid, "🛑 **تم إلغاء المهمة.**\nيمكنك إرسال رابط جديد.", parse_mode="Markdown")

def process_add_vip(msg):
    nid = msg.text.strip()
    if nid.isdigit():
        add_vip_user(nid); bot.reply_to(msg, f"✅ تم إضافة `{nid}`.", parse_mode="Markdown")
        try:
            s = get_session(nid)
            if s.get('unauth_msg_id'): sdm(nid, s['unauth_msg_id']); update_session(nid, {'unauth_msg_id': None})
            bot.send_message(nid, "🎉 **تم تفعيل اشتراكك!**\n🔗 أرسل رابط الدخول.", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(msg, "❌ معرف خاطئ.")

def process_del_vip(msg):
    did = msg.text.strip()
    if did.isdigit():
        remove_vip_user(did); bot.reply_to(msg, f"🗑️ تم حذف `{did}`.", parse_mode="Markdown")
        try: bot.send_message(did, "⛔️ **تم سحب صلاحياتك.**", parse_mode="Markdown")
        except: pass
    else: bot.reply_to(msg, "❌ معرف خاطئ.")

def process_broadcast(msg):
    t = msg.text
    if t in ["👥 قائمة الـ VIP","📊 حالة النظام","➕ إضافة عميل","➖ إزالة عميل","📢 إذاعة رسالة","🔙 القائمة الرئيسية"]:
        bot.reply_to(msg, "❌ إلغاء."); return
    sc = 0
    for uid in get_all_vips():
        try: bot.send_message(uid, f"📢 **إشعار:**\n\n{t}", parse_mode="Markdown"); sc += 1
        except: pass
    bot.send_message(msg.chat.id, f"✅ تم لـ `{sc}` مشترك.", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👑 لوحة الإدارة")
def admin_panel(msg):
    if str(msg.chat.id) != str(ADMIN_ID): return
    mk = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    mk.add(KeyboardButton("👥 قائمة الـ VIP"), KeyboardButton("📊 حالة النظام"))
    mk.add(KeyboardButton("➕ إضافة عميل"), KeyboardButton("➖ إزالة عميل"))
    mk.add(KeyboardButton("📢 إذاعة رسالة"), KeyboardButton("🔙 القائمة الرئيسية"))
    bot.reply_to(msg, "👑 **لوحة الإدارة** 👑", reply_markup=mk, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text in ["👥 قائمة الـ VIP","📊 حالة النظام","➕ إضافة عميل","➖ إزالة عميل","📢 إذاعة رسالة","🔙 القائمة الرئيسية"])
def admin_kb(msg):
    cid = msg.chat.id
    if str(cid) != str(ADMIN_ID): return
    t = msg.text
    if t == "👥 قائمة الـ VIP":
        v = get_all_vips()
        bot.reply_to(msg, "👥 **VIPs:**\n\n" + ("\n".join([f"🔹 `{u}`" for u in v]) if v else "فارغة."), parse_mode="Markdown")
    elif t == "📊 حالة النظام":
        wa = f"{sum(1 for w in workers if w.is_alive())}/{MAX_WORKERS} حي"
        bot.reply_to(msg, f"📊 **النظام:**\n📦 طابور: `{task_queue.qsize()}`\n💾 `{'MongoDB 🟢' if USE_MONGO else 'RAM 🟡'}`\n👷 Workers: `{wa}`", parse_mode="Markdown")
    elif t == "➕ إضافة عميل":
        m = bot.send_message(cid, "✏️ **ID:**"); bot.register_next_step_handler(m, process_add_vip)
    elif t == "➖ إزالة عميل":
        m = bot.send_message(cid, "✏️ **ID:**"); bot.register_next_step_handler(m, process_del_vip)
    elif t == "📢 إذاعة رسالة":
        m = bot.send_message(cid, "📢 **الرسالة:**"); bot.register_next_step_handler(m, process_broadcast)
    elif t == "🔙 القائمة الرئيسية":
        mk = ReplyKeyboardMarkup(resize_keyboard=True); mk.add(KeyboardButton("👑 لوحة الإدارة"))
        bot.reply_to(msg, "🔙", reply_markup=mk)

@bot.message_handler(func=lambda m: get_session(m.chat.id).get('status') == 'waiting_credentials')
def handle_creds(msg):
    cid = msg.chat.id; t = msg.text.strip()
    em = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', t)
    if em:
        email = em.group(0); pw = t.replace(email, '').strip()
        if pw:
            update_session(cid, {'email': email, 'password': pw, 'status': 'processing', 'interaction_time': time.time()})
            try: bot.delete_message(cid, msg.message_id)
            except: pass
            bot.send_message(cid, "✅ **تم!** جاري المصادقة...", parse_mode="Markdown"); return
    bot.send_message(cid, "⚠️ **خطأ!**\n`email@qwiklabs.net Password123`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    cid = call.message.chat.id; data = call.data
    if not is_vip(cid):
        try: bot.answer_callback_query(call.id, "❌")
        except: pass; return

    session = get_session(cid)
    update_session(cid, {'interaction_time': time.time()})

    if data == "cancel_ui":
        clear_session(cid)
        try: bot.edit_message_text("🛑 تم الإلغاء.", chat_id=cid, message_id=call.message.message_id)
        except: pass; return

    if data == "abort_mission":
        clear_session(cid)
        try: bot.answer_callback_query(call.id, "تم!")
        except: pass
        sdm(cid, call.message.message_id)
        bot.send_message(cid, "🛑 **تم إلغاء المهمة.** جاهز لرابط جديد.", parse_mode="Markdown"); return

    if data in ["replace_server", "add_new_server"]:
        url = session.get('target_url')
        if not url: return
        tid = gen_task_id()
        ud = {'active': True, 'status': 'queued', 'interaction_time': time.time(), 'task_id': tid}
        if data == "replace_server":
            od = get_server_by_url(url)
            if od: ud.update({'replace_mode': True, 'old_server_name': od.get('server_name', ''), 'selected_region': od.get('region', ''), 'protocol': od.get('protocol', 'vless')})
            try: bot.edit_message_text("🔄 **استبدال...**", chat_id=cid, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        else:
            ud.update({'replace_mode': False, 'add_new_mode': True})
            try: bot.edit_message_text("➕ **إضافة جديد...**", chat_id=cid, message_id=call.message.message_id, parse_mode="Markdown")
            except: pass
        update_session(cid, ud); ensure_workers()
        task_queue.put({'chat_id': cid, 'url': url, 'task_id': tid}); return

    if not session.get('active'):
        try: bot.answer_callback_query(call.id, "❌ منتهية.")
        except: pass; return

    if data.startswith("cont_"):
        ct = data[5:]; regs = session.get('available_regions', {}).get(ct, [])
        mk = InlineKeyboardMarkup(row_width=1)
        for r in regs: mk.add(InlineKeyboardButton(text=f"{translate_region(r['name'])} ({r['id']})", callback_data=f"reg_{r['id']}"))
        mk.add(InlineKeyboardButton("🔙 العودة", callback_data="back_to_conts"))
        try: bot.edit_message_text(f"📍 سيرفرات {ct}:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk)
        except: pass

    elif data.startswith("reg_"):
        rid = data[4:]; update_session(cid, {'selected_region': rid})
        mk = InlineKeyboardMarkup(row_width=3)
        mk.add(InlineKeyboardButton("⚡ VLESS", callback_data="proto_vless"), InlineKeyboardButton("🛡️ VMESS", callback_data="proto_vmess"), InlineKeyboardButton("🐎 TROJAN", callback_data="proto_trojan"))
        try: bot.edit_message_text(f"✅ المنطقة: `{rid}`\n\n👇 البروتوكول:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk, parse_mode="Markdown")
        except: pass

    elif data.startswith("proto_"):
        update_session(cid, {'protocol': data[6:]}); sdm(cid, call.message.message_id)

    elif data == "back_to_conts":
        gr = session.get('available_regions', {}); mk = InlineKeyboardMarkup(row_width=2)
        mk.add(*[InlineKeyboardButton(text=c, callback_data=f"cont_{c}") for c in gr.keys()])
        try: bot.edit_message_text("👇 اختر القارة:", chat_id=cid, message_id=call.message.message_id, reply_markup=mk)
        except: pass

@bot.message_handler(func=lambda m: m.text and m.text.startswith('http'))
def handle_url(msg):
    cid = msg.chat.id; url = msg.text
    try: bot.delete_message(cid, msg.message_id)
    except: pass
    if not is_vip(cid): send_unauthorized_msg(cid); return
    if not url.startswith("https://www.skills.google/google_sso"): return

    s = get_session(cid)
    if s.get('active'):
        m = bot.send_message(cid, "⚠️ **مهمة قيد التنفيذ!**\n/cancel أولاً.", parse_mode="Markdown")
        threading.Timer(15.0, lambda mid=m.message_id: sdm(cid, mid)).start(); return

    # ⭐ rate-limit: منع مستخدم واحد من ملء الطابور
    now = time.time()
    cooldown_exp = USER_COOLDOWN.get(str(cid), 0)
    if now < cooldown_exp:
        wait = int(cooldown_exp - now)
        m = bot.send_message(cid, f"⏳ **انتظر {wait} ثانية قبل إرسال رابط جديد.**", parse_mode="Markdown")
        threading.Timer(10.0, lambda mid=m.message_id: sdm(cid, mid)).start(); return

    ex = get_server_by_url(url)
    if ex and ex.get('project_id'):
        tid = gen_task_id()
        update_session(cid, {'target_url': url, 'task_id': tid})
        mk = InlineKeyboardMarkup(row_width=1)
        mk.add(InlineKeyboardButton("🔄 استبدال القديم", callback_data="replace_server"),
               InlineKeyboardButton("➕ سيرفر جديد", callback_data="add_new_server"),
               InlineKeyboardButton("🛑 إلغاء", callback_data="cancel_ui"))
        m = bot.send_message(cid, "⚠️ **رابط مستخدم!** كيف تفضل؟", reply_markup=mk, parse_mode="Markdown")
        update_session(cid, {'ui_msg_id': m.message_id}); return

    # ⭐ فحص امتلاء الطابور
    if task_queue.qsize() >= 20:
        m = bot.send_message(cid, "📋 **الطابور ممتلئ حالياً.**\nحاول مرة أخرى بعد قليل.", parse_mode="Markdown")
        threading.Timer(15.0, lambda mid=m.message_id: sdm(cid, mid)).start(); return

    tid = gen_task_id()
    m = bot.send_message(cid, "⏳ **تمت الإضافة للطابور...**", parse_mode="Markdown")
    update_session(cid, {'active': True, 'status': 'queued', 'target_url': url, 'ui_msg_id': m.message_id, 'interaction_time': time.time(), 'task_id': tid})
    USER_COOLDOWN[str(cid)] = now + COOLDOWN_SECONDS
    ensure_workers()
    task_queue.put({'chat_id': cid, 'url': url, 'task_id': tid})

@bot.message_handler(func=lambda m: True, content_types=['text','photo','video','document','audio','sticker','voice'])
def del_spam(msg):
    try: bot.delete_message(msg.chat.id, msg.message_id)
    except: pass

if __name__ == "__main__":
    print("💎 OCX PRO V5 ACTIVE...")
    nuke_all_chrome()
    try: bot.remove_webhook()
    except: pass

    # ── الحل النهائي للـ 409: اسحب updates بـ offset=-1 مرات متتالية
    # ده بيعمل "commit" لآخر update_id ويعطّل أي long-polling معلّق من نسخة تانية ──
    # لازم نكرّرها عشان Telegram ممكن يكون عنده pending long-polls كهلسة قديمة
    print("🔄 [Poll] Flushing stale polling sessions...")
    for attempt in range(5):
        try:
            bot.get_updates(offset=-1, timeout=1, long_polling_timeout=1)
            # لو وصل لهنا = نجح، مفيش conflict دلوقتي
            print(f"✅ [Poll] flush OK on attempt {attempt+1}")
            break
        except Exception as _e:
            if '409' in str(_e) or 'Conflict' in str(_e):
                print(f"⚠️ [Poll] flush {attempt+1}/5 blocked by 409 — retry...")
                time.sleep(2)
            else:
                print(f"⚠️ [Poll] flush {attempt+1}/5 OTHER: {_e}")
                break

    poll_backoff = 3
    while True:
        try:
            ensure_workers()
            # skip_pending=True + long_polling_timeout=20 = أقل احتمال للـ 409
            bot.polling(none_stop=True, timeout=20, skip_pending=True, long_polling_timeout=20)
            poll_backoff = 3
        except Exception as e:
            print(f"❌ [Poll] {e}")
            if '409' in str(e) or 'Conflict' in str(e):
                print(f"⚠️ [Poll] CRITICAL: نسخة تانية بتـ polling بنفس الـ token BOT_TOKEN!")
                print(f"⚠️ [Poll] ═══════════════════════════════════════════")
                print(f"⚠️ [Poll] المشكلة مش في الكود — في بوت تاني بيعمل polling خارجنا.")
                print(f"⚠️ [Poll] الحل: اذهب لـ @BotFather احذف الـ webhook، او غيّر BOT_TOKEN.")
                print(f"⚠️ [Poll] الباكوف الحالي: {poll_backoff}s — هيرجع صح بعد ما النسخة التانية توقف.")
                print(f"⚠️ [Poll] ═══════════════════════════════════════════")
                poll_backoff = min(poll_backoff * 2, 60)
            time.sleep(poll_backoff)
