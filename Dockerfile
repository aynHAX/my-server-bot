FROM python:3.10-slim

WORKDIR /app

# نسخ ملف المتطلبات وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت متصفح Chromium والملفات الأساسية لتشغيله
RUN playwright install chromium
RUN playwright install-deps chromium

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل السكربت
CMD ["python", "main.py"]
