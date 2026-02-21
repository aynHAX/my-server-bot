# استخدام نسخة بايثون خفيفة
FROM python:3.11-slim

# تحديث النظام وتثبيت متصفح Chromium ليتمكن البوت من استخدامه
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# تحديد مجلد العمل داخل السيرفر
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات البوت
COPY . .

# أمر تشغيل البوت
CMD ["python", "main.py"]
