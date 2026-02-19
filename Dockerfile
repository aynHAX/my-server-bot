# استخدام الصورة الرسمية من مايكروسوفت (جاهزة بكل مكتبات المتصفحات ونظام لينكس)
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

WORKDIR /app

# نسخ وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# أمر تشغيل البوت
CMD ["python", "bot.py"]
