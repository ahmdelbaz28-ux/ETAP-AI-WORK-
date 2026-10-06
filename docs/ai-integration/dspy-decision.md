# قرار وهندسة دمج DSPy Copilot — DSPy Decision & Integration Plan
**المستودع:** `https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git`  
**نقطة الأساس الحية:** `main @ 43fdd481f` (`43fdd481faf134f757914702db3b4ab596bfc429`)  
**تاريخ التوثيق:** 2026-09-27  
**الحالة:** تم الاستبدال بـ ADR-DSPY-001 (Superseded & Archived)

> [!IMPORTANT]
> **SUPERSEDED BY ADR-DSPY-001 (`docs/ai-integration/dspy-archive-decision.md`)**  
> تم استبدال هذا المقترح وقرار دمج فرع `v2` رسمياً بقرار الأرشفة الصادر في 2026-09-28 ([ADR-DSPY-001](./dspy-archive-decision.md)). مسار DSPy Copilot ومسودة PR #607 تمت أرشفتها كمسار بحثي/تجريبي، مع الإبقاء على علم الميزة `dspy_copilot` معطلاً بشكل دائم ومغلق (Strictly Fail-Closed: `default=False, rollout=0%`) ودون دمجه في النواة التنفيذية لـ M1–M3.

---

## 1. القرار المحسوم (التاريخي — تم الاستبدال بأرشفة v2 في ADR-DSPY-001)

القرار المعماري الأولي (المستبدل بـ ADR-DSPY-001):
1. **الأساس المقترح سابقاً:** فرع `feat/dspy-copilot-prepost-v2` (مؤرشف حالياً).
2. **فوق الأساس:** إعادة تشكيل فرع `fix/study-executor-study-type-gate` ليعمل بسلاسة فوقه.
3. **المحظور تماماً:** يُمنع منعاً باتاً دمج فرع `feat/dspy-copilot-prepost` (v1) بأي شكل من الأشكال.
4. **التحديث الحاسم (2026-09-28):** تقرر أرشفة مسار v2 بالكامل وعدم دمجه في main لتجنب الاعتماديات غير المستقرة، وإغلاق بوابة M0.3 على نحو Fail-Closed خالص.

---

## 2. التحقق الرقمي الدقيق بين الفروع الثلاثة (Git Topology & Commits Audit)

تم استخراج هذه الأرقام عبر أوامر Git المباشرة مقابل رأس `main @ 43fdd481f`:

| المعيار الرقمي | `feat/dspy-copilot-prepost-v2` | `feat/dspy-copilot-prepost` (v1) | `fix/study-executor-study-type-gate` |
|----------------|--------------------------------|----------------------------------|---------------------------------------|
| `git merge-base main <branch>` | `43fdd481faf134f757914702db3b4ab596bfc429` | `43fdd481faf134f757914702db3b4ab596bfc429` | `43fdd481faf134f757914702db3b4ab596bfc429` |
| `git rev-list --count main..<branch>` (متقدم بـ) | **5 commits** | **2 commits** | **2 commits** (محلياً: `0fcc311d0`, `334244ab4`) / **1** (origin) |
| `git rev-list --count <branch>..main` (متأخر بـ) | **0 commits** | **0 commits** | **0 commits** |
| `git diff --shortstat main..<branch>` | `25 files changed, 3129 insertions(+), 1 deletion(-)` | `24 files changed, 1920 insertions(+), 1 deletion(-)` | `2 files changed, 205 insertions(+), 16 deletions(-)` |

### كشف انحراف فرضيات الدليل:
ذكر الدليل التمهيدي أن `prepost` و `fix` متأخران عن main (بـ 1 و 2). التحقق المباشر يثبت أن جميع الفروع متفرعة بدقة من كوميت main الحالي (`43fdd481f`)، وبالتالي فإن عدد الكوميتات المتأخرة عن main هو **صفر** لجميع الفروع الثلاثة، ولا يوجد تفرع مفقود.

---

## 3. استراتيجية الدمج المعتمدة وأثرها (Merge Strategy & Downstream Impact)

### الاستراتيجية: Fast-Forward Rebase مع دمج صريح `merge --no-ff`
1. **الخطوة الأولى (التأسيس):**
   اعتماد كود `v2` ودمجه عبر `git merge --no-ff` للحفاظ على التاريخ النظيف وشجرة المراجعة.
2. **الخطوة الثانية (إعادة التشكيل):**
   إعادة تموضع (rebase) فرع `fix/study-executor-study-type-gate` فوق رأس فرع `v2` المدمج، بدلاً من دمجهما بالتوازي.
   - **السبب:** فرع `fix` يعدل `services/study_executor.py` واختباراته `tests/test_study_executor_deep.py`. بينما فرع `v2` تجنب لمس `services/study_executor.py` واعتمد على المغلف المستقل `services/study_executor_copilot.py` (في الفرع المؤرشف).
   - هذا الفصل يضمن انعدام التعارض النصي أثناء الدمج.

---

## 4. اختبار بوابة Fail-by-Default بالبراهين الحرفية

تطبق خدمة DSPy Copilot في فرع `v2` مبدأ الأمان المغلق بالافتراض (Fail-Closed / Fail-by-Default) الصارم، والذي يضمن عدم تسريب أي مخرجات غير معتمدة أو تنفيذ كود تجريبي عند إيقاف علم الميزة:

### 1. سلوك `run_ingest` عند تعطيل العلم:
* **السلوك:** يلقي استثناء `DspyIngestError("flag_disabled")` ولا ينتج أبداً أي مواصفة شبكة أو كود تنفيذي.
* **الشاهد الصريح:** في `services/dspy_copilot/runtime.py:131-133` (الفرع المؤرشف):
  ```python
  # Contract: run_ingest raises DspyIngestError on flag_disabled (fail-closed, never produces executable spec)
  if not is_enabled():
      raise DspyIngestError("flag_disabled")
  ```

### 2. سلوك `run_diagnose` عند تعطيل العلم:
* **السلوك:** يعيد كائن تشخيص يحتوي على `code="FLAG_DISABLED"` مع رسالة واضحة دون أي استدعاء لنموذج الذكاء الاصطناعي (Graceful Degrade).
* **الشاهد الصريح:** في `services/dspy_copilot/runtime.py:202-214` (الفرع المؤرشف):
  ```python
  # Contract: run_diagnose returns DiagnosticOutput with code=FLAG_DISABLED on flag_disabled (graceful degrade)
  if not is_enabled():
      return DiagnosticOutput(
          summary="DSPy Copilot is disabled by feature flag.",
          findings=[
              DiagnosticFinding(
                  severity="info",
                  code="FLAG_DISABLED",
                  message="Feature flag 'dspy_copilot' is inactive",
                  bus_id=None,
                  standard_ref=None,
              )
          ],
          recommendations=[],
          citations=[],
      )
  ```

* **فحص الاسم التاريخي "RC-1":** كما نبهت التعليمات، تم التأكد بالبحث أن نص "RC-1" غير موجود، وأن الاختبار يستند للسلوك الحقيقي المبرهن أعلاه والموثق في `tests/test_dspy_fallback.py:46-70` (الفرع المؤرشف).

---

## 5. المقارنة الجنائية: ما استُخدم من v2 وما استُبعد من prepost (v1)

### الملفات الموجودة في `v2` وتم استبعادها من `prepost` (إضافات v2 الحصرية):
1. **`tests/test_dspy_api_security.py`** (328 سطراً):
   - **سبب الاستخدام:** يحقق فحص أمان صارم لواجهة API (Multi-tenant isolation, JWT verification, X-API-Key, ومقاومة هجمات التجاوز).
2. **`tests/test_dspy_remediation.py`** (243 سطراً):
   - **سبب الاستخدام:** يوفر اختبارات شاملة لاقتراحات التصحيح والتكامل الهندسي مع معايير IEEE/IEC.
3. **`tests/test_agent_registration_regression.py`**:
   - **سبب الاستخدام:** يمنع أي انحدار أو كسر في تسجيل الوكلاء الـ 27 القائمين.
4. **`services/study_executor_copilot.py`**:
   - **سبب الاستخدام:** يغلف استدعاءات الكوبايلوت كـ hook خارجي نظيف دون التعديل التخريبي على `services/study_executor.py`.

### الملفات الموجودة في `prepost` (v1) وتم استبعادها من `v2`:
1. **`services/study_executor.py`** (تعديلات v1 المتشابكة):
   - **سبب الاستبعاد:** في v1 تم حشر تعديلات الكوبايلوت والتوجيه داخل المنفذ الأساسي مباشرة، مما خلق اعتمادية متشابكة وتعديلاً غير آمن على كود التشغيل. تم تفكيك هذا التداخل في v2 ونقل التعديل إلى فرع `fix/study-executor-study-type-gate` المنفصل.
2. **`tests/test_study_executor_deep.py`** (تعديلات v1 المباشرة):
   - **سبب الاستبعاد:** تم فصلها بالكامل لفرع الـ fix المستقل لضمان نقاء حزمة DSPy.

---

## 6. التحقق الحاسم لما قبل الدمج (البند 4)

تم تنفيذ الأوامر المقررة لإثبات عدم تسرب أي من ملفات DSPy إلى الفرع الرئيسي `main`:
```bash
git show main:services/dspy_copilot/runtime.py
git show main:services/study_executor_copilot.py
git show main:api/dspy.py
```
* **المخرج الحرفي لـ main:**
  - `fatal: path 'services/dspy_copilot/runtime.py' does not exist in 'main'`
  - `fatal: path 'services/study_executor_copilot.py' does not exist in 'main'`
  - `fatal: path 'api/dspy.py' does not exist in 'main'`
* **المخرج الحرفي لـ `feat/dspy-copilot-prepost-v2`:**
  - تم استعراض الملفات الثلاثة بنجاح كامل وجميعها موجودة وتعمل.
* **النتيجة:** التأكيد القاطع بأن ملفات DSPy غير مدمجة في `main` وجاهزة للدمج المنظم وفق المراحل المعتمدة.
