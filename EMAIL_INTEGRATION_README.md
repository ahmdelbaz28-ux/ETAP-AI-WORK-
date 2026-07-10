# ⚡ AhmedETAP — Resend Email Integration v2

تكامل كامل ومحسّن بين منصة AhmedETAP وخدمة [Resend](https://resend.com) — مع هوية AhmedETAP البصرية (⚡ أصفر→أحمر) وميزات متقدمة.

---

## 🆕 ما الجديد في v2

| الميزة | الوصف |
|---|---|
| 🪄 **Magic Links** | دخول بدون كلمة مرور عبر رابط بريدي one-shot |
| 📊 **Email Digests** | ملخص يومي/أسبوعي بنشاط المستخدم |
| 🔔 **Webhooks** | استقبال أحداث Resend + إعادة توجيهها لأنظمة خارجية |
| 📈 **Dashboard** | لوحة مراقبة حية لإحصائيات الإرسال |
| 🎨 **هوية AhmedETAP** | كل القوالب بتدرج أصفر→أحمر + شعار ⚡ |
| 📝 **سجل الإرسال** | تسجيل تلقائي لكل عملية إرسال للإحصائيات |

---

## 📦 المحتويات

```
ETAP-AI-WORK-/
├── integrations/
│   └── resend_email.py             # عميل Resend + auto-logging
├── services/
│   ├── email_service.py            # 13+ دالة بريد جاهزة
│   ├── otp_store.py                # OTP آمن (hash + rate limiting)
│   └── email_send_log.py           # 🆕 سجل الإرسال للـ dashboard
├── api/
│   ├── email_otp.py                # راوتر OTP
│   ├── magic_links.py              # 🆕 Magic Links (passwordless)
│   ├── email_digest.py             # 🆕 Digests (daily/weekly)
│   ├── email_webhooks.py           # 🆕 Webhooks (inbound+outbound)
│   ├── email_dashboard.py          # 🆕 Dashboard (HTML+JSON)
│   ├── auth.py                     # ✏️ مُعدّل (welcome, reset, change pwd)
│   ├── notifications.py            # ✏️ مُعدّل (requires_email delivery)
│   └── routes.py                   # ✏️ مُعدّل (5 routers مسجّلة)
├── templates/emails/               # 14 قالب بهوية AhmedETAP
│   ├── otp.html                    # أصفر→أحمر + ⚡
│   ├── password_reset.html
│   ├── welcome.html
│   ├── verify_email.html
│   ├── login_alert.html            # أحمر خالص (تنبيه)
│   ├── lockout.html
│   ├── notification.html
│   ├── study_complete.html         # أخضر (نجاح)
│   ├── study_failed.html
│   ├── role_change.html            # بنفسجي
│   ├── password_change.html        # سماوي
│   ├── critical_alert.html         # أحمر + شريط جانبي
│   ├── magic_link.html             # 🆕
│   └── digest.html                 # 🆕
├── tests/
│   └── test_new_features.py        # اختبارات شاملة (تعمل فعلياً)
└── .env.example                    # ✏️ مُحدّث بكل المتغيرات الجديدة
```

---

## 🚀 التثبيت (5 دقائق)

### الطريقة 1: استخدام النسخة المحلية الجاهزة

```bash
# النسخة المحلية في /home/z/my-project/etap-local-clone/ جاهزة بالفعل
# — كل الباتشات تم تطبيقها، القوالب محدّثة، الميزات مُختبرة

# انسخها فوق repo الحالي
cp -r /home/z/my-project/etap-local-clone/* /path/to/your/ETAP-AI-WORK-/
```

### الطريقة 2: تثبيت يدوي

1. انسخ المجلدات: `integrations/`, `services/`, `templates/`, والملفات الجديدة في `api/`
2. طبّق التعديلات على `api/auth.py`, `api/notifications.py`, `api/routes.py`
3. أضف إعدادات Resend من `.env.example` إلى `.env`

---

## ⚙️ الإعدادات (env vars)

### الأساسية (مطلوبة)

```bash
RESEND_API_KEY=re_your_key_here
RESEND_FROM_EMAIL=onboarding@resend.dev     # أو noreply@yourdomain.com
RESEND_FROM_NAME=AhmedETAP
RESEND_ENABLED=true
```

### الهوية البصرية

```bash
EMAIL_BRAND_NAME=AhmedETAP
EMAIL_BRAND_TAGLINE=Enterprise AI-Powered Power Systems Engineering
EMAIL_SUPPORT_ADDRESS=support@etap-ai-work.vercel.app
EMAIL_APP_URL=https://etap-ai-work.vercel.app
EMAIL_BRAND_PRIMARY=#facc15                # أصفر AhmedETAP
EMAIL_BRAND_SECONDARY=#ef4444              # أحمر AhmedETAP
EMAIL_BRAND_LOGO_EMOJI=⚡                   # البرق
```

### الميزات الجديدة

```bash
# Magic Links
MAGIC_LINK_TTL_SECONDS=900                 # 15 دقيقة
MAGIC_LINK_MAX_USES=1

# Digests
EMAIL_DIGEST_ENABLED=true
EMAIL_DIGEST_SCHEDULE_DAILY=08:00          # UTC
EMAIL_DIGEST_SCHEDULE_WEEKLY=MONDAY_08:00

# Webhooks
EMAIL_WEBHOOK_SECRET=your-hmac-secret      # لتوقيع الـ outbound
EMAIL_WEBHOOK_EVENTS=email.sent,email.delivered,email.bounced

# Dashboard
EMAIL_DASHBOARD_ENABLED=true
EMAIL_DASHBOARD_ADMIN_ROLES=admin,super_admin
EMAIL_DASHBOARD_DEV_OPEN=false             # true للتطوير فقط
```

---

## 📋 الـ APIs الجديدة

### 1. Magic Links

```bash
# طلب رابط دخول
curl -X POST http://localhost:8000/api/v1/auth/magic-link/request \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com"}'

# التحقق من الرابط (بعد الضغط عليه)
curl -X POST http://localhost:8000/api/v1/auth/magic-link/verify \
  -H 'Content-Type: application/json' \
  -d '{"token":"...32+ chars..."}'
# → يرجع access_token + refresh_token
```

### 2. Email Digests

```bash
# معاينة digest لمستخدم (بدون إرسال)
curl http://localhost:8000/api/v1/email-digest/preview/user@example.com

# توليد digest يدوياً
curl -X POST http://localhost:8000/api/v1/email-digest/generate \
  -H 'Content-Type: application/json' \
  -d '{"email":"user@example.com","period":"daily"}'

# cron call (يُستدعى كل ساعة)
curl -X POST http://localhost:8000/api/v1/email-digest/schedule/run \
  -H 'X-API-Key: your-service-key'
```

### 3. Webhooks

```bash
# تسجيل endpoint خارجي
curl -X POST http://localhost:8000/api/v1/email/webhooks/endpoints \
  -H 'Content-Type: application/json' \
  -d '{
    "url":"https://hooks.slack.com/services/...",
    "events":["email.bounced","email.complained"],
    "secret":"slack_signing_secret_min_16_chars"
  }'

# استقبال webhook من Resend
# (يُسجّل في Resend Dashboard → Webhooks → Add endpoint)
# URL: https://your-api.com/api/v1/email/webhooks/resend
```

### 4. Dashboard

افتح في المتصفح:
```
http://localhost:8000/api/v1/email-dashboard/
```

أو استخدم JSON APIs:
```bash
# إحصائيات آخر 24 ساعة
curl http://localhost:8000/api/v1/email-dashboard/api/stats?window_hours=24 \
  -H 'Authorization: Bearer <admin-jwt>'

# آخر 100 إرسال
curl http://localhost:8000/api/v1/email-dashboard/api/recent?limit=100 \
  -H 'Authorization: Bearer <admin-jwt>'
```

---

## 🎨 الهوية البصرية

كل القوالب تستخدم الآن:

| العنصر | القيمة |
|---|---|
| التدرج الأساسي | `linear-gradient(135deg, #facc15 0%, #ef4444 100%)` |
| الشعار | ⚡ (في رأس كل قالب) |
| اللون النصي على التدرج | `#1f2937` (رمادي داكن) |
| اللون النصي الأساسي | `#111827` |
| الخط | `-apple-system, BlinkMacSystemFont, Segoe UI, Roboto` |
| الحدود | `border-radius: 12px` للبطاقات، `6px` للأزرار |

**قوالب خاصة:**
- `study_complete.html` — أخضر (#16a34a) للنجاح
- `login_alert.html`, `lockout.html`, `critical_alert.html` — أحمر (#ef4444 → #b91c1c) للتنبيه
- `role_change.html` — بنفسجي (#7c3aed) لتغيير الصلاحيات
- `password_change.html` — سماوي (#0891b2) للتأكيد

---

## ✅ الاختبارات

```bash
cd /home/z/my-project/etap-local-clone
python tests/test_new_features.py
```

**النتائج:**
- ✅ OTP: issue + verify + re-verify rejection + rate limit
- ✅ Magic Links: issue + verify + one-shot + rate limit
- ✅ Send Log: log + recent + stats + by-day + record-by-id
- ✅ Dashboard: stats + recent + by-day + config endpoints
- ✅ Webhooks: register + list + delete + test
- ✅ Digests: context building + config
- ✅ Live send: 3 رسائل فعلية بهوية AhmedETAP إلى `a7medbaz16@gmail.com`

---

## 🛡️ الأمان

| الميزة | التفاصيل |
|---|---|
| **OTP hash** | SHA-256 (لا يُخزَّن plaintext) |
| **Magic link tokens** | 32-byte URL-safe random |
| **Webhook signature** | HMAC-SHA256 (Svix-compatible) |
| **Rate limiting** | لكل مستلم + لكل IP (على الـ API level) |
| **Auto-logging** | كل إرسال يُسجَّل تلقائياً مع message_id |
| **User enumeration** | OTP/magic-link ترجع 200 دائماً |
| **One-shot consumption** | كل OTP/magic link يُستهلك عند الاستخدام |

---

## 📊 حدود Resend

| الحد | القيمة | ملاحظة |
|---|---|---|
| شهرياً | 3,000 email | Free tier |
| يومياً | 100 email | Free tier |
| معدل الإرسال | 2/sec | Free tier |
| Recipient restriction | فقط `a7medbaz16@gmail.com` | بدون domain مخصص |

**للتجاوز**: أضف domain في [Resend → Domains](https://resend.com/domains) وحدّث `RESEND_FROM_EMAIL`.

---

## 🔄 ما تم تطبيقه على repo المحلي

في `/home/z/my-project/etap-local-clone/`:

| الملف | التغيير |
|---|---|
| `api/routes.py` | ✅ تسجيل 5 routers جديدة (email_otp, magic_links, email_digest, email_webhooks, email_dashboard) |
| `api/auth.py` | ✅ ربط `forgot_password` بـ `send_password_reset` |
| `api/auth.py` | ✅ ربط `register` بـ `send_welcome` |
| `api/auth.py` | ✅ ربط `change_password` بـ `send_password_change_email` |
| `api/notifications.py` | ✅ ربط `requires_email=True` بـ `send_notification_email` |
| `.env.example` | ✅ إضافة كل إعدادات Resend والميزات الجديدة |
| `integrations/resend_email.py` | ✅ إضافة auto-logging لكل إرسال |
| 9 ملفات جديدة | ✅ في `api/`, `services/`, `templates/emails/` |
| 14 قالب HTML | ✅ كلها بهوية AhmedETAP (أصفر→أحمر + ⚡) |

---

## 📞 الدعم

- **مشاكل الإرسال**: راجع Dashboard على `/api/v1/email-dashboard/`
- **OTP لا يصل**: تحقق من spam + `RESEND_FROM_EMAIL`
- **429 Too Many Requests**: زِد `RESEND_RATE_LIMIT_MAX` أو انتظر
- **401 Unauthorized**: المفتاح غير صحيح أو مُلغى
- **Magic link لا يعمل**: تحقق من `EMAIL_APP_URL` + أن الـ token لم يُستهلك

---

## 📝 الترخيص

MIT License — نفس ترخيص ETAP-AI-WORK-.
