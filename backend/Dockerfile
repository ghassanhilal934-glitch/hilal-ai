# syntax=docker/dockerfile:1
# Hilal AI — FastAPI backend, جاهز للنشر على Render.com (Free Web Service)
FROM python:3.11-slim

# Render يحقن PORT وقت التشغيل؛ 10000 هو الافتراضي المحلي لدينا.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=10000

WORKDIR /app

# ffmpeg: محركات الصوت/الفيديو والاستوديو والعلامة المائية.
# build-essential يوفّر gcc ومكتبات التطوير اللازمة لبناء حزم مثل bcrypt من المصدر.
# fonts-dejavu-core يوفّر خط drawtext الذي تستخدمه العلامة المائية.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        ffmpeg \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# سياق البناء على Render قد يكون جذر المستودع أو مجلد backend نفسه؛ ندعم الاثنين.
COPY . /src
RUN set -eu; \
    REQ="$(find /src -maxdepth 3 -type f -name requirements.txt -print -quit)"; \
    [ -n "$REQ" ] || { echo "requirements.txt غير موجود في سياق البناء" >&2; exit 1; }; \
    echo "تثبيت المتطلبات من: $REQ"; \
    python -m pip install --no-cache-dir --upgrade pip setuptools wheel; \
    python -m pip install --no-cache-dir -r "$REQ"; \
    python -m pip install --no-cache-dir bcrypt; \
    python -m pip install --no-cache-dir --no-deps \
        gradio_client==2.7.2 \
        huggingface_hub==0.24.7 \
        httpx==0.28.1 \
        'httpcore>=1.0' \
        'h11>=0.16' \
        'anyio>=4.0' \
        'sniffio>=1.3' \
        'fsspec>=2024.1' \
        'requests>=2.31' \
        'tqdm>=4.66' \
        'pyyaml>=6.0' \
        'click>=8.1' \
        'filelock>=3.13' \
        'packaging>=23' \
        'websocket-client>=1.7' \
        'websockets>=12'

# ضع ملفات الباكند مباشرة في /app حتى يعمل `uvicorn app:app`،
# وانسخ واجهة الويب إلى الموقع الذي يتوقعه app.py إن كانت ضمن السياق.
RUN set -eu; \
    if [ -f /src/backend/app.py ]; then \
        cp -a /src/backend/. /app/.; \
        if [ -d /src/web_and_android/web ]; then \
            mkdir -p /web_and_android; \
            cp -a /src/web_and_android/web /web_and_android/web; \
        fi; \
    else \
        cp -a /src/. /app/.; \
    fi; \
    mkdir -p /app/outputs; \
    rm -rf /src

EXPOSE $PORT

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '10000') + '/api/health', timeout=5).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port \"${PORT:-10000}\""]
