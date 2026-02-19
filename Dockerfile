FROM python:3.11-slim

WORKDIR /app

# إضافة xvfb لإنشاء شاشة وهمية
RUN apt-get update && apt-get install -y curl gnupg unzip wget xvfb

RUN curl -fsSLo /usr/share/keyrings/brave-browser-archive-keyring.gpg https://brave-browser-apt-release.s3.brave.com/brave-browser-archive-keyring.gpg
RUN echo "deb [signed-by=/usr/share/keyrings/brave-browser-archive-keyring.gpg] https://brave-browser-apt-release.s3.brave.com/ stable main"|tee /etc/apt/sources.list.d/brave-browser-release.list

RUN apt-get update && apt-get install -y brave-browser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
