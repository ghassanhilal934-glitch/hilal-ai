# -*- coding: utf-8 -*-
"""Hilal AI — FastAPI backend مع تحصين أمني Production-Grade."""
import base64
import hashlib
import re
import sys
import typing
import uuid
from pathlib import Path

# توافق مع Python 3.13 في Termux عند استخدام pydantic v1
if sys.version_info >= (3, 13):
    _forward_eval = typing.ForwardRef._evaluate

    def _patched_forward_eval(self, globalns, localns, *args, **kwargs):
        return _forward_eval(
            self, globalns, localns,
            args[0] if args else None,
            recursive_guard=kwargs.get("recursive_guard", set()),
        )

    typing.ForwardRef._evaluate = _patched_forward_eval

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

import admin
import auth
from config import (
    APP_BASE_URL,
    BINANCE_BEP20_ADDRESS,
    FREE_CHAT_DAILY_LIMIT,
    IS_PRODUCTION,
    MAX_B64_CHARS,
    MAX_UPLOAD_BYTES,
    OUTPUT_DIR,
    PACKAGES,
    POINTS_AUDIO,
    POINTS_CHAT,
    POINTS_IMAGE,
    POINTS_STUDIO,
    POINTS_VIDEO,
    RATE_LIMIT_AUTH,
    RATE_LIMIT_CHAT,
    RATE_LIMIT_GLOBAL,
    RATE_LIMIT_HEAVY,
)
from db import (
    chat_status,
    consume_free_chat,
    has_paid,
    init_db,
    refund_free_chat,
)
from engines import ads as ads_engine
from engines import audio as audio_engine
from engines import image as image_engine
from engines import studio as studio_engine
from engines import text as text_engine
from engines import video as video_engine
from payments import (
    PaymentError,
    check_attempt_block,
    clear_failed_attempts,
    record_failed_attempt,
    verify_payment,
)

# الواجهة الأمامية مُنسوخة داخل حزمة الباكند حتى تُخدم من نفس حاوية Render
WEB_DIR = Path(__file__).resolve().parent / "www"
if not WEB_DIR.is_dir():
    # توافق مع التشغيل المحلي القديم قبل نسخ الواجهة إلى backend/www
    WEB_DIR = Path(__file__).resolve().parent.parent / "web_and_android" / "web"

# في الإنتاج تُغلق نقاط التوثيق نهائياً
app = FastAPI(
    title="Hilal AI",
    version="1.1.0",
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url=None if IS_PRODUCTION else "/api/redoc",
    openapi_url=None if IS_PRODUCTION else "/api/openapi.json",
)


# ---------------------------------------------------------------------------
# Rate Limiting — مفتاح مركّب: عنوان IP + بصمة التوكن (أي مستخدم فعلي)
# ---------------------------------------------------------------------------
def rate_limit_key(request: Request) -> str:
    ip = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
    fingerprint = (
        hashlib.sha256(token.encode()).hexdigest()[:16] if token else "anon"
    )
    return f"{ip}:{fingerprint}"


limiter = Limiter(key_func=rate_limit_key, default_limits=[RATE_LIMIT_GLOBAL])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ---------------------------------------------------------------------------
# رؤوس الحماية
# ---------------------------------------------------------------------------
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
    )
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob:; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


# CORS مفتوح لكل النطاقات: الواجهة تُخدم من Render، والتطبيق من Capacitor،
# وقد تُفتح من نطاقات مخصصة أخرى، لذا نسمح بجميع المصادر صراحةً.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)


@app.on_event("startup")
def startup() -> None:
    init_db()


# ----------------------------- النماذج -------------------------------------
class RegisterIn(BaseModel):
    email: str
    password: str
    invite_code: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class ChatIn(BaseModel):
    prompt: str
    system: str | None = None


class StudioIn(BaseModel):
    prompt: str = ""
    mode: str = "design"        # design | edit
    image: str | None = None    # base64 صورة للتعديل


class ImageIn(BaseModel):
    prompt: str
    mode: str = "text"          # text | tryon
    image: str | None = None    # base64(person)
    style: str | None = None    # base64(garment/background)


class AudioIn(BaseModel):
    text: str
    voice: str = "ar-SA-HamedNeural"
    rate: str = "-18%"
    pitch: str = "-8Hz"
    effects: bool = True


class VideoIn(BaseModel):
    image: str                  # base64
    text: str | None = None
    audio: str | None = None    # base64 mp3
    watermark: bool | None = None


class PayIn(BaseModel):
    tx_hash: str
    package_id: str


class AdTicketIn(BaseModel):
    ticket: str


class AdminLoginIn(BaseModel):
    password: str


class AdminPointsIn(BaseModel):
    email: str
    points: float
    note: str = ""


class AdminBanIn(BaseModel):
    email: str
    banned: bool


# ----------------------------- تنظيف المدخلات -------------------------------
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_VOICE_RE = re.compile(r"^[a-zA-Z0-9\-]{2,48}$")
_RATE_RE = re.compile(r"^[+-]\d{1,2}%$")
_PITCH_RE = re.compile(r"^[+-]\d{1,3}Hz$")


def clean_text(value: str | None, max_len: int, field: str,
               required: bool = True) -> str:
    if value is None:
        if required:
            raise HTTPException(400, f"{field} مطلوب")
        return ""
    if not isinstance(value, str):
        raise HTTPException(400, f"{field} غير صالح")
    cleaned = _CONTROL_RE.sub("", value).strip()
    if required and not cleaned:
        raise HTTPException(400, f"{field} فارغ")
    if len(cleaned) > max_len:
        raise HTTPException(413, f"{field} طويل جداً (الحد الأقصى {max_len} حرف)")
    return cleaned


def validate_audio_options(voice: str, rate: str, pitch: str) -> tuple[str, str, str]:
    voice = clean_text(voice, 48, "الصوت")
    rate = clean_text(rate, 8, "السرعة")
    pitch = clean_text(pitch, 10, "الطبقة")
    if not _VOICE_RE.match(voice):
        raise HTTPException(400, "اسم الصوت غير صالح")
    if not _RATE_RE.match(rate):
        raise HTTPException(400, "السرعة غير صالحة")
    if not _PITCH_RE.match(pitch):
        raise HTTPException(400, "الطبقة غير صالحة")
    return voice, rate, pitch


def _detect_media(raw: bytes) -> tuple[str, str] | None:
    """يكتشف نوع الملف من البايات الحقيقية وليس من الامتداد."""
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif", ".gif"
    if raw[:3] == b"ID3" or (len(raw) > 2 and raw[0] == 0xFF and raw[1] & 0xE0 == 0xE0):
        return "audio/mpeg", ".mp3"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if raw[4:8] == b"ftyp":
        brand = raw[8:12]
        if brand.startswith(b"M4A") or brand in (b"mp4a", b"isom", b"mp42"):
            return "audio/mp4", ".m4a"
    return None


def save_b64(data: str, kind: str) -> Path:
    """يحفظ ملفاً مرفوعاً بأمان: حجم + نوع حقيقي + اسم UUID عشوائي."""
    if not isinstance(data, str) or len(data) > MAX_B64_CHARS:
        raise HTTPException(413, "الملف كبير جداً")
    if data.strip().startswith("data:"):
        if "," not in data:
            raise HTTPException(400, "ملف غير صالح")
        data = data.split(",", 1)[1]
    payload = re.sub(r"\s+", "", data)
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise HTTPException(400, "ترميز الملف غير صالح") from exc
    if len(raw) < 128:
        raise HTTPException(400, "الملف صغير جداً")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"حجم الملف يتجاوز {MAX_UPLOAD_BYTES // (1024 * 1024)}MB")

    detected = _detect_media(raw)
    if not detected:
        raise HTTPException(400, "نوع الملف غير مدعوم أو محتواه لا يطابق امتداده")
    mime, ext = detected
    if kind == "image" and not mime.startswith("image/"):
        raise HTTPException(400, "يرجى رفع صورة صالحة")
    if kind == "audio" and not mime.startswith("audio/"):
        raise HTTPException(400, "يرجى رفع ملف صوتي صالح")

    # اسم عشوائي تماماً يمنع Path Traversal والتخمين
    target = (OUTPUT_DIR / f"{uuid.uuid4().hex}{ext}").resolve()
    if target.parent != OUTPUT_DIR.resolve():
        raise HTTPException(400, "مسار الملف غير صالح")
    target.write_bytes(raw)
    return target


# ----------------------------- مساعدات -------------------------------------
def current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "يرجى تسجيل الدخول أولاً")
    user = auth.user_from_token(authorization.split(" ", 1)[1].strip())
    if not user:
        raise HTTPException(401, "الجلسة منتهية، سجّل الدخول مجدداً")
    return user


def charge(user: dict, cost: float, mode: str) -> None:
    if not auth.spend_points(user["id"], cost, mode):
        raise HTTPException(
            402, "نقاطك غير كافية، اشحن من نافذة الشحن أو ادعُ أصدقاءك"
        )


def file_url(path: Path) -> str:
    return f"/files/{path.name}"


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def admin_required(authorization: str | None = Header(default=None)) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "يرجى تسجيل دخول المدير")
    token = authorization.split(" ", 1)[1].strip()
    if not admin.verify_token(token):
        raise HTTPException(401, "جلسة المدير منتهية أو غير صالحة")


# ----------------------------- عام -----------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "service": "Hilal AI",
        "wallet_configured": bool(BINANCE_BEP20_ADDRESS),
        "production": IS_PRODUCTION,
    }


@app.get("/api/packages")
@limiter.limit(RATE_LIMIT_GLOBAL)
def packages(request: Request) -> dict:
    return {
        "wallet_address": BINANCE_BEP20_ADDRESS,
        "network": "BEP20 (BNB Smart Chain)",
        "token": "USDT",
        "packages": PACKAGES,
        "points_cost": {
            "study": 0,
            "chat": POINTS_CHAT,
            "studio": POINTS_STUDIO,
            "image": POINTS_IMAGE,
            "audio": POINTS_AUDIO,
            "video": POINTS_VIDEO,
        },
        "free_chat_limit": FREE_CHAT_DAILY_LIMIT,
    }


@app.post("/api/register")
@limiter.limit(RATE_LIMIT_AUTH)
def register(request: Request, payload: RegisterIn) -> dict:
    email = clean_text(payload.email, 254, "البريد")
    password = payload.password or ""
    invite = clean_text(payload.invite_code, 32, "رمز الدعوة", required=False)
    try:
        user = auth.register(email, password, invite or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    token = auth.login(email, password)
    return {"user": user, "token": token}


@app.post("/api/login")
@limiter.limit(RATE_LIMIT_AUTH)
def login(request: Request, payload: LoginIn) -> dict:
    email = clean_text(payload.email, 254, "البريد")
    token = auth.login(email, payload.password or "")
    if not token:
        raise HTTPException(401, "البريد أو كلمة المرور غير صحيحة")
    return {"token": token}


@app.post("/api/logout")
@limiter.limit(RATE_LIMIT_AUTH)
def logout(request: Request, user: dict = Depends(current_user),
           authorization: str | None = Header(default=None)) -> dict:
    auth.revoke_token(authorization.split(" ", 1)[1].strip())
    return {"ok": True}


@app.get("/api/me")
@limiter.limit(RATE_LIMIT_GLOBAL)
def me(request: Request, user: dict = Depends(current_user)) -> dict:
    paid = has_paid(user["id"])
    return {
        **user,
        "has_paid": paid,
        "invite_link": f"{APP_BASE_URL}/?invite={user['invite_code']}",
        **chat_status(user["id"], paid),
    }


@app.post("/api/verify-payment")
@limiter.limit(RATE_LIMIT_HEAVY)
def payment(request: Request, payload: PayIn,
            user: dict = Depends(current_user)) -> dict:
    tx = clean_text(payload.tx_hash, 66, "TxID").lower()
    package_id = clean_text(payload.package_id, 32, "الباقة")
    attempt_key = f"u{user['id']}:{client_ip(request)}"

    try:
        check_attempt_block(attempt_key)
    except PaymentError as exc:
        raise HTTPException(429, str(exc)) from exc

    try:
        result = verify_payment(tx, package_id, user["id"])
    except PaymentError as exc:
        record_failed_attempt(attempt_key)
        raise HTTPException(400, str(exc)) from exc

    clear_failed_attempts(attempt_key)
    return result


# ----------------------------- الإعلانات -----------------------------------
@app.get("/api/ads/status")
@limiter.limit(RATE_LIMIT_GLOBAL)
def ads_status(request: Request, user: dict = Depends(current_user)) -> dict:
    return {
        "ads_remaining": ads_engine.remaining_ads(user["id"]),
        "reward": ads_engine.AD_REWARD_POINTS,
        "watch_seconds": ads_engine.AD_MIN_SECONDS,
    }


@app.post("/api/ads/start")
@limiter.limit(RATE_LIMIT_HEAVY)
def ads_start(request: Request, user: dict = Depends(current_user)) -> dict:
    try:
        return ads_engine.start_ticket(user["id"])
    except ads_engine.AdError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/ads/claim")
@limiter.limit(RATE_LIMIT_HEAVY)
def ads_claim(request: Request, payload: AdTicketIn,
              user: dict = Depends(current_user)) -> dict:
    ticket = clean_text(payload.ticket, 4096, "تذكرة الإعلان")
    try:
        return ads_engine.claim_ticket(ticket, user["id"])
    except ads_engine.AdError as exc:
        raise HTTPException(400, str(exc)) from exc


# ----------------------------- الواجهة الرئيسية -----------------------------
@app.get("/")
def index_page() -> FileResponse:
    """عرض موقع Hilal AI الكامل مباشرة على المسار الرئيسي."""
    page = WEB_DIR / "index.html"
    if not page.exists():
        raise HTTPException(404, "ملف الواجهة غير موجود")
    return FileResponse(page)


# ----------------------------- لوحة المدير ---------------------------------
@app.get("/admin")
def admin_page() -> FileResponse:
    page = WEB_DIR / "admin.html"
    if not page.exists():
        raise HTTPException(404)
    return FileResponse(page)


@app.get("/privacy")
def privacy_page() -> FileResponse:
    page = WEB_DIR / "privacy.html"
    if not page.exists():
        raise HTTPException(404)
    return FileResponse(page)


@app.post("/api/admin/login")
@limiter.limit(RATE_LIMIT_AUTH)
def admin_login(request: Request, payload: AdminLoginIn) -> dict:
    try:
        token = admin.login(payload.password)
    except admin.AdminError as exc:
        raise HTTPException(401, str(exc)) from exc
    return {"token": token, "expires_minutes": admin.ADMIN_SESSION_MINUTES}


@app.get("/api/admin/stats")
@limiter.limit(RATE_LIMIT_GLOBAL)
def admin_stats(request: Request, _: None = Depends(admin_required)) -> dict:
    return admin.stats()


@app.get("/api/admin/users")
@limiter.limit(RATE_LIMIT_GLOBAL)
def admin_users(request: Request, limit: int = 100,
                _: None = Depends(admin_required)) -> dict:
    return {"users": admin.users(limit)}


@app.get("/api/admin/payments")
@limiter.limit(RATE_LIMIT_GLOBAL)
def admin_payments(request: Request, limit: int = 100,
                   _: None = Depends(admin_required)) -> dict:
    return {"payments": admin.payments(limit)}


@app.post("/api/admin/add-points")
@limiter.limit(RATE_LIMIT_AUTH)
def admin_add_points(request: Request, payload: AdminPointsIn,
                     _: None = Depends(admin_required)) -> dict:
    try:
        return admin.add_points(payload.email, payload.points, payload.note)
    except admin.AdminError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/admin/ban")
@limiter.limit(RATE_LIMIT_AUTH)
def admin_ban(request: Request, payload: AdminBanIn,
              _: None = Depends(admin_required)) -> dict:
    try:
        return admin.set_banned(payload.email, payload.banned)
    except admin.AdminError as exc:
        raise HTTPException(400, str(exc)) from exc


# ----------------------------- المحركات ------------------------------------
@app.post("/api/ai/chat")
@limiter.limit(RATE_LIMIT_CHAT)
def ai_chat(request: Request, payload: ChatIn,
            user: dict = Depends(current_user)) -> dict:
    """المحادثة العادية: 30 رسالة مجانية/24 ساعة، وغير محدودة للمشتركين."""
    prompt = clean_text(payload.prompt, 4000, "الرسالة")
    system = clean_text(payload.system, 2000, "التعليمات", required=False)
    paid = has_paid(user["id"])
    allowed, usage = consume_free_chat(user["id"], paid)
    if not allowed:
        raise HTTPException(
            402,
            f"استهلكت {FREE_CHAT_DAILY_LIMIT} رسالة مجانية اليوم. "
            "اشترك في إحدى الباقات لفتح محادثة غير محدودة، أو استخدم مساعد الدراسة مجاناً بلا حدود.",
        )
    try:
        reply = text_engine.chat(prompt, system or None)
    except Exception as exc:
        if not paid:
            refund_free_chat(user["id"])
        raise HTTPException(502, str(exc)) from exc
    return {
        "reply": reply,
        "points_left": auth.get_points(user["id"]),
        "chat": chat_status(user["id"], paid),
        "usage": usage,
    }


@app.post("/api/ai/study")
@limiter.limit(RATE_LIMIT_GLOBAL)
def ai_study(request: Request, payload: ChatIn,
             user: dict = Depends(current_user)) -> dict:
    """مساعد الدراسة: مجاني 100% بلا نقاط ولا حد يومي للرسائل."""
    prompt = clean_text(payload.prompt, 8000, "السؤال الدراسي")
    try:
        reply = text_engine.study(prompt)
    except Exception as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"reply": reply, "points_left": auth.get_points(user["id"])}


@app.post("/api/ai/studio")
@limiter.limit(RATE_LIMIT_HEAVY)
def ai_studio(request: Request, payload: StudioIn,
              user: dict = Depends(current_user)) -> dict:
    """استوديو التصميم وتعديل الصور: 0.5 نقطة لكل عملية."""
    mode = payload.mode if payload.mode in ("edit", "design") else "design"
    prompt = clean_text(
        payload.prompt, 2000, "وصف التصميم أو التعديل", required=(mode == "design")
    )
    if mode == "design" and not prompt:
        raise HTTPException(400, "اكتب وصف التصميم المطلوب")
    paid = has_paid(user["id"])
    charge(user, POINTS_STUDIO, "studio")
    try:
        if mode == "edit":
            if not payload.image:
                raise HTTPException(400, "ارفع صورة لتعديلها أو اختر وضع التصميم")
            source = save_b64(payload.image, "image")
            out = studio_engine.edit_image(
                source, OUTPUT_DIR, prompt, watermark=not paid
            )
            fallback = "تم تعديل الصورة وتحسينها ✅"
        else:
            out = image_engine.generate(
                studio_engine.design_prompt(prompt),
                OUTPUT_DIR,
                watermark=not paid,
            )
            fallback = "تم إنشاء التصميم 🎨"
        # النص الإعلاني مكافأة؛ فشل محرك النص لا يُفقد المستخدم نقاطه ولا صورته
        try:
            ad_copy = text_engine.caption(
                prompt or "صورة معدّلة بشكل احترافي"
            )
        except Exception:
            ad_copy = fallback
    except HTTPException:
        auth.add_points(user["id"], POINTS_STUDIO)
        raise
    except Exception as exc:
        auth.add_points(user["id"], POINTS_STUDIO)
        raise HTTPException(502, str(exc)) from exc
    return {
        "url": file_url(out),
        "caption": ad_copy,
        "points_left": auth.get_points(user["id"]),
        "studio_cost": POINTS_STUDIO,
    }


@app.post("/api/ai/image")
@limiter.limit(RATE_LIMIT_HEAVY)
def ai_image(request: Request, payload: ImageIn,
             user: dict = Depends(current_user)) -> dict:
    prompt = clean_text(payload.prompt, 2000, "وصف الصورة")
    if payload.mode not in ("text", "tryon"):
        raise HTTPException(400, "وضع الصورة غير صالح")
    charge(user, POINTS_IMAGE, "image")
    try:
        if payload.mode == "tryon":
            if not payload.image or not payload.style:
                raise HTTPException(400, "يرجى رفع صورة الشخص وصورة الملابس/الخلفية")
            person = save_b64(payload.image, "image")
            style = save_b64(payload.style, "image")
            out = image_engine.tryon(
                person, style, prompt, OUTPUT_DIR,
                watermark=not has_paid(user["id"]),
            )
        else:
            out = image_engine.generate(
                prompt, OUTPUT_DIR, watermark=not has_paid(user["id"])
            )
    except HTTPException:
        auth.add_points(user["id"], POINTS_IMAGE)
        raise
    except Exception as exc:
        auth.add_points(user["id"], POINTS_IMAGE)
        raise HTTPException(502, str(exc)) from exc
    return {"url": file_url(out), "points_left": auth.get_points(user["id"])}


@app.post("/api/ai/audio")
@limiter.limit(RATE_LIMIT_HEAVY)
def ai_audio(request: Request, payload: AudioIn,
             user: dict = Depends(current_user)) -> dict:
    text = clean_text(payload.text, 8000, "النص")
    voice, rate, pitch = validate_audio_options(
        payload.voice, payload.rate, payload.pitch
    )
    charge(user, POINTS_AUDIO, "audio")
    try:
        out = audio_engine.speak(
            text, OUTPUT_DIR, voice, rate, pitch, payload.effects
        )
    except Exception as exc:
        auth.add_points(user["id"], POINTS_AUDIO)
        raise HTTPException(502, str(exc)) from exc
    return {"url": file_url(out), "points_left": auth.get_points(user["id"])}


@app.post("/api/ai/video")
@limiter.limit(RATE_LIMIT_HEAVY)
def ai_video(request: Request, payload: VideoIn,
             user: dict = Depends(current_user)) -> dict:
    text = clean_text(payload.text, 8000, "النص", required=False)
    charge(user, POINTS_VIDEO, "video")
    try:
        portrait = save_b64(payload.image, "image")
        if payload.audio:
            audio_path = save_b64(payload.audio, "audio")
        elif text:
            audio_path = audio_engine.speak(text, OUTPUT_DIR, effects=False)
        else:
            raise HTTPException(400, "أرسل نصاً أو ملف صوتي للفيديو الناطق")
        watermark = payload.watermark
        if watermark is None:
            watermark = not has_paid(user["id"])
        out = video_engine.create(portrait, audio_path, OUTPUT_DIR, watermark=watermark)
    except HTTPException:
        auth.add_points(user["id"], POINTS_VIDEO)
        raise
    except Exception as exc:
        auth.add_points(user["id"], POINTS_VIDEO)
        raise HTTPException(502, str(exc)) from exc
    return {"url": file_url(out), "points_left": auth.get_points(user["id"])}


# ----------------------------- ملفات وواجهة --------------------------------
app.mount("/files", StaticFiles(directory=OUTPUT_DIR), name="files")
if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
