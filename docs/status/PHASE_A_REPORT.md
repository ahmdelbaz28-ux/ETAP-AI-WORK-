# تقرير المرحلة A (المُصحَّح) — Phase A Report

> **تنبيه وتصحيح:** تم إعداد هذا التقرير التزاماً بنموذج `REPORT_TEMPLATE.md` وميثاق الصدق الهندسي، لتصحيح التوصيف الواقعي لمخرجات Phase A عند الالتزام `d7228c24d412f08e6fee6317bdf539ba6d35a5c9` وإغلاق الفجوات التوثيقية والادعائية.

---

## 1) هوية المرحلة

- المرحلة: `Phase A — الوحدات الهندسية، توحيد القصر، سعة القواطع، تعزيزات المحادثة ومخطط الإجابة`
- `HEAD` المعتمد: `d7228c24d412f08e6fee6317bdf539ba6d35a5c9`
- حالة الشجرة: نظيفة (`clean tree`).
- ملاحظة توثيقية حاسمة: ملف `walkthrough.md` المشار إليه في بعض التوثيقات غير موجود في المستودع أصلًا (لم يتم دمجه أو رفعه)، ومستندات الحالة المعتمدة هي الموجودة داخل `docs/status/`.

---

## 2) جدول التعديلات المنجزة فعلياً في Phase A

| ملف (مسار كامل) | السطر/الدالة | قبل | بعد | السبب الهندسي والدليل |
|---|---|---|---|---|
| `core/units.py` | كامل الملف (جديد) | غير موجود | تعريف `UnitRegistry` وتحويل الوحدات | منع أخطاء تفاوت الوحدات الهندسية (kV, A, MVA) |
| `api/tool_policy.py` | `ENGINEERING_ALIASES`, `validate_engineering_units` | بدون تحقق وحدات | فحص مدخلات الأدوات والتحقق من الأبعاد | رفض التضارب البعدي `UNIT_DIMENSION_MISMATCH` |
| `core/study_engine.py` | 219-270 | معامل 0.95 ثابت | تفويض الحساب التحليلي لـ `IEC60909Engine` | توحيد حسابات القصر وإلغاء المعاملات الاعتباطية |
| `breaker_duty/catalog.py` | كامل الملف (جديد) | غير موجود | كتالوج قواطع IEC 62271-100 | توفير بيانات سعة القواطع المعيارية للمقارنة |
| `breaker_duty/evaluator.py` | كامل الملف (جديد) | غير موجود | فئات تقييم %Duty | حساب نسبة إجهاد القواطع مقابل السعات الاسمية |
| `engine/dispatch.py` | 174-181 | غير مسجل | تسجيل `breaker_duty` كـ `external` | تعريف نوع الدراسة في جدول التوجيه العام |
| `api/chat_stream.py` | 490-502, 505-526 | بدون موجه نظام مخصص أو تشذيب | حقن `etap_engineer_agent`، وتشذيب 8000 توكن | ضبط سلوك المهندس وتفادي تجاوز نافذة السياق |
| `knowledge/chunking.py` | كامل الملف (جديد) | غير موجود | تقطيع النصوص الهندسية (400-600 توكن) | تحسين جودة استرجاع RAG للمعايير |
| `knowledge/rag_engine.py` | 516-538 | بدون إعادة ترتيب | تفعيل hybrid re-ranking | رفع دقة استرجاع معايير IEEE/IEC |
| `api/answer_schema.py` | كامل الملف (جديد) | غير موجود | مخطط `EngineerAnswer` عبر Pydantic | توحيد هيكل الإجابات الهندسية |
| `ui/src/components/chat/MessageList.tsx` | 103-247 | لا يوجد عرض منظم | مكون `EngineerAnswerCard` | عرض الإجابات الهندسية المنظمة في الواجهة |

---

## 3) الأدلة الحرفية (Gate Execution)

```powershell
.venv-fix\Scripts\python.exe -m pytest tests/test_chat_stream.py tests/test_iec60909_published_cases.py tests/test_design_agent_scaffold.py tests/test_tool_policy.py tests/test_breaker_duty.py tests/test_phase_a_chat_enhancements.py tests/test_phase_a_rag_and_schema.py -q --tb=short
76 passed in 188.35s
```

```powershell
.venv-fix\Scripts\python.exe -m ruff check . --config ruff.toml
All checks passed! (RUFF_EXIT=0)
```

```powershell
.venv-fix\Scripts\python.exe scripts\claims_audit.py --strict
Summary: 16 Verified, 0 Missing empirical test coverage.
```

---

## 4) بوابة القبول لـ Phase A

| # | شرط المرحلة | النتيجة | الدليل الحرفي |
|---|---|---|---|
| 1 | التحقق البعدي للوحدات ومنع التخمين | ✅ محقق | `tests/test_tool_policy.py` (20 passed) |
| 2 | توحيد محرك القصر وإلغاء 0.95 | ✅ محقق | `tests/test_iec60909_published_cases.py` (15 passed) |
| 3 | كتالوج وفاحص سعة القواطع IEC 62271-100 | ✅ محقق وحدوياً | `tests/test_breaker_duty.py` (5 passed) |
| 4 | حقن موجه المهندس وتشذيب السياق | ✅ محقق | `tests/test_phase_a_chat_enhancements.py` (4 passed) |
| 5 | تقطيع RAG وإعادة الترتيب ومخطط الإجابة | ✅ محقق | `tests/test_phase_a_rag_and_schema.py` (4 passed) |

---

## 5) غير المنفَّذ بدقة وتصحيح الادعاءات السابقة (Crucial Scaffolds)

يقر هذا التقرير بوجود ثلاثة بنود تم تسجيلها كهياكل أولية (Scaffolds) دون اكتمال مسار تدفقها الإنتاجي، ويتم تصحيح أي ادعاء سابق يزعم اكتمالها:

| البند غير المكتمل | الحقيقة البرمجية والدليل الحرفي | السبب | معالجة الفجوة في Phase B |
|---|---|---|---|
| **مسار استدعاء `breaker_duty` عبر الموزع العام** (`breaker_duty-execution-path`) | الدراسة مسجلة في `engine/dispatch.py:174-181` كـ `handler_type="external"`، لكن الموزع الفعلي `services/study_executor.py:383-384` يرفض أي نوع غير `native` و`agent` برفع `ValueError`. لا يوجد أي مسار استدعاء إنتاجي مكتمل. | اقتصر عمل Phase A على بناء الحزمة واختبارها الوحدوي. | إضافة فرع تنفيذي صريح في `study_executor.py` مشروط براية `breaker_duty`. |
| **تكامل `model2vec` الفعلي** (`model2vec-integration`) | الحزمة مثبتة في البيئة والراية مسجلة في `api/feature_flags.py:181-187`، لكن لا يوجد سطر واحد يستورد المكتبة. دقة 96.7% نتجت حصراً عن `hybrid re-ranking`. | لم يتم ربط محرك `model2vec.StaticModel` بموفر التضمين في `rag_engine.py`. | ربط `model2vec` كمحرك تضمين محلي CPU عند تفعيل راية `rag_model2vec`. |
| **الفرض الخلفي لـ `chat_structured`** (`chat_structured-enforcement`) | راية `chat_structured` غير مستهلكة خلفياً في `api/chat_stream.py`؛ والتحقق من `EngineerAnswer` يتم عبر regex/JSON في الواجهة فقط (`MessageList.tsx:213`). | الاعتماد المؤقت على الواجهة دون فحص في تدفق البث الخلفي. | إضافة تحقق `EngineerAnswer.model_validate_json` وإرسال الحالة في حدث `done`. |

---

## 6) إقرار الصدق الهندسي

نقر بأن كافة التفاصيل المذكورة أعلاه تم التحقق منها فحصاً برمجياً واختبارياً دقيقاً، وأن البنود غير المكتملة تم حصرها وتوصيفها تمهيداً لإغلاقها الكامل في Phase B.
