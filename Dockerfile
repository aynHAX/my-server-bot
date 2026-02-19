FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# 1. تثبيت برنامج الشاشة الوهمية (Xvfb)
RUN apt-get update && apt-get install -y xvfb

# 2. نسخ وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. نسخ ملف التشغيل وباقي الملفات
COPY start.sh .
COPY . .

# 4. إعطاء صلاحية التشغيل للملف والبدء
RUN chmod +x start.sh
CMD ["./start.sh"]
