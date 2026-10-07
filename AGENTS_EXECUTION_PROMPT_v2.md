# PROMPT — تنفيذ مهام الأمان والعمليات المفقودة فعلياً في المستودع
# تاريخ المراجعة: 2026-10-07
# الحالة: قابل للتنفيذ — مبني على دليل كود فعلي

## الخلفية (نتائج مراجعة مستقلة موثقة)

### ما هو موجود بالفعل في الكود:
- **FIX-15 (fail-closed production gate):** `hf-space/app.py:167-212`
  - `_startup_auth_fail_closed_check()` يتحقق من:
    - `ENGINEERING_SERVICE_API_KEY` أو `HF_API_KEY`
    - `DATABASE_URL` (يرفض SQLite في الإنتاج ما لم `ALLOW_SQLITE_IN_PROD=true`)
    - `JWT_SECRET_KEY`
    - `REDIS_URL` (يحذر في الإنتاج بدون Redis مع شرط `replicas=1`)
  - في الإنتاج/التدريب: يرفع `RuntimeError` إذا كان أي متغير مفقود
  - في التطوير: يسمح بالوصول غير المصادق مع تحذير

- **FIX-27 (بوابة Alembic مع قفل Redis):** `hf-space/app.py:131-159`
  - `run_alembic_startup_gate()` يُستدعى في `lifespan()`
  - يستخدم `LockManager(client=redis_client)` مع `lock("alembic-migration", ttl_seconds=300, timeout_ms=120000)`
  - في الإنتاج: يفشل (`raise`) إذا فشلت الترحيلات
  - بدون Redis: يسجّل تحذير ويستمر (mode أحادي النسخة)

- **/healthz يفحص DB فعلياً:** `hf-space/app.py:722-758`
  - يستدعي `check_db_health()` من `api/database.py:348-371`
  - ينفذ `SELECT 1` عبر `async_session()`
  - يرد 503 مع `{"status": "degraded"}` عند فشل DB
  - **لا يفحص Redis** — فقط `/readyz` في `api/health.py:88-148` يفحص Redis

- **/version endpoint:** `hf-space/app.py:806-827`
  - يقرأ `DEPLOY_SHA` أو `/app/DEPLOY_SHA` أو `VERSION`
  - يعيد `commit_sha` في الاستجابة

- **Smoke gate في cd.yml:** `.github/workflows/cd.yml:317-412`
  - يفحص `/healthz` (30 محاولة)
  - يفحص `/version` للتطابق مع SHA المتوقع
  - يفحص Vercel
  - **لا يخضع لـ rollback تلقائي** — فقط يعلن الفشل

- **Dependabot auto-merge:** `.github/workflows/dependabot-auto-merge.yml`
  - **لا يوجد `--admin`** في الملف
  - يمنع الدمج التلقائي للحزم الحرجة (`CRITICAL_PACKAGES`)
  - ينتظر اكتمال الفحوصات قبل الدمج

- **secret-scan.yml:** `.github/workflows/secret-scan.yml:41`
  - `set -eo pipefail` موجود بالفعل
  - يفحص الأسرار عبر gitleaks + security_scan.py

### ما هو غير موجود فعلياً (مهام يجب إنجازها):

1. **اختبار نجاة البيانات (A4):** لا يوجد اختبار آلتي يثبت نجاة البيانات بعد إعادة تشغيل Space
2. **Meta-Guard workflow (B2):** `.github/workflows/anti-greenwash.yml` غير موجود
3. **CI_GATE_EXCEPTIONS.md (B2):** غير موجود
4. **Smoke test كامل (C2):** لا يوجد سكريبت ينفذ CSRF → register → login → project → study
5. **تدوير الأسرار فعلياً (D1):** يوجد توثيق للتسرب (`docs/archive/ETAP_Radical_Remediation_Plan_v2.0.md`) لكن لا دليل على التنفيذ
6. **تدقيق أسرار السبيس (D2):** لا يوجد ملف يوثق قائمة الأسرار

---

## المهمة A — بقاء البيانات عند تحديث/إعادة تشغيل الـ Space

### A1. قاعدة بيانات دائمة
- **الحالة:** الكود يمنع SQLite في الإنتاج بالفعل (`api/database.py:80-89`)
- **المطلوب:** لا يوجد كود إضافي مطلوب — التحقق من أن `DATABASE_URL` مضبوط على PostgreSQL في إعدادات HF Space
- **الملاحظة:** `hf-space/app.py:138-139` يتخطى الترحيلات إذا كان `DATABASE_URL` SQLite أو غير مضبوط

### A2. Redis للحالة المشتركة
- **الحالة:** `hf-space/app.py:191-203` يتحقق من `REDIS_URL` ويحذر في الإنتاج بدونه
- **المطلوب:** لا يوجد كود إضافي مطلوب — التحقق من أن `REDIS_URL` مضبوط في HF Space Secrets

### A3. خارجنة أي ملفات مستخدم مكتوبة محلياً
- **الحالة:** `api/database.py:248-261` أزالت مسار `/tmp/fallback` نهائياً
- **المطلوب:** فحص الكود عن أي كتابة محلية متبقية خارج `kill-switch` CUA

### A4. اختبار النجاة الإلزامي (دليل قاطع) — **مفقود، يجب إنشاؤه**
**الدليل:** لا يوجد سكريبت أو pytest يثبت نجاة البيانات بعد إعادة تشغيل Space.

**التنفيذ المطلوب:**
1. إنشاء `tests/test_hf_space_data_survival.py`
2. السكريبت يجب أن:
   - ينشئ مستخدم + مشروع + دراسة عبر API
   - يسجل طابعاً زمنياً وقيم `/version`
   - يحفّز "إعادة تشغيل" Space (أو يستخدم container restart محلي)
   - بعد العودة: يتحقق من وجود البيانات نفسها
   - يسجل النتيجة كـ pytest مع دليل قابل للتحقق

### A5. حماية الـ Space من النوم ومطابقة الإصدار
- **الحالة:** `cd.yml:349-395` يتحقق من تطابق `/version` مع SHA المتوقع
- **المطلوب:** لا يوجد كود إضافي مطلوب — التحقق من تشغيل cd.yml عند كل نشر

---

## المهمة B — إلغاء ابتلاع الفشل و"المسرح الأخضر" من كل البوابات

### B1. جرد شامل ثم تنظيف

**الأرقام الصحيحة (من الفحص الفعلي):**
- `continue-on-error:` → **23 موضعاً** في 50 workflow
- `|| true` → **33 موضعاً** في 50 workflow
- **الإجمالي: 56** (ليس 54 كما في البرومبت الأصلي)

**التصنيف حسب الملف:**

| الملف | continue-on-error | || true | الإجمالي | الحالة |
|------|---|---|---|---|
| `health-checks.yml` | 4 (Slack notifications) | 0 | 4 | غير مبرر — أحذف |
| `secret-scan.yml` | 1 (SARIF upload) | 0 | 1 | غير مبرر — أحذف |
| `sonarcloud-pr.yml` | 2 | 0 | 2 | غير مبرر — أحذف |
| `cd.yml` | 0 | 3 | 3 | `|| true` على curl probes — **غير مبرر** لأن `set -euo pipefail` موجود والفحص الحقيقي هو `if [ "$HEALTHY_HF" -ne 1 ]; then exit 1` |
| `ui-quality.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `security.yml` | 0 | 1 | 1 | غير مبرر — أحذف |
| `etap-infra-validate.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `etap-infra-integration.yml` | 0 | 4 | 4 | غير مبرر — أحذف |
| `docker-validation.yml` | 0 | 3 | 3 | غير مبرر — أحذف |
| `no-mock-in-prod.yml` | 0 | 3 | 3 | غير مبرر — أحذف |
| `npm-audit.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `load-test.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `integration-tests.yml` | 0 | 1 | 1 | غير مبرر — أحذف |
| `release-gate.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `rollback.yml` | 0 | 2 | 2 | غير مبرر — أحذف |
| `security-audit.yml` | 0 | 3 | 3 | غير مبرر — أحذف |
| `auto-index.yml` | 0 | 1 | 1 | غير مبرر — أحذف |
| `ai-code-review.yml` | 0 | 1 | 1 | غير مبرر — أحذف |

**الإصلاحات المحددة المطلوبة:**

1. **secret-scan.yml:**
   - `pipefail` موجود بالفعل (`set -eo pipefail` في السطر 41)
   - لكن `continue-on-error: true` على SARIF upload (سطر 64) يجب حذفه

2. **dependabot-auto-merge.yml:**
   - **لا يوجد `--admin`** في الملف (الادعاء في البرومبت الأصلي خاطئ)
   - الملف يمنع الدمج التلقائي للحزم الحرجة بالفعل

3. **بوابة صحة النشر في cd.yml:**
   - `cd.yml:336` يحتوي `|| true` على curl probe
   - **يجب حذف `|| true`** والسماح لـ `set -euo pipefail` بالعمل

### B2. بوابة Meta-Guard ضد الانتكاس — **مفقودة، يجب إنشاؤها**

**الدليل:** `.github/workflows/anti-greenwash.yml` غير موجود + `CI_GATE_EXCEPTIONS.md` غير موجود.

**التنفيذ المطلوب:**
1. إنشاء `.github/workflows/anti-greenwash.yml` يعمل على كل PR إلى main
2. السكريبت يجب أن يرفض الدمج إذا ظهر في أي workflow:
   - `continue-on-error` أو `|| true` في خطوات بوابة/نشر
   - `--admin` في أي مكان
   - `[skip ci]` في خطوات بوابة/نشر
   - تعديل يحذف خطوة فحص إلزامية
3. إنشاء `CI_GATE_EXCEPTIONS.md` يشرح كل استثناء ومبرره ومالكه
4. **الاختبار الذاتي:** إنشاء PR تجريبي يضيف `|| true` وتأكد أن البوابة ترفضه

### B3. تثبيت الأحمر القائم
- **الدليل:** لا يوجد commit أو run ID في السجل المحلي يشير إلى فشل E2E على `69d83d65a`
- `69d83d65a` هو "fix(security): document npm audit exception" — ليس له علاقة بـ E2E tests
- **المطلوب:** تشغيل `pytest tests/test_hf_space_*.py` محلياً لتحديد أي الفحوصات فاشلة

---

## المهمة C — سلسلة تحقق ما بعد النشر

### C1. عمق /healthz — **موجود جزئياً**
**الدليل:**
- `hf-space/app.py:722-758` — `/healthz` يفحص `check_db_health()` (SELECT 1)
- **لكن:** لا يفحص Redis — فقط `/readyz` في `api/health.py:88-148` يفعله
- **المطلوب:** إضافة فحص Redis إلى `/healthz` أو توثيق أن `/readyz` هو المسؤول عن Redis

### C2. Smoke آلي بعد كل نشر — **مفقود، يجب إنشاؤه**
**الدليل:** `.github/workflows/cd.yml:317-412` يحتوي على فحص `/healthz` و `/version` و Vercel فقط.

**التنفيذ المطلوب:**
1. إنشاء `scripts/post_deploy_smoke.py`
2. السكريبت يجب أن ينفذ:
   - جلب CSRF token (`GET /api/v1/csrf/token`)
   - تسجيل مستخدم تجريبي (`POST /api/v1/auth/register`)
   - دخول JWT (`POST /api/v1/auth/login`)
   - إنشاء مشروع (`POST /api/v1/projects`)
   - دراسة تجريبية (`POST /api/v1/studies/run`)
   - التحقق من النتيجة
3. أي خطوة تفشل = النشر يُعلَم فاشل
4. إضافة السكريبت إلى `cd.yml` بعد `smoke-and-health-gate`

### C3. مطابقة UI↔API — **مفقود، يجب إنشاؤه**
**الدليل:** `cd.yml:397-412` يفحص Vercel فقط.

**التنفيذ المطلوب:**
1. بعد فحص Vercel، التحقق من أن `https://etap-ai-work.vercel.app` و `https://ahmdelbaz28-ahmedetap-platform.hf.space` يشيران إلى نفس الإصدار
2. تسجيل النتيجة في ملخص التشغيل

---

## المهمة D — الأسرار والنظافة التشغيلية

### D1. تدوير كل بيانات الاعتماد المكشوفة — **موثق كمسرب، لم يُنفذ**
**الدليل:**
- `docs/archive/ETAP_Radical_Remediation_Plan_v2.0.md:243` يشير إلى `github_pat_11CCHF…` كمسرب
- `core/error_tracking.py:47-48` يحتوي على أنماط كشف الـ PAT
- **لكن:** لا يوجد commit جديد أو إشارة إلى token جديد
- **المطلوب:** تدوير فعلي لجميع الأسرار المسربة وتوثيقها

### D2. تدقيق أسرار السبيس — **مفقود، يجب إنشاؤه**
**الدليل:** لا يوجد ملف يوثق قائمة أسرار السبيس.

**التنفيذ المطلوب:**
1. إنشاء `docs/hf-space-secrets.md`
2. القائمة يجب أن تحتوي على:
   - اسم كل Secret (بلا قيمة)
   - وظيفته
   - ما إذا كان إلزامياً أو اختيارياً
   - التحقق من عدم وجود قيم placeholder

### D3. تثبيت إصدارات requirements.hf.txt — **موجود بالفعل**
**الدليل:** `requirements.hf.txt` يحتوي على:
- `>=X.Y.Z,<A.B.C` للإصدارات المثبتة
- `~=X.Y.Z` لإصدارات محددة
- لا توجد إصدارات عائمة `>=` بدون حد أعلى

---

## تعريف الإنجاز (Definition of Done) — الكل دون استثناء:

1. ✅ **FIX-15 و FIX-27 موجودان بالفعل** — لا تغيير مطلوب
2. ✅ **continue-on-error / || true** — cleanup كامل لـ 56 موضعاً
3. ✅ **Meta-Guard workflow** — `anti-greenwash.yml` يعمل ويُختبر برفض PR تجريبي
4. ✅ **CI_GATE_EXCEPTIONS.md** — موجود ويشرح كل استثناء
5. ✅ **اختبار نجاة البيانات (A4)** — `tests/test_hf_space_data_survival.py` موجود ويعمل
6. ✅ **Smoke test كامل (C2)** — `scripts/post_deploy_smoke.py` موجود ومُدمج في cd.yml
7. ✅ **/healthz يفحص Redis** — تم الإضافة أو التوثيق
8. ✅ **تدوير الأسرار (D1)** — منفذ فعلياً وموثق
9. ✅ **تدقيق أسرار السبيس (D2)** — `docs/hf-space-secrets.md` موجود
10. ✅ **requirements.hf.txt مثبت** — موجود بالفعل

---

## صيغة التقرير النهائي (إلزامية):

لكل بند من البنود أعلاه:
- **الحالة:** (منجز/فاشل/معطل بقرار مالك)
- **الدليل:** (run ID، رابط، ملف:سطر)
- **التاريخ:**

+ قسم إلزامي بعنوان "ما لم أنجزه ولماذا" — الفراغ فيه مؤشر سوء وليس سلامة.

---

*تم إنشاء هذا البرومبت بناءً على مراجعة مستقلة للكود الفعلي في المستودع، مع إزالة الادعاءات غير الصحيحة وتصحيح الأرقام وتحديد المهام المفقودة فعلياً.*
