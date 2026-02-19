FROM python:3.11

WORKDIR /app

# نسخ ملف المكتبات وتثبيتها
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح كروم مع ملفات نظام لينكس الأساسية لتشغيله
RUN playwright install --with-deps chromium

# نسخ باقي ملفات البوت
COPY . .

# أمر تشغيل البوت
CMD ["python", "bot.py"]
