# استخدام صورة Playwright الرسمية
FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

# تعيين مجلد العمل
WORKDIR /app

# نسخ ملف المتطلبات وتثبيت المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل البوت
CMD ["python", "main.py"]
