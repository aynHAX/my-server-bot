import os
import telebot
import threading
import time
import signal
import sys
from telebot.types import InputMediaPhoto
from flask import Flask
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from telebot.apihelper import ApiTelegramException
from playwright_stealth import stealth_sync

# --- الإعدادات ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("خطأ: يرجى التأكد من إضافة BOT_TOKEN في Environment Variables")
    sys.exit(1)

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# قفل لمنع تشغيل أكثر من متصفح في نفس الوقت (لحماية الرام)
browser_lock = threading.Lock()

# --- خادم Flask للبقاء مستيقظاً (Health Check) ---
@app.route('/')
def health_check():
    return "Bot is running and optimized!", 200

def run_flask():
    # المنفذ 8000 هو القياسي في Koyeb
    app.run(host="0.0.0.0", port=int(os.environ.get('PORT', 8000)), debug=False, use_reloader=False)

# --- أوامر البوت ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "مرحباً! 🧙‍♂️\nأرسل لي رابط Google Skills وسأقوم بمعالجته بطريقة آمنة ومحسّنة.\n\nملاحظة: سأقوم بمحاكاة متصفح حقيقي لتجاوز الحماية.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    text = message.text.strip()
    
    # التحقق من الرابط
    if "skills.google" not in text:
        bot.reply_to(message, "⚠️ الرجاء إرسال رابط صحيح يخص منصة Google Skills 🔗")
        return
        
    # التحقق من انشغال البوت
    if browser_lock.locked():
        bot.reply_to(message, "⏳ المعالج مشغول حالياً بطلب آخر. يرجى الانتظار لحظات...")
        return

    with browser_lock:
        wait_msg = bot.reply_to(message, "🚀 جاري التشغيل بالوضع الخفي المحسّن (Stealth Mode)...\n⏳ قد يستغرق هذا بضع ثوانٍ.")
        screenshot_path = f"screenshot_{message.chat.id}.jpg"
        browser = None
        context = None
        
        try:
            with sync_playwright() as p:
                # --- إعدادات التشغيل المحسنة للسيرفرات ---
                # يجب استخدام headless=True لأن السيرفرات لا تحتوي على شاشة (Display)
                browser = p.chromium.launch(
                    headless=True, 
                    args=[
                        "--no-sandbox", 
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage", # مهم لمنع مشاكل الذاكرة
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled", # إخفاء أنك بوت
                        "--window-size=1280,720"
                    ]
                )
                
                # تظاهر بمتصفح حقيقي
                real_user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
                
                context = browser.new_context(
                    viewport={'width': 1280, 'height': 720},
                    user_agent=real_user_agent,
                    locale="en-US",
                    color_scheme='light' # تثبيت المظهر لتجنب المشاكل
                )
                
                # سكريبتات إضافية لإخفاء آثار البوت
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5];
                    });
                """)
                
                page = context.new_page()
                stealth_sync(page) # تطبيق المكتبة السحرية
                
                # --- مرحلة الإحماء (Warm-up) ---
                try:
                    # زيارة جوجل لبناء ملفات تعريف الارتباط
                    page.goto("https://www.google.com", timeout=30000)
                    time.sleep(1.5) 
                except Exception:
                    # إذا فشل الإحماء نستمر، ليس أمراً حرجاً
                    pass
                
                # --- الذهاب للرابط المستهدف ---
                page.goto(text, timeout=60000)
                
                # انتظار تحميل العناصر قليلاً
                time.sleep(2)
                
                # أخذ اللقطة الأولى
                page.screenshot(path=screenshot_path, type="jpeg", quality=50)
                
                with open(screenshot_path, 'rb') as photo:
                    stream_msg = bot.send_photo(message.chat.id, photo, caption="🔴 بث مباشر (الوضع: سري وآمل)...")
                    
                try:
                    bot.delete_message(message.chat.id, wait_msg.message_id)
                except Exception:
                    pass
                
                # --- حلقة البث المباشر ---
                # تقليل عدد التحديثات لتجنب الحظر من تيليجرام
                for i in range(10): 
                    time.sleep(3) 
                    
                    # تحقق مما إذا كان المتصفح لا يزال مفتوحاً
                    if not page.is_closed():
                        page.screenshot(path=screenshot_path, type="jpeg", quality=50)
                        
                        try:
                            with open(screenshot_path, 'rb') as photo:
                                media = InputMediaPhoto(photo, caption=f"🔴 بث مباشر... ({i+1}/10)")
                                bot.edit_message_media(chat_id=message.chat.id, message_id=stream_msg.message_id, media=media)
                        except ApiTelegramException as e:
                            if "message is not modified" in str(e):
                                continue
                            elif "message to edit not found" in str(e):
                                break
                            else:
                                print(f"Telegram Error: {e}")
                    else:
                        break
                            
                try:
                    bot.edit_message_caption(chat_id=message.chat.id, message_id=stream_msg.message_id, caption="✅ انتهى البث المباشر بنجاح.")
                except Exception:
                    pass
        
        except PlaywrightTimeoutError:
            try:
                bot.edit_message_text("⏰ خطأ: انتهى وقت الانتظار. الموقع يستغرق وقتاً طويلاً للتحميل.", message.chat.id, wait_msg.message_id)
            except Exception:
                bot.send_message(message.chat.id, "⏰ خطأ: انتهى وقت الانتظار.")
                
        except Exception as e:
            error_msg = f"❌ حدث خطأ غير متوقع:\n<code>{str(e)[:500]}</code>"
            try:
                bot.edit_message_text(error_msg, message.chat.id, wait_msg.message_id, parse_mode='HTML')
            except Exception:
                bot.send_message(message.chat.id, error_msg, parse_mode='HTML')
            
        finally:
            # --- تنظيف الموارد (أهم جزء) ---
            try:
                if context: context.close()
                if browser: browser.close()
            except Exception:
                pass
                
            if os.path.exists(screenshot_path):
                try:
                    os.remove(screenshot_path)
                except Exception:
                    pass

# --- إدارة إيقاف البرنامج ---
def signal_handler(signum, frame):
    print("Bot is shutting down...")
    bot.stop_polling()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    # تشغيل Flask في خيط منفصل
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print("Bot started polling...")
    # استخدام infinity_polling لإعادة التشغيل التلقائي عند الأخطاء
    bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)
