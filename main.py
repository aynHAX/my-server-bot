import os
import threading
import asyncio
import random
import re
from flask import Flask
from telegram import Update, InputMediaPhoto
from telegram.error import BadRequest, RetryAfter
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from playwright.async_api import async_playwright
import playwright_stealth as p_stealth
from pyvirtualdisplay import Display

# --- إعداد Flask لـ Koyeb ---
app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running perfectly on Koyeb!"

def run_flask():
    port = int(os.environ.get("PORT", 8000)) # 👈 منفذ Koyeb الافتراضي
    app.run(host='0.0.0.0', port=port)

active_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if len(update.message.text.split()) < 2:
        await update.message.reply_text("❌ أرسل الرابط بعد الأمر...")
        return
    
    raw_url = update.message.text.split(maxsplit=1)[1].strip()

    if chat_id in active_sessions and active_sessions[chat_id].get('is_running'):
        await update.message.reply_text("⚠️ لديك بث يعمل بالفعل، قم بإيقافه أولاً بـ /stop")
        return

    active_sessions[chat_id] = {'is_running': True, 'step': 'accept_terms', 'browser_instance': None, 'display': None}
    await update.message.reply_text("🎭 جاري فتح الجلسة المحمية (Xvfb) على Koyeb...")

    disp = Display(visible=0, size=(1280, 800))
    disp.start()
    active_sessions[chat_id]['display'] = disp

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False, 
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-blink-features=AutomationControlled',
                    '--start-maximized',
                    '--disable-infobars',
                    '--disable-extensions',
                    '--disable-background-networking',
                    '--mute-audio'
                ]
            )
            active_sessions[chat_id]['browser_instance'] = browser
            
            browser_context = await browser.new_context(
                no_viewport=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York'
            )
            
            page = await browser_context.new_page()
            
            try: await p_stealth.stealth_async(page)
            except: await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            await page.goto(raw_url, timeout=120000)
            await asyncio.sleep(4) # انتظار لتخطي الشاشة البيضاء (SSO)
            
            screenshot_bytes = await page.screenshot(type='jpeg', quality=60)
            live_message = await context.bot.send_photo(
                chat_id=chat_id, 
                photo=screenshot_bytes, 
                caption="🔴 بث مباشر\n⏳ جاري تنفيذ المهام..."
            )

            while active_sessions.get(chat_id, {}).get('is_running'):
                current_step = active_sessions[chat_id].get('step')

                try:
                    if current_step == 'accept_terms':
                        understand_btn = page.locator("text='I understand'").first
                        if await understand_btn.is_visible(timeout=500):
                            await asyncio.sleep(random.uniform(1.0, 2.0)) 
                            await understand_btn.click(force=True)
                            active_sessions[chat_id]['step'] = 'wait_for_console'
                        else:
                            for text in ["Ik begrijp het", "Accept all", "I agree", "Agree", "Confirm"]:
                                btn = page.get_by_text(text, exact=False).first
                                if await btn.is_visible(timeout=200):
                                    await btn.click(force=True)
                                    active_sessions[chat_id]['step'] = 'wait_for_console'
                                    break

                    elif current_step == 'wait_for_console':
                        if "console.cloud.google.com" in page.url or await page.get_by_text("Cloud overview").is_visible(timeout=500):
                            page_text = await page.content()
                            match = re.search(r'qwiklabs-gcp-[a-zA-Z0-9\-]+', page_text)
                            project_id = match.group(0) if match else ""
                            shell_url = f"https://console.cloud.google.com/cloudshell?project={project_id}"
                            await page.goto(shell_url, timeout=120000)
                            active_sessions[chat_id]['step'] = 'start_cloud_shell'

                    elif current_step == 'start_cloud_shell':
                        start_btn = page.get_by_text("Start Cloud Shell", exact=False).first
                        if await start_btn.is_visible(timeout=500):
                            checkbox = page.get_by_role("checkbox").first
                            if await checkbox.is_visible(): await checkbox.check(force=True)
                            await asyncio.sleep(1)
                            await start_btn.click(force=True)
                            active_sessions[chat_id]['step'] = 'wait_for_authorize'

                    elif current_step == 'wait_for_authorize':
                        auth_btn = page.get_by_text("Authorize", exact=True).first
                        if await auth_btn.is_visible(timeout=500):
                            await auth_btn.click(force=True)
                            active_sessions[chat_id]['step'] = 'done'
                            await context.bot.send_message(chat_id=chat_id, text="🎉 تم تجهيز التيرمينال بنجاح!")
                except Exception:
                    pass

                await asyncio.sleep(3)
                if not active_sessions.get(chat_id, {}).get('is_running'): break
                
                try:
                    new_screenshot = await page.screenshot(type='jpeg', quality=50)
                    await context.bot.edit_message_media(
                        chat_id=chat_id, 
                        message_id=live_message.message_id, 
                        media=InputMediaPhoto(new_screenshot)
                    )
                except BadRequest as e:
                    if "Message is not modified" in str(e): continue
                except RetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                except Exception: 
                    continue

            if browser: await browser.close()
            
    except Exception as e:
        error_msg = str(e)
        if "Target closed" not in error_msg:
            await update.message.reply_text(f"❌ خطأ تقني: {error_msg}")
            
    finally:
        if chat_id in active_sessions:
            d = active_sessions[chat_id].get('display')
            if d: d.stop() 
            del active_sessions[chat_id]

async def stop_stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in active_sessions:
        active_sessions[chat_id]['is_running'] = False
        browser = active_sessions[chat_id].get('browser_instance')
        if browser:
            try: await browser.close()
            except: pass
        await update.message.reply_text("⏹️ تم إنهاء البث.")
    else:
        await update.message.reply_text("⚠️ لا يوجد بث نشط لإيقافه.")

if __name__ == '__main__':
    TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if TOKEN:
        threading.Thread(target=run_flask, daemon=True).start()
        application = ApplicationBuilder().token(TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("stop", stop_stream))
        
        print("🚀 البوت يعمل الآن على منصة Koyeb...", flush=True)
        application.run_polling(drop_pending_updates=True)
    else:
        print("❌ خطأ: التوكن غير موجود! تأكد من إضافته في إعدادات Koyeb.", flush=True)
