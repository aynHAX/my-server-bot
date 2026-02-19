# استخدام نسخة بايثون خفيفة لتسريع البناء وتقليل الحجم
FROM python:3.11-slim

# تحديد مجلد العمل داخل الحاوية
WORKDIR /app

# نسخ ملف المكتبات أولاً (للاستفادة من ميزة التخزين المؤقت في Docker)
COPY requirements.txt .

# تثبيت المكتبات المطلوبة
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع إلى الحاوية
COPY . .

# الأمر الذي سيتم تنفيذه لتشغيل البوت
CMD ["python", "main.py"]
