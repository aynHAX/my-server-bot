FROM python:3.11-slim

WORKDIR /app

# تثبيت الأدوات الأساسية المطلوبة لتحميل Brave
RUN apt-get update && apt-get install -y curl gnupg unzip wget

# إضافة مفتاح ومستودع متصفح Brave الرسمي
RUN curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main"|tee /etc/apt/sources.list.d/brave-browser-release.list

# تثبيت متصفح Brave
RUN apt-get update && apt-get install -y brave-browser

# نسخ وتثبيت مكتبات بايثون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات البوت
COPY . .

CMD ["python", "main.py"]
