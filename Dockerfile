FROM python:3.11-slim

WORKDIR /app

# قمنا بإزالة libgconf-2-4 من هنا لأن النظام لم يعد يحتاجها
RUN apt-get update && apt-get install -y \
    curl gnupg unzip wget xvfb \
    chromium chromium-driver \
    fonts-liberation libnss3 libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
