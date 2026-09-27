# خط الأساس الجنائي لقدرات النظام — Capability Baseline
**المستودع:** `https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git`  
**نقطة الأساس الحية:** `main @ 43fdd481f` (`43fdd481faf134f757914702db3b4ab596bfc429`)  
**تاريخ التحقق الجنائي:** 2026-09-27  
**الحالة:** معتمد جنائياً ومثبت كودياً (صفر تخمين — Zero Hallucination)

---

## 1. ملخص العد والتحقق الجنائي التمهيدي (الخطوة 1.1)

تم التحقق من الحجم الفعلي لجدول الإرسال الموحد `STUDY_DISPATCH` في [engine/dispatch.py](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py) عبر الأمر:
```bash
python -c "import engine.dispatch as d; print('len:', len(d.STUDY_DISPATCH))"
```
* **المخرج الحرفي للتحقق:** `len: 20`.
* **العدد الفعلي:** **20 مدخلاً بالضبط**.

### هيكل بناء الـ 20 مدخلاً في [engine/dispatch.py:99-170](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L99-L170):
1. **4 دراسات أصلية (native):** `load_flow`, `short_circuit`, `arc_flash`, `protection_coordination` (مسندة إلى دوال [PowerSystemEngine](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L434)).
2. **12 دراسة وكلاء (agent):** مشتقة من `STUDY_TYPE_AGENT_MAP` في [agents/__init__.py:80-97](file:///c:/Users/EWS-01/Desktop/etap/agents/__init__.py#L80-L97) (بعد استثناء الـ 4 الأصلية):
   `harmonic_analysis`, `optimal_power_flow`, `motor_starting`, `transient_stability`, `cable_sizing`, `earth_grid`, `renewable_integration`, `battery_storage`, `scada`, `digital_twin`, `etap_expert`, `etap_gui`.
3. **4 دراسات مضافة صراحة في نهاية الدالة `_build_dispatch()`:**
   - `ahmed_etap_orchestration` ([engine/dispatch.py:149](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L149)): نوعها `external` مسندة إلى `AhmedETAPSkillAgent`.
   - `optimization` ([engine/dispatch.py:155](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L155)): نوعها `external` مسندة إلى `OptimizationAgent`.
   - `generative_design` ([engine/dispatch.py:161](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L161)): نوعها `agent` مسندة إلى `agents.design_agent.DesignAgent`.
   - `breaker_duty` ([engine/dispatch.py:167](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L167)): نوعها `external` مسندة إلى `breaker_duty.evaluator.BreakerDutyEvaluator`.

---

## 2. جدول إمكانية الوصول والتصنيف الجنائي للـ 20 مدخلاً (الخطوة 1.2)

يوثق هذا الجدول إمكانية الوصول الفعلية لكل مدخل من الـ 20 عبر المنافذ الأربعة الرئيسية في النظام:
1. `study_executor`: [services/study_executor.py:390-536](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L390-L536)
2. `study_service`: [services/study_service.py:232-285](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L232-L285)
3. `shim engine.py`: [engine/engine.py:49-60, 460-464](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L49-L60)
4. `shared_handlers`: [api/shared_handlers.py:593-785](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L593-L785)

قيم التصنيف المعتمدة حصراً:
* `REACHABLE`: شاهد file:line يثبت استدعاءً وتنفيذاً فعلياً.
* `UNREACHABLE`: شاهد file:line يثبت raise مبكر أو كوداً ميتاً.
* `EXTERNAL_ONLY`: معرف كـ external، غير قابل للوصول عبر المنفذ بالتصميم.
* `UNKNOWN`: لا يوجد شاهد قطعي.

| # | entry | handler_type | handler | study_executor | study_service | shim engine.py | shared_handlers | Classification | evidence file:line |
|---|-------|--------------|---------|----------------|---------------|----------------|-----------------|----------------|--------------------|
| 1 | `load_flow` | native | `run_load_flow` | REACHABLE | REACHABLE | REACHABLE | REACHABLE | REACHABLE | [study_executor.py:440](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L440), [study_service.py:243](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L243), [engine.py:50](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L50), [shared_handlers.py:716](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L716) |
| 2 | `short_circuit` | native | `run_fault_analysis` | REACHABLE | REACHABLE | REACHABLE | UNREACHABLE | REACHABLE | [study_executor.py:445](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L445), [study_service.py:248](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L248), [engine.py:51](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L51), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 3 | `arc_flash` | native | `run_arc_flash` | REACHABLE | REACHABLE | REACHABLE | UNREACHABLE | REACHABLE | [study_executor.py:455](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L455), [study_service.py:257](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L257), [engine.py:56](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L56), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 4 | `protection_coordination` | native | `run_protection_coordination` | REACHABLE | REACHABLE | REACHABLE | UNREACHABLE | REACHABLE | [study_executor.py:467](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L467), [study_service.py:278](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L278), [engine.py:52](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L52), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 5 | `harmonic_analysis` | agent | `agents.registry.HarmonicAnalysisAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 6 | `optimal_power_flow` | agent | `agents.registry.OptimalPowerFlowAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 7 | `motor_starting` | agent | `agents.motor_starting_agent.MotorStartingAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 8 | `transient_stability` | agent | `agents.stability_agent.StabilityAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 9 | `cable_sizing` | agent | `agents.cable_sizing_agent.CableSizingAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 10 | `earth_grid` | agent | `agents.earth_grid_agent.EarthGridAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 11 | `renewable_integration` | agent | `agents.renewable_agent.RenewableAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 12 | `battery_storage` | agent | `agents.battery_storage_agent.BatteryStorageAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 13 | `scada` | agent | `agents.scada_agent.SCADAAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 14 | `digital_twin` | agent | `agents.digital_twin_agent.DigitalTwinAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [study_service.py:284](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L284), [engine.py:462](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L462), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 15 | `etap_expert` | agent | `agents.etap_expert_agent.ETAPExpertAgent` | REACHABLE | UNREACHABLE | UNREACHABLE | REACHABLE | REACHABLE | [study_executor.py:478-485](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L478-L485), [shared_handlers.py:621-665](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L621-L665) |
| 16 | `etap_gui` | agent | `agents.etap_gui_agent.ETAPGUIAgent` | REACHABLE | UNREACHABLE | UNREACHABLE | REACHABLE | REACHABLE | [study_executor.py:487-494](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L487-L494), [shared_handlers.py:667-714](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L667-L714) |
| 17 | `ahmed_etap_orchestration` | external | `AhmedETAPSkillAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | EXTERNAL_ONLY | [dispatch.py:149](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L149), [study_executor.py:426](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L426), [study_executor.py:496-533](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L496-L533) |
| 18 | `optimization` | external | `OptimizationAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | EXTERNAL_ONLY | [dispatch.py:155](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L155), [study_executor.py:426](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L426), [shared_handlers.py:614](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L614) |
| 19 | `generative_design` | agent | `agents.design_agent.DesignAgent` | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | UNREACHABLE | [dispatch.py:161](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L161), [study_executor.py:535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535), [shared_handlers.py:782](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L782) |
| 20 | `breaker_duty` | external | `breaker_duty.evaluator.BreakerDutyEvaluator` | REACHABLE (behind flag) | UNREACHABLE | UNREACHABLE | UNREACHABLE | REACHABLE | [study_executor.py:413-420](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L413-L420), [shared_handlers.py:614](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L614) |

---

## 3. الفراغات والتدقيق الحرج في الكود الحي

### أ. فحص أنواع الـ `agent` داخل [services/study_executor.py:476-536](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L476-L536):
* تدخل الطلبات الدالة `_dispatch` (السطر 390).
* عندما يكون `handler_type == "agent"` (السطر 424)، يتم استدعاء `_dispatch_agent(canonical, parameters)` (السطر 425).
* داخل دالة `_dispatch_agent`:
  - السطور [478-485](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L478-L485): تُعالج دراسة `etap_expert` وتستدعي `ETAPExpertAgent().answer(question)`.
  - السطور [487-494](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L487-L494): تُعالج دراسة `etap_gui` وتستدعي `ETAPGUIAgent().answer(question)`.
  - السطر [535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L535): **تصطدم جميع أنواع الـ agent الـ 11 الأخرى بـ:**
    `raise ValueError(f"Unsupported agent-routed study type: {study_type}")`.
* **العدد الفعلي لأنواع agent التي ترفع `ValueError`:** **11 نوعاً حصراً** (وليس 13 كما توهم الدليل القديم).
  (الأنواع هي: `harmonic_analysis`, `optimal_power_flow`, `motor_starting`, `transient_stability`, `cable_sizing`, `earth_grid`, `renewable_integration`, `battery_storage`, `scada`, `digital_twin`, `generative_design`).

### ب. كشف الكود الميت الجنائي في `ahmed_etap_orchestration`:
* في [engine/dispatch.py:149](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L149):
  `dispatch["ahmed_etap_orchestration"] = StudyRegistration(handler_type="external", handler="AhmedETAPSkillAgent", ...)`
* في [services/study_executor.py:422-428](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L422-L428):
  التوجيه يفحص فقط:
  - `if registration.handler_type == "native": return self._dispatch_native(...)`
  - `if registration.handler_type == "agent": return self._dispatch_agent(...)`
  - ثم السطر [426](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L426):
    `raise ValueError(f"Unsupported handler_type '{registration.handler_type}' for study '{canonical}'")`
* **البرهان:** بما أن `handler_type` مسجل كـ `"external"`، فإن أي طلب لـ `ahmed_etap_orchestration` يرفع `ValueError` فوراً عند السطر 426، ولا يصل إطلاقاً إلى دالة `_dispatch_agent`.
* **النتيجة:** الكتلة البرمجية المعرفة داخل `_dispatch_agent` في السطور [496-533](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L496-L533) (والتي تنشئ `AhmedETAPSkillAgent` وتنفذ حلقة المهام عبر `ThreadPoolExecutor`) هي **كود ميت بنسبة 100% (Dead Code)** يستحيل أن يبلغه أي مسار تنفيذ عبر `_dispatch`.

### ج. دراسة `breaker_duty` وحراستها بالعلم:
* في [services/study_executor.py:413-420](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L413-L420):
  تم وضع تفرع خاص صريح قبل التعميم:
  ```python
  if canonical == "breaker_duty":
      from api.feature_flags import is_strict_feature_enabled

      if not is_strict_feature_enabled("breaker_duty"):
          raise ValueError("Study type 'breaker_duty' is disabled by feature flag")
      from breaker_duty.evaluator import BreakerDutyEvaluator

      return BreakerDutyEvaluator().execute_study(parameters)
  ```
* **البرهان:** تعمل الدراسة فقط عند تفعيل العلم الصارم `FEATURE_FLAG_BREAKER_DUTY=true`. وعند تعطيله ترفع `ValueError("Study type 'breaker_duty' is disabled by feature flag")`.

---

## 4. جدول المسارات المتوازية (الخطوة 1.3)

يوثق هذا الجدول كافة الملفات التي تحتوي على خرائط أو تعريفات أو شيمز للدراسات والوكلاء، موضحاً العدد الفعلي وطبيعة كل مسار وما إذا كان تكراراً مستقلاً أم مجرد واجهة (View):

| الملف | عدد المدخلات الفعلي | طبيعة المسار (Nature) | علاقة المصدر (Independent Duplicate أم View) | الدليل والشاهد (Evidence file:line) |
|-------|--------------------|----------------------|---------------------------------------------|-------------------------------------|
| [engine/dispatch.py](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py) | **20** | خريطة إرسال موحدة (`STUDY_DISPATCH`) | **مصدر الحقيقة الموحد المقصود (ADR-0002)** | جدول موحد يجمع Native و Agent و External ([dispatch.py:100-170](file:///c:/Users/EWS-01/Desktop/etap/engine/dispatch.py#L100-L170)). |
| [agents/models.py](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py) | **17** | تعداد أساسي (`StudyType` enum) | **مصدر الحقيقة لأسماء الدراسات المعيارية** | كائن Enum معياري ([models.py:33-51](file:///c:/Users/EWS-01/Desktop/etap/agents/models.py#L33-L51)). ينقصه `ahmed_etap_orchestration` و `optimization` و `breaker_duty`. |
| [agents/__init__.py](file:///c:/Users/EWS-01/Desktop/etap/agents/__init__.py) | **16** (في STUDY_TYPE_AGENT_MAP)<br>+ **8** (في ETAP_EXECUTION_AGENT_MAP)<br>+ **14** (في ALL_AGENT_CLASSES) | سجل فئات الوكلاء الثابت | **تكرار جزئي / خريطة ربط ثابتة** | يربط كل `StudyType` بفئة الوكيل المقابلة ([agents/__init__.py:80-97](file:///c:/Users/EWS-01/Desktop/etap/agents/__init__.py#L80-L97)). ينقصه `generative_design`. |
| [agents/registry.py](file:///c:/Users/EWS-01/Desktop/etap/agents/registry.py) | **30** مفتاحاً<br>(27 وكيلاً فريداً + 3 أسماء مستعارة) | مصنع ومسجل الوكلاء الديناميكي (`create_agent_registry`) | **سجل ديناميكي مستقل (DI Container)** | ينشئ كائنات الوكلاء الحية ([agents/registry.py:1422-1503](file:///c:/Users/EWS-01/Desktop/etap/agents/registry.py#L1422-L1503)). |
| [services/study_executor.py](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py) | **20** (تستورد STUDY_DISPATCH) | منفذ وموجه الدراسات الفعلي | **مستهلك لـ STUDY_DISPATCH مع تنفيذ مجتزأ** | ينفذ 4 Native و 2 Agent و 1 External وراء علم، ويفشل على الـ 13 الباقية ([study_executor.py:399, 413, 422, 424, 535](file:///c:/Users/EWS-01/Desktop/etap/services/study_executor.py#L399-L535)). |
| [services/study_service.py](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py) | **4** (Native) + **7** (ETAP mapping) | موجه طبقة الخدمة القديم | **تكرار مستقل مجتزأ (Legacy Duplication)** | يستخدم دوال hardcoded `_run_native_study` و `_run_etap_study` بمعزل تام عن `STUDY_DISPATCH` ([study_service.py:243-284, 307-315](file:///c:/Users/EWS-01/Desktop/etap/services/study_service.py#L243-L315)). |
| [engine/engine.py](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py) | **4** (في `_STUDY_REGISTRY`) | واجهة تكيفية قديمة (Deprecation Shim) | **واجهة جزئية لمحرك الحسابات (Shim View)** | تقتصر فقط على الدراسات الأربع الأصلية لمحرك `PowerSystemEngine` ([engine.py:49-60, 460-464](file:///c:/Users/EWS-01/Desktop/etap/engine/engine.py#L49-L60)). |
| [api/shared_handlers.py](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py) | **18** (في `STUDY_TYPES`) | معالج الطلبات السريعة (Lightweight Mock Handler) | **تكرار مستقل مجتزأ مع محاكاة وهمية** | مشتق من `StudyType` + `ahmed_etap_orchestration`. ينفذ `load_flow` و `etap_expert` و `etap_gui` ويعيد نتائج وهمية أو خطأ للباقي ([shared_handlers.py:90, 613-785](file:///c:/Users/EWS-01/Desktop/etap/api/shared_handlers.py#L90-L785)). يجهل تماماً وجود `breaker_duty` و `optimization`. |
| [src/core/agents.ts](file:///c:/Users/EWS-01/Desktop/etap/src/core/agents.ts) | **11** (في `AGENT_REGISTRY`) | سجل وكلاء TypeScript و Mastra | **سجل مستقل لبيئة Node.js / Mastra** | يعرف بيانات الوكلاء وقدراتهم لبيئة Mastra ([src/core/agents.ts:54-129](file:///c:/Users/EWS-01/Desktop/etap/src/core/agents.ts#L54-L129)). ينتهي الملف عند السطر 136 تماماً. |

---
**خلاصة الخط الأساس:** يثبت التدقيق الجنائي وجود تشظٍ في سلطة تعريف وإرسال الدراسات بين 8 ملفات، حيث تنفرد `engine/dispatch.py` بالشمول النظري (20 مدخلاً)، بينما يقتصر التنفيذ الفعلي في `study_executor.py` على 7 دراسات فقط، وتعاني دراسة `ahmed_etap_orchestration` من حالة كود ميت بسبب تناقض `handler_type`.
