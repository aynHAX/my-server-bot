# استخدام نسخة بايثون خفيفة
FROM python:3.11-slim

# تحديث النظام وتثبيت متصفح Chromium والشاشة الوهمية والخطوط
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    xvfb \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
