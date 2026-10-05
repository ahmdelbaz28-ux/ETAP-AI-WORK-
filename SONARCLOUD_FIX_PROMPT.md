# برومبت توجيهي للوكيل المنفذ — إصلاح مشاكل SonarCloud | ETAP-AI-WORK-

**Project**: https://sonarcloud.io/project/overview?id=ahmdelbaz28-ux_ETAP-AI-WORK-
**Repository**: https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
**عدد المشاكل**: 110 (المصدر: `reports/sonar_issues.json` — تحليل 2026-09-02)
**الهدف**: إصلاح كل مشاكل SonarCloud المفتوحة. هذا البرومبت يحتوي كل مشكلة مع الملف والسطر والقاعدة والإصلاح المطلوب — **بدون أي بحث إضافي**.

---

## ملخص المشاكل حسب الخطورة

### BLOCKER (1)
- **pythonsecurity:S5131** — `hf-space/app.py:1796` — بيانات مستخدم غير معالجة تعكس في الاستجابة (XSS)

### CRITICAL (18)
| القاعدة | العدد | المواقع |
|---------|-------|---------|
| python:S3776 Cognitive Complexity | 10 | `api/routes.py:389,748`، `security/wiring.py:94`، `api/agents.py:1232`، `etap_integration/etap_com.py:688`، `gis_integration/providers/__init__.py:60`، `api/feature_flags.py:154`، `api/session_stream.py:164,415,471`، `hf-space/app.py:709` |
| typescript:S3776 Cognitive Complexity | 3 | `ui/src/store/chatStore.ts:290,399`، `ui/src/lib/llm-chat.ts:1053` |
| python:S1192 Duplicate Literal | 5 | `api/results_store.py:152,195,365`، `api/chat_stream.py:260`، `gis_integration/providers/arcgis_provider.py:17` |

### MAJOR (45+)
| القاعدة | العدد | المواقع الرئيسية |
|---------|-------|------------------|
| python:S8415 ناقص `responses` في FastAPI | 22 | `api/results_store.py` (21)، `api/agents.py` |
| pythonsecurity:S5145 log injection | 22 | التفاصيل في `reports/sonar_issues.json` |
| python:S9073 assertions مركبة | 4 | `tests/test_session_stream.py:149`، `tests/test_p8_advanced_routes.py:240`، `tests/test_agent_executor.py:562`، `tests/test_approvals.py:75` |
| typescript:S3358 ternaries متداخلة | 4 | `ui/src/components/chat/ActivityDrawer.tsx:78`، `ui/src/store/chatStore.ts:367,550`، `ui/src/lib/llm-chat.ts:1114` |
| مفردة | 14 | `api/agents.py:245` S3923، `api/approvals.py:438` S1871، `scripts/scenarios/run_scenario_4.py:435` S2583، `api/results_store.py:378` S7493، `api/session_stream.py:164` S7497، `etap_integration/etap_com.py:1486` S6549، `core/network_topology.py:431` S1066، `tests/test_p7c_mcp_export.py:578,590` S5778، `ui/src/components/viewer/ResultViewer.tsx:86` S7762، `ui/src/components/cards/DecisionCard.tsx:25` S4624، `ui/src/components/settings/SecurityFlagsPanel.tsx:117,119` S6772، `ui/.../ProviderKeysPanel.test.tsx:183` S7721 |

### MINOR (30+)
- python:S8410 (3)، S9083 (2)، S7503 (2)، S9117، S7504، S6546 (`etap_com.py:1114`)، S1172 (`api/agents.py:1155`)، S9100 (`tests/test_p8_advanced_routes.py:49`)، S8997 (`tests/test_agent_executor.py:250`)
- typescript:S6582 (5)، S6759 (2)، S3863 (2)، S7754، S7722
- pythonsecurity:S5145 (22)

---

## تعليمات الإصلاح التفصيلية (بالدليل والمسارات الدقيقة)

### 1. `api/results_store.py` — 28 مشكلة (الأولوية القصوى)

**(a) python:S1192 CRITICAL — استخرج ثوابت:**
- سطر 152: `"application/octet-stream"` مكررة 5 مرات → ثابت `MIME_OCTET_STREAM`
- سطر 195: `"Invalid file_path"` مكررة 4 مرات → `ERR_INVALID_PATH`
- سطر 365: `"Result not found"` مكررة 4 مرات → `ERR_RESULT_NOT_FOUND` (ملاحظة: السطر 766 يشير أصلاً إلى `ERR_RESULT_NOT_FOUND` — تحقق من وجوده، أضفه إن لم يوجد)

**(b) python:S8415 MAJOR — أضف `responses={...}` لزخارف الراوتات:**
- كود `400` في الأسطر: 195, 197, 200, 202, 205, 207, 209, 271, 277, 356, 372
- كود `413` في الأسطر: 281, 358, 568
- كود `404` في الأسطر: 365, 367, 603, 643, 661
- كود `500` في الأسطر: 388, 409, 591
- الإصلاح: أضف مثل `responses={400: {"description": "Invalid file path"}}` لزخرف الراوت الذي يحتوي على `HTTPException` المُعلَّم. بعض الراوتات موثقة بالفعل (مثلاً الأسطر 727–733 و752–758) — اتبع نفس الأسلوب بالضبط.

**(c) python:S7493 MAJOR — سطر 378:** `open()` متزامنة داخل `async def` → استبدل بـ `aiofiles.open()` (أضف `import aiofiles`) أو `anyio.to_thread.run_sync`.

**ترتيب التنفيذ:** الثوابت أولاً (يزيل 3 CRITICAL)، ثم كتل `responses` (يزيل 22 MAJOR)، ثم السطر 378.

---

### 2. `api/routes.py` — 2× python:S3776 CRITICAL
- سطر 389: Cognitive Complexity 22 → يجب أن يكون ≤15
- سطر 748: Cognitive Complexity 18 → ≤15
- الإصلاح: استخرج الفروع الداخلية إلى دوال مساعدة، استخدم guard clauses/early returns. السلوك يجب أن يبقى مطابقاً.

### 3. `security/wiring.py:94` — python:S3776 CRITICAL
- Cognitive Complexity 29 → ≤15 (أسوأ ملف بايثون). استخرج فروع التحقق إلى دوال صغيرة مُسمّاة.

### 4. `api/agents.py` — 3 مشاكل
- سطر 245 python:S3923 MAJOR: كل فروع الـ `if` متطابقة (الأدلة: عبارات مكررة في 246 و248) → احذف الشرط أو ادمج الفروع.
- سطر 1155 python:S1172 MINOR: معامل `host` غير مستخدم → احذفه وحدّث المتصلين.
- سطر 1232 python:S3776 CRITICAL: Cognitive Complexity 20 → ≤15 → استخرج دوالاً مساعدة.

### 5. `etap_integration/etap_com.py` — مشكلتان
- سطر 688 python:S3776 CRITICAL: 17 → ≤15 → قسّم الدالة.
- سطر 1486 pythonsecurity:S6549 MAJOR: مسار مبني من بيانات مستخدم → عرّضه بـ `os.path.realpath` على مجلد أساس وارفض الخروج عنه (نفس نمط فحوصات المسار في `api/results_store.py`).

### 6. `gis_integration/providers/arcgis_provider.py:17` — python:S1192 CRITICAL
- النص `"ArcGISProvider is archived; use QGISProvider or MockGISProvider"` مُعلَّم 6 مرات.
- الدليل: الثابت `MSG_ARCGIS_ARCHIVED` موجود فعلاً في `arcgis_provider.py:30` ويُستخدم في الأسطر 64–79؛ والنص الحر مكتوب يدوياً أيضاً في `gis_integration/providers/__init__.py:98`.
- الإصلاح: في `__init__.py` استورد `MSG_ARCGIS_ARCHIVED` بدل إعادة كتابة النص؛ لو ما زال Sonar يعلّم `arcgis_provider.py` فهو false positive → `# NOSONAR python:S1192` مع السبب.

### 7. `gis_integration/providers/__init__.py:60` — python:S3776 CRITICAL
- منطق الـ factory Cognitive Complexity 16 → ≤15. الإصلاح: استخرج فرع `arcgis_online` feature-flag (الأسطر 101–114) إلى دالة `_resolve_arcgis_online(mock_allowed)`.

### 8. `api/feature_flags.py:154` — python:S3776 CRITICAL
- Cognitive Complexity 17 → ≤15. الإصلاح: استخرج حساب env/effective-enabled (مكرر في ~الأسطر 467–470 و527–528) إلى دالة `_effective_enabled(enabled) -> bool`؛ وقسّم فروع التحقق المتداخلة.

### 9. `api/session_stream.py` — 3× S3776 CRITICAL + 1× S7497 MAJOR
- سطر 164: التعقيد 17 → ≤15؛ **وأيضاً** python:S7497 MAJOR: يجب إعادة رمي `asyncio.CancelledError` بعد التنظيف: `except asyncio.CancelledError: <cleanup>; raise`.
- سطر 415: التعقيد 27 → ≤15.
- سطر 471: التعقيد 27 → ≤15.
- الإصلاح: استبدل سلاسل `if` المتداخلة لنوع الرسالة بجدول dispatch (dict) من دوال صغيرة لكل نوع.

### 10. `hf-space/app.py` — BLOCKER + CRITICAL
- **سطر 1796 pythonsecurity:S5131 BLOCKER:** بيانات مستخدم غير معالجة تعكس → غلّف بـ `html.escape()` (أو template autoescaping). هذا أولوية أمنية عليا.
- سطر 709 python:S3776 CRITICAL: التعقيد 21 → ≤15 → استخرج دوالاً مساعدة.

### 11. `scripts/scenarios/run_scenario_4.py:435` — pythonbugs:S2583 MAJOR
- الشرط يُقيَّم دائماً على false. افحص الأسطر 430–445 (دالة `_compute_diff` / حلقة features): المقارنة تستخدم قيم غير متوافقة. صحّح المقارنة حسب المنطق المقصود.

### 12. `api/approvals.py:438` — python:S1871 MAJOR
- الفرع في الأسطر 438–439 مطابق للسطر 435 (كلاهما يرمي `HTTPException` بكود 422 مع `policy_decision.get("reason")`). ادمج الفرعين أو ميّز الرسائل.

### 13. `api/chat_stream.py:260` — python:S1192 CRITICAL
- نص SSE `"data:"` مكرر 4 مرات → عرّف `SSE_DATA_PREFIX = "data:"` أعلى الملف واستخدمه في كل مكان.

### 14. `core/network_topology.py:431` — python:S1066 MAJOR
- `if` متداخلة داخل `if` بدون `else` → ادمجهما: `if cond_a and cond_b:`.

---

### 15. إصلاحات TypeScript / UI

| الملف | السطر | القاعدة | الإصلاح |
|-------|-------|---------|---------|
| `ui/src/components/viewer/ResultViewer.tsx` | 86 | S7762 MAJOR | `parentNode.removeChild(childNode)` → `childNode.remove()` |
| `ui/src/components/settings/SecurityFlagsPanel.tsx` | 117,119 | S6772 MAJOR | صحّح المسافة الغامضة في JSX |
| `ui/src/components/cards/DecisionCard.tsx` | 25 | S4624 MAJOR | حلّل template literals المتداخلة إلى ثوابت وسيطة |
| `ui/src/components/chat/ActivityDrawer.tsx` | 78 | S3358 MAJOR | استخرج الـ ternary المتداخل إلى متغير مسمّى |
| `ui/src/store/chatStore.ts` | 290 | S3776 CRITICAL | Cognitive Complexity 44 → ≤15 (استخرج دوالاً بأسلوب reducer) |
| `ui/src/store/chatStore.ts` | 399 | S3776 CRITICAL | 18 → ≤15 |
| `ui/src/store/chatStore.ts` | 367, 550 | S3358 MAJOR | استخرج الـ ternaries المتداخلة |
| `ui/src/lib/llm-chat.ts` | 1053 | S3776 CRITICAL | 37 → ≤15 |
| `ui/src/lib/llm-chat.ts` | 1114 | S3358 MAJOR | استخرج الـ ternary المتداخل |
| `ui/src/lib/llm-chat.ts` | 1008 | S2245 MAJOR | Math.random لـ jitter غير أمني → `// NOSONAR typescript:S2245` مع السبب، أو استخدم `crypto.getRandomValues` |
| `ui/src/components/settings/__tests__/ProviderKeysPanel.test.tsx` | 183 | S7721 MAJOR | انقل `renderWithExistingKey` إلى نطاق الـ outer scope |
| `ui/src/lib/__tests__/advanced-routes.test.tsx` | 26-27 | S3863 MINOR | ادمج استيراد `../advanced-routes` المكرر في استيراد واحد |

### 16. ملفات اختبار بايثون

| الملف | السطر | القاعدة | الإصلاح |
|-------|-------|---------|---------|
| `tests/test_session_stream.py` | 149 | S9073 MAJOR | قسّم assertion المركب إلى assert منفصلة |
| `tests/test_p8_advanced_routes.py` | 240 | S9073 MAJOR | قسّم assertion المركب |
| `tests/test_p8_advanced_routes.py` | 49 | S9100 MAJOR | احذف `yield` عديم الفائدة |
| `tests/test_agent_executor.py` | 562 | S9073 MAJOR | قسّم assertion المركب |
| `tests/test_agent_executor.py` | 250 | S8997 MAJOR | استخدم fixture الـ `monkeypatch` بدل تعديل الحالة العامة يدوياً |
| `tests/test_approvals.py` | 75 | S9073 MAJOR | قسّم assertion المركب |
| `tests/test_p7c_mcp_export.py` | 578, 590 | S5778 MAJOR | استدعاء واحد فقط قد يرمي استثناء داخل كل `pytest.raises` |

---

### 17. pythonsecurity:S5145 — 22× حقن سجلات (MINOR، دفعة واحدة)
- المواقع الدقيقة: صفّ `reports/sonar_issues.json` بالقاعدة `pythonsecurity:S5145`.
- الإصلاح لكل موضع باستخدام أنماط موجودة في المشروع:
  - تنظيف أحرف التحكم أولاً (نمط `api/dual_control.py:46-50` دالة `_sanitize_log_value`)، أو
  - تجزئة القيمة (نمط `api/email_otp.py:201-203`)، أو
  - `# NOSONAR pythonsecurity:S5145: <field> already validated against <source>` عندما تكون القيمة من طرف السيرفر.

### 18. python:S8410 — Annotated FastAPI DI (3× MINOR)
- `api/studies.py:206` (+2 موضع في `reports/sonar_issues.json`): غيّر `x: T = Depends(f)` → `x: Annotated[T, Depends(f)]`. النمط الصحيح داخل المشروع: `api/studies.py:335-342`.

### 19. باقي الـ MINORs (دفعة)
- `python:S7503` (2): احذف كلمة `async` عديمة الفائدة (واحدة `api/agent_executor.py:221`).
- `python:S6546` (`etap_integration/etap_com.py:1114`): استخدم union type `str | None`.
- `typescript:S6582` (5): سوء استخدام `??` مقابل `||`.
- `typescript:S6759` (2): اجعل props الـ component readonly (واحد: `ui/src/pages/settings/ProvidersTab.tsx:23`).
- أخرى: `python:S9083` (2)، `S9117`، `S7504`، `typescript:S7754`، `S7722` — راجع `reports/sonar_issues.json`.

---

## ترتيب التنفيذ الموصى به

1. **إصلاحات سريعة (~40 مشكلة):** `api/results_store.py` → `api/chat_stream.py:260` → `api/approvals.py:438` → `api/agents.py:245,1155` → ملفات الاختبار (قسم 16) → `core/network_topology.py:431`.
2. **الأمن:** `hf-space/app.py:1796` (BLOCKER) → `etap_com.py:1486` (S6549) → دفعة S5145 (22 موضع).
3. **Cognitive Complexity (CRITICAL — أعد الهيكلة بحذر، شغّل الاختبارات بعد كل ملف):** `security/wiring.py:94` → `ui/src/store/chatStore.ts:290` → `ui/src/lib/llm-chat.ts:1053` → `api/session_stream.py:415,471` → `api/routes.py:389,748` → `api/agents.py:1232` → `api/feature_flags.py:154` → `etap_integration/etap_com.py:688` → `hf-space/app.py:709` → `gis_integration/providers/__init__.py:60`.
4. **دفعة TypeScript/UI** (قسم 15) + باقي الـ MINORs (أقسام 18–19).
5. **التحقق** (أدناه) ثم push — يعيد SonarCloud المسح تلقائياً.

## أوامر التحقق

```powershell
cd c:\Users\EWS-01\Desktop\etap
ruff check .
python -m pytest tests/ -x -q
cd ui
npm run lint
npm run test
```

## قواعد للوكيل المنفذ

1. **لا تخترع قيماً** — كل ثابت/إصلاح مشتق من الكود الموجود والأدلة أعلاه.
2. **حافظ على السلوك** — إعادة هيكلة فقط؛ لا تغيّر استجابات الـ API أو بوابات الأمان أو معنى الاختبارات.
3. **`# NOSONAR`** فقط لحالات الإيجابية الخاطئة المؤكدة، مع ذكر السبب في السطر.
4. **شغّل الاختبارات بعد كل ملف** (`python -m pytest <related test> -q`)؛ توقف فوراً عند أي regression.
5. **أرقام الأسطر من تحليل 2026-09-02** — إن تغيّرت، ابحث بالقاعدة/الرسالة المقتبسة وليس بالسطر مباشرة.
6. قائمة المشاكل الآلية: `reports/sonar_issues.json` (110 مشكلة)؛ نصية: `reports/sonar_issues_full.txt`.
7. مشروع SonarCloud: `ahmdelbaz28-ux_ETAP-AI-WORK-` — المسح يعمل تلقائياً عند الـ push.

