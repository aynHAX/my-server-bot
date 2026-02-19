import asyncio
import os
import random
import re
from telegram import Update, InputMediaPhoto
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright
import playwright_stealth as p_stealth

from flask import Flask
import threading

# -----------------------------------------
# 1. إعداد خادم الويب الوهمي لإرضاء Koyeb
# -----------------------------------------
app = Flask(__name__)

@app.route('/')
def index():
    return "Playwright Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get('PORT', 8000))
    app.run(host="0.0.0.0", port=port)

# -----------------------------------------
# 2. إعداد بوت التيليغرام ومتغيرات البيئة
# -----------------------------------------
TOKEN = os.environ.get('BOT_TOKEN') # جلب التوكن من إعدادات Koyeb لحمايته
if not TOKEN:
    raise ValueError("لم يتم العثور على BOT_TOKEN. تأكد من إضافته في إعدادات Koyeb.")

active_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("❌ أرسل الرابط بعد الأمر...\nمثال: /start https://google.com")
        return

    raw_url = context.args[0]
    active_sessions[chat_id] = {'is_running': True, 'step': 'accept_terms'}
    
    await update.message.reply_text("🎭 جاري محاكاة 'سلوك بشري' بوضع التصفح النظيف (Incognito)...")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized',
                    '--disable-infobars',
                    '--no-sandbox', 
                    '--disable-setuid-sandbox' 
                ]
            )
            
            browser_context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            page = await browser_context.new_page()
            
            try:
                if hasattr(p_stealth, 'stealth_async'):
                    await p_stealth.stealth_async(page)
                elif hasattr(p_stealth, 'stealth'):
                    await p_stealth.stealth(page)
                else:
                    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            except Exception:
                pass

            await page.mouse.move(random.randint(100, 400), random.randint(100, 400))
            await page.goto(raw_url, timeout=120000, wait_until="load")
            
            screenshot_bytes = await page.screenshot()
            live_message = await context.bot.send_photo(
                chat_id=chat_id, 
                photo=screenshot_bytes, 
                caption="🔴 بث مباشر (وضع التخفي)\nأرسل /stop للإنهاء\n⏳ جاري تنفيذ المهام التسلسلية..."
            )

            while active_sessions.get(chat_id, {}).get('is_running'):
                
                current_step = active_sessions.get(chat_id, {}).get('step')

                # 📌 المرحلة 1: قبول شروط جوجل
                if current_step == 'accept_terms':
                    try:
                        button_texts = ["I understand", "Ik begrijp het", "Accept all", "I agree", "Agree", "Confirm"]
                        for text in button_texts:
                            btn = page.get_by_text(text, exact=False).first
                            if await btn.is_visible(timeout=500):
                                print(f"✅ ظهر زر '{text}'! جاري الضغط...")
                                await asyncio.sleep(1)
                                await btn.click(force=True) 
                                active_sessions[chat_id]['step'] = 'wait_for_console'
                                break 
                    except Exception:
                        pass

                # 📌 المرحلة 2: انتظار لوحة التحكم + استخراج الـ Project ID
                elif current_step == 'wait_for_console':
                    try:
                        is_ready = False
                        check_texts = ["Welcome student", "Agree and continue", "Create and manage", "Cloud overview"]
                        
                        for text in check_texts:
                            if await page.get_by_text(text, exact=False).first.is_visible(timeout=200):
                                is_ready = True
                                break
                        
                        if is_ready or "console.cloud.google.com" in page.url:
                            print("✅ تم رصد لوحة تحكم Google Cloud! جاري استخراج Project ID...")
                            await asyncio.sleep(2)
                            
                            page_text = await page.content()
                            match = re.search(r'qwiklabs-gcp-[a-zA-Z0-9\-]+', page_text)
                            
                            if match:
                                project_id = match.group(0)
                                print(f"🎯 تم التقاط المشروع: {project_id}")
                                shell_url = f"https://shell.cloud.google.com/?project={project_id}"
                            else:
                                print("⚠️ لم يتم العثور على Project ID، سيتم فتح الرابط الافتراضي.")
                                shell_url = "https://shell.cloud.google.com/"
                                
                            await page.goto(shell_url, timeout=120000)
                            active_sessions[chat_id]['step'] = 'start_cloud_shell'
                    except Exception:
                        pass

                # 📌 المرحلة 3: الموافقة على شروط Cloud Shell
                elif current_step == 'start_cloud_shell':
                    try:
                        start_btn = page.get_by_text("Start Cloud Shell", exact=False).first
                        if await start_btn.is_visible(timeout=500):
                            print("✅ ظهرت نافذة شروط Cloud Shell! جاري الموافقة...")
                            
                            checkbox = page.get_by_role("checkbox").first
                            if await checkbox.is_visible(timeout=1000):
                                await checkbox.check(force=True) 
                            else:
                                await page.locator('input[type="checkbox"]').first.click(force=True)
                            
                            await asyncio.sleep(1.5) 
                            await start_btn.click(force=True)
                            
                            active_sessions[chat_id]['step'] = 'wait_for_authorize'
                            
                        elif await page.get_by_text("Authorize", exact=True).first.is_visible(timeout=200):
                            active_sessions[chat_id]['step'] = 'wait_for_authorize'
                    except Exception:
                        pass

                # 📌 المرحلة 4: اصطياد زر Authorize
                elif current_step == 'wait_for_authorize':
                    try:
                        auth_btn = page.get_by_text("Authorize", exact=True).first
                        if await auth_btn.is_visible(timeout=500):
                            print("✅ ظهر زر 'Authorize'! جاري الضغط...")
                            await asyncio.sleep(1)
                            await auth_btn.click(force=True)
                            
                            active_sessions[chat_id]['step'] = 'done'
                            print("🎉 تم الانتهاء! التيرمينال جاهز ومتصل بالمشروع الصحيح.")
                            await context.bot.send_message(chat_id=chat_id, text="🎉 تم تجهيز التيرمينال بنجاح وتم ربطه بمشروعك!")
                    except Exception:
                        pass

                await asyncio.sleep(3) 

                if not active_sessions.get(chat_id, {}).get('is_running'): 
                    break
                
                try:
                    new_screenshot = await page.screenshot()
                    await context.bot.edit_message_media(
                        chat_id=chat_id,
                        message_id=live_message.message_id,
                        media=InputMediaPhoto(new_screenshot)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e):
                        continue
                except Exception: 
                    continue

            await browser.close()
            await context.bot.send_message(chat_id=chat_id, text="⏹️ تم إغلاق الجلسة بنجاح.")
            
    except Exception as e:
        # هنا تم قص رسالة الخطأ لتجنب مشكلة (Message is too long) في تيليغرام
        error_message = str(e)[:500] 
        await update.message.reply_text(f"❌ حدث خطأ، التفاصيل (مختصرة):\n{error_message}")
    finally:
        if chat_id in active_sessions: 
            del active_sessions[chat_id]

async def stop_stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_sessions:
        active_sessions[chat_id]['is_running'] = False
        await update.message.reply_text("⏳ جاري الإغلاق...")

if __name__ == '__main__':
    print("🚀 جاري تشغيل خادم الويب والبوت...")
    
    # تشغيل خادم الويب في مسار منفصل
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # تشغيل البوت
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop_stream))
    application.run_polling()
