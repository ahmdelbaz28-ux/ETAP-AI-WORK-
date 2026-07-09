# Cloudflare R2 Storage — دليل التفعيل والاستخدام

## نظرة عامة

Cloudflare R2 هو تخزين كائنات (object storage) متوافق مع S3، بدون رسوم خروج (egress fees). يُستخدم لتخزين:
- ملفات المستخدمين (إعدادات الشبكة، مدخلات الدراسات)
- التقارير المُنشأة (PDF exports، نتائج الدراسات)
- مخرجات محاكاة ETAP
- الملفات الكبيرة التي لا تناسب Postgres

---

## الخطوة 1: تفعيل R2 من لوحة التحكم

R2 يتطلب تفعيل يدوي من لوحة تحكم Cloudflare (لا يمكن عبر API).

🔗 **افتح:** https://dash.cloudflare.com/?to=/:account/workers-and-pages

1. من القائمة الجانبية، اضغط **"R2 Object Storage"**
2. اضغط **"Get started"** أو **"Enable R2"**
3. أدخل معلومات الدفع (لن يُخصم شيء — الخطة المجانية تشمل 10GB)
4. اقرأ ووافق على الشروط
5. R2 سيكون مفعّل خلال ثواني

---

## الخطوة 2: إنشاء Bucket (بعدين ما تفعّل R2)

بعد تفعيل R2، أنشئ الـ bucket:

🔗 **افتح:** https://dash.cloudflare.com/?to=/:account/workers-and-pages

1. في صفحة R2، اضغط **"Create bucket"**
2. اسم الـ bucket: `ahmedetap-storage`
3. الموقع: **APAC** (الأقرب للخليج)
4. اضغط **Create**

أو عبر API (بعد التفعيل):
```bash
curl -X POST "https://api.cloudflare.com/client/v4/accounts/8ea12977423cb0079cf4d227a0195bb1/r2/buckets" \
  -H "Authorization: Bearer YOUR_CF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"ahmedetap-storage","locationHint":"apac"}'
```

---

## الخطوة 3: إنشاء R2 API Token

للوصول لـ R2 من الـ backend (عبر S3-compatible API):

🔗 **افتح:** https://dash.cloudflare.com/?to=/:account/r2/api-tokens

1. اضغط **"Create API token"**
2. الاسم: `ahmedetap-r2-token`
3. الصلاحيات: **Object Read & Write**
4. الـ bucket: `ahmedetap-storage` (أو "Apply to all buckets")
4. اضغط **Create**
5. **انسخ القيمتين:**
   - Access Key ID
   - Secret Access Key

---

## الخطوة 4: ربط الـ Bucket بالـ Worker

في ملف `wrangler-r2.toml`، الربط مُعد مسبقاً:
```toml
[[r2_buckets]]
binding = "STORAGE"
bucket_name = "ahmedetap-storage"
```

للنشر:
```bash
cd cloudflare/
wrangler deploy -c wrangler-r2.toml
```

هذا ينشر نسخة الـ Worker التي تدعم R2 مباشرة (أسرع من S3 API).

---

## الخطوة 5: إعداد المتغيرات على HF Space

بعد الحصول على R2 API Token، أضف هذه المتغيرات لـ HF Space:

🔗 **افتح:** https://huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform/settings

أضف هذه الـ Secrets:

| الاسم | القيمة |
|------|--------|
| `R2_ACCOUNT_ID` | `8ea12977423cb0079cf4d227a0195bb1` |
| `R2_ACCESS_KEY_ID` | (الـ Access Key ID من الخطوة 3) |
| `R2_SECRET_ACCESS_KEY` | (الـ Secret Access Key من الخطوة 3) |
| `R2_BUCKET_NAME` | `ahmedetap-storage` |
| `R2_PUBLIC_URL_PREFIX` | `https://storage.ahmed.net` (بعد إعداد النطاق المخصص) |

أو عبر API:
```python
from huggingface_hub import HfApi
api = HfApi(token='YOUR_HF_TOKEN')
secrets = {
    'R2_ACCOUNT_ID': '8ea12977423cb0079cf4d227a0195bb1',
    'R2_ACCESS_KEY_ID': 'YOUR_ACCESS_KEY',
    'R2_SECRET_ACCESS_KEY': 'YOUR_SECRET_KEY',
    'R2_BUCKET_NAME': 'ahmedetap-storage',
}
for key, value in secrets.items():
    api.add_space_secret('ahmdelbaz28/AhmedETAP-Platform', key, value)
```

---

## الخطوة 6: (اختياري) نطاق مخصص لـ R2

للوصول العام للملفات عبر `https://storage.ahmed.net`:

🔗 **افتح:** https://dash.cloudflare.com/?to=/:account/r2/buckets/ahmedetap-storage/settings

1. في إعدادات الـ bucket، اضغط **"Connect Domain"**
2. اكتب: `storage.ahmed.net`
3. Cloudflare سيضيف DNS record تلقائياً
4. الملفات ستكون متاحة على: `https://storage.ahmed.net/<key>`

---

## الاستخدام في الكود

```python
from api.r2_storage import r2, is_r2_enabled

if is_r2_enabled():
    # رفع ملف
    key = await r2.upload(
        "reports/study-123.pdf",
        pdf_bytes,
        "application/pdf",
        metadata={"project_id": "abc", "study_type": "load_flow"},
        cache_control="private, max-age=3600"
    )

    # تحميل ملف
    data = await r2.download("reports/study-123.pdf")

    # حذف ملف
    await r2.delete("reports/study-123.pdf")

    # قائمة الملفات
    files = await r2.list("reports/", limit=100)

    # رابط مؤقت (صالح لساعة)
    url = r2.presign("reports/study-123.pdf", expires=3600)

    # رابط عام (يحتاج نطاق مخصص)
    url = r2.public_url("reports/study-123.pdf")

    # توليد مفتاح فريد
    key = r2.generate_key(prefix="reports", extension="pdf", user_id="user-123")
```

---

## الخطة المجانية (Free Tier)

| المورد | الحد المجاني | التكلفة بعده |
|--------|-------------|--------------|
| التخزين | 10 GB/شهر | $0.015/GB/شهر |
| العمليات Class A (writes) | 1 مليون/شهر | $4.50/مليون |
| العمليات Class B (reads) | 10 مليون/شهر | $0.36/مليون |
| **الخروج (egress)** | **مجاني دائماً** | $0.00 |

ميزة R2 الرئيسية: **egress مجاني** — على عكس AWS S3 الذي يأخذ $0.09/GB.

---

## الملفات في هذا الدليل

| الملف | الوصف |
|------|--------|
| `api/r2_storage.py` | وحدة Python للوصول لـ R2 (S3-compatible) |
| `cloudflare/worker-r2.js` | نسخة Worker مع R2 binding مباشر |
| `cloudflare/wrangler-r2.toml` | إعداد النشر مع R2 binding |
| `cloudflare/R2_SETUP.md` | هذا الدليل |
