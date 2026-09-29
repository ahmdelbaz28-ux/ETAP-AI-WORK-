# خطة المرحلة M3 — طبقة التخطيط والتوجيه (Planning & Coordination)

**المشروع:** منصة أحمد إيتاب (AhmedETAP AI Engineering Platform)  
**المرحلة:** M3 — Planning & Coordination Layer  
**نقطة الأساس الحية:** `main @ e683211fc` (بعد إغلاق M2 وفتح PR #610)  
**فرع العمل:** `feat/ai-m3-planning-coordination` (متطابق تماماً مع رأس `main` — `git diff main...HEAD` فارغ)  
**تاريخ الإعداد:** 2026-09-27  
**الحالة:** خطة مقترحة (Proposal) بانتظار اعتماد المعمار الرئيسي — صفر تعديل كود، وكل شاهد مثبت `file:line` من الشجرة الحية (Zero Hallucination)

---

## 1. الأساس المرجعي والتفويض

1. **M2 مغلقة رسمياً** — تقرير الإغلاق: [`docs/ai-integration/m2-report.md`](./m2-report.md)، وطلب الدمج `#610` مفتوح وقابل للدمج (`feat/m2-contracts-registry → main`، حالة GitHub API الموثقة: `open` + `mergeable=true`).
2. **بند مؤجل صراحةً من M2.3 إلى M3:** إزالة ازدواجية سجل الوكلاء في `src/core/agents.ts` (11 معرّفاً) لأنها تتطلب إعادة هيكلة طبقة التوجيه Mastra — [m2-report.md §6](./m2-report.md#6-المتطلبات-المؤجلة-إلى-m3).
3. **موضوع المرحلة** بحسب فرع العمل: وصل مكوّنات التخطيط (Planning) والتوجيه (Coordination) القائمة فعلاً في الشجرة، فوق عقود M2 التنفيذية، مع صفر تغيير سلوكي افتراضي (Fail-Closed).
4. **ملاحظة تدقيقية:** لا توجد في المستودع اليوم وثيقة M0–M6 رسمية (بحث شامل في `docs/ai-integration/`، تقارير `P0`–`P5`، و`ROADMAP.md`)؛ صيغت هذه الخطة حصراً من الشواهد الحية، وتنتظر الاعتماد أو المواءمة مع الوثيقة الرسمية إن وُجدت.

---

## 2. جرد المكوّنات الحية (Component Inventory — كل سطر بشاهد قطعي)

| # | المكوّن | الموضع (`file:line`) | الدور | حالة الوصل اليوم |
|---|---------|----------------------|-------|-------------------|
| 1 | `GoalRouter` | [agents/router.py:77](file:///c:/Users/EWS-01/Desktop/etap/agents/router.py#L77) | توجيه الأهداف نصياً إلى `StudyType` عبر قواعد كلمات مفتاحية | **حي** — يُنشأ في [orchestrator.py:111](file:///c:/Users/EWS-01/Desktop/etap/agents/orchestrator.py#L111) |
| 2 | `RouterDecision` | [agents/router.py:69](file:///c:/Users/EWS-01/Desktop/etap/agents/router.py#L69) | قرار توجيه موحّد (`study_types`, `confidence`, `reason`) | **حي** |
| 3 | `determine_execution_order` | [agents/router.py:172](file:///c:/Users/EWS-01/Desktop/etap/agents/router.py#L172) | ترتيب تنفيذ ثابت بالأولوية (LOAD_FLOW أولاً ثم الباقي) | **حي** — مستدعى في [workflow.py:103](file:///c:/Users/EWS-01/Desktop/etap/agents/workflow.py#L103) |
| 4 | `GoalPlannerAgent` | [agents/goal_planner_agent.py:54](file:///c:/Users/EWS-01/Desktop/etap/agents/goal_planner_agent.py#L54) | تفكيك الأهداف وتقدير الأولويات والاعتماديات | **حي** — أوزان تركيبية ثابتة `0.4/0.4/0.2` ([سطر 92-94](file:///c:/Users/EWS-01/Desktop/etap/agents/goal_planner_agent.py#L92-L94)) |
| 5 | `AdaptiveTaskScheduler` | [agents/optimizers/adaptive_planner.py:47](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/adaptive_planner.py#L47) | جدولة CPM تكيفية: مسار حرج + دفعات تنفيذ متوازية | **معزول (Orphan)** — لا مستهلك إنتاجي واحد؛ الاستيراد الوحيد في [tests/test_multi_objective_and_planner.py:10](file:///c:/Users/EWS-01/Desktop/etap/tests/test_multi_objective_and_planner.py#L10) |
| 6 | `ContextualBanditRouter` | [agents/optimizers/bandit_router.py:24](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L24) | توجيه تعلّمي LinUCB مع رجوع آمن إلى `GoalRouter` ([سطر 43](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L43)) | **معزول (Orphan)** — لا مستهلك إنتاجي؛ الاستيراد الوحيد في [tests/test_bandit_and_cascade.py:10](file:///c:/Users/EWS-01/Desktop/etap/tests/test_bandit_and_cascade.py#L10) |
| 7 | `WorkflowEngine` | [agents/workflow.py:77](file:///c:/Users/EWS-01/Desktop/etap/agents/workflow.py#L77) | منسّق خطوط التنفيذ متعددة الدراسات والتحقق النهائي | **حي** — موصول في [orchestrator.py:112](file:///c:/Users/EWS-01/Desktop/etap/agents/orchestrator.py#L112) |
| 8 | عقود M2 التنفيذية | [contracts/ai/models.py](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py) — السطور [111](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L111), [135](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L135), [152](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L152), [173](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L173), [254](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L254) | DAG الخطة، سياق التنفيذ، الطلب، سجل التتبع | **معرّفة — صفر مستهلك في زمن التشغيل** |
| 9 | حقول الربط `run_id/plan_id/node_id` | [agents/models.py:77-80](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py#L77-L80) (`AgentResult`) و [95-97](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py#L95-L97) (`EngineeringTask`) | ربط نتائج الوكلاء بالعقد التنفيذي | **معرّفة — لا تُملأ في أي مسار فعلي اليوم** |
| 10 | سجل الوكلاء TypeScript | [src/core/agents.ts:54-140](file:///c:/Users/EWS-01/Desktop/etap/src/core/agents.ts#L54-L140) | 11 معرّف وكيل + `promptHandle` | **حي** — المستهلك الوحيد [src/routes/agents.ts:7](file:///c:/Users/EWS-01/Desktop/etap/src/routes/agents.ts#L7) (تأجيل M2.3) |
| 11 | `OptimizationAgent` | [agents/optimizers/optimization_agent.py:29](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/optimization_agent.py#L29) | تحسينات swarm / metaheuristic | **مسجَّل في السجل** (مفتاح `optimization` ضمن 30 مفتاحاً) لكن study type خارجي غير مخدوم |
| 12 | `SpecializedExecutionUnavailableError` | [core/exceptions.py:10](file:///c:/Users/EWS-01/Desktop/etap/core/exceptions.py#L10) | فشل مغلق (ValueError subclass) للدراسات المسجلة بلا معالج | **حي** — وسيلة الرفض الموحدة اليوم |

---

## 3. تحليل الفجوات (Gap Analysis — كل فجوة بشاهدين قطعيين على الأقل)

### G1 — الجدولة التكيفية (CPM) معزولة عن مسار التخطيط
- **الادعاء المعلن في الكود:** `AdaptiveTaskScheduler` "يستبدل التقييم الثابت 0.4/0.4/0.2 في `GoalPlannerAgent`" — [adaptive_planner.py:4-6](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/adaptive_planner.py#L4-L6).
- **الواقع الحي:** الوكيل ما زال يجمع بالوزن الثابت ([goal_planner_agent.py:200-209](file:///c:/Users/EWS-01/Desktop/etap/agents/goal_planner_agent.py#L200-L209))، ولا يوجد أي استيراد إنتاجي للجدولة؛ الاستيراد الوحيد في الاختبارات ([tests/test_multi_objective_and_planner.py:10](file:///c:/Users/EWS-01/Desktop/etap/tests/test_multi_objective_and_planner.py#L10)).
- **الأثر:** قدرة المسار الحرج والدفعات المتوازية ([adaptive_planner.py:119-155](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/adaptive_planner.py#L119-L155)) غير مستفاد منها في أي تدفق تنفيذ.

### G2 — الموجّه التعلّمي (LinUCB) معزول عن الـ Orchestrator
- **الشاهد 1:** الفئة قائمة بخوارزميتها ورجوعها الآمن — [bandit_router.py:24](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L24) و [bandit_router.py:43](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L43).
- **الشاهد 2:** المنشأة الفعلية في الـ orchestrator تستخدم `GoalRouter` الصريح — [orchestrator.py:111](file:///c:/Users/EWS-01/Desktop/etap/agents/orchestrator.py#L111).
- **الفجوة المزدوجة:** لا مسار تحديث مكافآت (reward/telemetry) من نتائج الدراسات إلى الأذرع، ولا علم ميزة يحكم التفعيل.

### G3 — عقود M2 التنفيذية غير مستهلكة في زمن التشغيل
- **الشاهد 1:** العقود معرّفة ومختبَرة تزامنياً — [contracts/ai/models.py:111/135/173/254](file:///c:/Users/EWS-01/Desktop/etap/contracts/ai/models.py#L111)، ومِرآتها TS في `src/core/contracts/ai.ts`.
- **الشاهد 2:** `WorkflowEngine` يبني الترتيب من دالة أولوية ثابتة — [workflow.py:103](file:///c:/Users/EWS-01/Desktop/etap/agents/workflow.py#L103) — ولا يُنتج `ExecutionPlanContract` ولا يُصدر `ExecutionTraceContract`، وحقول الربط في [agents/models.py:77-80](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py#L77-L80) لا تُملأ في أي مسار.
- **الأثر:** الجسر التعاقدي Python↔TypeScript مبنيّ لكن غير مُفعَّل تشغيلياً (أساس M4+ المحتمل).

### G4 — ازدواجية سجل الوكلاء (البند المؤجل من M2.3)
- **الشاهد 1:** 11 معرّفاً في TS — [src/core/agents.ts:54-140](file:///c:/Users/EWS-01/Desktop/etap/src/core/agents.ts#L54-L140).
- **الشاهد 2:** السجل البايثوني الحيّ يسجل **30 مفتاحاً** (27 فئة فريدة + 3 أسماء مستعارة: `harmonic`, `opf`, `protection`) — قياس حي مباشر اليوم عبر `create_agent_registry()` المستدعاة في [agents/registry.py:1422](file:///c:/Users/EWS-01/Desktop/etap/agents/registry.py#L1422).
- **التفويض:** مؤجل صراحة من [m2-report.md §6](./m2-report.md#6-المتطلبات-المؤجلة-إلى-m3) لاستلزامه إعادة هيكلة طبقة Mastra.

### G5 — الالتباس التنفيذي لدراسة `optimization` (قرار معماري مطلوب)
- **الشاهد 1:** `OptimizationAgent` فئة كاملة مسجّلة في السجل — [optimization_agent.py:29](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/optimization_agent.py#L29).
- **الشاهد 2:** `optimization` مسجَّلة `handler_type="external"` في جدول الإرسال — [engine/dispatch.py:155-160](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L155-L160) — فتسقط في [study_executor.py:432-433](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L432-L433) على `SpecializedExecutionUnavailableError` دون أي موجّه HTTP خارجي نشط.
- **ملاحظة مقارنة:** نفس الصنف من المشكلة عولج سابقاً لدراسة `ahmed_etap_orchestration` (M0.3) بإعادة توجيهها محلياً — [study_executor.py:425-426](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L425-L426) → [_dispatch_agent:502-545](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L502-L545). يمكن اعتماد النمط نفسه أو قرار الحذف/التوثيق الصريح.

### تصحيحات تدقيقية على خط الأساس P0 (Drift Note — شفافية إلزامية)
| ما قالته وثيقة P0 (خط أساس `43fdd481f`) | الواقع الحي اليوم على `e683211fc` | الشاهد |
|---|---|---|
| `ahmed_etap_orchestration` كود ميت بنيوياً يرفع استثناءً عند الإرسال | **عولج في M0.3:** التوجيه الآن يمر إلى `_dispatch_agent` وينفّذ فعلياً | [study_executor.py:425-426](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L425-L426) |
| الرفض برفع `ValueError` نصي في موضعين | الرفض الموحّد هو `SpecializedExecutionUnavailableError` (مصنَّف `code="SPECIALIZED_EXECUTION_UNAVAILABLE"`) | [core/exceptions.py:10-19](file:///c:/Users/EWS-01/Desktop/etap/core/exceptions.py#L10-L19) |
| «13 دراسة ترفع الخطأ» | **11 دراسة وكيلية** فقط ما زالت غير مخدومة عبر المنفذ: `battery_storage, cable_sizing, digital_twin, earth_grid, generative_design, harmonic_analysis, motor_starting, optimal_power_flow, renewable_integration, scada, transient_stability` — القياس الحي: `STUDY_DISPATCH` = 20 مدخلاً (4 native + 13 agent + 3 external) | [study_executor.py:547-549](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L547-L549) |

---

## 4. بنود العمل المقترحة (M3.1 → M3.5)

لكل بند: الهدف، النطاق المقترح، شرط القبول، والمخاطر. الترقيم يتبع نمط M2 (M2.1 → M2.4).

### M3.1 — وصل الجدولة التكيفية (CPM) في مسار التخطيط
- **الهدف:** إنتاج جدولة حقيقية (مسار حرج + دفعات تنفيذ متوازية) من `GoalPlannerAgent` عبر `AdaptiveTaskScheduler` مع رجوع آمن إلى الأوزان الثابتة الحالية.
- **النطاق المقترح:** `agents/goal_planner_agent.py` (دمج اختياري)، `agents/optimizers/__init__.py` (تصدير متماثل)، اختبارات وصل جديدة.
- **شرط القبول:** بقاء `tests/test_multi_objective_and_planner.py` أخضر؛ مخرجات التقييم الافتراضية الحالية دون تغيير؛ اختبار يثبت الرجوع الآمن عند مدخلات ناقصة/معطوبة.
- **المخاطر:** تغيير سلوكي غير مقصود — يحيَّد بجعل الوصل خلف معامل صريح + إثراء الإخراج (additive) حصراً.

### M3.2 — طبقة التوجيه التعلّمي (خلف علم ميزة — افتراضي معطّل)
- **الهدف:** تفعيل `ContextualBanditRouter` اختيارياً فوق `GoalRouter` مع مسار مكافآت من نتائج الدراسات، ورجوع آمن 100% إلى `KEYWORD_RULES` (المنصوص عليه أصلاً في [bandit_router.py:6](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L6) و [bandit_router.py:43](file:///c:/Users/EWS-01/Desktop/etap/agents/optimizers/bandit_router.py#L43)).
- **النطاق المقترح:** نقطة الإنشاء [orchestrator.py:111](file:///c:/Users/EWS-01/Desktop/etap/agents/orchestrator.py#L111)، واجهة حقن في `agents/router.py`، تجميع reward من `AgentResult`، اختبارات.
- **شرط القبول:** `tests/test_router_regression.py` و `tests/test_router_completeness_gate.py` و `tests/test_bandit_and_cascade.py` خضراء؛ سلوك مطابق حرفياً لليوم عندما العلم معطّل (fail-closed default off).
- **المخاطر:** عدم حتمية التعلّم — تُحيَّد بالعلم المعطّل افتراضياً وحدود أمان على القرار.

### M3.3 — استهلاك عقود M2 التنفيذية في زمن التشغيل
- **الهدف:** `WorkflowEngine` يبني `ExecutionPlanContract` (عقد = دراسات، `depends_on` مستمدة من ترتيب الأولوية)، ويمرّر `run_id/plan_id/node_id` إلى نتائج الوكلاء، ويصدر تتبعاً نهائياً مطابقاً لـ `ExecutionTraceContract`.
- **النطاق المقترح:** `agents/workflow.py`، تعبئة حقول [agents/models.py:77-80](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py#L77-L80)، اختبارات تزامن خطة جديدة فوق `tests/test_contract_sync.py`.
- **شرط القبول:** بقاء `tests/test_contract_sync.py` أخضر + اختبارات جديدة تثبت تعبئة الحقول؛ صفر تغيير في نتائج الدراسات نفسها (بيانات إثرائية فقط).
- **المخاطر:** تشابك مع المسار الحرج — يُنفَّذ كطبقة إثراء (additive) لا تحجب أي فشل أصلي.

### M3.4 — تصفية ازدواجية سجل الوكلاء TS (البند المؤجل من M2.3)
- **الهدف:** مصدر حقيقة واحد للبيانات الوصفية للوكلاء (11 في TS مقابل 27 فئة بايثونية) مع الحفاظ على الواجهات القائمة: `getAgent`, `listAgentIds`, `getAgentPromptHandle` ([agents.ts:142-153](file:///c:/Users/EWS-01/Desktop/etap/src/core/agents.ts#L142-L153)).
- **النطاق المقترح:** `src/core/agents.ts` و`src/routes/agents.ts:7`، وإعادة هيكلة طبقة توجيه Mastra بحسب الحاجة.
- **شرط القبول:** بناء TS + Meta-CI + اختبارات `tests/unit/routes/agents.test.ts` خضراء؛ لا كسر لمفاتيح البرومبتات (`promptHandle`).
- **المخاطر:** مسّ طبقة Mastra — يتطلب تشغيل حزمة اختبارات TS كاملة قبل الدمج.

### M3.5 — حسم مسار دراسة `optimization` (قرار معماري + تنفيذ)
- **الهدف:** إنهاء التباس G5 بخيار محسوم: (أ) توجيه محلي إلى `OptimizationAgent` على غرار معالجة `ahmed_etap_orchestration` في M0.3، أو (ب) إبقاؤها external مع توثيق صريح `NOT_EXECUTABLE` ورسالة رفض نهائية واضحة.
- **النطاق المقترح:** `services/study_executor.py` (إن اختير أ) أو [`capability-matrix.md`](./capability-matrix.md) (إن اختير ب)، + اختبار سلوكي واحد.
- **شرط القبول:** اختبار يثبت السلوك النهائي صراحةً (نجاح منفَّذ أو فشل مغلق موثَّق) بلا أي غموض.
- **المخاطر:** منخفضة — قرار مغلق بنطاق محدود جداً.

---

## 5. بوابات الإغلاق المقترحة (M3 Acceptance Gates)

| البوابة | الشرط | آلية التحقق |
|---|---|---|
| **Gate 1** | Meta-CI نظيف بالكامل | `python scripts/check_workflows_meta.py` (يتضمن Registry Integrity Guard من M2.4) |
| **Gate 2** | حزمة وصل M3 خضراء | اختبارات الوصل الجديدة + `test_router_regression` + `test_router_completeness_gate` + `test_multi_objective_and_planner` + `test_bandit_and_cascade` + `test_contract_sync` |
| **Gate 3** | الحزمة الأساسية 100% خضراء | تشغيل كامل بلا انحدار |
| **Gate 4** | تقرير الإغلاق | `docs/ai-integration/m3-report.md` بنمط M2 |
| **قيد دائم** | Fail-Closed | كل ميزة تكييف/تعلّم جديدة معطّلة افتراضياً، وصفر تغيير سلوكي عند إطفائها |

---

## 6. خارج النطاق (Out of Scope)

1. إحياء الـ 11 دراسة الوكيلية غير المخدومة عبر `study_executor` — حزمة مستقلة لاحقة (تتطلب ربط موجه الوكلاء العام بـ `STUDY_TYPE_AGENT_MAP` وتمرير `EngineeringTask` للوكيل).
2. أي تعديل على `engine/dispatch.py` (`STUDY_DISPATCH` = SSoT مقفل منذ M2.3).
3. تعديلات `.github/workflows/` أو ملفات الأمان والسرية.

---

## 7. القرارات المفتوحة المطلوبة من المعمار الرئيسي

1. **اعتماد النطاق:** هل يُعتمد M3.1–M3.5 كما هي، أم يعاد ترتيب الأولويات أو يُستبعد بند؟
2. **وثيقة الخط الرئيسي M0–M6:** لا توجد نسخة منها في المستودع اليوم (بحث شامل في `docs/ai-integration/*` وتقارير `P0`–`P5` و`ROADMAP.md`)؛ تُزوَّد للفريق إن وُجدت للمواءمة الحرفية للبوابات.
3. **قرار M3.5:** الخيار (أ) توجيه محلي إلى `OptimizationAgent` أم (ب) توثيق `NOT_EXECUTABLE` الصريح؟

---

## 8. حالة الفرع والشواهد الختامية

| البند | القيمة | الشاهد |
|---|---|---|
| رأس `main` المحلي | `e683211fc` | `git log -1 --format=%h` |
| تفرع فرع M3 قبل إيداع هذه الوثيقة | متطابق مع `main` (صفر تباعد) | `git diff main...HEAD` ← مخرج فارغ |
| طلب دمج M2 | `#610` — `open` / `mergeable=true` | GitHub REST API (تحقق مباشر) |
| تعديلات كود في هذه الخطة | **صفر** — وثيقة مقترح فقط | `git diff --stat` بعد الإيداع = هذا الملف وحده |

**التوقيع:** الوكيل المنفذ — منصة أحمد إيتاب  
**التاريخ:** 2026-09-27

