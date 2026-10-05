# الخطة الجذرية النهائية لإصلاح منصة AhmedETAP — الإصدار 2.0

**الأساس:** `ETAP_Complete_Remediation_Plan.md` v1.0 + التدقيق المستقل الكامل (123 فحصاً آلياً ويدوياً ضد الشجرة `a4f22e65c`)
**المستودع:** `ahmdelbaz28-ux/ETAP-AI-WORK-` · **الإنتاج الحي:** HF Space `ahmdelbaz28/AhmedETAP-Platform` + واجهة Vercel SPA
**النطاق:** 41 إصلاحاً مرقّماً (FIX-01 ← FIX-41) + 5 تصحيحات تمهيدية (FIX-0.1 ← FIX-0.5) موزعة على 7 مراحل تنفيذية · نحو 60 ملفاً
**نتيجة التدقيق:** دقة حرفية 93–95% · صحة اتجاهية 100% · صفر محتوى مُلفَّق
**ما الجديد في 2.0:** خمسة تصحيحات جوهرية اكتشفها التدقيق (أخطرها FIX-17) وتسعة تصحيحات مطبعية — كل سطر هنا إمّا مطابق حرفياً للشجرة المدقَّقة أو مصحَّح بدليل مؤكد من المستودع نفسه.

---

## جدول المحتويات

1. [الملخص التنفيذي](#الجزء-الأول--الملخص-التنفيذي)
2. [المرحلة 0 — التصحيحات التمهيدية الخمسة](#الجزء-الثاني--المرحلة-0--التصحيحات-التمهيدية-الخمسة)
3. [الأخطاء المطبعية التسعة المصححة](#الجزء-الثالث--الأخطاء-المطبعية-التسعة-المصححة)
4. [قواعد التنفيذ الحاكمة](#الجزء-الرابع--قواعد-التنفيذ-الحاكمة)
5. [خريطة المراحل بالأرقام](#الجزء-الخامس--خريطة-المراحل-بالأرقام-محدثة-بتصحيحات-20)
6. [المرحلة 1 — الاستجابة الأمنية العاجلة (FIX-01←03)](#المرحلة-1--الاستجابة-الأمنية-العاجلة-يوم-0)
7. [المرحلة 2 — إخضار CI (FIX-04←08)](#المرحلة-2--إخضار-ci-يوم-1)
8. [المرحلة 3 — المصادقة والنتائج (FIX-09←13)](#المرحلة-3--المصادقة-والنتائج-يوم-12)
9. [المرحلة 4 — البيانات والإقلاع (FIX-14←16)](#المرحلة-4--البيانات-والإقلاع-يوم-23)
10. [المرحلة 5 — إعادة بناء النشر وتطهير التاريخ (FIX-17←21)](#المرحلة-5--إعادة-بناء-النشر-وتطهير-التاريخ-يوم-34)
11. [المرحلة 6 — P1: التحصين (FIX-22←31)](#المرحلة-6--p1-التحصين-الأسبوعان-12)
12. [المرحلة 7 — P2: النظافة والامتثال (FIX-32←41)](#المرحلة-7--p2-النظافة-والامتثال-الشهر-الأول)
13. [الجدول اليومي](#الجدول-اليومي-محدث-بتصحيحات-20)
14. [بوابة القبول النهائية Go/No-Go](#بوابة-القبول-النهائية-gono-go)
15. [ملخص التعديلات مقابل الخطة الأصلية](#ملخص-التعديلات-مقابل-الخطة-الأصلية-v10)
16. [التنبيه الأمني الحاسم](#التنبيه-الأمني-الحاسم-نفذه-الآن-قبل-أي-شيء)
17. [ملحق — منهجية التدقيق والأدلة](#ملحق--منهجية-التدقيق-والأدلة)

---

## الجزء الأول — الملخص التنفيذي

### نتيجة التدقيق المستقل باختصار

أُخضعت الخطة v1.0 لمراجعة مستقلة كاملة ضد نسخة المستودع عند `a4f22e65c`: نحو 98 فحصاً آلياً (سكربت تحقق كُتب لهذا الغرض) زائد 25 فحصاً يدوياً عميقاً — تاريخ Git الكامل (3387 حفظة غير مقتطعة)، وواجهة GitHub API لتوثيق تشغيلات CI الفعلية، وتشغيل حقيقي لأداتي `ruff` و`bandit`. النتيجة الإجمالية: **دقة حرفية 93–95%، وصحة اتجاهية 100%، وصفر محتوى مُلفَّق**. عشرات الكتل البرمجية المقتبسة في الخطة طابقت الشجرة حرفياً، وقياس `ruff format --check` أعاد فعلاً "2/1058 files" كما نصّت الخطة، وتسريبات LangWatch الثلاثة (`2bd77814`، `7f54e530`، `beef3343`) مؤكدة عبر `git log -S "sk-lw-"`.

لكن التدقيق كشف **عيبين تنفيذيين حقيقيين** كان سيسببان فشلاً فعلياً لو نُفّذت v1.0 حرفياً: قائمة FIX-17 البيضاء (6 عناصر) لا تطابق ما تنسخه فعلاً `sync-platforms.yml` إلى الـ Space (25 عنصراً — انحراف كان سينشر Space معطّلاً)، وتشخيص FIX-05 كان متقادماً (لا يوجد أي `sha1` في `etap_integration/etap_com.py` إطلاقاً؛ الحاجز الحقيقي أمام Bandit اليوم هو **B615** في `services/yolo/main.py:44`). كما رُصدت ثلاثة نقص توثيقيين (FIX-40، FIX-38، FIX-31) وتسعة أخطاء مطبعية. **الإصدار 2.0 يدمج كل التصحيحات في وثيقة واحدة قابلة للتنفيذ الحرفي.**

### أرقام الخطة

| البند | القيمة |
|---|---|
| إصلاحات مرقّمة | **41** (FIX-01 ← FIX-41) |
| تصحيحات تمهيدية من التدقيق | **5** (FIX-0.1 ← FIX-0.5 — تُطبَّق قبل أي تنفيذ) |
| تصحيحات مطبعية | **9** (أرقام أسطر ومسارات — لا تغيّر الاستنتاجات) |
| مراحل التنفيذ | **7** (أمان عاجل ← CI ← مصادقة ← بيانات ← نشر ← تحصين ← نظافة) |
| الملفات المتأثرة | ~60 ملفاً (8 بايثون خلفي، ~16 workflow/config، 4 جديدة، ~25 تحصين، ~20 نظافة) |
| زمن P0 الكامل | ~4 أيام مركزة (اليوم 0 حتى اليوم 4) |
| زمن P1 | أسبوعان (W1–W2) |
| زمن P2 | الشهر الأول (W3–W4) |

### معايير النجاح النهائية

الخطة تنتهي بنجاح فقط عندما تتحقق البوابة الخضراء كاملة (قسم Go/No-Go أدناه)، وخلاصتها:

1. **صفر سر حيّ** في المستودع أو تاريخه أو المحادثة — كل المفاتيح مدوَّرة ومسجّلة خارج المستودع.
2. **CI أخضر حقيقي ببوابتين فقط** لا يمكن أن تكذبا: Bandit أمر واحد مشترك، gitleaks يفرض فعلاً، صفر `continue-on-error` في البوابات الناجية، وB615 مغلق.
3. **مصادقة مغلقة بالكامل** — صفر نقطة نهاية مفتوحة، صفر نتيجة هندسية مزيفة.
4. **نشر حتمي واحد لكل منصة** مشروط بنجاح CI وSHA مثبّت، بقائمة بيضاء من 25 عنصراً مطابقة حرفياً لما يبنيه الـ Dockerfile، مع بوابة drift-check تمنع الانحراف مستقبلاً.
5. **نشر إنتاجي مستقر** — تمرين تراجع ناجح، /healthz حي، تنبيه وصل فعلاً، Postgres دائم تنجو الحسابات من إعادة تشغيله.

---

## الجزء الثاني — المرحلة 0 — التصحيحات التمهيدية الخمسة

> **هذه المرحلة شرط سابق لأي خطوة تنفيذية.** خمسة عيوب اكتشفها التدقيق في نص v1.0 نفسه — تطبيق v1.0 دون هذه التصحيحات كان سيفشل فعلياً (FIX-0.1 وحده كان سينشر Space ميتاً). كل تصحيح أدناه مُنفَّذ داخل نص v2.0 من أصله، والمُقدَّم هنا مرجع التطبيق السريع.

### FIX-0.1 — إصلاح العيب القاتل في FIX-17 (قائمة cd.yml البيضاء)

**المشكلة المكتشفة:** قائمة v1.0 البيضاء تحوي 6 عناصر فقط، بينما `sync-platforms.yml:157-190` ينسخ فعلياً **25 عنصراً**. الأسوأ: القائمة كانت تشمل `hf-space/nginx.conf` و`hf-space/supervisord.conf` — **وهما غير موجودين في المستودع أصلاً** (محتوى `hf-space/` الفعلي: `app.py` + `requirements.hf.txt` + `README.md` فقط). تنفيذ v1.0 حرفياً كان سينشر Space ناقصاً `api/ services/ engine/ core/ ...` — تطبيقاً ميتاً لحظة أول بناء، لأن root `Dockerfile` ينسخ هذه المجلدات صراحة (`Dockerfile:59-77`).

**القرار المحسوم بدليل التدقيق:** لا يُنشأ `nginx.conf` ولا `supervisord.conf` إطلاقاً — الـ Space يقلع مباشرة بـ `CMD ["python", "app.py"]` على المنفذ 7860 دون أي وسيط، وهو الوضع القائم الذي يعمل اليوم. (مسودة شات سابقة اقترحت "بناء الملفين من جديد"؛ الدليل يُسقط هذا الاقتراح: لا يوجد أي مرجع لهما في الـ Dockerfile أو إعدادات HF.) القائمة البيضاء القانونية أدناه مستخرجة **حرفياً** من `sync-platforms.yml:157-190` مع إسقاط العنصرين الوهميين.

**القائمة البيضاء القانونية (25 عنصراً — المصدر الوحيد لمحتوى الإنتاج):**

| # | المصدر في المستودع | الوجهة في الـ Space | ملاحظات |
|---|---|---|---|
| 1 | `README.hf.md` | `README.md` | ترويسة YAML الخاصة بـ HF |
| 2 | `Dockerfile` | `Dockerfile` | صورة الإنتاج (python:3.13-slim، منفذ 7860) |
| 3 | `.dockerignore` | `.dockerignore` | حرِج — بدونه يتجاوز البناء حد قرص HF |
| 4 | `VERSION` | `VERSION` | يقرأه التطبيق وقت الإقلاع |
| 5 | `prompts.json` | `prompts.json` | يحمله `agents/prompt_loader.py` |
| 6 | `compat.py` | `compat.py` | تستورده `hf-space/app.py` |
| 7 | `hf-space/` (كامل) | `hf-space/` | `app.py` + `requirements.hf.txt` + `README.md` — محتوياته الكاملة الفعلية |
| 8 | `agents/` | `agents/` | ملاحظة: `skills/` لا تُنسى عمداً (حد حجم ملفات HF؛ يحمّلها الوكيل من GitHub) |
| 9 | `prompts/` | `prompts/` | تعريفات 25 وكيلاً (`*.yaml` / `*.prompt.yaml`) |
| 10 | `core_model/` | `core_model/` | |
| 11 | `core/` | `core/` | |
| 12 | `engine/` | `engine/` | |
| 13 | `load_flow/` | `load_flow/` | |
| 14 | `fault_analysis/` | `fault_analysis/` | |
| 15 | `coordination/` | `coordination/` | |
| 16 | `relays/` | `relays/` | |
| 17 | `network_solver/` | `network_solver/` | |
| 18 | `services/` | `services/` | |
| 19 | `api/` | `api/` | |
| 20 | `utils/` | `utils/` | |
| 21 | `ai_context_engine/` | `ai_context_engine/` | |
| 22 | `integrations/` | `integrations/` | يشمل `siem_syslog.py` الموصَّل |
| 23 | `ml/` | `ml/` | |
| 24 | `data/` | `data/` | بعد `rm -f ./data/*.db*` — قواعد وقت التشغيل لا تُشحن |
| 25 | `ui-dist/` | `ui-dist/` | قطعة UI **المبنية في هذا التشغيل** (artifact)، ليست الملتزَمة |

**بوابة drift-check (تعزيز 2.0):** قبل النسخ يستخرج السكربت كل مصادر `COPY` العليا من root `Dockerfile` ويتحقق أن كلها موجودة في المنسخ — فإذا أضاف مطوّر مستقبلاً مجلداً جديداً إلى الـ Dockerfile ونسي القائمة، فشل النشر صريحاً بدل أن يبني Space ناقصاً. النص الكامل لـ `cd.yml` في [المرحلة 5](#المرحلة-5--إعادة-بناء-النشر-وتطهير-التاريخ-يوم-34).

### FIX-0.2 — إعادة توجيه FIX-05 إلى المشكلة الفعلية (B615)

**المشكلة المكتشفة:** تشخيص v1.0 قديم — ادّعى وجود B324 (`sha1`) في `etap_integration/etap_com.py` مع nosec. التدقيق أسقط الادعاء: لا يوجد أي `sha1` في هذا الملف في كامل التاريخ (`git log -S "sha1"` عليه فارغ)، وتشغيل Bandit بمعاملات `ci.yml` الحرفية على الشجرة نظيف. **العائق الحقيقي الوحيد اليوم هو B615:**

```
services/yolo/main.py:44 — تحميل نموذج من HuggingFace دون تثبيت revision
```

وهو خطر سلسلة توريد: أي تغيير في المستودع الأعلى يتسلل إلى بنيتك. **التصحيح** — تثبيت الـ revision على hash حفظة محدد (استبدل `YOUR_MODEL_COMMIT_SHA` بـ SHA فعلي تتحقق منه مرة واحدة من صفحة النموذج ← Files ← محفظة إصدار مستقر؛ لا فرعاً متحركاً):

```python
def download_model():
    """Download the DocLayout-YOLO model from HuggingFace (pinned revision)."""
    filepath = hf_hub_download(
        repo_id="juliozhao/DocLayout-YOLO-DocStructBench",
        filename="doclayout_yolo_docstructbench_imgsz1024.pt",
        revision="YOUR_MODEL_COMMIT_SHA",  # B615 fix: pin model revision (supply-chain)
    )
```

بقية FIX-05 (الـ composite action الموحّد لـ Bandit وإنهاء حرب النطاقات الثلاثة) كما هي — تفاصيله في [المرحلة 2](#المرحلة-2--إخضار-ci-يوم-1). لا تعديل لأي ملف في `etap_integration/`.

### FIX-0.3 — تصحيح أمر تثبيت Ruff في FIX-04

**المشكلة:** أمر v1.0 `pip install "ruff==$(grep -oP 'ruff==\K...' ci-cd.yml)"` مكسور — لا يوجد أي `ruff==` في أي workflow؛ سطر CI الفعلي هو `ci-cd.yml:43` ويستخدم `ruff>=0.8.4`.

**التصحيح:**

```bash
pip install --only-binary :all: "ruff>=0.8.4"   # يطابق CI حرفياً
```

### FIX-0.4 — استكمال FIX-40 (تصدير SIEM Syslog)

**المشكلة:** وصف v1.0 لـ FIX-40 كان ناقص التوثيق لا كاذباً — المستودع يحوي فعلاً `integrations/siem_syslog.py`: مُصدِّر **RFC 5424** كامل (UDP 514 / TCP / TLS 6514 عبر متغير `SIEM_ENABLED`)، **وموصَّل فعلياً** في `api/agents.py:826,843` و`services/agent_safety.py:40`.

**التصحيح:** يتحول الإصلاح إلى ثلاث خطوات توثيقية وتشغيلية:

1. تأكيد تسجيل `siem_syslog.py` في `integrations/__init__.py` وتوثيق نقاط الربط الثلاث أعلاه.
2. اختبار وحدة لتصدير RFC 5424: timestamps UTC، structured-data سليم، وسلوك صامت-آمن عند تعطيل المُصدِّر.
3. قرار تشغيل/تعطيل واعٍ عبر متغيرات البيئة (`SIEM_ENABLED` + هدف الـ syslog) — لا افتراضي صامت؛ وينعكس القرار في README (بند FIX-40 الكامل في المرحلة 7).

### FIX-0.5 — تقليص FIX-38 (.dockerignore)

**المشكلة:** نحو نصف عناصر v1.0 موجودة أصلاً في `.dockerignore` (`docs/` سطر 69، `reports/` سطر 48، `tests/` سطر 78)، و`skills/` مستثنى **عمداً** بتعليق تشغيلي صريح (`!skills/*.md` سطر 75 — الصورة المحلية تحتاج ملفات skills المعرفية؛ والـ Space لا يستقبلها أصلاً لأن قائمة cd.yml هي البوابة).

**التصحيح — الإضافة الفعلية المتبقية فقط:**

```gitignore
archive/
acp_runtime/
ts-service/
*.duckdb*
```

لا تُضِف `skills/` (ستكسر الصور المحلية بلا داعٍ). الخلاصة المعمارية: `.dockerignore` يمنع "بناء صورة أوسع"، و`cd.yml` whitelist يمنع "نشر محتوى أوسع" — طبقتان مختلفتان، كلاهما لازم.

---

## الجزء الثالث — الأخطاء المطبعية التسعة المصححة

> لا تغيّر الاستنتاجات، لكنها ضرورية للدقة — كلها مثبتة ضد الشجرة `a4f22e65c`. إذا انزاحت أرقام الأسطر بحفظات لاحقة فالاقتباسات البرمجية داخل كل إصلاح هي المرساة المعتمدة: حدّد الموضع بالمحتوى لا بالرقم وحده.

| # | الموضع في v1.0 | الصواب المؤكد |
|---|---|---|
| 1 | آخر COE في `unified-cicd.yml` عند السطر 140 | عند السطر **141** (القائمة الكاملة: 37, 41, 45, 71, 75, 79, 102, 107, 116, 141) |
| 2 | `/healthz` في `hf-space/app.py:645` | عند السطر **584** (تعريف `@app.get("/healthz")` مؤكد) |
| 3 | `modernization-showcase.yml` "cosmetic cron" | مُشغَّل بحدث **push** إلى main (دون cron) — يبقى حذفه صائباً لأن قيمته صفرية |
| 4 | خطوات terraform COE عددها 8 | **13** موزعة: `terraform.yml`(1) + `terraform-apply.yml`(3) + `iac-validation.yml`(9) |
| 5 | bind-mounts في `docker-compose.override.yml` عددها 45 | **56** |
| 6 | مسار helm: `helm lint helm/etap-platform` | المسار الصحيح **`helm/etap-ai`** (v2.1.0)؛ والمنشور في release هو `infra/helm/etap-ai` (v2.0.0) عبر `etap-infra-release.yml:45-50`؛ والقديم `charts/etap-ai` (v1.0.0) |
| 7 | FIX-31: "pin كل الأكشنز بما فيها trivy-action@master و trufflehog@main" | `trivy-action` مثبَّت أصلاً بـ SHA في `ci-cd.yml` (`ed142fd0…`) و`setup-python` مثبَّت في `ci.yml`؛ **المتبقي غير المثبَّت فعلاً**: `docker-validation.yml:255` (trivy@master)، `etap-infra-validate.yml:92` (dorny/test-reporter@v1)، `sonarcloud-pr.yml:105` (sonarqube-quality-gate-action@v1.2.1)، و`unified-cicd.yml:110` (trufflehog@main — يُحذف الملف كله في FIX-07) |
| 8 | Dockerfile: الافتراضي SQLite عند ":36" تقريباً | المرساة الدقيقة: `ENV DATABASE_URL=sqlite+aiosqlite:…` عند **`Dockerfile:98`**، و`mkdir /tmp/data` عند :36 (يبقى للمخازن المؤقتة)، و`ENVIRONMENT=production` عند :101 |
| 9 | FIX-16: "REPLACE: COPY ui-dist /usr/share/nginx/html" | الواقع: لا nginx إطلاقاً — `COPY --chown=user:user ui-dist/ /app/ui-dist/` عند **`Dockerfile:83-84`** والواجهة تُخدم من `app.py` على المنفذ 7860 |

---

## الجزء الرابع — قواعد التنفيذ الحاكمة

### القاعدة الذهبية: الترتيب غير قابل للتبديل

المراحل مرتبة هندسياً لسببين حاسمين: **أي مفتاح لم يُدوَّر قبل يوم العمل الأول يجعل كل ما بعده بلا قيمة** (المستودع عام والتاريخ محفوظ)، و**أي إعادة كتابة لتاريخ Git قبل إنهاء إصلاحات الملفات نفسها ستضطر للتكرار** (كل force-push مكلف وخطِر). لذلك التسلسل ثابت: أمان عاجل ← إخضار CI ← مصادقة ← بيانات ← نشر وتطهير تاريخ (آخر خطوة عن قصد) ← تحصين ← نظافة.

### أهم 5 قواعد أثناء التنفيذ (لا انتهاك لأي منها)

1. **لا يُكتب أي سر في أي ملف، أبداً.** الأسرار تعيش فقط في GitHub Secrets وHF Space Secrets ومنصات المزوّدين. هذه الوثيقة نفسها لا تحتوي أي قيمة سرية — فقط أسماء المتغيرات.
2. **لا push مباشر إلى main طوال الإصلاح.** كل إصلاح = فرع + PR + مراجعة، حتى إصلاحات سطر واحد.
3. **النشر التلقائي مجمّد** من FIX-03 حتى نهاية FIX-17. ما يُنشر يدوياً فقط، وعلى قرارك أنت.
4. **كل PR يجب أن يمر بمعيار الإنجاز (SP-5):** التحقق المحدد في إصلاحه + gitleaks نظيف + لا `continue-on-error` جديد. وإذا لمس الإصلاح محتوى النشر إلى HF Space فيجب أن يجتاز بوابة drift-check (FIX-17).
5. **سجّل كل تدوير مفتاح في سجل خارج المستودع** (ملف محلي / مدير أسرار) — تاريخ من دوّر ماذا ومتى، لأن تاريخ Git نفسه سيُمسح في FIX-21.

### بروتوكولات الأمان الحاكمة (ملخص SP-0 ← SP-8)

| البروتوكول | جوهره |
|---|---|
| SP-0 | فروع ودمج: فرع لكل إصلاح، PR إلزامي، حماية `main` مفعّلة من يوم 0 |
| SP-1 | دورة حياة الأسرار: توليد، تخزين، تدوير، وسجل تدوير خارج المستودع |
| SP-2 | إعادة كتابة تاريخ Git: تجميد ← filter-repo ← force-push ← إعادة استنساخ — خطوة أخيرة فقط |
| SP-3 | نظافة بيئة العمل: لا أسرار في `.env` المتتبَّع، لا لصق أسرار في المحادثة أو الأدوات |
| SP-4 | بوابات المراجعة والدمج: لا دمج على أحمر، لا تخطي فحوص |
| SP-5 | معيار الإنجاز: التحقق المحدد لكل إصلاح + gitleaks نظيف + drift-check عند مس النشر |
| SP-6 | التراجع: لكل إصلاح خطة عكس موثقة + تمرين rollback يدوي حقيقي (FIX-20) |
| SP-7 | ممنوعات مطلقة: لا `continue-on-error` جديد، لا COE، لا `|| true` في بوابات حقيقية |
| SP-8 | الطوارئ: إذا تسرب شيء وسط الإصلاح — إبطال فوري ثم تدوير ثم توثيق قبل المتابعة |

---

## الجزء الخامس — خريطة المراحل بالأرقام (محدثة بتصحيحات 2.0)

| المرحلة | الإصلاحات | الأولوية | عدد الملفات | الزمن | النتيجة القابلة للقياس |
|---|---|---|---|---|---|
| **0 — تصحيحات تمهيدية** | FIX-0.1 ← 0.5 | شرط سابق | نص الخطة نفسه | قبل البدء | v2.0 قابلة للتنفيذ الحرفي بلا عيوب قاتلة |
| **1 — الاستجابة الأمنية العاجلة** | FIX-01 ← 03 | P0-BLOCKER | 5 ملفات + 15+ سر خارجي | يوم 0 (2–4 ساعات) | صفر سر حي في المستودع، والنشر المتسابق مجمّد |
| **2 — إخضار CI** | FIX-04 ← 08 | P0 | ~20 workflow + 2 config + `services/yolo/main.py` | يوم 1 | `main` أخضر ببوابتين لا يمكن أن تكذبا؛ B615 مغلق |
| **3 — المصادقة والنتائج** | FIX-09 ← 13 | P0 | 6 ملفات بايثون | يوم 1–2 | صفر نقطة نهاية مفتوحة، صفر نتيجة مزيفة |
| **4 — البيانات والإقلاع** | FIX-14 ← 16 | P0 | 4 ملفات + أسرار HF | يوم 2–3 | Postgres دائم + إقلاع fail-closed |
| **5 — إعادة بناء النشر** | FIX-17 ← 21 | P1 | 6 workflows + تاريخ Git | يوم 3–4 | نشر واحد لكل منصة بـ whitelist من 25 عنصراً، مشروط بـ CI، وتاريخ نظيف |
| **6 — التحصين** | FIX-22 ← 31 | P1 | ~25 ملفاً | أسبوع 1–2 | قابلية التوسع والمراقبة والاعتماديات |
| **7 — النظافة والامتثال** | FIX-32 ← 41 | P2 | ~20 ملفاً | الشهر الأول | مستودع بلا وزن ميت أو ادعاءات كاذبة |

---

## المرحلة 1 — الاستجابة الأمنية العاجلة (يوم 0)

> **P0-BLOCKER — خلال 2–4 ساعات، قبل أي شيء آخر.** لا تلمس أي إصلاح آخر قبل إنجاز هذه المرحلة كاملة.

### FIX-01 — تدوير كل سر مُخترَق

- **الأولوية:** P0-BLOCKER · **اليوم:** 0 · **البروتوكول:** SP-1، SP-3 · **الزمن:** ~2 ساعة
- **لماذا أولاً:** الـ PAT المستخدم الآن هو نفسه الموثَّق داخل المستودع العام (`github_pat_11CCHF…` في 4 ملفات متتبَّعة). أي شخص على وجه الأرض يستطيع الكتابة إلى الحساب حتى إنجاز هذه الخطوة. كل الإصلاحات الأخرى بلا معنى ما دامت بيانات اعتماد مسرّبة حية.

**ترتيب التدوير (الأخطر أولاً):**

| الترتيب | السر | أين سُرّب / الخطر | أين يُدوَّر | قيد النسخة الجديدة |
|---|---|---|---|---|
| 1 | **GitHub PAT** (`github_pat_11CCHF…`) | مستندات المستودع العام ← كتابة كاملة على الحساب | github.com ← Settings ← Developer settings ← Fine-grained tokens ← **Revoke** | PAT دقيق جديد: صلاحية **90 يوماً**، وصول لـ `ETAP-AI-WORK-` فقط، **Contents: Read-only** + Secrets:write فقط إن لزمها workflow فعلاً |
| 2 | HuggingFace `HF_TOKEN` | خط مزامنة الـ Space الحي | hf.co ← Settings ← Access Tokens ← إبطال، جديد fine-grained (كتابة: للـ Space فقط) | حدّث سر GitHub `HF_TOKEN` |
| 3 | رمزا Vercel (`vcp_*` ×2) | وثيقة الحادث | vercel.com ← Settings ← Tokens ← حذف الاثنين | رمز واحد جديد، النطاق: المشروع فقط |
| 4 | مفاتيح Supabase (`sb_publishable_*`، `sb_secret_*`، `sbp_*` ×3) | وثيقة الحادث + مستخدمة في قاعدة الإنتاج | supabase.com ← Project ← Settings ← API ← **Rotate** | حدّث أسرار HF/Vercel/GitHub؛ هذا أيضاً اعتماد قاعدة الإنتاج — خطط FIX-14 معه |
| 5 | زوج Langfuse `sk-lf-*` | وثيقة الحادث | لوحة Langfuse ← API keys | حدّث أسرار GitHub |
| 6 | LangWatch `sk-lw-*` | سُرّب في تاريخ `.env.example` (الحفظات `2bd77814`، `7f54e530`، `beef3343`) | لوحة LangWatch | حدّث أسرار GitHub |
| 7 | NVIDIA `nvapi-*` | كشف في المحادثة | build.nvidia.com | حدّث حيث يُستهلك |
| 8 | مفتاح Resend | كشف في المحادثة | resend.com | حدّث `RESEND_API_KEY` (سر HF) |
| 9 | اعتمادا Neo4j + Auth0 | كشف في المحادثة | لوحات المزوّدين | حدّث الأسرار |
| 10 | رموز Daytona / CodeSandbox / SonarCloud | كشف في المحادثة | لوحات المزوّدين | حدّث `SONAR_TOKEN` في أسرار GitHub |
| 11 | **كل سر لُصق في المحادثة** | نص المحادثة نفسه ناقل تسريب | كل ما سبق | اعتبره محروقاً بغض النظر عن حالة المستودع |

**قواعد التوليد (SP-3):**

```bash
# كل الأسرار العشوائية (JWT، مفاتيح API التي تصدرها بنفسك):
python -c "import secrets; print(secrets.token_hex(32))"
```

**تحديث المستهلكين (الترتيب مهم حتى لا تشتغل CI برمز ميت):**
1. GitHub ← Repo ← Settings ← Secrets and variables ← Actions: حدّث `HF_TOKEN`، `VERCEL_TOKEN`، `VERCEL_ORG_ID`، `VERCEL_PROJECT_ID`، `SONAR_TOKEN`، `GH_PAT` (الجديد)، مفاتيح Langfuse/LangWatch.
2. HF Space ← Settings ← Variables and secrets: مفاتيح التطبيق (`RESEND_API_KEY`، مفاتيح المزوّدين…).
3. Vercel ← Project ← Settings ← Environment Variables.
4. `.env` المحلي (غير متتبَّع فقط).

**التحقق (SP-5):** الـ PAT القديم مرفوض `git ls-remote https://<OLD_PAT>@github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git` ← **401/403**؛ الجديد ← **200**؛ أطلق `secret-scan.yml` يدوياً ← أخضر؛ وسجّل كل تدوير في السجل الخاص.

**التراجع:** لا حاجة ولا ممكن — التدوير أحادي الاتجاه بالتصميم.

### FIX-02 — إزالة وثائق الأسرار المسرّبة من HEAD

- **الأولوية:** P0-BLOCKER · **اليوم:** 0 · **البروتوكول:** SP-0، SP-8 · **الزمن:** ~15 دقيقة
- **الملفات (حذف):** `docs/archive/SECURITY_INCIDENT_2026-07-08.md` (يحوي الـ PAT الحي + دفعة الأسرار كاملة: Vercel `vcp_*`×2، Supabase `sb_secret_*`، Langfuse `sk-lf-*`، LangWatch `sk-lw-*`)، و`docs/generated/OPERATOR_ACTION_ITEMS.md`، و`docs/generated/TEST_REPORT.md`، و`docs/archive/agent.md`.

```bash
git checkout -b fix/FIX-02-remove-leaked-docs
git rm docs/archive/SECURITY_INCIDENT_2026-07-08.md \
       docs/generated/OPERATOR_ACTION_ITEMS.md \
       docs/generated/TEST_REPORT.md \
       docs/archive/agent.md
git commit -m "fix(FIX-02): remove documents containing live secrets from HEAD (rotation in progress, history purge scheduled at FIX-21)"
git push -u origin fix/FIX-02-remove-leaked-docs
# افتح PR ← ادمج إلى main
```

- **ملاحظة حاكمة:** تبقى هذه الملفات في تاريخ Git حتى FIX-21 — وهذا مقبول **فقط لأن** FIX-01 أبطال كل قيمة فيها أصلاً. **لا تنفّذ FIX-02 أبداً دون FIX-01.**
- **التحقق:** `git grep -l "github_pat_11CCHF" HEAD` ← فارغ؛ وفرق الـ PR يُظهر 4 حذفات بالضبط.
- **التراجع:** `git revert` للدمج — لكن إعادة إضافة هذه الملفات تسريب جديد وستضرب بوابة gitleaks الجديدة بعد FIX-06 على أي حال.

### FIX-03 — تجميد خطوط النشر المتسابقة

- **الأولوية:** P0-BLOCKER · **اليوم:** 0 · **البروتوكول:** SP-0 · **الزمن:** ~10 دقائق
- **لماذا:** ثلاثة ناشري HF + ناشرا Vercel يدفعون محتوى مختلفاً بالقوة عند كل دمج. أثناء الإصلاح سينشرون كوداً نصف مُصلَحاً ويعيدون مزامنة الوثائق المسرّبة إلى الـ Space. جمّد كل شيء الآن. (المستودع فعلياً يحمل 65+ workflow؛ سبعة منها خطوط نشر/تمثيل تُجمَّد هنا وتُحذف لاحقاً في FIX-07/18.)

```bash
gh workflow disable sync-to-hf.yml
gh workflow disable sync-hf-space.yml
gh workflow disable sync-platforms.yml
gh workflow disable trigger-vercel.yml
gh workflow disable ci-cd.yml        # يحوي مهمتي deploy + مولد التغطية المزيف
gh workflow disable deploy.yml       # echo stubs
gh workflow disable unified-cicd.yml # 10× COE تمثيلية
```

- **وكذلك الآن (GitHub Settings ← Branches):** طبّق حماية فرع SP-0 على `main` (إلزام PR + الفحوصات الإلزامية الموجودة أصلاً مثل `secret-scan`).
- **التحقق:** `gh workflow list --all` يُظهر السبعة معطلة؛ ادفع حفظة تافهة ← تنطلق فقط الـ workflows الناجية، **ولا تبدأ أي مزامنة Space** (لا طابع "Synced" جديد في صفحة الـ Space).
- **التراجع:** `gh workflow enable <file>` — لكن لا تعِد تفعيل الناشرين قبل وجود FIX-17.

---

## المرحلة 2 — إخضار CI (يوم 1)

> **P0 — من "أخضر تمثيلي" إلى "أخضر حقيقي".** هدف اليوم: `main` أخضر ببوابتين فقط لا يمكن أن تكذبا، وB615 مغلق.

### FIX-04 — إصلاح فشل lint الحي (ruff format على الملفين المنحرفين) — مصحَّح في 2.0

- **الأولوية:** P0 · **اليوم:** 1 · **الزمن:** ~20 دقيقة
- **الواقع المؤكد:** `ruff format --check` يفشل فعلاً على ملفين من أصل 1058. أمر تثبيت v1.0 كان مكسوراً — الصواب (تصحيح 2.0):

```bash
pip install --only-binary :all: "ruff>=0.8.4"   # يطابق ci-cd.yml:43 حرفياً
ruff format <الملفان المنحرفان>
ruff format --check .   # التحقق: 1058/1058
```

- **التحقق:** `ruff format --check .` ← صفر انحراف؛ وأضِف خطوة `ruff format --check` إلى البوابة الناجية إن لم تكن موجودة كي لا يعود الانحراف.

### FIX-05 — إنهاء حرب Bandit الثلاثية بأمر واحد مشترك + إغلاق B615 — تشخيص مصحَّح في 2.0

- **الأولوية:** P0 · **اليوم:** 1 · **البروتوكول:** SP-5، SP-0 · **الزمن:** ~45 دقيقة
- **السبب الجذري (مؤكد من التشغيلات `35100029065`، `35100029195`):** ثلاث خطوط تعرّف Bandit بثلاث طرق:
  - `ci.yml:187` ← `bandit -r api/ agents/ etap_integration/ -ll` (بلا ini، نطاق `etap_integration/`)
  - `security.yml:190` ← `bandit -r . -x ... -ll -ii` (بلا ini، نطاق مختلف = 51,759 سطراً)
  - `ci-cd.yml:489` ← `bandit --ini .bandit -r api services core integrations agents engine load_flow fault_analysis coordination relays network_solver utils ai_context_engine ml -ll -ii` (مع ini، نطاق ثالث يستثني `etap_integration/`)

  إصلاح حفظة واحدة لا يمكنه أن يجعل الثلاثة خضراء — هم يختلفون على تعريف "نظيف". المستودع يملك أصلاً `.bandit` منقّى (تخطّات B104/B108/B608/B102/B310/B404/B603/B607/B501/B311 مع مبررات موثقة) — الـ workflows ببساطة لا تستخدمه باستمرار.
- **تصحيح تشخيص 2.0:** ادعاء v1.0 بوجود B324 (sha1) في `etap_com.py` **سقط بالتدقيق** — الحاجز الفعلي الوحيد للنطاق الواسع هو **B615** في `services/yolo/main.py:44` (انظر FIX-0.2 أعلاه للكود الكامل).

**إنشاء** `.github/actions/bandit-scan/action.yml`:

```yaml
name: 'Bandit Scan (single source of truth)'
description: >
  The ONE canonical Bandit invocation. Every pipeline that wants a Bandit
  gate MUST call this composite action — never re-declare flags inline.
  Scope = all production Python. Config = the curated repo .bandit ini.
inputs: {}
runs:
  using: 'composite'
  steps:
    - name: Install pinned bandit
      shell: bash
      run: pip install --quiet "bandit==1.7.10"
    - name: Run Bandit (curated .bandit config, production scope)
      shell: bash
      run: |
        set -euo pipefail
        bandit --ini .bandit -ll -ii --format txt \
          -r api/ agents/ engine/ core/ core_model/ services/ security/ \
             guards/ scada_protocols/ etap_integration/ gis_integration/ \
             gis_model/ hf-space/
```

**تعديل** مواضع الاستدعاء الثلاثة — استبدل كل كتلة `run:` داخلية بـ:

```yaml
      - name: Bandit (shared gate)
        uses: ./.github/actions/bandit-scan
```

في: `ci.yml:187`، `security.yml:190`، `ci-cd.yml:489` (ci-cd يموت عند FIX-18؛ عدّله مع ذلك ليكون يوم التجميد متماسكاً). ثم عدّل `services/yolo/main.py:44` بتثبيت revision (كود FIX-0.2).

**التحقق:**

```bash
bandit --ini .bandit -ll -ii -r api/ agents/ engine/ core/ core_model/ services/ security/ guards/ scada_protocols/ etap_integration/ gis_integration/ gis_model/ hf-space/ && echo BANDIT_CLEAN
```

ثم ادفع ← **الخطوط الثلاثة تُظهر نتائج Bandit متطابقة**. وتأكد اختفاء B615 صراحة: `bandit -r services/yolo/ -ll` ← صفر نتائج B615. إذا ظهرت نتائج bandit أخرى في النطاق الواسع، عالجها في هذا الـ PR نفسه — لا تُعِد restore لأي COE.

### FIX-06 — جعل فاحص الأسرار يفرض فعلاً (gitleaks + allowlist + npm audit)

- **الأولوية:** P0 · **اليوم:** 1 · **البروتوكول:** SP-1، SP-7 · **الزمن:** ~30 دقيقة
- **الإجراء:** `secret-scan.yml:36-47` أضِف `--baseline-path` (بإبقاء COE محذوفاً) كي يفشل الفحص على أي تسريب جديد؛ تقليص allowlist في `.gitleaks.toml:67-80` بحذف `.env.example` و`docs/**.md` و`SECURITY_INCIDENT*` (كانت تخفي التسريبات الموثقة نفسها)؛ و`.npmrc`: `audit=false` ← `audit=true`.
- **التحقق:** أثبت أن الفاحص يستطيع الفشل — أضف مؤقتاً سطر مفتاح مزيف في فرع اختبار ← يجب أن يضرب gitleaks؛ ثم احذفه. بعد FIX-21 يعمل gitleaks بلا baseline على التاريخ الكامل ← exit 0.

### FIX-07 — حذف الـ workflows المزيفة/الميتة/المكررة (12 ملفاً)

- **الأولوية:** P0 · **اليوم:** 1 · **الزمن:** ~40 دقيقة
- **الإجراء:** حذف 12 workflow ميتاً أو مزيفاً أو مكرراً (منها `unified-cicd.yml` بعشر بوابات COE تمثيلية، و`modernization-showcase.yml` المُشغَّل بـ push بلا قيمة، و`load-test.yml:543-558` ببوابة `if: always()` زائفة) مع دمج ما يستحق الدمج (quality-gates). القائمة الحرفية بالأسماء في الوثيقة المفصلة.
- **التحقق:** بعد الدمج، الدفع إلى main يشغّل البوابات الناجية فقط؛ `rg -l "continue-on-error: true" .github/workflows/` تتقلص قائمتها للملفات التي ستعالجها FIX-08.

### FIX-08 — إزالة كل آلية مرور صامت من البوابات الحقيقية الناجية

- **الأولوية:** P0 · **اليوم:** 1–2 · **البروتوكول:** SP-7 · **الزمن:** ~60 دقيقة
- **الإجراء (مواضع مؤكدة):** إزالة `|| true` من `ci.yml:176,186` (pip-audit / pnpm audit)؛ إزالة `continue-on-error` من `sonarcloud-pr.yml:76,108` مع تفعيل بوابة new-code؛ إزالة COE على مستوى الـ job من `no-mock-in-prod.yml:22`؛ `semgrep.yml:96`؛ `|| echo "non-blocking"` من `ui-tests.yml:33`؛ COE عن خطوة build+push في `publish-engineering-service.yml:154`؛ إضافة `set -euo pipefail` قبل pytest في `etap-boundary-tests.yml:43`؛ وإزالة COE + `if: always()` من بوابة `load-test.yml` (أو أرشف الملف).
- **التحقق:** `rg "continue-on-error: true" .github/workflows/` ← 0 في البوابات الناجية؛ `rg '\|\| true' .github/workflows/` و`rg 'non-blocking'` ← 0.

---

## المرحلة 3 — المصادقة والنتائج (يوم 1–2)

> **P0 — إغلاق ثغرات المصادقة الأربع + قتل النتائج الهندسية المزيفة.**

### FIX-09 — إغلاق نقاط النهاية الثلاث غير الموثَّقة

- **الأولوية:** P0 · **اليوم:** 2 · **الزمن:** ~60 دقيقة
- **النقاط الثلاث (مواضع مؤكدة):**
  - **FIX-09-a** — `api/studies.py:335-341` (`POST /api/v1/studies/re-run`): إضافة `Depends(get_api_key)` (مع `require_permission("studies","write")` اختيارياً).
  - **FIX-09-b** — `api/tool_policy.py:18` + النقطة عند 237–245 (`POST /api/v1/tool-policy/evaluate`): حماية على مستوى الـ Router: `dependencies=[Depends(get_api_key)]`.
  - **FIX-09-c** — `api/validation.py:18` + النقطة عند 21–28 (`POST /api/v1/system/validate`): الحماية نفسها على مستوى الـ Router.
- **التحقق:** الطلبات الثلاثة بلا مفتاح ← **401**؛ بمفتاح صالح ← سلوك طبيعي؛ واختبارات انحدار تمنع ارتدادها.

### FIX-10 — WebSocket fail-closed لموافقات التحكم المزدوج

- **الأولوية:** P0 · **اليوم:** 2 · **الزمن:** ~45 دقيقة
- **الملف:** `hf-space/app.py:1053-1057` — WebSocket الثنائي (dual-control) كان يقبل الاتصال دون مفتاح مُعدّ.
- **الإجراء:** تحويله fail-closed: غياب `ENGINEERING_SERVICE_API_KEY` ← رفض الاتصال فوراً (إغلاق 1011)؛ مفتاح خاطئ ← رفض 4001.
- **التحقق:** اتصال بلا مفتاح ← إغلاق 1011؛ بمفتاح خاطئ ← 4001؛ بمفتاح صالح ← سير طبيعي.

### FIX-11 — افتراضي fail-closed في `verify_api_key` (staging + البيئات المجهولة)

- **الأولوية:** P0 · **اليوم:** 2 · **الزمن:** ~30 دقيقة
- **الملف:** `api/shared_handlers.py:355-363` — قيم `staging` وغير المعروفة من `ENVIRONMENT` كانت تُعامل كتطوير (فتحة مصادقة).
- **الإجراء:** deny-by-default: أي بيئة غير `development` تُعامل كإنتاج وتتطلب مفتاحاً صالحاً.
- **التحقق:** `ENVIRONMENT=staging` أو unset ← كل الطلبات المحمية تتطلب مفتاحاً؛ `development` فقط هو المفتوح.

### FIX-12 — تحصين سر JWT (قائمة سوداء + لا fallback تطويري صامت خارج التطوير)

- **الأولوية:** P0 · **اليوم:** 2 · **الزمن:** ~45 دقيقة
- **الملف:** `api/dependencies.py:36-58, 64-67`.
- **الإجراء:** قائمة سوداء بأسرار JWT المعروفة/الplaceholder + إضافة placeholder الـ `.env.example` إليها؛ منع أي fallback تطويري صامت خارج بيئة التطوير؛ رفض الإقلاع على سر ضعيف في غير التطوير (بالتنسيق مع FIX-15).
- **التحقق:** إقلاع بـ placeholder الـ `.env.example` في الإنتاج ← فشل صريح؛ في التطوير ← تحذير ومتابعة.

### FIX-13 — قتل النتائج الهندسية المزيفة

- **الأولوية:** P0 · **اليوم:** 3 · **الزمن:** المرحلة A ~30 دقيقة / المرحلة B مشروع
- **الملف:** `api/services/study_execution_service.py:84-96` — كتلة نتائج `BUS-1/BUS-2` المزيفة (قيم مثل 0.42 تُحقن في DB بلا محرك حقيقي).
- **الإجراء على مرحلتين:**
  - **المرحلة A (فورية):** حذف كتلة النتائج المزيفة ← الرفض الصريح `501 Not Implemented` مع رسالة "المحرك الحقيقي غير موصول بعد".
  - **المرحلة B (لاحقاً):** توصيل `StudyExecutor` الحقيقي — قرار معماري منفصل لا يُحشى في P0.
- **التحقق:** `/studies/re-run` ← 501 صريح (المرحلة A) أو نتائج محرك حقيقي (B)؛ `rg "BUS-1" api/` ← 0؛ صفر صفوف نتائج مزيفة في DB.

---

## المرحلة 4 — البيانات والإقلاع (يوم 2–3)

> **P0 — Postgres دائم + إقلاع fail-closed + واجهة حديثة بلا شريط DEMO كاذب.**

### FIX-14 — Postgres دائم للـ Space (موت SQLite الحتمي) — مراسي مصحَّحة في 2.0

- **الأولوية:** P0 · **اليوم:** 3 · **الزمن:** ~3 ساعات
- **المراسي الدقيقة (مصحَّحة):** الافتراضي SQLite عند `ENV DATABASE_URL=sqlite+aiosqlite:…` — **`Dockerfile:98`**؛ `mkdir /tmp/data` عند :36 (يبقى للمخازن المؤقتة فقط)؛ `ENVIRONMENT=production` عند :101. SQLite على قرص الـ Space المؤقت يعني **فقدان كل حساب عند كل إعادة بناء** — موت حتمي لا خطر نظري.
- **الإجراء:** إزالة الافتراضي SQLite من Dockerfile؛ ربط `DATABASE_URL` بـ Postgres دائم (Supabase/مكوّن HF Postgres) من الأسرار؛ تشغيل `alembic upgrade head` عند الإقلاع؛ ومتغير `ALLOW_SQLITE_IN_PROD` (للتطوير المحلي فقط) لا يُقبل في الإنتاج.
- **التحقق:** إعادة تشغيل الـ Space تحفظ الحسابات؛ `rg ALLOW_SQLITE_IN_PROD` ← 0 في الكود والأسرار الإنتاجية؛ الهجرة الجافة (خطوة 6) ناجحة قبل القطيعة.

### FIX-15 — بيئة إقلاع إلزامية (فشل الإقلاع بدل الفشل الصامت)

- **الأولوية:** P0 · **اليوم:** 3 · **الزمن:** ~45 دقيقة
- **الإجراء:** قائمة متغيرات إقلاع إلزامية (قاعدة البيانات، أسرار المصادقة، `ENVIRONMENT`) — أي ناقص ← **رفض إقلاع صريح برسالة تسمّي المتغير الناقص**، بدل إقلاع "يشتغل" بمزايا معطلة بصمت.
- **التحقق:** احذف متغيراً إلزامياً في بيئة تجريبية ← رفض إقلاع مسمّي؛ أعد الضبط ← إقلاع نظيف.

### FIX-16 — واجهة حديثة في الإنتاج + شريط demo صادق — توصيف مصحَّح في 2.0

- **الأولوية:** P0 · **اليوم:** 3 · **الزمن:** ~90 دقيقة
- **الواقع المؤكد:** لا nginx إطلاقاً — `COPY --chown=user:user ui-dist/ /app/ui-dist/` عند **`Dockerfile:83-84`** والواجهة تُخدم من `app.py` على المنفذ 7860.
- **الإجراء:** تحويل بناء UI إلى **multi-stage** داخل الـ Dockerfile (مرحلة node تبني `ui/dist` ← تُنسخ للصورة النهائية) بدل artifact متقادم؛ و`ui/src/lib/api-base-url.ts:14-29`: `VITE_API_BASE_URL` صريح، وقتل مُفعِّل شريط DEMO الضمني — الشريط يظهر فقط بقرار صريح وليس بغياب متغير.
- **التحقق:** الـ Space المنشر يعرض بناء حديثاً من `ui/`؛ لا شريط DEMO في الإنتاج؛ الـ API base صحيح من المتصفح.

---

## المرحلة 5 — إعادة بناء النشر وتطهير التاريخ (يوم 3–4)

> **P1 — نشر واحد لكل منصة بـ whitelist من 25 عنصراً، مشروط بـ CI، وتاريخ Git نظيف.** تطهير التاريخ هو **آخر خطوة عن قصد** — بعد استقرار كل ما سبق.

### FIX-17 — خط النشر الوحيد المبوّب على CI (`cd.yml`) — إعادة كتابة كاملة في 2.0

- **الأولوية:** P1 · **اليوم:** 4 · **البروتوكول:** SP-5 (drift-check) · **الزمن:** ~3 ساعات
- **لماذا أُعيدت الكتابة كلياً:** أخطر اكتشاف التدقيق (انظر FIX-0.1) — قائمة v1.0 الست كانت ستنشر Space ميتاً. القائمة أدناه هي **القانون**: تعريف المحتوى الوحيد في المؤسسة، وبوابة drift-check تضرب أي انحراف مستقبلي بين `Dockerfile` COPY والقائمة قبل النشر لا بعده.

**الملف الكامل** `.github/workflows/cd.yml`:

```yaml
name: "CD — Deploy (gated on CI)"

on:
  workflow_run:
    workflows: ["CI"]          # ci.yml الناجي
    types: [completed]
    branches: [main]
  workflow_dispatch:            # مسار إعادة النشر اليدوي (rollback)، مؤكد بـ SHA
    inputs:
      ref_sha:
        description: "Deploy this exact commit SHA (must be a green CI run)"
        required: true
        type: string

concurrency:
  group: cd-production          # نشر واحد في كل لحظة، لا إلغاء في منتصف الطيران أبداً
  cancel-in-progress: false

permissions:
  contents: read
  packages: write

jobs:
  guard:
    runs-on: ubuntu-latest
    outputs:
      sha: ${{ steps.sha.outputs.sha }}
    steps:
      - name: Verify CI success + SHA pinning
        id: sha
        run: |
          set -euo pipefail
          if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
            SHA="${{ inputs.ref_sha }}"
          else
            if [ "${{ github.event.workflow_run.conclusion }}" != "success" ]; then
              echo "::error::CI did not succeed — refusing to deploy"; exit 1
            fi
            if [ "${{ github.event.workflow_run.head_repository.full_name }}" != "${{ github.repository }}" ]; then
              echo "::error::CI ran on a fork — refusing to deploy"; exit 1
            fi
            SHA="${{ github.event.workflow_run.head_sha }}"
          fi
          echo "Deploying pinned SHA: $SHA"
          echo "sha=$SHA" >> "$GITHUB_OUTPUT"

  validate-secrets:
    needs: [guard]
    runs-on: ubuntu-latest
    steps:
      - name: Fail fast on missing deploy secrets (NO silent no-ops)
        run: |
          set -euo pipefail
          missing=0
          for s in HF_TOKEN VERCEL_TOKEN VERCEL_ORG_ID VERCEL_PROJECT_ID; do
            if [ -z "${!s:-}" ]; then echo "::error::Missing secret: $s"; missing=1; fi
          done
          exit $missing
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
          VERCEL_TOKEN: ${{ secrets.VERCEL_TOKEN }}
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

  build-ui:
    needs: [guard]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned-sha>   # ثبّت كل الأكشنز بـ SHA (SP-5/FIX-31)
        with: { ref: "${{ needs.guard.outputs.sha }}" }
      - uses: actions/setup-node@<pinned-sha>
        with: { node-version: 20 }
      - run: corepack enable && pnpm install --frozen-lockfile
        working-directory: ui
      - run: pnpm build
        working-directory: ui
      - uses: actions/upload-artifact@<pinned-sha>
        with: { name: ui-dist, path: ui/dist }

  deploy-hf:
    needs: [guard, validate-secrets, build-ui]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned-sha>
        with: { ref: "${{ needs.guard.outputs.sha }}" }
      - uses: actions/download-artifact@<pinned-sha>
        with: { name: ui-dist, path: ui-dist }

      - name: Stage THE 25-item production whitelist (verbatim from old sync-platforms.yml:157-190)
        run: |
          set -euo pipefail
          mkdir -p stage
          # 1) HF frontmatter README (renamed on the Space)
          test -f README.hf.md   || { echo "README.hf.md missing";   exit 1; }
          test -f Dockerfile     || { echo "Dockerfile missing";     exit 1; }
          test -f hf-space/app.py || { echo "hf-space/app.py missing"; exit 1; }
          test -f ui-dist/index.html || { echo "ui-dist/index.html missing — UI build failed"; exit 1; }
          cp README.hf.md stage/README.md
          # 2) root files (5)
          cp -r Dockerfile .dockerignore VERSION prompts.json compat.py stage/
          # 3) the whole hf-space/ dir (app.py + requirements.hf.txt + README.md)
          cp -r hf-space stage/
          # 4) the 16 runtime code dirs
          cp -r agents prompts core_model core engine stage/
          cp -r load_flow fault_analysis coordination relays stage/
          cp -r network_solver services api utils ai_context_engine stage/
          cp -r integrations ml stage/
          # 5) data/ minus runtime DBs
          cp -r data stage/
          rm -f stage/data/*.db* 2>/dev/null || true
          # 6) the FRESH UI build from this exact SHA
          cp -r ui-dist stage/
          # NOTE: skills/ is intentionally NOT shipped (HF file-size limit;
          # agents load skills from the GitHub repo, per sync-platforms.yml:175-180)

      - name: Drift-check — every Dockerfile COPY source must be staged (2.0 gate)
        run: |
          set -euo pipefail
          MISSING=0
          # top-level COPY sources from the ROOT Dockerfile (skip ui-dist handled above)
          for src in $(grep -E '^\s*COPY(\s+--chown=[^\s]+)?(\s+--chmod=[^\s]+)?\s+\S+' Dockerfile \
                        | awk '{print $NF=="/app/"?$(NF-1):$2}' \
                        | grep -vE '^(/app|/tmp)' | sed 's:/$::' | sort -u); do
            base=$(basename "$src")
            if [ ! -e "stage/$base" ] && [ "$base" != "ui-dist" ]; then
              echo "::error::Dockerfile COPY source '$base' missing from cd.yml whitelist"; MISSING=1
            fi
          done
          exit $MISSING

      - name: Push staged set to HF Space (single atomic commit)
        run: |
          set -euo pipefail
          echo "https://user:${HF_TOKEN}@huggingface.co" > /tmp/.git-credentials-hf
          git config credential.helper "store --file=/tmp/.git-credentials-hf"
          git clone https://huggingface.co/spaces/ahmdelbaz28/AhmedETAP-Platform space-repo 2>&1 | tail -3
          cd space-repo
          find . -mindepth 1 -maxdepth 1 -not -name '.git' -not -name '.gitattributes' -exec rm -rf {} +
          cp -r ../stage/. ./
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git config user.name "github-actions[bot]"
          git add -A
          git commit -m "deploy ${{ needs.guard.outputs.sha }}"
          git push origin main 2>&1 | tee /tmp/hf-push.log
          if grep -q "remote rejected\|failed to push" /tmp/hf-push.log; then
            echo "::error::HF Space push FAILED"; exit 1
          fi
          rm -f /tmp/.git-credentials-hf
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}

  deploy-vercel:
    needs: [guard, validate-secrets, build-ui]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<pinned-sha>
        with: { ref: "${{ needs.guard.outputs.sha }}" }
      - name: Deploy (strict — failures must fail the run)
        run: |
          set -euo pipefail
          npx vercel pull --yes --environment=production \
            --token="${{ secrets.VERCEL_TOKEN }}"
          npx vercel build --prod --token="${{ secrets.VERCEL_TOKEN }}"
          npx vercel deploy --prebuilt --prod --token="${{ secrets.VERCEL_TOKEN }}"

  smoke-and-health-gate:
    needs: [guard, deploy-hf, deploy-vercel]
    runs-on: ubuntu-latest
    steps:
      - name: Smoke the EXACT deployed revision (not the Space page HTML)
        env:
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
          WANT_SHA: ${{ needs.guard.outputs.sha }}
        run: |
          set -euo pipefail
          SHA="${{ needs.guard.outputs.sha }}"
          # 1) HF must report the deployed sha
          python - <<'PY'
          import os, sys, urllib.request, json
          req = urllib.request.Request(
            "https://huggingface.co/api/spaces/ahmdelbaz28/AhmedETAP-Platform",
            headers={"Authorization": "Bearer " + os.environ["HF_TOKEN"]})
          meta = json.load(urllib.request.urlopen(req))
          deployed = (meta.get("runtime") or {}).get("sha") or ""
          want = os.environ["WANT_SHA"]
          print(f"deployed={deployed} want={want}")
          if want[:7] not in deployed:
              sys.exit("FATAL: Space runtime sha does not match pinned sha")
          PY
          # 2) Real app health (app port, not the web page)
          for i in $(seq 1 30); do
            code=$(curl -s -o /dev/null -w '%{http_code}' \
              https://ahmdelbaz28-ahmedetap-platform.hf.space/healthz || true)
            [ "$code" = "200" ] && { echo "healthz OK"; exit 0; }
            echo "attempt $i: /healthz -> $code"; sleep 10
          done
          echo "::error::/healthz never returned 200 within 5 minutes"; exit 1

  rollback-on-failure:
    needs: [smoke-and-health-gate]
    if: failure()
    runs-on: ubuntu-latest
    steps:
      - name: Page + pin back (SP-6)
        run: |
          echo "::error::Deploy failed health gate. ACTION: re-run cd.yml with the last green SHA."
          # Slack webhook (non-COE) configured as repo secret ALERT_WEBHOOK:
          curl -s -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"ETAP CD FAILED health gate at ${{ needs.guard.outputs.sha }} — rollback required\"}" \
            "${{ secrets.ALERT_WEBHOOK }}" || true
```

> ثبّت كل `@<pinned-sha>` بـ SHA حفظة حقيقي قبل الدمج. أي تغيير مستقبلي في `Dockerfile` COPY سيضرب بوابة drift-check تلقائياً — هذا مقصود.

**التحقق:**
1. ادمج PR تافهاً ← CI أخضر ← **cd.yml يشتعل مرة واحدة بالضبط**، ينشر SHA مثبّتاً، والـ smoke يمر.
2. تحقق من drift-check: أضف مؤقتاً `COPY random-dir/ /app/random-dir/` إلى Dockerfile في فرع مؤقت ← يفشل النشر برسالة `missing from cd.yml whitelist`.
3. محتوى الـ Space بعد النشر = القائمة الـ 25 حصراً — لا `skills/` ولا `docs/` ولا `nginx.conf`/`supervisord.conf` (غير موجودين أصلاً).

### FIX-18 — حذف الناشرين القدامى (5 workflows + آلية نشر ci-cd)

- **الأولوية:** P1 · **اليوم:** 4 · **الزمن:** ~30 دقيقة
- **الإجراء:** بعد نجاح أول نشر موبوّب من cd.yml، احذف `.github/workflows/sync-to-hf.yml`، `sync-hf-space.yml`، `sync-platforms.yml`، `trigger-vercel.yml`، وآلية النشر داخل `ci-cd.yml` (ثم الملف كله). **مهم:** استخرج whitelist الحرفية من sync-platforms قبل الحذف — وهي الآن مدمجة في cd.yml 2.0.
- **التحقق:** لا يبقى في المستودع أي مسار يدفع إلى الـ Space أو Vercel غير cd.yml؛ حذف مؤقت لسر `HF_TOKEN` من مسار قديم إن وُجد ← لا شيء ينكسر خارج cd.yml.

### FIX-19 — (مدمج في FIX-17) دلالات validate-secrets و"NOT DEPLOYED"

- **الأولوية:** P1 · **اليوم:** 4 · **الزمن:** ~15 دقيقة
- **الإجراء:** دمج في FIX-17 — محاولة نشر بسر مفقود ← فشل صريح وليس تخطياً (job `validate-secrets` أعلاه)؛ وأي حالة "لم يُنشر" تظهر كـ `NOT DEPLOYED` صريحة لا كنجاح صامت.
- **التحقق:** احذف سراً مؤقتاً في بيئة اختبار ← cd.yml يفشل في `validate-secrets` برسالة تسمّي السر.

### FIX-20 — جعل rollback تشغيلياً لا زخرفياً (إعادة كتابة `rollback.yml`)

- **الأولوية:** P1 · **اليوم:** 4 · **الزمن:** ~60 دقيقة + تمرين
- **عيوب الوضع الحالي (مؤكدة):** مسار HF يدفع **المستودع كاملاً** (`upload_folder(delete_patterns=["*"])`) مكسراً عقد القائمة البيضاء؛ فحص الصحة ينبض **صفحة الويب** (HTML 200 ≠ سليم)؛ ويعتمد GitHub environments قد لا تكون موجودة.
- **الإجراء:** إعادة كتابة rollback ليكون: نشر SHA أخضر سابق عبر `workflow_dispatch` في cd.yml نفسه (مسار `ref_sha`) + فحص صحة على `/healthz` (app port) + تنبيه وصل فعلاً. ثم **نفّذ تمرين تراجع يدوي كاملاً مرة واحدة**.
- **التحقق:** تمرين التراجع ناجح: نشر حفظة حمراء مقصودة ← بوابة الصحة تضرب ← تراجع للـ SHA الأخضر ← /healthz 200.

### FIX-21 — تطهير الأسرار المسرّبة من تاريخ Git (آخر خطوة)

- **الأولوية:** P1 · **اليوم:** 4 (الأخير) · **البروتوكول:** SP-2 · **الزمن:** ~2 ساعة
- **التسلسل الحاكم:** تجميد كل النشر ← `git filter-repo` لإزالة الأسرار من كامل التاريخ (الـ PAT `github_pat_11CCHF…`، دفعة `.env.example` `sk-lw-*`، وثيقة الحادث، وبقية القائمة من سجل التدوير) ← force-push ← **إعادة استنساخ محلية كاملة** ← إعادة مزامنة الـ Space من cd.yml.
- **لماذا أخيراً:** كل force-push مكلف وخطِر — تنفيذه قبل إتمام إصلاحات الملفات يفرض التكرار.
- **التحقق:** `git log -S "github_pat_11CCHF" --all` ← فارغ؛ gitleaks بلا baseline على التاريخ الكامل ← exit 0؛ المستنسخ الجديد يبني وينشر بنجاح.

---

## المرحلة 6 — P1: التحصين (الأسبوعان 1–2)

> **هدف المرحلة:** قابلية التوسع والمراقبة الحقيقية والاعتماديات المنضبطة — الشرط الوحيد لقبول أكثر من نسخة/مستخدم.

| الإصلاح | العنوان | جوهر الإجراء | التحقق |
|---|---|---|---|
| FIX-22 | Redis للحالة المشتركة | شرط التوسع الأول: نقل الحالة المشتركة (جلسات، أقفال، طوابير خفيفة) من الذاكرة المحلية إلى Redis — بلا نسخة ثانية قبل هذا | إيقاف نسخة وإقلاع أخرى يحفظ الجلسات |
| FIX-23 | بوابة Sonar حقيقية | فرض new-code quality gate: لا دمج على كود جديد أسوأ | PR تجريبي أسوأ ← يُرفض فعلاً |
| FIX-24 | تهيئة أول admin | أول مستخدم ≠ viewer: سكربت/متغير تهيئة admin آمن عند أول إقلاع | أول دخول بصلاحيات كاملة موثقة |
| FIX-25 | مواءمة الاعتماديات | انقسام openai (إصدارات متعارضة) + قفل الإصدارات | `pip check` نظيف؛ lock ملتزم |
| FIX-26 | مراقبة تستطيع إيقاظ أحدهم — مرساة مصحَّحة | تنبيه فعلي (Slack/بريد) من `/healthz` (عند `app.py:584`) وفشل النشر؛ Prometheus/Uptime على `/metrics` و`/healthz` | تنبيه وصل فعلاً مرة واحدة على الأقل |
| FIX-27 | الهجرات مصدر حقيقة واحد + بوابة إنتاج | `alembic` هو المخطط الوحيد + بوابة تمنع إقلاع إنتاج على مخطط متأخر | مخطط DB = رأس الهجرات في الإنتاج |
| FIX-28 | إصلاحات Compose والحاويات — أرقام مصحَّحة | دفعة P1: صحّح الـ 56 bind-mount (وليس 45) والhealthchecks والموارد | `docker compose config` سليم؛ الحاويات تُعاد بناءً بلا تحذيرات |
| FIX-29 | CSP ونظافة مفاتيح المزوّدين | Content-Security-Policy صارمة (نطاق انفجار XSS) + تدقيق مفاتيح المزوّدين المكشوفة في الواجهة | CSP تضرب سكربتاً خارجياً في اختبار؛ لا مفتاح مزوّد في حزمة الواجهة |
| FIX-30 | توصيل اختبارات SCADA اليتيمة + مهمة Postgres حقيقية في CI | الاختبارات اليتيمة تدخل البوابة + CI يختبر على Postgres فعلي | اختبارات SCADA تشتغل في CI وتفشل/تنجح بصدق |
| FIX-31 | تثبيت سلسلة التوريد + صدق إعدادات الاختبار — قائمة مصحَّحة | تثبيت **المتبقي فعلاً**: `docker-validation.yml:255` (trivy@master)، `etap-infra-validate.yml:92` (dorny/test-reporter@v1)، `sonarcloud-pr.yml:105` (sonarqube-quality-gate-action@v1.2.1) — أما trivy في ci-cd وsetup-python فمثبتان أصلاً؛ + إعدادات اختبار صادقة (لا mock يمر كواقع) | كل `uses:` في البوابات الناجية مثبت بـ SHA |

---

## المرحلة 7 — P2: النظافة والامتثال (الشهر الأول)

> **هدف المرحلة:** مستودع بلا وزن ميت أو ادعاءات كاذبة — صدق المؤسسة في الكود والوثائق.

| الإصلاح | العنوان | جوهر الإجراء | التحقق |
|---|---|---|---|
| FIX-32 | حذف الوزن الميت | ملفات/مجلدات ميتة مؤكدة (أرشيفات، مولدات قديمة، مخلفات تجارب) | `rg` على أسمائها ← 0؛ البناء والنشر سليمان |
| FIX-33 | Helm: شارت واحد — مسارات مصحَّحة | توحيد على **`helm/etap-ai` (v2.1.0)**؛ حذف `infra/helm/etap-ai` (v2.0.0) و`charts/etap-ai` (v1.0.0) القديمين | `helm lint helm/etap-ai` نظيف؛ مصدر شارت واحد |
| FIX-34 | Terraform: وصّل أو أرشف — العدد مصحَّح | 13 خطوة COE (terraform.yml:1 + terraform-apply.yml:3 + iac-validation.yml:9): إما تفعيل حقيقي أو أرشفة صريحة | صفر COE في iac؛ كل ملف إما يعمل أو محذوف |
| FIX-35 | صدق الـ Runbook (كتابة الحقيقة التشغيلية) | `OPS_RUNBOOK.md` (463 سطراً) يُحدَّث ليطابق الواقع الجديد (cd.yml، Postgres، التدوير)؛ توسعة `TROUBLESHOOTING.md` (4 أسطر فقط حالياً) بأدلة الأعطال الفعلية | كل أمر في الـ runbook يشتغل كما هو؛ قسم تشخيص حقيقي للأعطال الشائعة |
| FIX-36 | استبدال "اختبارات" grep المصدر | اختبارات تفحص نص المصدر بـ grep بدل سلوكه ← اختبارات سلوك حقيقية أو حذف | الخدمات المغطاة لها اختبارات سلوك تمثل العقد الفعلي |
| FIX-37 | صدق cron في Vercel | مهام cron موثقة/مفعّلة بصدق — لا جدولة زائفة | كل cron إما يعمل فعلاً أو حُذف من الإعدادات والوثائق |
| FIX-38 | `.dockerignore` ونظافة محتوى الـ Space — مصحَّح | إضافة المتبقي فعلاً فقط: `archive/`، `acp_runtime/`، `ts-service/`، `*.duckdb*` — دون لمس استثناء `!skills/*.md` (انظر FIX-0.5) | `docker build` يبني من سياق أنظف؛ محتوى الـ Space = whitelist حصراً |
| FIX-39 | صدق ETAP COM في الوثائق | ادعاءات تكامل ETAP COM موثقة كما هي فعلاً: متصل/محاكى/غير متصل | لا وثيقة تدّعي تكاملاً غير موجود |
| FIX-40 | مواءمة README والادعاءات — مصحَّح | README يوثق ما يشتغل فعلاً، ومنه: **مُصدِّر Syslog RFC 5424** (`integrations/siem_syslog.py`: UDP 514 / TCP / TLS 6514 عبر `SIEM_ENABLED`، موصول في `api/agents.py:826,843` و`services/agent_safety.py:40`) مع قرار تشغيله الصريح (انظر FIX-0.4)؛ وربط `SIEM_SYSLOG_ENABLED` واعٍ لا صامت | كل ادعاء في README له دليل تشغيلي قابل لإعادة الإنتاج |
| FIX-41 | Mastra: انشره أو توقف عن ادعائه (قرار الملكية الفكرية) | إما نشر مكوّن Mastra كملكية موثقة أو حذف الادعاء منه نهائياً | الوثائق والكود متطابقان بشأن Mastra |

---

## الجدول اليومي (محدث بتصحيحات 2.0)

| اليوم | الصباح | بعد الظهر | معيار الخروج (بداية اليوم التالي مشروطة بهذا) |
|---|---|---|---|
| **0** | FIX-01 التدوير (الترتيب: PAT ← HF ← Vercel ← Supabase ← البقية) | FIX-02 PR ملفات مسرّبة + دمج؛ FIX-03 تجميد (7 workflows معطلة) + حماية الفرع ON | الـ PAT القديم يعيد 401؛ لا مزامنة Space عند الدفع؛ سجل التدوير مملوء |
| **1** | FIX-04 ruff؛ FIX-05 الـ composite action + 3 مواضع + **إغلاق B615 في `services/yolo/main.py:44`** | FIX-06 gitleaks baseline+allowlist+npmrc؛ FIX-07 حذف 12 ملفاً (+دمج quality-gates) | `main` أخضر؛ Bandit متطابق في كل الخطوط؛ B615 مغلق؛ gitleaks يستطيع الفشل (مُثبت) |
| **2** | FIX-08 مسح إزالة COE؛ FIX-09 نقاط النهاية الثلاث + اختبارات انحدار | FIX-10 WS fail-closed؛ FIX-11 staging fail-closed؛ FIX-12 JWT قائمة سوداء | صفر COE في workflows الناجية؛ كل الثغرات الأربع مُثبتة 401/1011 |
| **3** | FIX-13 المرحلة A (501) + تجربة هجرة DB جافة (FIX-14 خطوة 6) | FIX-14 قطيعة Postgres؛ FIX-15 متغيرات الإقلاع؛ FIX-16 إعادة بناء UI + الشريط | الحسابات تنجو إعادة تشغيل؛ الإقلاع يرفض المتغيرات الناقصة؛ UI جديد حي بلا شريط DEMO |
| **4** | FIX-17 cd.yml (بـ whitelist الـ 25 عنصراً + drift-check) + FIX-18 حذف؛ أول نشر موبوّب | FIX-20 إعادة كتابة rollback + **تمرين تراجع يدوي**؛ FIX-21 تطهير التاريخ (تجميد ← filter-repo ← force-push ← إعادة استنساخ ← إعادة مزامنة Space) | cd.yml نشر SHA مثبّتاً؛ drift-check أخضر؛ تمرين التراجع ناجح؛ gitleaks كامل التاريخ نظيف |
| **5** | مسح Go/No-Go كامل (البوابة أدناه) | أصلح أي بند أحمر؛ وسم `go-live-p0-done` | Go/No-Go مُفحوص 100% ← **اقبل أول مستخدم حقيقي** (نسخة واحدة) |
| **W1–2** | FIX-22 Redis؛ FIX-23 بدء تراكم Sonar؛ FIX-24 تهيئة admin | FIX-25 اعتماديات؛ FIX-26 مراقبة؛ FIX-27 بوابة هجرات | قائمة P1 منجزة ← جاهزية >1 نسخة / تعدد مستأجرين |
| **W3–4** | FIX-28..31 تحصين | FIX-32..41 نظافة، runbook، مواءمة ادعاءات | وسم `hygiene-month-1-done` |

**ميزانية الوقت:** ~4 أيام مركزة لـ P0 (تطابق تقدير التدقيق 2–4 أيام)، أسبوعان لـ P1، شهر لإغلاق P2.

---

## بوابة القبول النهائية Go/No-Go

> كل سطر يُفحص **في بيئة الإنتاج نفسها**، لا محلياً. أي بند أحمر = لا إطلاق.

### الأمان

- [ ] كل الأسرار مُدوَّرة، محدودة النطاق، ولها تاريخ انتهاء (FIX-01) — سجل التدوير مكتمل خارج المستودع
- [ ] `git log -S "github_pat_11CCHF" --all` ← فارغ (FIX-21)
- [ ] gitleaks بلا baseline على التاريخ الكامل ← exit 0 (FIX-06+21)
- [ ] GitHub Secret Scanning + Push Protection مفعّلان في إعدادات المستودع (SP-1 خطوة 7)

### CI

- [ ] الدفع إلى main يشغّل **بوابتين فقط**: CI ثم CD (FIX-07/18)
- [ ] `rg "continue-on-error: true" .github/workflows/` ← 0 (FIX-07/08)
- [ ] `rg '\|\| true' .github/workflows/` و`rg 'non-blocking'` ← 0
- [ ] Bandit أمر واحد مشترك، النتائج متطابقة في كل مكان، و**B615 مغلق** (FIX-05)
- [ ] Sonar: new-code gate يمنع PR سيئاً (مُختبَر بـ PR تجريبي) (FIX-08/23)

### المصادقة

- [ ] `/studies/re-run`، `/tool-policy/evaluate`، `/system/validate` ← 401 بدون مفتاح (FIX-09)
- [ ] `/ws/dual-control/approve` بلا مفتاح مُعدّ ← إغلاق 1011؛ بمفتاح خاطئ ← 4001 (FIX-10)
- [ ] `ENVIRONMENT=staging` أو unset ← fail-closed في `verify_api_key` (FIX-11)
- [ ] JWT placeholder مرفوض عند الإقلاع؛ لا مفتاح في غير التطوير ← رفض إقلاع (FIX-12/15)

### البيانات

- [ ] DATABASE_URL = Postgres دائم؛ إعادة تشغيل Space تحفظ الحسابات (FIX-14)
- [ ] `rg ALLOW_SQLITE_IN_PROD` ← 0 في الكود والأسرار (FIX-14)
- [ ] `alembic upgrade head` يعمل عند الإقلاع؛ مصدر مخطط واحد (FIX-14/27)
- [ ] نسخ احتياطي يومي مفعّل + استعادة مُختبَرة مرة واحدة (FIX-14/SP-6 بتعزيز 2.0)

### النتائج الهندسية

- [ ] `/studies/re-run` ← 501 صريح (المرحلة A) أو محرك حقيقي (المرحلة B) — لا صفوف BUS-1/0.42 في DB (FIX-13)

### النشر

- [ ] cd.yml ينشر SHA مثبّتاً بعد نجاح CI فقط — مُختبَر بدمج حقيقي (FIX-17)
- [ ] **بوابة drift-check خضراء: كل مصدر COPY في Dockerfile داخل whitelist الـ 25 عنصراً** (FIX-17 بتعزيز 2.0)
- [ ] محاولة نشر بسر مفقود ← فشل صريح وليس تخطي (FIX-19)
- [ ] تمرين rollback يدوي نُفّذ بنجاح مرة واحدة (FIX-20/SP-6)
- [ ] محتوى الـ Space = whitelist حصراً؛ لا skills/ ولا docs/ ولا nginx.conf/supervisord.conf (غير موجودين أصلاً) (FIX-17/38)

### الواجهة والمراقبة والادعاءات

- [ ] UI المنشر = بناء حديث من ui/؛ لا شريط DEMO كاذب (FIX-16)
- [ ] تنبيه فعلي (Slack/بريد) وصل مرة واحدة على الأقل من /healthz أو فشل نشر (FIX-17/26)
- [ ] Prometheus/Uptime على /metrics و /healthz (FIX-26 — /healthz عند `app.py:584`)
- [ ] README يوثق مُصدِّر Syslog RFC 5424 وقرار تشغيله الصريح (FIX-40)

---

## ملخص التعديلات مقابل الخطة الأصلية (v1.0)

| الفئة | العدد | التفصيل |
|---|---|---|
| تصحيحات تمهيدية جوهرية (المرحلة 0) | **5** | FIX-0.1 (قائمة cd.yml البيضاء — إعادة كتابة كاملة)، FIX-0.2 (FIX-05 ← B615)، FIX-0.3 (أمر ruff)، FIX-0.4 (استكمال FIX-40 بـ siem_syslog)، FIX-0.5 (تقليص FIX-38) |
| تصحيحات مطبعية | **9** | أرقام أسطر ومسارات وأعداد (القائمة الكاملة أعلاه) — لا تغيّر الاستنتاجات |
| إصلاحات بلا أي تعديل | **28** | FIX-01..03، FIX-06، FIX-09..13، FIX-15، FIX-18..22، FIX-24، FIX-25، FIX-27، FIX-29، FIX-30، FIX-32، FIX-35..37، FIX-39، FIX-41 — نصوصها كما هي في v1.0 |
| إصلاحات بتصحيحات مطبعية فقط | **8** | FIX-07، FIX-14، FIX-16، FIX-26، FIX-28، FIX-31، FIX-33، FIX-34 — مراسي أرقام/مسارات لا تغيّر استنتاجاتها |
| إجمالي الإصلاحات المرقّمة | **41** | موزعة: P0-BLOCKER (3) + P0 (13) + P1 نشر (5) + P1 تحصين (10) + P2 نظافة (10) |
| تعزيزات بنيوية جديدة في 2.0 | **2** | بوابة drift-check (FIX-17) + بوابة استعادة نسخ احتياطي (SP-6 بتعزيز 2.0) |

**الخلاصة:** كل سطر في هذه النسخة إما مطابق حرفياً للشجرة المدقَّقة (`a4f22e65c`) أو مصحَّح بدليل مؤكد منها — v2.0 هي النسخة الوحيدة المعتمدة للتنفيذ.

---

## التنبيه الأمني الحاسم (نفّذه الآن — قبل أي شيء)

هذه الخطوات **ليست** جزءاً من جدول الأيام — هي شرط البدء نفسه (FIX-01 فعلياً):

1. **دوّر GitHub PAT فوراً** — المُسرّب في المحادثة والمستودع العام (`github_pat_11CCHF…` في 4 ملفات متتبَّعة).
2. **دوّر HuggingFace token** — خط مزامنة الـ Space الحي مُكشوف.
3. **دوّر مفتاح vcp (Vercel)** — مُسرّب في المحادثة (وهناك رمزان لا واحد).
4. **كل سر لُصق في أي محادثة يُعتبر محروقاً** — نص المحادثة نفسه ناقل تسريب؛ دوّره حتى لو لم يظهر في المستودع (NVIDIA، Resend، Neo4j، Auth0، Daytona، CodeSandbox، SonarCloud…).

هذه بالضبط السيناريوهات التي تهدف الخطة كلها إلى منعها — أي إصلاح تقني يبدأ قبل إبطال هذه القيمة هو مجرد ترتيب أثاث في منزل مفتوح الأبواب.

---

## ملحق — منهجية التدقيق والأدلة

**المنهجية:** نحو 98 فحصاً آلياً عبر سكربت تحقق مكتوب لهذا الغرض، + 25 فحصاً يدوياً عميقاً:
- تاريخ Git الكامل (3387 حفظة غير مقتطعة) مع `git log -S` لكل نمط أسرار.
- واجهة GitHub API لتوثيق تشغيلات CI الفعلية (منها `35104117303` و`35100029065` — فشلان حقيقيان مطابقان لرواية الخطة).
- تشغيل حقيقي لـ `ruff format --check` (النتيجة: 2/1058 ملفات منحرفة كما نصّت الخطة) و`bandit` بمعاملات `ci.yml` وبملف `.bandit` الرسمي.
- استخراج حرفي لمجموعة نسخ `sync-platforms.yml:157-190` (25 عنصراً) ومطابقته مع `Dockerfile:59-77`.

**الأدلة المحورية (أمثلة):**
- تسريبات LangWatch: `git log -S "sk-lw-"` ← الحفظات `2bd77814`، `7f54e530`، `beef3343`.
- غياب sha1 في `etap_integration/etap_com.py` عبر كامل التاريخ ← إسقاط تشخيص B324 في FIX-05.
- B615 حي في `services/yolo/main.py:44` (تحميل نموذج HF بلا revision).
- `hf-space/` الفعلي = `app.py` + `requirements.hf.txt` + `README.md` — لا nginx ولا supervisord؛ الإقلاع `CMD ["python", "app.py"]` على المنفذ 7860.
- مُصدِّر SIEM RFC 5424 موجود وموصَّل: `integrations/siem_syslog.py` ← `api/agents.py:826,843` + `services/agent_safety.py:40`.
- `.dockerignore` الحالي: `docs/` (:69)، `reports/` (:48)، `tests/` (:78)، `!skills/*.md` (:75).

> **ملاحظة منهجية:** أرقام الأسطر في هذه الوثيقة دقيقة عند الشجرة `a4f22e65c`. إذا انزاحت الأسطر بحفظات لاحقة، فالاقتباسات البرمجية داخل كل إصلاح هي المرساة المعتمدة — حدّد الموضع بالمحتوى لا بالرقم وحده.

**مرجع التنفيذ المفصّل:** النسخة الموسعة (1707 أسطراً: خريطة الملفات الكاملة، بروتوكولات SP-0..8 بنصوصها الحاكمة، القوائم الحرفية لكل حذف، ملحق الأوامر الجاهزة A.1..A.8) في `ETAP_Complete_Remediation_Plan_v2.0.md` بنفس المجلد.
