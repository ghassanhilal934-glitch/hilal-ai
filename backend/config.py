# -*- coding: utf-8 -*-
"""إعدادات Hilal AI — تُقرأ من المتغيرات أو ملف .env"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent
OUTPUT_DIR = BASE_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)
ENV_FILE = BASE_DIR / ".env"


def load_dotenv(path: Path | None = None) -> None:
    path = path or ENV_FILE
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv()


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_int(name: str, default: int) -> int:
    try:
        return int(env(name, str(default)))
    except ValueError:
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(env(name, str(default)))
    except ValueError:
        return default


_WEAK_SECRETS = {
    "",
    "secret",
    "changeme",
    "change-me",
    "hilal-ai-change-this-secret",
    "change-this-to-a-long-random-secret",
}


def _persist_secret(secret: str) -> None:
    """يكتب المفتاح في .env إذا كان الملف قابلاً للكتابة."""
    try:
        lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
        replaced = False
        for index, line in enumerate(lines):
            if line.strip().startswith("SECRET_KEY="):
                lines[index] = f"SECRET_KEY={secret}"
                replaced = True
                break
        if not replaced:
            lines.append(f"SECRET_KEY={secret}")
        ENV_FILE.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    except OSError:
        # على HuggingFace Spaces تُحقن الأسرار كمتغيرات بيئة； نكتفي بالقيمة المؤقتة
        pass


def ensure_secret_key() -> str:
    key = env("SECRET_KEY", "").strip()
    if key.lower() in _WEAK_SECRETS or len(key) < 32:
        key = secrets.token_urlsafe(64)
        os.environ["SECRET_KEY"] = key
        _persist_secret(key)
    return key


SECRET_KEY = ensure_secret_key()

# البيئة: development فقط تسمح بنقاط التوثيق المفتوحة
ENVIRONMENT = env("ENVIRONMENT", "production").strip().lower()
IS_PRODUCTION = ENVIRONMENT not in {"development", "dev", "local"}

# JWT
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = env_int("JWT_EXPIRE_MINUTES", 1440)
JWT_ISSUER = "hilal-ai"

# مكافحة التلاعب بالمدفوعات
PAYMENT_MAX_FAILURES = env_int("PAYMENT_MAX_FAILURES", 5)
PAYMENT_BLOCK_MINUTES = env_int("PAYMENT_BLOCK_MINUTES", 15)

# لوحة المدير
ADMIN_PASSWORD = env("ADMIN_PASSWORD", "").strip()
ADMIN_SESSION_MINUTES = env_int("ADMIN_SESSION_MINUTES", 480)

# الإعلانات مقابل النقاط
ADMOB_REWARDED_ID = env(
    "ADMOB_REWARDED_ID", "ca-app-pub-3940256099942544/5224354917"
).strip()
WEB_AD_DIRECT_LINK = env("WEB_AD_DIRECT_LINK", "https://example.com").strip()
AD_REWARD_POINTS = 0.5
AD_DAILY_LIMIT = env_int("AD_DAILY_LIMIT", 5)
AD_MIN_SECONDS = env_int("AD_MIN_SECONDS", 25)
AD_TICKET_TTL_SECONDS = env_int("AD_TICKET_TTL_SECONDS", 300)
AD_TICKET_TYPE = "ad_reward"

# حدود الرفع
MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 5)
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_B64_CHARS = int(MAX_UPLOAD_BYTES * 1.4) + 2048

# Rate limits
RATE_LIMIT_GLOBAL = env("RATE_LIMIT_GLOBAL", "120/minute")
RATE_LIMIT_AUTH = env("RATE_LIMIT_AUTH", "10/minute")
RATE_LIMIT_CHAT = env("RATE_LIMIT_CHAT", "30/minute")
RATE_LIMIT_HEAVY = env("RATE_LIMIT_HEAVY", "5/minute")

BINANCE_BEP20_ADDRESS = env("BINANCE_BEP20_ADDRESS", "").strip()
USDT_CONTRACT = env(
    "USDT_CONTRACT", "0x55d398326f99059fF775485246999027B3197955"
).strip()
BSC_RPC_URLS = [
    u.strip()
    for u in env(
        "BSC_RPC_URLS",
        "https://bsc-dataseed.binance.org,https://bsc-rpc.publicnode.com",
    ).split(",")
    if u.strip()
]
MIN_CONFIRMATIONS = env_int("MIN_CONFIRMATIONS", 1)
APP_BASE_URL = env(
    "APP_BASE_URL", "https://hilal-ai-8s01.onrender.com"
).rstrip("/")
HF_TOKEN = env("HF_TOKEN", "").strip() or None

# حساسية الخطة: النطاقات الافتراضية للعمل المحلي؛ app.py يسمح بكل النطاقات صراحةً
_default_origins = [
    APP_BASE_URL,
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://192.168.1.104:8000",
    "https://localhost",
    "http://localhost",
    "capacitor://localhost",
    "ionic://localhost",
]
CORS_ORIGINS = sorted(
    {o.rstrip("/") for o in env("CORS_ORIGINS", "").split(",") if o.strip()}
    or set(_default_origins)
)

# مساعد الدراسة مجاني 100% بلا حدود، والمحادثة العادية مجانية حتى 30 رسالة يومياً
FREE_CHAT_DAILY_LIMIT = env_int("FREE_CHAT_DAILY_LIMIT", 30)
CHAT_WINDOW_SECONDS = 24 * 60 * 60
POINTS_CHAT = 0                       # محادثة مجانية للمشتركين و30 رسالة/يوم للباقين
POINTS_IMAGE = env_int("POINTS_IMAGE", 1)
POINTS_AUDIO = env_int("POINTS_AUDIO", 1)
POINTS_VIDEO = env_int("POINTS_VIDEO", 2)
POINTS_STUDIO = env_float("POINTS_STUDIO", 0.5)   # استوديو التصميم وتعديل الصور

POLLINATIONS_TEXT_URL = "https://text.pollinations.ai/"
POLLINATIONS_IMAGE_URL = "https://image.pollinations.ai/prompt/"
MUSE_SPACE = "trymonolith/MuseTalk"
VTON_SPACE = "WeShopAI/WeShopAI-Virtual-Try-On"

PACKAGES = {
    "starter": {
        "name": "الباقة الأساسية",
        "name_en": "Starter",
        "price_usdt": 5.0,
        "points": 10,
    },
    "pro": {
        "name": "الباقة الاحترافية",
        "name_en": "Pro",
        "price_usdt": 12.0,
        "points": 30,
    },
    "vip": {
        "name": "باقة صناع المحتوى",
        "name_en": "VIP",
        "price_usdt": 25.0,
        "points": 80,
    },
}

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
