FROM python:3.11-slim

WORKDIR /app

# تثبيت الشاشة الوهمية، متصفح Chromium، الدرايفر، والخطوط الأساسية لعمل الصفحات
RUN apt-get update && apt-get install -y \
    curl gnupg unzip wget xvfb \
    chromium chromium-driver \
    fonts-liberation libnss3 libgconf-2-4 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
