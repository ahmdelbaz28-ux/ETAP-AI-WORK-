# خطة المرحلة M5 — التحقق والأتمتة (Verification & Automation)

**المشروع:** منصة أحمد إيتاب (AhmedETAP AI Engineering Platform)  
**المرحلة:** M5 — CUA Safety & Interactive Approvals, Post-Action Verification, Engineering Assertions & REJECTED Propagation  
**نقطة الأساس الحية:** `main @ fbfc82574` (بعد دمج M4 عبر PR #636)  
**فرع العمل:** `feat/ai-m5-verification-automation`  
**تاريخ الإعداد:** 2026-09-30  
**البنود المرجعية:** 15 (CUA Automation & Interactive Approvals)، 16 (Engineering Assertions & Fail-Closed Propagation)

> **قاعدة التحقق الحي:** كل رقم سطر في برومبت الخطة الرئيسية مأخوذ من تدقيق تاريخي عند `43fdd481f`. هذا المستند يمثل **تدقيق الانحراف (Drift Audit)** قبل أي تعديل — حيث اختلف الكود الحي عن الوصف، ثُبّت الحي وتوثق الفرق كتابةً أدناه قبل التنفيذ (بروتوكول المفاجآت الإلزامي).

---

## 1. تدقيق الانحراف الحي (Live Drift Audit)

| البند | وصف الخطة (عند `43fdd481f`) | الحقيقة الحية (`fbfc82574`) | القرار المنفَّذ |
|---|---|---|---|
| **M5.1(أ)** | `api/agents.py:617-624` تُغفل `on_confirmation_request` فيفشل CONTROL fail-closed بدل انتظار موافقة تفاعلية | ✅ مؤكد حرفياً: `api/agents.py:617-624` يستدعي `agent.execute_cua_loop(question=..., max_steps=..., require_confirmation=..., audit_dir=..., start_url=...)` دون تمرير `on_confirmation_request` | ربط بنية الموافقات المعتمدة القائمة في `api/approvals.py:87-96` و`api/agent_executor.py:496-534` عبر معالج انتظار موافقة تفاعلي بـ TTL مدته 300 ثانية وثبات Idempotency |
| **M5.1(ب)** | الاعتراف بغياب التحقق في `cua/life_safety.py:747-749` | ⚠️ المسار الحي هو `agents/life_safety.py:747-749` (المجلد `agents/` وليس `cua/`). النص الحرفي: `"Limitation: In a GUI automation context (CUA), there is no deterministic way to 'undo'..."` | إضافة آلية **التحقق الحتمي بعد الفعل (Deterministic Post-Action Verification)**: قراءة حالة القيمة/الشبكة المستهدفة بعد كل خطوة نقر/إدخال للتحقق من أثر الفعل برمجياً قبل إعلانه ناجحاً |
| **M5.1(ج)** | أتمتة rollback (يدوي حالياً في `life_safety.py:806-841`) | ✅ مؤكد في `agents/life_safety.py:806-841`: `manual_steps = f"MANUAL ROLLBACK REQUIRED..."` و`"rollback_type": "manual_only"` | أتمتة تنفيذ خطوات الـ rollback عبر CUA handler وتوثيق مسار التراجع في `ExecutionTraceContract` |
| **M5.1(د)** | إدخال `tenant_id` وسياسة الأدوات وفحص حدود الإحداثيات في `agents/cua_base_executor.py:287-705` | ✅ مؤكد: الحلقة تفتقر لفحص حدود الشاشة لمنع النقر خارج نافذة تطبيق ETAP وللتحقق من نطاق المستأجر | إضافة فحص حدود الإحداثيات (`_assert_coordinate_bounds`) وتضمين `tenant_id` وسياسة الأدوات |
| **M5.2(أ)** | طبقة Assertions غائبة في `services/study_executor.py` | ✅ مؤكد: `services/study_executor.py` لا يستورد أو ينفذ `EngineeringAssertionLayer` نهائياً | ربط مسار `study_executor` بنتائج `EngineeringAssertionLayer` مع تطبيق الفحوصات المعيارية وإخضاع كل دراسة للتحقق |
| **M5.2(ب)** | تفعيل `validate_fallback_output` (:565 في `copilot/ai/engineering_assertions.py`) أو حذفه بنظافة | ✅ مؤكد: الدالة معرّفة في الأسطر 565-645 كدالة غير مستدعاة (كود ميت) | استثمار المنطق المتقدم لفحص الحدود الفيزيائية في `validate_fallback_output` وربطه بالتحقق الحتمي العام |
| **M5.2(ج)** | استبدال `COMPLETED with validation_status=False` في `workflow.py:780-785` بحالة `REJECTED` ونشرها الصارم | ✅ مؤكد: `agents/workflow.py:783` يضع `result.validation_status = False` لكن `result.status` يبقى `AgentStatus.COMPLETED` | تعيين `result.status = AgentStatus.REJECTED` عند فشل التأكيدات الهندسية الحتمية، ومنع أي عقدة تالية تعتمد عليها من التنفيذ (Fail-Closed) ونشرها في `ExecutionTraceContract` |

---

## 2. نطاق التنفيذ (M5.1 → M5.2)

### M5.1 — أتمتة وحوكمة CUA:
1. **ربط بوابة الموافقات التفاعلية:**
   - تعديل `api/agents.py` لتمرير كولباك موافقة تفاعلية `on_confirmation_request` يعتمد على نظام `PendingAction` في `api/approvals.py` بدلاً من الفشل الفوري في وضع `CONTROL`.
2. **التحقق الحتمي بعد الفعل (Post-Action Verification):**
   - إضافة بروتوكول `verify_post_action()` في `agents/life_safety.py` و`agents/etap_gui_agent.py` للتحقق من أثر الإجراءات على واجهة وبيانات ETAP.
3. **أتمتة الـ Rollback:**
   - دعم التراجع البرمجي التلقائي عن طريق استرجاع اللقطات والحالات السابقة.
4. **حوكمة العزل وفحص الحدود:**
   - إضافة فحص برمجي للإحداثيات في `agents/cua_base_executor.py` لضمان عدم خروج المؤشر أو النقرات عن حدود النافذة المحددة هندسياً، مع ربط كامل لـ `tenant_id`.

### M5.2 — تعميم طبقة التأكيدات الهندسية (Engineering Assertions):
1. **إلزامية التأكيدات في `StudyExecutor`:**
   - ربط نتائج الدراسات في `services/study_executor.py` بـ `copilot/ai/engineering_assertions.py` وإسقاط أي نتيجة تخالف المعايير (IEEE C84.1, IEC 60909, IEC 60255, IEEE 1584, IEC 60364).
2. **تطهير ودمج `validate_fallback_output`:**
   - الاستفادة من قواعد الفحص الفيزيائي المدمجة وربطها بنظام التحقق الشامل.
3. **فرض ونشر حالة `AgentStatus.REJECTED`:**
   - تحديث `agents/workflow.py` و`agents/orchestrator.py` لنشر حالة `REJECTED` الصريحة، وإيقاف أي دراسات لاحقة تعتمد على النتائج المرفوضة، وتوثيق ذلك في `ExecutionTraceContract`.

---

## 3. بوابات قبول M5 (Acceptance Gates)

| البوابة | الشرط الفني | آلية التحقق |
|---|---|---|
| **Gate 1** | CONTROL بلا موافقة تفاعلية موثقة ينتج انتظاراً صريحاً أو إجهاضاً موثقاً — لا تجاوز أبداً | اختبار سلبي موثق في `tests/test_m5_cua_approvals.py` |
| **Gate 2** | كل فعل CUA يمر بالتحقق بعد الفعل، وتعطيل التحقق يفشل الخطوة تلقائياً | اختبار سلوكي في `tests/test_m5_cua_approvals.py` |
| **Gate 3** | سيناريو فشل حرج في التأكيدات ينتج حالة `REJECTED` صريحة ويوقف الـ downstream | اختبار تكامل في `tests/test_m5_assertions_rejected.py` |
| **Gate 4** | سلامة Meta-CI وRuff وTypeScript بنسبة 100% | `python scripts/check_workflows_meta.py` + `ruff check` + `tsc --noEmit` |

---
