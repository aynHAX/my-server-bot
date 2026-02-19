FROM mcr.microsoft.com/playwright/python:v1.42.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# تثبيت برنامج الشاشة الوهمية (السلاح السري!)
RUN apt-get update && apt-get install -y xvfb

COPY . .

# إجبار بايثون على العمل داخل الشاشة الوهمية كأنه جهاز حقيقي
CMD ["xvfb-run", "-a", "python", "main.py"]
