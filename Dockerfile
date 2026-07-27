FROM python:3.11-slim

# ── تثبيت التبعيات في طبقة واحدة مع خطوط إضافية ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    xvfb \
    xauth \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# ── اطبع نسخة chromium المثبتة (لل debug وللـ version_main على Railway) ──
RUN chromium --version || true \
    && chromedriver --version || true

WORKDIR /app

# ── تثبيت مكتبات Python (طبقة مخزنة مؤقتاً) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─ـ اطبع نسخة undetected-chromedriver بعد التثبيت (لل debug) ──
RUN python -c "import undetected_chromedriver as uc, selenium; print('uc', uc.__version__ if hasattr(uc,'__version__') else '?', 'selenium', selenium.__version__)" || true

COPY . .

# ── دليل بروفائل لازم يكون قابل للكتابة + HOME صريح (uc بيكتب patcher هنا) ──
ENV HOME=/app \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp
RUN mkdir -p /tmp /root/.local/share/undetected_chromedriver && chmod -R 777 /tmp

EXPOSE 8080

# ── فحص صحة داخلي ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# ── -u لإخراج فوري بدون تخزين مؤقت ──
CMD ["python", "-u", "main.py"]
