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

# ── ترقيع chromedriver لتمويه cdc_ strings (يدويًا، بديل لـ undetected-chromedriver) ──
# chromedriver بسيط — فيه سلاسل cdc_ بش كل ريلاي بيكتشفها جوجل. نبدّلها بـ xxx_.
# بده سطر Python واحد يستبدل البايتات في الـ binary ما بين أي تشغيل.
RUN python - <<'EOF'
import re, pathlib, shutil, sys
for driver_path in ['/usr/bin/chromedriver', '/usr/lib/chromium/chromedriver']:
    p = pathlib.Path(driver_path)
    if not p.exists():
        continue
    try:
        data = bytearray(p.read_bytes())
        # pattern cdc_ followed by alpha — typical chromedriver detection strings
        new = re.sub(rb'cdc_[a-zA-Z0-9_]{3,20}', b'xxx_' + b'_'*20, data)
        # trim the placeholder to original length per-match
        # simplest: just replace 'cdc_' occurrences with 'xxx_'
        patched = data.replace(b'cdc_', b'xxx_')
        if patched != data:
            shutil.copy2(p, str(p)+'.bak')
            p.write_bytes(patched)
            # keep executable bits
            import os, stat
            st = os.stat(p)
            os.chmod(p, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"✅ [patch] patched {p} ({len(data)} bytes)")
        else:
            print(f"ℹ️ [patch] no cdc_ found in {p} (already patched?)")
    except Exception as e:
        print(f"⚠️ [patch] {p}: {e}")
EOF
RUN chromedriver --version || true

WORKDIR /app

# ── تثبيت مكتبات Python (طبقة مخزنة مؤقتاً) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─ـ اطبع نسخة selenium بعد التثبيت (لل debug) ──
RUN python -c "import selenium; print('selenium', selenium.__version__)" || true

COPY . .

# ── دليل بروفائل لازم يكون قابل للكتابة ──
ENV HOME=/app \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp
RUN mkdir -p /tmp && chmod -R 777 /tmp

EXPOSE 8080

# ── فحص صحة داخلي ──
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# ── -u لإخراج فوري بدون تخزين مؤقت ──
CMD ["python", "-u", "main.py"]
