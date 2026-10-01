# مصفوفة القدرات والوكلاء وسلطة التعريف — Capability Matrix
**المستودع:** `https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git`  
**نقطة الأساس الحية:** `main @ 43fdd481f` (`43fdd481faf134f757914702db3b4ab596bfc429`)  
**تاريخ التحقق الجنائي:** 2026-09-27  
**الحالة:** معتمد جنائياً ومثبت كودياً (صفر تخمين — Zero Hallucination)

---

## 1. محاور المصفوفة والتحقق العددي الحرفي

* **المحور الرأسي (الدراسات):** 20 دراسة من جدول `STUDY_DISPATCH` في [engine/dispatch.py](../../engine/dispatch.py).
* **المحور الأفقي (الوكلاء):** 27 فئة وكيل فريدة مسجلة ومُنشأة في `create_agent_registry` داخل [agents/registry.py:1422-1503](../../agents/registry.py#L1422-L1503):
  1. `load_flow` (`LoadFlowAgent`)
  2. `short_circuit` (`ShortCircuitAgent`)
  3. `harmonic_analysis` (`HarmonicAnalysisAgent`)
  4. `optimal_power_flow` (`OptimalPowerFlowAgent`)
  5. `protection_coordination` (`ProtectionCoordinationAgent`)
  6. `etap_execution` (`ETAPExecutionAgent`)
  7. `validation` (`ValidationAgent`)
  8. `report` (`ReportGenerationAgent`)
  9. `arc_flash` (`ArcFlashAgent`)
  10. `motor_starting` (`MotorStartingAgent`)
  11. `transient_stability` (`StabilityAgent`)
  12. `cable_sizing` (`CableSizingAgent`)
  13. `earth_grid` (`EarthGridAgent`)
  14. `renewable_integration` (`RenewableAgent`)
  15. `battery_storage` (`BatteryStorageAgent`)
  16. `scada` (`SCADAAgent`)
  17. `digital_twin` (`DigitalTwinAgent`)
  18. `anomaly` (`AnomalyAgent`)
  19. `predictive` (`PredictiveAgent`)
  20. `weather` (`WeatherAgent`)
  21. `goal_planner` (`GoalPlannerAgent`)
  22. `optimization` (`OptimizationAgent`)
  23. `generative_design` (`DesignAgent`)
  24. `code_guard` (`CodeGuardAgent`)
  25. `etap_expert` (`ETAPExpertAgent`)
  26. `etap_gui` (`ETAPGUIAgent`)
  27. `ahmed_etap` (`AhmedETAPSkillAgent`)
  *(ملاحظة: يحتوي السجل بالإضافة لهؤلاء على 3 أسماء مستعارة: `harmonic`, `opf`, `protection` ليصبح إجمالي مفاتيح القاموس 30 مفتاحاً تم فحصها وتحميلها بنجاح دون أي خطأ استيراد).*

---

## 2. جدول المصفوفة وحالة التنفيذ وسلطة التعريف

أحكام الحالة المعتمدة:
* `EXECUTABLE`: ينفذ فعلياً اليوم عبر مسار حي مثبت بالشاهد (`file:line`).
* `NOT_EXECUTABLE`: كود الوكيل معرَّف في النظام لكن لا ينفذ عبر مسار إرسال الدراسات (`study_executor`).
* `DEAD_CODE`: كود موجود في مسار الإرسال يستحيل وصول التنفيذ إليه بسبب خلل بنيوي أو شرط رافض قبله.
* `UNKNOWN`: لا يوجد شاهد قطعي.

| # | نوع الدراسة (`STUDY_DISPATCH`) | الوكيل المسؤول في السجل (`registry.py`) | حالة التنفيذ عبر `study_executor` اليوم | سلطة التعريف الحالية (Authority of Definition) | الشاهد والدليل القاطع (`file:line`) |
|---|-------------------------------|-----------------------------------------|----------------------------------------|------------------------------------------------|-------------------------------------|
| 1 | `load_flow` | `LoadFlowAgent` | **EXECUTABLE** | `engine/dispatch.py:102` + `engine/engine.py:50` | ينفذ عبر `PowerSystemEngine.run_load_flow` في [study_executor.py:440](../../services/study_executor.py#L440). |
| 2 | `short_circuit` | `ShortCircuitAgent` | **EXECUTABLE** | `engine/dispatch.py:103` + `engine/engine.py:51` | ينفذ عبر `PowerSystemEngine.run_fault_analysis` في [study_executor.py:445](../../services/study_executor.py#L445). |
| 3 | `arc_flash` | `ArcFlashAgent` | **EXECUTABLE** | `engine/dispatch.py:104` + `engine/engine.py:56` | ينفذ عبر `PowerSystemEngine.run_arc_flash` في [study_executor.py:455](../../services/study_executor.py#L455). |
| 4 | `protection_coordination` | `ProtectionCoordinationAgent` | **EXECUTABLE** | `engine/dispatch.py:108` + `engine/engine.py:52` | ينفذ عبر `PowerSystemEngine.run_protection_coordination` في [study_executor.py:467](../../services/study_executor.py#L467). |
| 5 | `harmonic_analysis` | `HarmonicAnalysisAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:82` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). الوكيل حي لكن مسار التوجيه مفقود. |
| 6 | `optimal_power_flow` | `OptimalPowerFlowAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:83` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 7 | `motor_starting` | `MotorStartingAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:85` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 8 | `transient_stability` | `StabilityAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:86` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 9 | `cable_sizing` | `CableSizingAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:88` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 10 | `earth_grid` | `EarthGridAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:89` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 11 | `renewable_integration` | `RenewableAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:90` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 12 | `battery_storage` | `BatteryStorageAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:91` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 13 | `scada` | `SCADAAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:92` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 14 | `digital_twin` | `DigitalTwinAgent` | **NOT_EXECUTABLE** | تنازع بين `engine/dispatch.py:136` و `agents/__init__.py:93` | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 15 | `etap_expert` | `ETAPExpertAgent` | **EXECUTABLE** | `engine/dispatch.py:136` + `agents/etap_expert_agent.py` | ينفذ عبر `ETAPExpertAgent().answer()` في [study_executor.py:478-485](../../services/study_executor.py#L478-L485). |
| 16 | `etap_gui` | `ETAPGUIAgent` | **EXECUTABLE** | `engine/dispatch.py:136` + `agents/etap_gui_agent.py` | ينفذ عبر `ETAPGUIAgent().answer()` في [study_executor.py:487-494](../../services/study_executor.py#L487-L494). |
| 17 | `ahmed_etap_orchestration` | `AhmedETAPSkillAgent` | **DEAD_CODE** | `engine/dispatch.py:149` (سجلت كـ external) | يرفع السطر [study_executor.py:426](../../services/study_executor.py#L426) خطأ على external قبل بلوغ كتلة الكود في السطور [496-533](../../services/study_executor.py#L496-L533). |
| 18 | `optimization` | `OptimizationAgent` | **NOT_EXECUTABLE** | `engine/dispatch.py:155` (نوعها external) | يرفع `ValueError` في [study_executor.py:426](../../services/study_executor.py#L426). |
| 19 | `generative_design` | `DesignAgent` | **NOT_EXECUTABLE** | `engine/dispatch.py:161` (وكيل هيكلي وراء علم معطل) | يرفع `ValueError` في [study_executor.py:535](../../services/study_executor.py#L535). |
| 20 | `breaker_duty` | لا يوجد وكيل (Evaluator) | **EXECUTABLE** (behind flag) | `engine/dispatch.py:167` + `services/study_executor.py:413` | ينفذ عبر `BreakerDutyEvaluator` في [study_executor.py:413-420](../../services/study_executor.py#L413-L420) بشرط تفعيل العلم. |

*(وكلاء الدعم والتحقق الإضافيون في السجل: `etap_execution`, `validation`, `report`, `anomaly`, `predictive`, `weather`, `goal_planner`, `code_guard` ليسوا دراسات مستقلة في جدول الإرسال وإنما وكلاء دعم ومهام فرعية).*

---

## 3. الخلاصة الإلزامية والتحليل الحاكم للمسارات الميتة (نص تحليلي لا جدول)

بناءً على الفحص الجنائي الدقيق لكود التشغيل في `main @ 43fdd481f`:

1. **حصر الدراسات التي لا تملك أي مسار تنفيذ حي اليوم عبر `study_executor`:**
   من أصل 20 دراسة مسجلة في `STUDY_DISPATCH`، يوجد **13 دراسة لا تملك أي مسار تنفيذ حي اليوم عبر منفذ التنفيذ الرئيسي (`services/study_executor.py`)**:
   - **11 دراسة وكلاء معطلة بالتوجيه:** `harmonic_analysis`, `optimal_power_flow`, `motor_starting`, `transient_stability`, `cable_sizing`, `earth_grid`, `renewable_integration`, `battery_storage`, `scada`, `digital_twin`, `generative_design`. هذه الوكلاء معرفة وتعمل بنجاح عند استدعائها المباشر في بيئة بايثون، ولكن عند إرسال طلب دراسة عبر `StudyExecutor._dispatch` تصطدم جميعها بالسطر [services/study_executor.py:535](../../services/study_executor.py#L535) الذي يرفع `ValueError("Unsupported agent-routed study type")` لعدم وجود كتل شرطية تستقبلها.
   - **دراسة واحدة كود ميت بنيوياً:** `ahmed_etap_orchestration`. هذه الدراسة لها كتلة معالجة كاملة مكتوبة في السطور [496-533](../../services/study_executor.py#L496-L533)، لكنها مسجلة كـ `handler_type="external"` في جدول الإرسال ([engine/dispatch.py:149](../../engine/dispatch.py#L149))، مما يجعل دالة التوجيه ترفضها وتلقي استثناءً عند السطر [426](../../services/study_executor.py#L426) قبل أن تصل إلى دالة معالجة الوكلاء إطلاقاً.
   - **دراسة خارجية معطلة:** `optimization`، مسجلة كـ `external` وترفع `ValueError` فوراً عند السطر 426 لغياب موجه للمهام الخارجية في `study_executor`.

2. **تحليل المالك المحتمل للقرار (Ownership of Decision):**
   - بالنسبة للدراسات الـ 11 التابعة للوكلاء (`harmonic_analysis` إلى `generative_design`): **المالك موجود تقنياً** وهو فريق تطوير طبقة التنفيذ (`services/study_executor.py`). المطلوب هندسياً هو ربط موجه الوكلاء العام بسجل الوكلاء `STUDY_TYPE_AGENT_MAP` وتمرير `EngineeringTask` للوكيل بدلاً من قصر المعالجة على `etap_expert` و `etap_gui`.
   - بالنسبة لـ `ahmed_etap_orchestration`: **المالك مفقود بسبب تضارب التوصيف المعماري (Architectural Conflict)**. قرار تصنيفها كـ `external` في ADR-0002 يتناقض مع وجود كود بايثون محلي لها في `agents/ahmed_etap_orchestrator.py` وكتلة تنفيذ داخل `study_executor.py`. يتطلب الأمر قراراً معمارياً موحداً: إما تغيير تصنيفها إلى `agent` لتعمل محلياً، أو حذف الكتلة الميتة وتوجيهها لخدمة هندسية خارجية عبر HTTP.
   - بالنسبة لـ `optimization`: **المالك غير موجود**؛ الدراسة أُضيفت كمدخل في جدول الإرسال دون وجود مسار تكاملي خارجي نشط في الخدمة.
   - بالنسبة لـ `breaker_duty`: **المالك موجود** ومُحكم؛ مسارها يعمل عبر المقيّم المتخصص خلف علم ميزة صارم، وتملك مسار تنفيذ مشروط وواضح.
