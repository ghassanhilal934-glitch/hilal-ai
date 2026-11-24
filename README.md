# 🌙 Hilal AI — منصة ذكاء اصطناعي عربية بمحركات مجانية 100%

واجهة عصرية بالعربية (RTL) تشبه Gemini + واجهة برمجية FastAPI + SQLite + نظام نقاط ودعوات + تحقق تلقائي من تحويلات USDT على BSC (BEP20) + APK عبر GitHub Actions + إضافة Chrome (Manifest V3).

> المحركات كلها مجانية بلا مفتاح API: Pollinations (نص/صور)، edge-tts (صوت)، ffmpeg (مونتاج)، ومساحات HuggingFace Gradio المجانية (تحريك الشفاه/تغيير الملابس).

---

## 1) هيكل المشروع

```
hilal_ai/
├── backend/                     # FastAPI + SQLite
│   ├── app.py                   # كل نقاط النهاية + تقديم الواجهة
│   ├── config.py                # قراءة .env والإعدادات
│   ├── db.py                    # جداول users/sessions/payments/usage_logs/chat_usage
│   ├── auth.py                  # تسجيل/دخول/نقاط/دعوات
│   ├── payments.py              # تحقق BEP20 عبر RPC مجاني
│   ├── admin.py                 # لوحة المدير (إحصائيات/نقاط/حظر)
│   ├── engines/
│   │   ├── ads.py               # إعلانات مقابل نقاط (تذاكر JWT + حد يومي)
│   │   ├── watermark.py         # علامة Hilal AI عبر ffmpeg (صور + فيديو)
│   │   ├── text.py              # Pollinations Text + أوضاع الدراسة/النص الإعلاني
│   │   ├── studio.py            # فلاتر ffmpeg لتعديل الصور + موجهات التصميم
│   │   ├── image.py             # Pollinations Image + Gradio VTON
│   │   ├── audio.py             # edge-tts + ffmpeg
│   │   └── video.py             # تقسيم + MuseTalk + ffmpeg + علامة مائية
│   ├── Dockerfile               # جاهز لـ HuggingFace Docker Spaces
│   ├── requirements.txt
│   ├── .env.example
│   └── start.sh
├── web_and_android/
│   ├── web/                     # الواجهة العربية + لوحة المدير (admin.html/js/css)
│   ├── assets/                  # icon.png و splash.png (مع عبارة الراعي الرسمي)
│   ├── tools/make_assets.py     # مولّد الأيقونة وشاشة البداية
│   ├── capacitor.config.json
│   ├── package.json
│   ├── chrome_extension/        # Manifest V3
│   └── .github/workflows/build-apk.yml
└── .github/workflows/           # (اختياري) رفع الباكند أيضاً
```

---

## 2) التشغيل محلياً (Termux أو أي بيئة Python 3.10+)

```sh
cd ~/social_bot/hilal_ai/backend
cp .env.example .env
# عدّل .env: ضع عنوان محفظتك BEP20 في BINANCE_BEP20_ADDRESS
pip install -r requirements.txt
pip install --no-deps gradio_client==2.7.2 huggingface_hub==0.24.7 \
  httpx==0.28.1 requests==2.31.0 tqdm pyyaml click filelock packaging \
  websocket-client websockets fsspec
sh start.sh
```

افتح: `http://localhost:8000`

> في Termux/Arm64 قد يحتاج `pydantic` إلى إصدار 1.10.15 (موجود في `requirements.txt`). ملف `sitecustomize.py` يتولى توافق Python 3.13.

### المتغيرات المهمة في `.env`

| المتغير | المعنى |
|---|---|
| `BINANCE_BEP20_ADDRESS` | عنوان استقبال USDT على BSC. **لا تضع المفتاح الخاص أبداً.** |
| `APP_BASE_URL` | الرابط العام للتطبيق، يظهر في رابط الدعوة. |
| `SECRET_KEY` | سري للجلسات (غيّره). |
| `BSC_RPC_URLS` | RPCs مجانية: `bsc-dataseed.binance.org` و `bsc-rpc.publicnode.com`. |
| `USDT_CONTRACT` | `0x55d398326f99059fF775485246999027B3197955` (BEP20 USDT). |
| `MIN_CONFIRMATIONS` | تأكيد واحد يكفي افتراضياً. |
| `HF_TOKEN` | اختياري لرفع حصة مساحات Gradio المجانية. |
| `POINTS_*` | تكلفة الصور/الصوت/الفيديو بالنقاط. `POINTS_STUDIO` = 0.5 لتصميم/تعديل الصور. |
| `FREE_CHAT_DAILY_LIMIT` | رسائل المحادثة المجانية يومياً للمستخدم غير المشترك (افتراضي 30؛ تتجدد كل 24 ساعة). |
| `ADMIN_PASSWORD` | كلمة مرور لوحة المدير على `/admin`. يُنشأ رابط غير مفعّل إذا تركت فارغاً. |
| `ADMIN_SESSION_MINUTES` | صلاحية جلسة المدير (افتراضي 480 دقيقة). |
| `ADMOB_REWARDED_ID` | معرّف إعلان AdMob ذو المكافأة (افتراضي = معرّف اختبار Google). |
| `WEB_AD_DIRECT_LINK` | رابط إعلان يُفتح في المتصفح عندما لا يكون التطبيق أصلياً. |
| `AD_DAILY_LIMIT` | أقصى عدد إعلانات يومياً (افتراضي 5). |
| `AD_MIN_SECONDS` | أقل مدة مشاهدة قبل صرف المكافأة (افتراضي 25 ثانية). |

---

## 3) نظام النقاط والاشتراكات

- كل مستخدم جديد: **2 نقطة مجانية**.
- كل صديق يسجّل برابط الدعوة أو رمز الدعوة: **+1 نقطة** للداعي.
- الباقات:

| الباقة | السعر | النقاط |
|---|---:|---:|
| Starter | 5 USDT | 10 |
| Pro | 12 USDT | 30 |
| VIP | 25 USDT | 80 |

- التكلفة الافتراضية: صورة/صوت = 1 نقطة، فيديو ناطق = نقطتان، **استوديو التصميم وتعديل الصور = 0.5 نقطة**.
- **🎓 مساعد الدراسة:** مجاني 100%، بلا نقاط ولا حد يومي للرسائل.
- **💬 المحادثة العادية:** 30 رسالة مجانية يومياً لغير المشترك (عداد واضح يتجدد كل 24 ساعة من أول رسالة). الاشتراك بأي باقة يفتح محادثة **غير محدودة**.
- المستخدمون المجانيون يحصلون على علامة مائية صغيرة `Hilal AI` على الصور والفيديو؛ بعد أول دفع مؤكّد تُزال تلقائياً.
- **الإعلانات مقابل النقاط 🎬:** شاهد إعلاناً واحصل على **0.5 نقطة**، حتى 5 إعلانات يومياً.

### الأوضاع الستة في الشريط العلوي

| الوضع | التكلفة | الوصف |
|---|---|---|
| 💬 محادثة | 30 رسالة/يوم مجاناً ثم اشتراك | ردود عربية عامة عبر Pollinations؛ المشترك غير محدود. |
| 🎓 مساعد الدراسة 🎓 | **0 نقطة / بلا حدود** | معلّم ذكي يشرح الدروس، يلخّص النصوص، يحل المسائل خطوة بخطوة، ويصنع اختبارات تدريبية بالعربية أو الإنجليزية حسب لغة الطالب. |
| 🎨 تصميم وتعديل الصور 🎨 | **0.5 نقطة** | تجميل/فلترة الصور المرفوعة (إضاءة، سينمائي، أبيض وأسود، فينتاج...) أو توليد شعارات وإعلانات ومنشورات مع **نص إعلاني جاهز للنسخ**. |
| 🖼️ صور / 🎙️ صوتيات / 🎬 فيديو ناطق | نقاط | تعمل بالنقاط المبدئية أو الإعلانات أو الاشتراك. |

نقاط النهاية الجديدة:

| الطريقة | المسار | الوصف |
|---|---|---|
| POST | `/api/ai/study` | `{prompt}` → رد تعليمي مجاني بلا خصم ولا عدّاد يومي. |
| POST | `/api/ai/studio` | `{prompt, mode:"design"|"edit", image?}` → `{url, caption, points_left, studio_cost}`؛ يُخصم 0.5 نقطة ويُسترد عند أي فشل. |

> عبارة **"Official Sponsor: Ghassan Hilal"** تظهر في القائمة الجانبية، وأسفل الشاشة الرئيسية، وشاشة الترحيب (سواء نسخة الويب أو `assets/splash.png` داخل APK).

### الإعلانات مقابل النقاط (Rewarded Ads)

1. `POST /api/ads/start` → يُنشئ تذكرة JWT موقّعة ومرتبطة بالمستخدم (صالحة 5 دقائق)، ويعيد معرّف AdMob ورابط الويب وعدد الإعلانات المتبقية.
2. الواجهة تشغّل إعلان AdMob أصلياً داخل APK، أو تفتح `WEB_AD_DIRECT_LINK` في المتصفح، وتبدأ عدّاً تنازلياً من 25 ثانية.
3. `POST /api/ads/claim` `{ticket}` → يتحقق الخادم من:
   - صحة التوقيع وارتباط التذكرة بالمستخدم،
   - مرور 25 ثانية على الأقل منذ الإنشاء،
   - عدم استخدام التذكرة من قبل (قيد `claimed` داخل معاملة)،
   - عدم تجاوز 5 إعلانات خلال اليوم.
   ثم يضيف 0.5 نقطة فوراً داخل نفس المعاملة.
4. أي محاولة تلاعب (تذكرة مكررة، تذكرة لمستخدم آخر، تقدّم الوقت) تُرفض.

> في `APK` أضفنا `@capacitor-community/admob` مع معرّف اختبار رسمي من Google. استبدل `ADMOB_REWARDED_ID` و`appId` في `capacitor.config.json` بمعرّفاتك الحقيقية قبل النشر.

### التحقق من الدفع (`POST /api/verify-payment`)

1. يحوّل المستخدم USDT (BEP20) إلى عنوانك بالضبط وبالمبلغ المساوي للباقة أو أكثر.
2. يرسل `tx_hash` + `package_id` من نافذة الشحن.
3. السيرفر يسأل RPC مجاني عبر `eth_getTransactionReceipt`، يفحص:
   - نجاح المعاملة، عدد التأكيدات،
   - حدث `Transfer` الخاص بعقد USDT،
   - أن المستلم هو عنوانك،
   - أن المبلغ ≥ سعر الباقة.
4. يمنع تكرار TxID عبر جدول `payments`، ثم يضيف النقاط فوراً.

> ملاحظة: التحقق يقرأ **البلوكشين فقط**؛ لا يوجد أي اعتماد على خدمة دفع مدفوعة. RPCs المجانية قد تُخنق أحياناً؛ أضف RPC مجانياً آخر إلى `BSC_RPC_URLS` عند الحاجة.

---

## 4) نقاط النهاية API

| الطريقة | المسار | الوصف |
|---|---|---|
| GET | `/api/health` | فحص الحالة |
| GET | `/api/packages` | الباقات + عنوان المحفظة + تكلفة النقاط |
| POST | `/api/register` | `{email,password,invite_code?}` → `{user,token}` |
| POST | `/api/login` | `{email,password}` → `{token}` |
| GET | `/api/me` | بيانات المستخدم + رابط الدعوة + `has_paid` |
| POST | `/api/verify-payment` | `{tx_hash,package_id}` |
| GET | `/api/ads/status` | عدد الإعلانات المتبقية + المكافأة |
| POST | `/api/ads/start` | إنشاء تذكرة إعلان موقّعة |
| POST | `/api/ads/claim` | `{ticket}` → صرف 0.5 نقطة بعد التحقق |
| POST | `/api/ai/chat` | `{prompt,system?}` ← Pollinations |
| POST | `/api/ai/image` | `{prompt,mode,image?,style?}` ← Pollinations / Gradio VTON |
| POST | `/api/ai/audio` | `{text,voice,rate,pitch,effects}` ← edge-tts + ffmpeg |
| POST | `/api/ai/video` | `{image,text?,audio?}` ← MuseTalk + ffmpeg |

كل نقاط `/api/ai/*` و`/api/me` تحتاج ترويسة:

```
Authorization: Bearer <token>
```

الملفات الناتجة تُقدَّم من `/files/<name>`.

التوثيق التفاعلي: `/api/docs`.

---

## 5) الرفع المجاني على HuggingFace Spaces (باكند + واجهة معاً)

1. اذهب إلى <https://huggingface.co/new-space> واختر:
   - **SDK:** Docker
   - **Visibility:** Public
   - **Space name:** مثلاً `hilal-ai`
2. ارفع **محتويات مجلد `backend/`** إلى جذر المستودع (أي أن يصبح `Dockerfile` و`app.py` في الجذر):

   ```sh
   cd hilal_ai/backend
   git init
   git add .
   git commit -m "Hilal AI backend"
   git remote add space https://huggingface.co/spaces/<YOUR_NAME>/hilal-ai
   git push -f space main
   ```

3. في تبويب **Settings → Repository secrets** أضف:

   | Secret | القيمة |
   |---|---|
   | `BINANCE_BEP20_ADDRESS` | عنوانك BEP20 |
   | `APP_BASE_URL` | `https://<YOUR_NAME>-hilal-ai.hf.space` |
   | `SECRET_KEY` | قيمة عشوائية طويلة |
   | `HF_TOKEN` | اختياري، توكن HuggingFace بصلاحية `read` |

4. انتظر حتى تظهر حالة Space = **Running**. الرابط النهائي هو `APP_BASE_URL` نفسه؛ الواجهة العربية تُقدَّم من نفس العنوان.

> قاعدة بيانات SQLite داخل الحاوية قد تُعاد تهيئتها عند إعادة تشغيل Space المجاني. للاستخدام الإنتاجي طويل الأمد، اربطvolume أو استخدم قاعدة بيانات مجانية خارجية؛ لكن للعرض والتجربة يعمل كما هو.

---

## 6) بناء APK مجاني عبر GitHub Actions

1. أنشئ مستودع GitHub جديداً وارفع **مجلد `hilal_ai` كاملاً** إليه (بحيث يوجد `web_and_android/.github/workflows/build-apk.yml`).
2. افتح **Actions → Build Hilal AI APK → Run workflow** (أو اعمل push إلى `main`).
3. بعد انتهاء البناء، نزّل الأرشيف `Hilal-AI` واستخرج منه `Hilal-AI.apk` وثبّته على الجوال.
4. سجّل الدخول مباشرة؛ لا حاجة لضبط رابط الخادم يدوياً.

> الواجهة تكتشف تلقائياً رابط الخادم:
> - عند فتحها من المتصفح: تستخدم `window.location.origin` (مثلاً `https://hilal-ai-8s01.onrender.com`).
> - داخل APK/Capacitor: تستخدم الرابط الثابت `DEFAULT_API_URL` المعرّف في `web_and_android/web/app.js`.
>
> لتغيير الرابط الافتراضي للـ APK، عدّل قيمة `DEFAULT_API_URL` في `web_and_android/web/app.js` إلى رابط الـ Space المنشور، ثم أعد بناء APK. تظهر القيمة نفسها في نافذة **الإعدادات → Default API URL** مع زر «استخدام الافتراضي».

---

## 7) إضافة Chrome (Manifest V3)

1. افتح `chrome://extensions` وفعّل **Developer mode**.
2. **Load unpacked** واختر مجلد `web_and_android/chrome_extension`.
3. سجّل الدخول من الواجهة الكاملة مرة واحدة؛ سيتم مزامنة `apiBase` و`token` إلى الإضافة تلقائياً عبر `chrome.storage.sync`.

---

## 8) اختبارات سريعة تم تنفيذها

```sh
curl http://localhost:8000/api/health
curl -X POST http://localhost:8000/api/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@hilal.ai","password":"secret123"}'
# ثم استخدم token مع /api/ai/chat أو /api/ai/audio أو /api/ai/image أو /api/ai/video
```

تم التحقق فعلياً من: تسجيل 2 نقطة، +1 نقطة بالدعوة، خصم النقطة عند المحادثة واستردادها عند الفشل، توليد صوت MP3، توليد صورة JPG، وإنتاج فيديو ناطق 512×912 بعلامة مائية للمستخدم المجاني.

---

## 9) التحصين الأمني (Production-Grade)

- **كلمات المرور:** `passlib` مع `bcrypt` عند توفره (الاستضافة العادية) و`pbkdf2_sha256` بـ 310k دورة على Termux/arm64. كلمات المرور القديمة ما زالت تُتحقَّق للتوافق.
- **الجلسات:** رموز **JWT** بتوقيع HS256 وصلاحية افتراضية 24 ساعة (`JWT_EXPIRE_MINUTES`)، مع معرّف `jti` مسجّل في قاعدة البيانات حتى يمكن إبطاله فوراً عبر `POST /api/logout`.
- لا يمكن لمستخدم الوصول إلى حساب أو نقاط مستخدم آخر؛ هوية المستخدم تُستخرج دائماً من الرمز داخل الخادم وليس من أي حقل يرسله العميل.
- `SECRET_KEY` عشوائي بطول 64 بايت يُولَّد تلقائياً ويُكتب إلى `backend/.env` إذا كان مفقوداً أو ضعيفاً.
- خصم النقاط وإضافة النقاط عند الدفع يتم داخل `BEGIN IMMEDIATE` مع شرط `points >= cost`؛ لا يمكن تجاوز الرصيد ولا استغلال التزامن.
- `/api/verify-payment` يمنع تكرار TxID عبر قيد فريد + قفل المعاملة، ويحظر مؤقتاً بعد 5 محاولات فاشلة لمدة 15 دقيقة (`PAYMENT_MAX_FAILURES` / `PAYMENT_BLOCK_MINUTES`).
- Rate limiting عبر `slowapi` بمفتاح مركّب `IP + بصمة التوكن`: 10/دقيقة للتسجيل والدخول، 30/دقيقة للمحادثة، 5/دقيقة للعمليات الثقيلة والدفع.
- تنظيف المدخلات: إزالة أحرف التحكم، حدود طول لكل حقل، فحص نوع الملف من **Magic Bytes** (وليس الامتداد)، حد 5MB، وأسماء ملفات `UUID` عشوائية.
- رؤوس الحماية: `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, `CSP`, `Referrer-Policy`, `Permissions-Policy`, و`HSTS` في الإنتاج.
- نقاط التوثيق `/api/docs` و`/redoc` مغلقة في وضع `production`. أضف `ENVIRONMENT=development` محلياً فقط إذا أردتها.
- CORS مفتوح لجميع النطاقات (`allow_origins=["*"]` مع `allow_credentials=False`) كي تعمل الواجهة من Render والتطبيق الأصلي وأي نطاق مخصص.

> ملاحظة: على Termux/arm64 لا تتوفر عجلة `bcrypt` مبنية مسبقاً؛ لذلك يعمل `passlib` تلقائياً بـ `pbkdf2_sha256`. في `Dockerfile` يُثبَّت `bcrypt` صراحةً فتُستخدم خوارزمية bcrypt في الإنتاج.

---

## 10) ملاحظة "مجاني 100%"

الأنظمة مجانية من ناحيتك (لا مفاتيح ولا فواتير)، لكن مزوّدي الخدمات المجانية يفرضون حصصاً وقيوداً على الطلبات. البرنامج يتعامل مع ذلك: يعيد المحاولة، ينتظر عند رسالة 402 من Pollinations، ويستخدم خطة بديلة (صورة ثابتة) إذا تعذّر تحريك الشفاه. للحصول على استقرار أعلى أضف `HF_TOKEN` وRPC مجانياً إضافياً.

---

## 11) رابط النشر الدائم على Render

**الرابط الدائم:**
```
https://hilal-ai-8s01.onrender.com
```

- الواجهة الكاملة منسوخة أيضاً إلى `backend/www` وتُقدَّم مباشرة على `/` من نفس الحاوية.
- قيمة `DEFAULT_API_URL` في `web_and_android/web/app.js` (المستخدمة داخل APK) و`APP_BASE_URL` في `backend/config.py` تشيران إلى رابط Render، لذا تعمل روابط الدعوة والتطبيق من أي مكان.
- مشروع أندرويد (Capacitor) يضبط `server.url` على الرابط نفسه؛ أي تحديث للموقع يظهر في APK فوراً بعد إعادة البناء.
- عند تغيّر الرابط، حدّث هذه المواضع ثم أعد النشر وإعادة بناء APK.

> الخطة المجانية في Render تُوقف الخدمة بعد 15 دقيقة من عدم النشاط، وتعيد تشغيلها عند أول طلب ( قد يستغرق ذلك نحو دقيقة ). نظام الملفات مؤقت؛ استخدم Render Postgres إن احتجت حفظ البيانات طويلة الأمد.

---

## 12) لوحة تحكم المدير 🛠️

افتح:

```
https://hilal-ai-8s01.onrender.com/admin
```

- كلمة المرور تُقرأ من `ADMIN_PASSWORD` في `backend/.env` (غيّرها قبل الإطلاق!).
- تسجيل الدخول يعطي **JWT منفصلاً** بصلاحية 8 ساعات (`ADMIN_SESSION_MINUTES`)، مخزّناً في `sessionStorage`؛ لا يمنح صلاحيات مستخدم عادي.
- تعرض اللوحة:
  - إحصائيات: المستخدمون، من دفع، إجمالي USDT، النقاط المتداولة، الإعلانات المستلمة، تسجيلات اليوم.
  - جدول المستخدمين مع بحث سريع، ونقاط، وعدد المدفوعات، ورابط الدعوة.
  - سجل مدفوعات USDT (TxID + البريد + الباقة + المبلغ).
- إجراءات:
  - **منح/خصم نقاط يدوياً** لأي بريد (مع ملاحظة وتسجيل في `admin_logs`).
  - **حظر / فك حظر** مستخدم: يُلغي كل جلساته فوراً ويمنعه من الدخول والاستخدام.

نقاط النهاية (كلها تتطلب `Authorization: Bearer <admin-token>` عدا الدخول):

| الطريقة | المسار | الوصف |
|---|---|---|
| POST | `/api/admin/login` | `{password}` → `{token}` |
| GET | `/api/admin/stats` | الإحصائيات |
| GET | `/api/admin/users` | قائمة المستخدمين |
| GET | `/api/admin/payments` | سجل المدفوعات |
| POST | `/api/admin/add-points` | `{email,points,note?}` |
| POST | `/api/admin/ban` | `{email,banned}` |

---

## 13) لمسات الانتشار وعلامة مائية

- **شريط قوالب بضغطة زر** فوق مربع الإدخال: قصة رعب في غرفة مهجورة، صورة ببدلة رسمية، مذيع أخبار، وتعليق صوتي وثائقي. كل زر يحوّل الوضع تلقائياً ويملأ النص.
- **علامة مائية نصية أنيقة `Hilal AI` عبر ffmpeg** تُضاف تلقائياً إلى **كل الصور والفيديوهات** للمستخدمين غير الدافعين، وتُزال فور تأكيد أول دفع (أي باقة). التنفيذ في `engines/watermark.py`.
- **أصول الأندرويد**: `web_and_android/assets/icon.png` (1024×1024) و`splash.png` (2732×2732) بخلفية سوداء نقية `#000000` وشعار `H Ai` (H ذهبي لامع + Ai أبيض)، وتحمل شاشة البداية عبارة `Official Sponsor: Ghassan Hilal`. جاهزة لـ `npx cap sync android` وبناء APK. يمكن إعادة توليدها بـ `python web_and_android/tools/make_assets.py` (يستخدم Pillow، ويتحوّل تلقائياً إلى ffmpeg إن لم يتوفر Pillow).

---

## 14) قائمة ما قبل الإطلاق

1. غيّر `ADMIN_PASSWORD` و`SECRET_KEY` و`BINANCE_BEP20_ADDRESS` في `backend/.env`.
2. استبدل `ADMOB_REWARDED_ID` و`WEB_AD_DIRECT_LINK` بمعرّفاتك الحقيقية، و`appId` في `capacitor.config.json`.
3. حدّث `DEFAULT_API_URL` و`APP_BASE_URL` إلى رابط النشر الدائم (أو احتفظ برابط النفق للتجربة).
4. شغّل `sh start_tunnel.sh` (للتجربة) أو انشر على HuggingFace Space / خادم خاص.
5. افتح `/admin` وتأكد من الإحصائيات، ثم أجرِ أول اختبار دفع حقيقي على BEP20.
6. أعد بناء APK من GitHub Actions ليحمل أيقونة `H Ai` وشاشة البداية الجديدتين.

---

## 15) الدعم والتواصل عبر Gmail 📧

- البريد: **ghassanhilal934@gmail.com**
- يظهر زر «تواصل معنا / الدعم الفني» في:
  - القائمة الجانبية للتطبيق،
  - نافذة «شحن النقاط» (لاستفسارات الدفع BEP20 والنقاط)،
  - صفحة **سياسة الخصوصية** على `/privacy` (مع زر «طلب حذف بياناتي»).
- الزر يفتح تطبيق البريد مباشرة عبر `mailto:`، ويوجد بجانبه زر **نسخ البريد** بضغطة واحدة (يعمل داخل APK والمتصفح حتى بدون صلاحية الحافظة).
- لتفادي إخفاء Cloudflare لعناوين البريد، يُحقّق البريد ديناميكياً من `web/support.js` ولا يظهر كنص ثابت في HTML.

---

## 16) تثبيت هوية H Ai في المنصات

- **الأندرويد/Capacitor**: السكربت `tools/install_android_assets.py` ينسخ الأيقونة إلى `res/mipmap-*/ic_launcher.png` بأحجام 48→192، ويضع `splash.png` في `res/drawable/` مع إعداد `@capacitor/splash-screen` بخلفية سوداء. يعمل تلقائياً في GitHub Actions بعد `npx cap add android`.
- **إضافة كروم**: `chrome_extension/icon16.png` و`icon32` و`icon48` و`icon128` مسجّلة في `manifest.json`، وشعار `popup.html` يستخدمها.
- **واجهة الويب**: `web/logo.png` يظهر في شعار القائمة الجانبية والشريط العلوي.
- إعادة التوليد الكاملة:
  ```sh
  python -m pip install Pillow
  python web_and_android/tools/make_assets.py
  python web_and_android/tools/install_android_assets.py
  ```
