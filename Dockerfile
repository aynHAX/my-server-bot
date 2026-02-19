FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# 1. تثبيت برنامج الشاشة الوهمية (Xvfb)
RUN apt-get update && apt-get install -y xvfb

# 2. نسخ وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. نسخ باقي ملفات المشروع
COPY . .

# 4. السحر هنا: تشغيل البوت داخل الشاشة الوهمية ليعمل المتصفح كأنه في حاسوب حقيقي
CMD ["xvfb-run", "--auto-servernum", "--server-args=-screen 0 1920x1080x24", "python", "bot.py"]
