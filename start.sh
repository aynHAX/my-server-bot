#!/bin/bash

# 1. تشغيل الشاشة الوهمية في الخلفية
echo "Starting Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 &

# 2. تحديد المتغير ليعرف المتصفح أي شاشة يستخدم
export DISPLAY=:99

# 3. تشغيل البوت
echo "Starting Bot..."
python bot.py
