# استخدام نسخة بايثون النظيفة
FROM python:3.10

# تثبيت الشاشة الوهمية
RUN apt-get update && apt-get install -y xvfb

WORKDIR /app

# تنصيب المكتبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تنصيب متصفح كروم مع المتطلبات الأساسية
RUN playwright install --with-deps chromium

# نسخ باقي الملفات
COPY . .

# تشغيل البوت (حرف u لإظهار السجلات فوراً)
CMD ["python", "-u", "main.py"]
