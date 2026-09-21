# Implementation Plan — إغلاق خطة «الصدق الهندسي + Chat-First» (جولة الإغلاق)

## [Overview]

**هدف واحد:** إغلاق كل ما تبقّى من البرومبت الرئيسي (المراحل 0–10) على المستودع الحقيقي عبر **9 مراحل تنفيذية متسلسلة (S0→S8)**، لكل مرحلة برومبت مستقل، بوابة قبول قابلة للقياس، تقرير موحّد، ووقفٌ إلزامي لطلب التصريح قبل المرحلة التالية — مع بروتوكول دفع/دمج نظيف.

### السياق المُتحقَّق منه (لا افتراضات)

هذه الخطة مبنية على تحقق ميداني مباشر بتاريخ **2026-09-21** وليس على نص البرومبت، لأن **عدة بنود في البرومبت قديمة**:

| بند البرومبت | الادعاء في البرومبت | الحقيقة المُتحقَّقة | الدليل |
|---|---|---|---|
| 1-1 | `arc_flash_engine.py:261` يهمل VarCf (`iarc_reduced = 0.85 * iarc`) | **مُصلَح**: `iarc_reduced = iarc_varcf`، والسطر 668 يستخدم `round(iarc_reduced, 4)` | قراءة `fault_analysis/arc_flash_engine.py:261,268,657-668` |
| 1-2 | حالات ST دائرية بلا تيار مخفض | **غير دقيق**: الاختبار يقرأ من `tests/gold_cases/ieee1584_st_published.json` (2169B) وليس من محرك التنفيذ | `7 passed in 18.50s` للأمر `pytest tests/test_arcflash_1584_st_cases.py` |
| 1-3 | `core/study_engine.py:257-263` صيغة مبسطة | **مُصلَح**: يفوّض `ArcFlashEngine` (ADR-0004) | التزام `45a520b9d` + قراءة `core/study_engine.py:254-296` |
| 1-4 | OPF يقول "simplified" بلا صدق موثق | **مُصلَح**: docstring يعلن planning-grade approximation | التزام `45a520b9d` + قراءة `load_flow/optimal_power_flow.py:442-446` |
| 2 | acceleration_factor بـ 19 مرجعًا حيًّا | **مُزال** من API والواجهتين (+ عمود DB فقط مسموح) | `test_solver_parameter_cleanup.py` قائم + التزام `c7cf56e6c` |
| 3 | ruff 58 خطأ + F821 | **مُصلَح**: `ruff check .` = 0 | `RUFF_CLEAN_ZERO` (اختبار exit code) |
| 3-3 | مصفوفة 3.13 فقط | **مُصلَح**: 3.11/3.12/3.13 | `.github/workflows/python-compatibility.yml` + التزام `1636e7e4b` |
| 4-1 | علم `chat_first_ui` غير معرّف | **مُعرَّف**: enabled=true, ga, 100% | `api/feature_flags.py:127-132` + `.feature-flags.json` |
| 5/6 | شاشات كاذبة + تجربة ناقصة | **مُصلَح ومدفوع**: QuickActionsBar/empty-state/history/RTL/REV | التزامات `ff8703e9f`, `b694a28c6`, `28c015fdf`, `0808f74c4` |
| 7 | الوثائق غير موجودة | **أُنشئت**: VALIDATION_REPORT + COMPLIANCE_MATRIX + TRUST_CHARTER + AR | التزام `9c653d50a` |

### نقطة الانطلاق المعتمدة

- `HEAD == origin/main == c7cf56e6cee23451648ade93520f2b78f386ae27`، والشجرة **نظيفة** (`git status --porcelain` فارغ).
- `claims_audit --strict` = **16/16 VERIFIED** (شُغِّل حيًّا).
- `.venv-fix`: pytest 9.1.1 / pytest-asyncio / pytest-cov 7.1.0 / ruff 0.16.7 — **بدون pytest-xdist وبدون pytest-timeout** ⇒ أمر `-n 8 --timeout=90` الموصوف في البرومبت **يفشل** في هذه البيئة (سابق: تعطل الأوامر بهما).
- `requirements-dev.txt` يتضمن `pytest-timeout>=2.4.0` و**لا يتضمن pytest-xdist**.

### الفجوات الحقيقية المتبقية (نطاق هذه الخطة)

1. **BYOK لا يعمل من المتصفح (عيب مؤكد):** `api/routes.py:767-777` و`787-797` — `allow_headers` لا يتضمن `x-user-llm-key` / `x-user-llm-provider` بينما `ui/src/lib/llm-chat.ts:1150-1155` يرسلهما ⇒ CORS Preflight يفشل؛ اختبارات `TestClient` لا تكشفه.
2. **تناقض سياقي:** `api/chat_stream.py:119-133` docstring ما زال يصف قاعدة "no client keys ever" المخالفة للسلوك الجديد.
3. **ازدواج مسار BYOK:** مسار قديم `x-active-key` (`api/routes.py:437,439` + `ui/src/lib/api.ts:24,34`) وجديد `X-User-LLM-Key` بلا توثيق للفرق (قاعدة الاصطلاح الواحد).
4. **IEC 60909 (بند 1-5) غير مغلق:** توثيق `calculate_ku`/`_get_rx_ratio`/`_calculate_kappa` والتحقق من ادعاءات "Method B/C" في التوثيق.
5. **أرقام غير مثبتة في الوثائق:** `docs/VALIDATION_REPORT.md` يقول `IEEE 1584 → 0.00% Exact Match` بينما اختبار ST نفسه يتسامح ±5%/±15% ⇒ رقم غير قابل للتكرار بهذه الصيغة، و`CERTIFIED PASS` لغة ادعائية.
6. **الطوارئ CUA فقط:** `ui/src/components/chat/EmergencyStopButton.tsx` لا يستدعي `abortStream()` الموجود في `ui/src/store/chatStore.ts:1009`.
7. **وكيل التصميم التوليدي خارج النطاق جاء إلى main** (`7617d30be`) وبنيويًا `engine/dispatch.py:136-139` سيجعل `generative_design` يستلزم `system` (الاستثناء مقصور على ETAP_EXPERT/ETAP_GUI) ⇒ تعارض مع تصميم الوكيل.
8. **`SECURITY.md`:** أُضيف سطر تدوير المفاتيح دون تأكيد المالك (البرومبت 7-5 يشترطه).

### منهجية العمل (الملزمة)

- **مرحلة واحدة = جلسة واحدة للوكيل.** يُمنع على المنفذ قراءة برومبتات المراحل الأخرى (منع فقدان السياق).
- **بوابة واحدة:** لا تُفتح المرحلة التالية إلا بتقرير موحّد + **تصريح المستشار** بعد مراجعة الأدلة.
- **ذاكرة الجولة** = `docs/status/STATUS_BOARD.md` فقط، وتُحدَّث في نهاية كل مرحلة.
- **التجميد (R2):** لا تعديل أي ملف أثناء القياسات، ويُثبت ذلك بثبات `git rev-parse HEAD` قبل/بعد.
- **ممنوع في كل المراحل:** force-push على `main` أو أي فرع مشترك؛ أي بيانات وهمية/fallback؛ أي ادعاء بلا أمر نُفِّذ؛ أي مسار يتجاوز `tool_policy` ونظام الموافقات.

## [Types]

**لا أنواع تشغيلية جديدة مطلوبة في هذه الجولة.** التغييرات النوعية المحدودة:

| النوع | الملف | التغيير | الحالة |
|---|---|---|---|
| `StudyType.GENERATIVE_DESIGN = "generative_design"` | `agents/models.py:62` | أُضيف في الالتزام `7617d30be` | **قائم — يحتاج مواءمة dispatch (S5)** |
| `ProviderConfig` | `api/chat_stream.py:137-141` | لا تغيير — BYOK يعيد استخدامه كما هو | مُتحقق |
| عقد القناة (HTTP contract) | — | هيدران هما العقد: `X-User-LLM-Key` + `X-User-LLM-Provider`؛ **لا يتحولان لحقول Pydantic** (يظل `extra="forbid"` فعّالًا) | قرار تصميمي — يُوثَّق في S1 |
| `SolverParams` (TS) | `ui/src/components/chat/ParametersDrawer.tsx` | لا تغيير — أُزيل منه `acceleration_factor` مسبقًا | مُتحقق |
| `OPFResult` (`lmp_per_bus`/`binding_constraints`) | `load_flow/optimal_power_flow.py` | **مؤجل** لحزمة AC-OPF/HHO (القرار D5) | خارج النطاق |

**أنواع على مستوى التوثيق (جديدة، لا كود):** مخطط جدول `STATUS_BOARD` (مرحلة/حالة/دليل/متبقٍ/مخاطر)، وأقسام `REPORT_TEMPLATE` السبعة، وقوالب برومبت المرحلة (هوية/حالة مؤكدة/ملفات/خطوات/بوابة/تقرير/توقف).

**ممنوع في هذه الجولة:** أي تغيير على `AgentResult` أو`EngineeringTask` (`agents/models.py:64-86`) أو`StudyRegistration` (`engine/dispatch.py`) — أخطر لمس هذه العقود هو `requires_system` في مُنشئ الجدول (سلوكي وليس نوعيًا — يُعالج في S5).

## [Files]

### ملفات جديدة (أنشأها المستشار الآن — توثيق فقط)

| المسار (مطلق) | الغرض |
|---|---|
| `c:\Users\EWS-01\Desktop\etap\implementation_plan.md` | وثيقة الخطة الشاملة (هذا الملف) |
| `c:\Users\EWS-01\Desktop\etap\docs\status\STATUS_BOARD.md` | الذاكرة الرسمية للجولة (تُحدَّث نهاية كل مرحلة) |
| `c:\Users\EWS-01\Desktop\etap\docs\status\REPORT_TEMPLATE.md` | نموذج التقرير الإلزامي |
| `c:\Users\EWS-01\Desktop\etap\docs\phases\README.md` | قواعد استخدام المراحل |
| `c:\Users\EWS-01\Desktop\etap\docs\phases\S0.md` … `S8.md` + `S1_5.md` + `START_HERE.md` | برومبت كل مرحلة (ملف مستقل يُسلَّم للوكيل وحده) + دليل المالك |

### ملفات جديدة (ينشئها المنفذ خلال S0–S6)

| المسار (مطلق) | الغرض | ملاحظة |
|---|---|---|
| `c:\Users\EWS-01\Desktop\etap\logs\baseline_2026-09-21.txt` | خط أساس حرفي قبل أي تعديل | **مستثنى من git** (`.gitignore:328 logs/`) ⇒ لا يُدفع؛ يُثبت وجوده محليًا بالتقرير |
| `c:\Users\EWS-01\Desktop\etap\ui\src\__tests__\p6\emergency-stop.test.tsx` | اختبار إيقاف حقيقي للدراسة الجارية | إن لم يوجد اختبار بنفس الاسم في الدليل |
| `c:\Users\EWS-01\Desktop\etap\tests\test_iec60909_method_evidence.py` | أدلة kappa/R-X حسابات يدوية | البديل المفضل: توسيع `tests/test_iec60909_published_cases.py` القائم |

### ملفات قائمة تُعدَّل (بالترتيب — كل ملف بتغييره المحدد)

| # | المسار (مطلق) | التغيير المحدد | المرحلة |
|---|---|---|---|
| 1 | `api\routes.py` | إضافة `"x-user-llm-key"` و`"x-user-llm-provider"` إلى **كلا** مصفوفتَي `allow_headers` (حاليًا في منطقة السطور 767-777 و787-797 — الأرقام تتغير بعد التعديل الأول، ابحث بالسياق) | S1 |
| 2 | `api\chat_stream.py` | تصحيح docstring `119-133` (إزالة تناقض "no client keys ever") + توثيق العلاقة مع المسار القديم `x-active-key` | S1 |
| 3 | `ui\src\lib\llm-chat.ts` | توثيق اختيار القناة (كانت التعديلات موجودة: السطور ~1150-1155) — لا تغيير سلوكي إلا إن اعتمدتُ توحيد الاصطلاح | S1 |
| 4 | `docs\AR\README.ar.md` + `docs\generated\*` (المتعلق بالـAPI) | وصف القناة الحقيقية بعد الإغلاق | S1 |
| 5 | `fault_analysis\iec60909_engine.py` | توثيق `calculate_ku` (سطر 148) بمرجع البند الدقيق + حسم `_get_rx_ratio`/`_calculate_kappa` (424-449) وحذف/تنفيذ ادعاءات Method B/C | S2 |
| 6 | `docs\VALIDATION_REPORT.md` | استبدال كل رقم غير قابل للتكرار (أبرزها `IEEE 1584 → 0.00% Exact Match`) بأرقام مخرجات حية + تاريخ + `git rev-parse HEAD`؛ إزالة `CERTIFIED PASS` | S3 |
| 7 | `docs\STANDARDS_COMPLIANCE_MATRIX.md` | التحقق صفًا صفًا + عمود القيود المعلنة | S3 |
| 8 | `docs\TRUST_CHARTER.md` | تضييق ادعاء MathGuard إلى النطاق الفعلي (بند 7-3أ) + مواءمة لغة "PE stamp" مع قرار السلامة القانونية | S3 |
| 9 | `SECURITY.md` | تعليق سطر التدوير حتى تأكيد المالك (D4) | S3 |
| 10 | `ui\src\components\cards\ResultCard.tsx` | إزالة/تليين عبارة `16/16 Verified (claims_audit)` الثابتة + إسقاط أي إسناد معياري غير مدعوم (مثال: `data_export → ISO 27001`) | S3 |
| 11 | `ui\src\components\chat\EmergencyStopButton.tsx` | استدعاء `abortStream()` **قبل** `activateEmergencyStop()` + رسائل تفرق بين ما أكده الخادم وما أُوقف محليًا | S4 |
| 12 | `ui\src\components\chat\ActivityDrawer.tsx` | زر `Stop` لكل عملية جارية مربوط بنفس المسار | S4 |
| 13 | `engine\dispatch.py` | في `_build_dispatch()`: إضافة `StudyType.GENERATIVE_DESIGN` إلى استثناء `requires_system=False` | S5 |
| 14 | `AGENTS.md` | توثيق DesignAgent + قناة BYOK + تصحيح أي ادعاء قديم | S5 |
| 15 | `requirements-dev.txt` | إضافة `pytest-xdist>=3.6` **فقط** إذا أُقرّ في S0 (وإلا إسقاط `-n 8` من كل أوامر البوابة) | S0 |

**لا حذف ولا نقل لأي ملف** في هذه الجولة. الخيار (ب) لوكيل التصميم = إرجاع بالـ PR (قرار المالك D2) وليس حذفًا يدويًا.

## [Functions]

### دوال تُعدَّل (الاسم — الملف — التغيير المطلوب)

| # | الدالة | الملف (مطلق) | التغيير | المرحلة |
|---|---|---|---|---|
| 1 | `_build_dispatch()` | `engine\dispatch.py:101-161` | إضافة `StudyType.GENERATIVE_DESIGN` إلى استثناءات `requires_system` (المنطقة ~136-139) فلا تُلزَم الدراسة المدعومة بالوكيل بالبيانات النظامية | S5 |
| 2 | `_calculate_kappa(self, bus_index)` | `fault_analysis\iec60909_engine.py:437-449` | لا تغيير في المعادلة (Method A: `1.02 + 0.98*exp(-3*R/X)` مع كبح 2.0) — إضافة توثيق البند والحدود؛ وأي ادعاء "Method B/C" في المستودع: إما كود مطابق أو حذف الادعاء | S2 |
| 3 | `_get_rx_ratio(self, bus_index)` | `fault_analysis\iec60909_engine.py:424-435` | توثيق أن R/X يستخدم الجزء التخيلي **بإشارته** (موثق بالسطر 432) + مرجع البند | S2 |
| 4 | `calculate_ku(...)` | `fault_analysis\iec60909_engine.py:148-165` | توثيق البند الدقيق لعوامل KG/KT/KS مع تبرير التسمية (بند 1-5 من البرومبت) — بلا تغيير سلوكي | S2 |
| 5 | `resolve_provider_config(provider, model, user_api_key=None, user_provider=None)` | `api\chat_stream.py:146-201` | **لا تغيير سلوكي** بلا قرار توحيد الاصطلاح؛ يُصلح فقط الـdocstring الأعلى (119-133) المناقض للسلوك، ويُوثَّق عقد الهيدرين | S1 |
| 6 | `sanitize_error_text(text, limit, extra_secrets)` | `api\chat_stream.py:252-272` | ممدَّدة مسبقًا (تضمين `cfg.api_key` في التطهير) — يُضاف اختبار «لا ظهور للمفتاح في أي سجل» | S1 |
| 7 | `abortStream()` + `activateEmergencyStop(reason?)` | `ui\src\store\chatStore.ts:1009` و`:1068` | **لا تغيير في التوقيع** — يُعاد تركيبهما في مكوّن الزر (abort → activate) | S4 |
| 8 | مكوّن `EmergencyStopButton` (دالة React) | `ui\src\components\chat\EmergencyStopButton.tsx` | استدعاء `abortStream()` قبل نداء الخادم + رسائل تفصل «أوقف محليًا» عن «أكده الخادم» | S4 |

### دوال جديدة (لأغراض الاختبار/الملاءمة فقط)

| الدالة | الملف | الغرض | المرحلة |
|---|---|---|---|
| `test_preflight_allows_byok_headers` | `tests\test_chat_stream.py` | إثبات أن قائمة `access-control-allow-headers` تتضمن `x-user-llm-key` (فراغ الاختبار الحالي لأنه لا يطبق CORS) | S1 |
| `test_byok_key_never_logged` | `tests\test_chat_stream.py` | `caplog`/مخارج السجل خالية من المفتاح المُمرَّر | S1 |
| `test_dispatch_generative_design_requires_no_system` | `tests\test_design_agent_scaffold.py` (توسيع) | `STUDY_DISPATCH["generative_design"].requires_system is False` | S5 |
| حالات `kappa` اليدوية | `tests\test_iec60909_method_evidence.py` **أو** توسيع `tests\test_iec60909_published_cases.py` | R/X=0.1 → kappa يدوية؛ R/X→0 → 2.0؛ R/X كبير → ≈1.02 | S2 |

### دوال محذوفة

**لا حذف** في هذه الجولة (يبقى المسار القديم `x-active-key` فعّالًا حتى قرار توحيد معلن).

## [Classes]

| الفئة | الملف (مطلق) | الحالة | التغيير |
|---|---|---|---|
| `DesignAgent(BaseAgent)` | `agents\design_agent.py:48` | قائمة من `7617d30be` (خارج نطاق البرومبت الأصلي) | لا تعديل في المنطق — فقط مواءمة `dispatch` + توثيق `AGENTS.md` + اختبار dispatch (قرار D2 يحدد الإكمال أو العزل) |
| `ArcFlashEngine` | `fault_analysis\arc_flash_engine.py` | **لا تغيير** — VarCf والحدود مؤكدة صحيحة | — |
| `EmergencyStopButton` (مكوّن) | `ui\src\components\chat\EmergencyStopButton.tsx` | تعديل سلوكي | تركيب abort + activate (S4) |
| `ResultCard` (مكوّن) | `ui\src\components\cards\ResultCard.tsx` | تعديل توثيقي/صدق | إزالة الادعاء الثابت (S3) |

**لا فئات جديدة ولا محذوفة.** `StudyRegistration` تبقى كما هي — يتغير فقط **قرار** قيمة `requires_system` عند بناء الجدول.

## [Dependencies]

| الحزمة | التغيير | المبرر | المرحلة |
|---|---|---|---|
| `pytest-xdist>=3.6` | إضافة إلى `requirements-dev.txt` **فقط** إذا اختير المسار (أ) | أمر البوابة `-n 8` في البرومبت يفشل اليوم لأن الحزمة غير مثبتة وغير مذكورة في المانيفست | S0 |
| `pytest-timeout>=2.4.0` | موجودة في `requirements-dev.txt` — **تثبيت محلي فقط** في `.venv-fix` | غير مثبتة حاليًا ⇒ `--timeout=90` يفشل | S0 |

**لا تغييرات runtime** (لا حزم إنتاجية جديدة، لا ترقيات إصدارات). حزمة إصلاح ثغرات المانيفستات (`requirements*.txt` + `pnpm-lock`) **خارج نطاق هذه الجولة** (بقرار منفصل).
**ملاحظة بيئية إلزامية:** التقاط stderr على PowerShell يفقد مخرجات الأدوات (`ruff`) — تُحوَّل المخرجات إلى ملف مؤقت (`1> %TEMP%\out.txt 2>&1`) ثم تُقرأ.

## [Testing]

### الاستراتيجية
1. **اختبارات مقيَّدة بالمرحلة** + **بوابة كلية** في S6. كل ادعاء في أي تقرير = أمر نُفِّذ ونتيجته الحرفية.
2. **دليل التجميد (R2):** `git rev-parse HEAD` قبل/بعد كل قياس = نفس القيمة، و`git status --porcelain` نظيف.
3. **ممنوع** `skip/xfail` لإخفاء فشل، وممنوع «نجحت الاختبارات» بلا أرقام.

### اختبارات كل مرحلة

| المرحلة | الاختبار/الدليل | الملف |
|---|---|---|
| S1 | Preflight يسمح `x-user-llm-key` · 503 عند غياب كل المفاتيح · المفتاح لا يظهر في السجلات | `tests\test_chat_stream.py` |
| S1.5 | إغلاق 8 إخفاقات خط أساس (قوس×2 · rate-limit×3 · HF-parity · symlink · headers) — تشغيل تسلسلي إلزامي | الملفات الستة في `docs\phases\S1_5.md` |
| S2 | kappa يدوية (R/X=0.1) · سقف 2.0 عند R/X→0 · ≈1.02 عند R/X كبير · ثبات نتائج الحالات المنشورة | `tests\test_iec60909_published_cases.py` (أو ملف جديد) |
| S3 | إعادة تشغيل `run_ieee_benchmarks.py` + `claims_audit --strict` + اختبارات ST/الذهبية، وتصحيح الوثائق حسب المخرجات | الوثائق الثلاث + `ResultCard.tsx` |
| S4 | ترتيب abort→activate · فشل الخادم لا يُظهر «تأكيد» · تعطيل الزر بعد التنشيط | `ui\src\__tests__\p6\*` |
| S5 | `STUDY_DISPATCH["generative_design"].requires_system is False` + الرفض الصريح عند العلم المغلق | `tests\test_design_agent_scaffold.py` |
| S6 | البوابة الكاملة (أدناه) | كل ما سبق |

### البوابة الكلية (S6) — الأوامر الحرفية
```powershell
# 1) الاختبارات الكاملة (أضف -n 8 فقط إن أُقرّ تثبيت xdist في S0)
& .venv-fix/Scripts/python -m pytest tests/ --ignore=tests/load --ignore=tests/stress --ignore=tests/chaos -q --tb=short
# 2) الجودة الساكنة
& .venv-fix/Scripts/python -m ruff check . --config ruff.toml
& .venv-fix/Scripts/python validate_syntax.py
& .venv-fix/Scripts/python validation_suite.py
& .venv-fix/Scripts/python scripts/claims_audit.py --strict
& .venv-fix/Scripts/python -m pytest tests/test_engineering_service.py -q
# 3) التغطية (قياس أولًا — العتبة بقرار D6)
& .venv-fix/Scripts/python -m pytest tests/ -q --cov=. --cov-report=term-missing
# 4) الواجهة
pnpm -C ui typecheck ; pnpm -C ui test ; pnpm -C ui build
```
> أرقام البرومبت (`validation_suite 31/31`, `test_engineering_service 74/74`) **ادعاءات تُقاس** — إن اختلفت تُسجَّل الحقيقة ويُبلَّغ المستشار فورًا.

### قياسات حالية موثوقة تُستخدم لكشف الانحدار
| القياس | القيمة الحالية المؤكدة |
|---|---|
| `ruff check .` | 0 (exit 0) |
| `claims_audit --strict` | 16 Verified / 0 Missing |
| `tests/test_arcflash_1584_st_cases.py` | 7 passed (18.50s) |
| زمن `test_solver_parameter_cleanup` + `test_design_agent_scaffold` | **غير مقيس** (تجاوز حد الأداة 30s) — يُقاس في S0 |

## [Implementation Order]

1. **S0 — التثبيت وخط الأساس.** لماذا أولًا: كل الأبواب التالية تعتمد على بيئة قياس صحيحة وخط أساس معروف (وقرار xdist/timeout يحسم شكل أوامر كل المراحل). مخرج: `logs/baseline_2026-09-21.txt` + قرار البيئة + زمن الاختبارات الثلاثة المفردة.
2. **S1 — إغلاق BYOK الصدق.** لماذا الآن: أعلى عيب مؤكد يحجب قبول 4-4 (محادثة من ChatWorkspace) وهو الأسهل إثباتًا.
2.5. **S1.5 — إغلاق F-BASE-A (8 إخفاقات خط أساس).** لماذا هنا: بوابة S6 هي «0 failed»، وS3 تبني الوثائق على قياسات حية، وتصحيح توقعات اختبارَي القوس (للمعادلة المعيارية — مطلب 1-3) لا يجوز تأجيله. الثلاثة الخاصة بوكيل التصميم تُغلق في S5.
3. **S2 — إغلاق IEC 60909.** لماذا: البند الوحيد المتبقي من المرحلة 1 (توثيق/حسم Method) ولا يعتمد على S1.
4. **S3 — تدقيق أدلة الثقة.** لماذا بعد S1/S2: أرقام الوثائق تتبع الكود النهائي، وإعادة التشغيل تُنتج الأرقام الحقيقية.
5. **S4 — الطوارئ الحقيقي.** لماذا: مطالب قبول 5-4 وسيناريو 8-4-و مستقل عن المسارات الخلفية.
6. **S5 — وكيل التصميم.** لماذا: يمس `agents`/`dispatch` ولا يجوز أن يتقاطع مع S1–S4؛ يتطلب قرار المالك D2.
7. **S6 — القياس النهائي الشامل.** لماذا: لا يُقاس الشامل قبل إغلاق كل التعديلات (تجميد كامل).
8. **S7 — الدفع النظيف.** لماذا: بعد استقرار الكود والقياسات؛ يمنع أي دفع مباشر لـ`main` بعد اليوم.
9. **S8 — التقرير النهائي + HF smoke.** لماذا: توثيق ما استُشهد به فعلًا، وإقرار ما تبقّى بالتصريح.

**خارج هذه الجولة صراحةً:** حزمة AC-OPF/HHO (P0–P2) · خطة ثغرات المانيفستات (CSV) · أي ترقية حزم إنتاجية · أي ملف خارج قوائم المراحل.

## Appendix A — سجل الأدلة المنفَّذة (تحقق المستشار 2026-09-21)

| الأمر | النتيجة الحرفية |
|---|---|
| `git rev-parse HEAD origin/main` | `c7cf56e6cee23451648ade93520f2b78f386ae27` (متطابقان) |
| `git status --porcelain` | فارغ (الشجرة نظيفة) |
| `ruff check . --config ruff.toml` | `RUFF_CLEAN_ZERO` (exit 0) |
| `python scripts/claims_audit.py --strict` | `Summary: 16 Verified, 0 Missing empirical test coverage.` |
| `pytest tests/test_arcflash_1584_st_cases.py -q -o addopts='' -p no:cacheprovider` | `7 passed in 18.50s` |
| قراءة `api/routes.py:767-777,787-797` | `allow_headers` لا يتضمن `x-user-llm-key` ⇒ عيب CORS مؤكد |
| `pip list` في `.venv-fix` | pytest 9.1.1 · pytest-asyncio 1.4.0 · pytest-cov 7.1.0 · ruff 0.16.7 — **لا xdist/لا timeout** |
| قراءة `requirements-dev.txt` | pytest · pytest-asyncio · pytest-cov · `pytest-timeout>=2.4.0` — **لا pytest-xdist** |
| `git ls-remote origin refs/heads/feat/trust-hardening` | `7617d30be…` (متأخر عن `main` الذي يحمل نفس الجولة) |
| `pytest tests/test_solver_parameter_cleanup.py tests/test_design_agent_scaffold.py tests/test_iec60909_published_cases.py` | **تجاوز حد الأداة (30s)** — لم تُقَس؛ تُقاس في S0 |
| قراءة `ui/src/components/chat/EmergencyStopButton.tsx` | يستدعي kill-switch الـCUA فقط — لا `abortStream` ⇒ بند 5-4 مفتوح |
| قراءة `engine/dispatch.py:101-161` | الاستثناء `requires_system=False` مقصور على `ETAP_EXPERT/ETAP_GUI` ⇒ عيب `generative_design` مؤكد |

## Appendix B — بروتوكول الدفع/الدمج النظيف (تفصيل S7)

```powershell
git fetch origin
git switch -c fix/trust-closure origin/main            # نقطة الانطلاق
# التزامات صغيرة بمدلولات: fix(api)… / fix(iec60909)… / docs(trust)… / fix(chat)… / fix(dispatch)…
git pull --rebase origin main                          # قبل كل push
& .venv-fix/Scripts/python -m ruff check . --config ruff.toml
& .venv-fix/Scripts/python -m pytest <اختبارات المرحلة> -q
git push -u origin fix/trust-closure
# PR واحد: "fix: close BYOK/IEC-60909/trust-evidence gaps (S0–S6)" يضم ملخص المراحل بأرقامها
# راقب: ci · quality-gates · ui-quality · secret-scan · api-schema · python-compatibility حتى الاخضرار
git fetch origin ; git rev-parse origin/main            # يجب أن يطابق نقطة الأساس وإلا أعد الدورة
git ls-remote origin main                              # بعد الدمج: SHA جديد + الشجرة نظيفة
```
**محرّمات:** force-push على `main`/أي فرع مشترك · `--ours/--theirs` أعمى · الدمج وبوابة حمراء · حذف فرع ليس لك · نشر رقم بلا أمر.

## Appendix C — فهرس التسليم والتشغيل

| الملف | المحتوى | الحالة |
|---|---|---|
| `implementation_plan.md` | هذه الوثيقة (Overview → Implementation Order + ملاحق) | ✅ |
| `docs\phases\README.md` | قواعد استخدام المراحل | ✅ |
| `docs\phases\S0.md` … `S8.md` | برومبت كل مرحلة (يُسلَّم ملف واحد في كل جلسة) | ✅ |
| `docs\status\STATUS_BOARD.md` | الذاكرة الرسمية + القرارات D1–D6 + المخاطر | ✅ |
| `docs\status\REPORT_TEMPLATE.md` | نموذج التقرير الإلزامي (7 أقسام) | ✅ |

**خطوات التشغيل:** أرسل `docs\phases\S0.md` للوكيل المنفذ **وحده** → استلم تقريره بنموذج `REPORT_TEMPLATE` → راجع الأدلة وصرّح بـS1 → وهكذا حتى S8.

**ملفات قيادة الجولة** (هذه الوثائق) أنشأها المستشار وغير مُلتزمة في git حتى يُقرَّر إدراجها ضمن التزامات S7 — لا تُحذف ولا تُعدَّل إلا بتصريح.

**قرارات تنتظر المالك:** D1 تجميد الوكيل الآخر · D2 وكيل التصميم (إكمال/عزل) · D3 اعتماد التزامات `main` المباشرة كنقطة انطلاق · D4 تأكيد تدوير المفاتيح · D5 توقيت AC-OPF/HHO · D6 عتبة التغطية.




