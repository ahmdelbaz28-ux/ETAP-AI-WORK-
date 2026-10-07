# PROMTP — تنشيط الميزات المعطلة بأمان: دليل توجيهي للوكيل المنفذ

**version:** 1.0.0  
**date:** 2026-10-07  
**status:** EXECUTION GUIDE  
**risk_class:** HIGH — يتطلب قرارًا هندسيًا موثّقًا لكل ميزة

---

## 1. المبدأ الأساسي (القاعدة الذهبية)

> **"لا تفعّل علمًا قبل أن تتأكد من وجود مسار تنفيذ حي له عبر StudyExecutor."**

الغالبية العظمى من المشاكل الحالية ليست في الأعلام نفسها، بل في أن `services/study_executor.py` يملك كتل معالجة لحوالي 6 دراسات فقط (`load_flow`, `short_circuit`, `arc_flash`, `protection_coordination`, `etap_expert`, `etap_gui`) بينما المسجل في `engine/dispatch.py` 20 دراسة. الـ 14 دراسة المتبقية تصطدم بـ `SpecializedExecutionUnavailableError` أو `ValueError` قبل أن تصل إلى الوكيل أصلًا.

**لا تحاول أبدًا تعديل `is_feature_enabled()` أو `is_strict_feature_enabled()` في `api/feature_flags.py` كحل بديل.** هذه الدوال مصممة لتكون فحص بوابة فقط وليست مسار تنفيذ.

---

## 2. الطبقات الأمنية الثلاث

### الطبقة 1 — Fail-Closed Gate (علم الميزة)
- كل وكيل له علم ميزة خاص به في `api/feature_flags.py`
- الوكلاء الخطيرون (`generative_design`, `breaker_duty`) يستخدمون `is_strict_feature_enabled()` الذي **لا يجبر True في بيئة dev/test**
- **لا تغير هذه الدالة أبدًا** — هي الحماية الأساسية

### الطبقة 2 — Executor Gate (مسار التنفيذ)
- حتى لو كان العلم `enabled=True`، يجب أن يوجد كتلة معالجة في `StudyExecutor._dispatch()` أو `StudyExecutor.execute_native()`
- بدون هذه الكتلة، يرفع `SpecializedExecutionUnavailableError` فورًا

### الطبقة 3 — Validation Gate (التحقق من المعايرة)
- المحولات الفيزيائية تحتاج اختبارات معايرة مقابل حالات منشورة (benchmark cases)
- بدون معايرة، النتائج غير جديرة بالثقة ولا يجوز استخدامها في تصميم حقيقي

---

## 3. خطة التنشيط التدريجي (الترتيب الزمني المثالي)

### المرحلة A — إصلاح مسار التنفيذ (الأولوية القصوى)

**الهدف:** جعل الدراسات الـ 11 المعلّقة قابلة للوصول عبر `StudyExecutor`.

**الخطوات:**

1. **توسيع `_dispatch()` في `study_executor.py`** لإضافة كتل معالجة للدراسات التالية:
   - `harmonic_analysis` → استدعاء `HarmonicAnalysisAgent().execute(task)`
   - `optimal_power_flow` → استدعاء `OptimalPowerFlowAgent().execute(task)`
   - `motor_starting` → استدعاء `MotorStartingAgent().execute(task)`
   - `transient_stability` → استدعاء `StabilityAgent().execute(task)`
   - `cable_sizing` → استدعاء `CableSizingAgent().execute(task)`
   - `earth_grid` → استدعاء `EarthGridAgent().execute(task)`
   - `renewable_integration` → استدعاء `RenewableAgent().execute(task)`
   - `battery_storage` → استدعاء `BatteryStorageAgent().execute(task)`
   - `scada` → استدعاء `SCADAAgent().execute(task)`
   - `digital_twin` → استدعاء `DigitalTwinAgent().execute(task)`
   - `generative_design` → استدعاء `DesignAgent().execute(task)` مع فحص العلم أولاً

2. **القالب العام لكل كتلة:**

```python
elif study_type == "<STUDY_TYPE>":
    if not is_strict_feature_enabled("<feature_flag_key>", default=False):
        raise SpecializedExecutionUnavailableError(
            canonical=study_type,
            reason=f"Feature flag '<feature_flag_key>' is disabled"
        )
    agent = AGENT_REGISTRY["<agent_key>"]
    result = asyncio.get_event_loop().run_until_complete(
        agent.execute(task)
    )
    return self._serialize_agent_result(result, task_id)
```

3. **التحقق بعد كل إضافة:**
   - تشغيل `pytest tests/test_study_reachability_gate.py -q`
   - التأكد من أن `STUDY_DISPATCH["<study_type>"].requires_system` صحيح

### المرحلة B — المعايرة والتحقق (قبل التفعيل)

**الهدف:** ضمان أن النتائج تطابق المعايير المنشورة قبل فتح الأعلام في الإنتاج.

**للدراسات التالية مطلوب معايرة explicit:**

| الدراسة | المعيار | الحالة المطلوبة | الملف المرجعي |
|---------|---------|------------------|---------------|
| `harmonic_analysis` | IEEE 519-2022 | 3 حالات منشورة على الأقل | `tests/test_harmonic_analysis.py` |
| `optimal_power_flow` | DC-OPF + AC-OPF | حالة IEEE 30-bus | `tests/test_optimal_power_flow.py` |
| `motor_starting` | IEEE 399-1997 | 2 حالة: Direct-on-Delta + Star-Delta | `tests/test_motor_starting_agent.py` |
| `transient_stability` | IEEE 399 + Swing Eq | حالة Stability Case 1 | `tests/test_stability_agent.py` |
| `cable_sizing` | IEC 60364 + IEC 60287 | 3 أحمال مختلفة | `tests/test_cable_sizing_agent.py` |
| `earth_grid` | IEEE 80 | حالة Leybourne-Smith | `tests/test_earth_grid_agent.py` |

**خطوات المعايرة:**
1. تشغيل السيناريو المرجعي
2. مقارنة النتائج مع القيم المنشورة بنسبة خطأ مقبولة:
   - Load Flow: ±1% for voltages, ±2% for power flows
   - Short Circuit: ±5% for currents (IEC 60909 tolerance)
   - Arc Flash: ±15% for incident energy (IEEE 1584-2018 tolerance)
   - Harmonics: ±3% for THD
   - Protection: ±0.1s for TMS
3. توثيق النتائج في `docs/validation/`

### المرحلة C — التفعيل التدريجي بالإنتاج

**لا تفتح علمًا مباشرة إلى 100% rollout.** اتبع هذا المسار:

#### الخطوة 1: بيئة التطوير
```powershell
# في .env.development أو مباشرة في PowerShell:
$env:FEATURE_FLAG_HARMONIC_ANALYSIS = "true"
$env:FEATURE_FLAG_OPTIMAL_POWER_FLOW = "true"
$env:FEATURE_FLAG_MOTOR_STARTING = "true"
```
- تشغيل اختباراتRegression كاملة
- التأكد من عدم وجود `SpecializedExecutionUnavailableError`

#### الخطوة 2: بيئة Staging
```json
// .feature-flags.json (بيئة staging)
{
  "harmonic_analysis": {
    "enabled": true,
    "status": "beta",
    "rollout_percentage": 10,
    "allow_list": ["admin@company.com"],
    "updated_at": "2026-10-07T..."
  }
}
```
- مراقبة `/metrics` (Prometheus) لـ error rate
- فحص `langfuse` traces للأداء
- Breeder testing: اختبار 10% من المستخدمين المسجلين

#### الخطوة 3: التوسيع التدريجي
```
اليوم 1-3:   rollout 10% + allow_list
اليوم 4-7:   rollout 25% + allow_list
اليوم 8-14:  rollout 50% + allow_list
اليوم 15-21: rollout 100% + status: stable
```

#### الخطوة 4: إغلاق Bug Bash (24-48 ساعة بعد كل زيادة)
- فحص `docs/status/STATUS_BOARD.md`
- جمع feedback من المستخدمين
- إصلاح أي مشاكل قبل الزيادة التالية

### المرحلة D — ميزات خاصة (Scaffolds)

#### `generative_design` (المخاطرة الأعلى)
**لا تفتح هذا العلم أبدًا بدون الموافقة الصريحة من مهندس كهرباء مرخص + مستند أمان مكتوب.**

قبل التفعيل:
1. إنشاء `docs/safety/generative_design_acceptance_criteria.md`
2. توثيق جميع القيود الهندسية:
   - لا يُستخدم لتصميم محطات حقيقية بدون مراجعة خبير
   - المخرجات تحتاج دائمًا validation يدوية
   - يجب الإفصاح للعميل أن النتائج توليد آلي
3. تشغيل `pytest tests/test_design_agent_scaffold.py -v` والتأكد من:
   - `test_dispatch_generative_design_flag_disabled_returns_failed` ✅
   - `test_dispatch_generative_design_flag_enabled_no_system_required` ✅
4. فتح العلم فقط في بيئة dev/test أولاً
5. **لا تزيد rollout أبدًا عن 5% في الإنتاج** حتى يجتاز 3 أشهر من استخدام آمن

#### `breaker_duty` (مخاطرة متوسطة)
1. التأكد من أن `BreakerDutyEvaluator` لديه حالات اختبار معايرة
2. فتح العلم في staging أولاً
3. rollout تدريجي من 10% إلى 100% مثل المرحلة C

---

## 4. القواعد غير القابلة للكسر (Non-Negotiable)

### ❌ ممنوع تمامًا
1. تعديل `is_feature_enabled()` أو `is_strict_feature_enabled()` لإجبار القيمة True
2. حذف فحص العلم (`if not is_strict_feature_enabled(...)`) من أي وكيل
3. تفعيل علم في الإنتاج بدون اختبار معايرة واضح
4. زيادة rollout من 0% إلى 100% دفعة واحدة
5. تفعيل `generative_design` بدون موافقة مهندس مرخص + وثيقة قبول مخاطر
6. تعديل `_TYPES_REQUIRING_SYSTEM` لإجبار `requires_system=False` على دراسة تحتاج بيانات نظام

### ✅ مطلوب تمامًا
1. كتابة اختبار يثبت أن الدراسة تشتغل عند تفعيل العلم
2. كتابة اختبار يثبت أن الدراسة ترفض عند إيقاف العلم
3. توثيق الحالات المرجعية والنتائج المتوقعة
4. إضافة `risk_class` و `lifecycle_status` في `capability_registry.py`
5. تحديث `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md` بكل دراسة مُفعّلة
6. إضافة metric في Prometheus لمراقبة نجاح/فشل كل دراسة مفعّلة

---

## 5. قائمة الفحص النهائية (Checklist) لكل ميزة

قبل الإعلان عن تفعيل أي ميزة، أكد النقاط التالية:

- [ ] **مسار تنفيذ حي:** `StudyExecutor` يملك كتلة معالجة واضحة للدراسة
- [ ] **اختبار نجاح عند تفعيل العلم:** pytest يمرحل عند `enabled=True`
- [ ] **اختبار رفض عند إيقاف العلم:** pytest يمرحل عند `enabled=False`
- [ ] **معايرة فيزيائية:** نتائج الدراسة مطابقة لحالات منشورة بنسبة خطأ مقبولة
- [ ] **توثيق:** `docs/validation/<study_type>_validation.md` محدّث
- [ ] **تسجيل في capability_registry:** `lifecycle_status` ليس `DISABLED`
- [ ] **ملف ETHIC/SAFETY** (للمخاطر العالية): موجود ومُوقّع
- [ ] **مراقبة:** Prometheus rule + Grafana dashboard محدّث
- [ ] **تتبع أخطاء:** Langfuse project يتابع traces للدراسة
- [ ] **استراتيجية تراجع:** خطة Rollback موثّقة في `DEPLOYMENT_ROLLBACK.md`

---

## 6. أمر التفعيل الحرفي (للوكيل)

عندما يبدأ الوكيل التنفيذ، يجب أن يتبع هذا التسلسل حرفيًا:

```
1. قراءة services/study_executor.py:106-535 → فهم البنية الحالية
2. قراءة engine/dispatch.py:101-180 → فهم STUDY_DISPATCH
3. قراءة agents/registry.py:1581 → فهم AGENT_REGISTRY
4. قراءة api/feature_flags.py:69-205 → فهم DEFAULT_FEATURE_FLAGS
5. اختيار دراسة واحدة من القائمة أدناه
6. إضافة كتلة المعالجة في study_executor.py داخل _dispatch()
7. كتابة اختبار في tests/ يثبت:
   a. نجاح التنفيذ عند تفعيل العلم
   b. رفض التنفيذ عند إيقاف العلم
8. تشغيل pytest للاختبار الجديد
9. تحديث docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md بصف الدراسة
10. تحديث capability_registry.py: lifecycle_status ← BETA (ليس DISABLED)
11. تحديث api/feature_flags.py: status ← "beta" (ليس "experimental")
12. تشغيل اختبارات Regression الكاملة: pytest tests/ -q --timeout=60
13. إذا نجحت جميع الخطوات → تقديم تقرير بالإجراءات المنفّذة
```

### ترتيب التنفيذ المقترح (من الأسهل إلى الأصعب)

1. **`harmonic_analysis`** — محرك موجود، معايرة واضحة (IEEE 519)
2. **`optimal_power_flow`** — محرك موجود، DC-OPF أبسط من AC-OPF
3. **`motor_starting`** — محرك موجود، معايير IEEE 399 واضحة
4. **`transient_stability`** — محرك موجود، Swing Equation بسيط
5. **`cable_sizing`** — محرك موجود، معايير IEC 60364 واضحة
6. **`earth_grid`** — محرك موجود، IEEE 80 حالة واحدة كافية
7. **`renewable_integration`** — محرك موجود، IEEE 1547
8. **`battery_storage`** — محرك موجود، IEC 62933
9. **`scada`** — يتطلب Modbus/OPC UA حقيقي → تأخير حتى توفر البنية التحتية
10. **`digital_twin`** — يتطلب stream حقيقي → تأخير حتى توفر البنية التحتية
11. **`generative_design`** — scaffold فقط، مخاطرة عالية → آخراً
12. **`breaker_duty`** — scaffold فقط، مخاطرة متوسطة → تالي لاخير

---

## 7. الهوامش والمراجع

- **ملف الأعلام:** `api/feature_flags.py`
- **ملف الإرسال:** `engine/dispatch.py`
- **ملف التنفيذ:** `services/study_executor.py`
- **ملف السجل:** `agents/registry.py`
- **ملف الأنواع:** `agents/models.py`
- **ملف السجل:** `engine/capability_registry.py`
- **توثيق التصميم:** `docs/ARCHITECTURAL_CONSOLIDATION_REPORT.md`
- **قاعدة المعايرة:** `scripts/run_ieee_benchmarks.py`

---

**تنبيه نهائي:** هذا البرومبت دليل توجيهي فقط. كل خطوة تنفيذ تحتاج مراجعة بشرية قبل الدفع إلى الإنتاج. الوكيل يجب أن يقدم تقريرًا مكتوبًا بالإجراءات المقترحة قبل تنفيذ أي تعديل.
