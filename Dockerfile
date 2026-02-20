FROM python:3.11-slim

WORKDIR /app

# تثبيت الشاشة الوهمية + متصفح Chromium والدرايفر المطابق له تماماً
RUN apt-get update && apt-get install -y \
    curl gnupg unzip wget xvfb \
    chromium chromium-driver

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
