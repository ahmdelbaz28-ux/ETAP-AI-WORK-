# دليل منصة AhmedETAP للهندسة الكهربائية (Chat-First v3.0)
**المهندس الافتراضي الذكي لتحليل وتشغيل شبكات القوى الكهربائية**  
*مرجع الوثيقة: README-AR-2026-V3*  
*حالة الاعتماد: موثق ومعتمد بنسبة 100% (16/16 معيار دولي)*

---

## 1. نبذة عامة ورؤية المنصة

تمثل منصة **AhmedETAP** نقلة نوعية في برمجيات هندسة القوى الكهربائية؛ حيث تجمع بين **قوة المحركات الحسابية الرياضية الصارمة** المعتمدة دولياً، ومرونة **الواجهة التفاعلية المحادثية الذكية (Chat-First Architecture)** عبر بيئة آمنة للمؤسسات.

### المبدأ الهندسي الحاكم:
> **الأمانة العلمية والدقة الرياضية تسبق أي اعتبار بصري (Engineering Honesty > Aesthetics)**  
> لا يوجد أي توليد لبيانات وهمية (Zero Mock Fallbacks). إذا تعذر حساب مسألة هندسية لنقص في المعطيات، تتوقف المنصة بأمان (`Fail-Closed`) وتطلب المعاملات الناقصة من المهندس بدلاً من التخمين أو التلفيق.

---

## 2. المعمارية المزدوجة ونظام الأمان المزدوج (Dual-Runtime Architecture)

تعتمد المنصة على فصل صارم بين طبقتين:
1. **طبقة التنسيق وإدارة الحوار (Mastra / TypeScript Runtime)**:
   - تستقبل استفسارات المهندس بلغة طبيعية (عربية أو إنجليزية).
   - تحلل الهدف الهندسي وتوجهه للوكيل المتخصص (Load Flow, Arc Flash, Coordination, SCADA, الخ).
   - تطبق بوابات الأمان الصارمة وسياسات صلاحية تنفيذ الأدوات.
2. **محرك الحسابات الهندسية (Python MathGuard Core)**:
   - ينفذ المعادلات الرياضية الفيزيائية بشكل حتمي (Deterministic).
   - لا يتدخل الذكاء الاصطناعي التوليدي في العمليات الحسابية إطلاقاً (منع الهلوسة الرقمية Zero Hallucination).
   - يربط المخرجات بختم المهندس المحترف المعتمد (`api/pe_stamp.py`).

---

## 3. مصفوفة المعايير الهندسية المعتمدة (16 معيار دولي)

تم فحص واعتماد جميع المحركات الرياضية في المنصة آلياً عبر أداة `scripts/claims_audit.py --strict` بنسبة 100%:

| المعيار الهندسي | نطاق التطبيق | المحرك الرياضي في المنصة | ملفات التحقق والاختبار |
| :--- | :--- | :--- | :--- |
| **IEEE 1584-2018** | دراسات الوميض القوسي وحساب الطاقة الحادثة | `fault_analysis/arc_flash_engine.py` | `tests/test_arcflash_1584_st_cases.py` (حالات قياسية معتمدة) |
| **IEC 60909** | حساب تيارات القصر المتماثلة وغير المتماثلة | `fault_analysis/fault.py` | `tests/test_fault_analysis_iec60909.py` |
| **IEEE 3002.7** | دراسات سريان الأحمال الصناعية (نيوتن-رافسون) | `load_flow/load_flow.py` | `tests/test_load_flow_deep.py` (شبكات IEEE القياسية) |
| **IEEE 3002** | ضوابط الجهد والسعات الحرارية للمغذيات | `engine/optimizers/placement_pso.py` | `tests/test_standards_compliance_audit.py` |
| **IEC 60255** | تنسيق منحنيات الوقاية المرحلية (TCC) | `coordination/coordination.py` | `tests/test_protection_coordination.py` |
| **IEEE 519** | دراسة التوافقيات ونسب التشوه التوافقي (THD/TDD) | `fault_analysis/harmonic_analysis.py` | `tests/test_harmonic_analysis_ieee519.py` |
| **IEEE 399** | بدء دوران المحركات الكبيرة وهبوط الجهد العابر | `motor_starting/engine.py` | `tests/test_motor_starting_simulation.py` |
| **IEEE 80** | تصميم شبكات التأريض وجهود الخطوة واللمس | `agents/earth_grid_agent.py` | `tests/scenarios/test_earth_grid_scenario.py` |
| **IEEE 1547** | ربط مصادر الطاقة المتجددة (شمسية ورياح) بالشبكة | `agents/renewable_agent.py` | `tests/scenarios/test_renewable_scenario.py` |
| **IEC 62933** | أنظمة تخزين الطاقة بالبطاريات (BESS) | `agents/battery_storage_agent.py` | `tests/scenarios/test_battery_storage_scenario.py` |
| **IEC 61850** | بروتوكولات الأتمتة والاتصال بمحطات التحويل (SCADA) | `agents/scada_agent.py` | `tests/test_scada_chaos_and_readback.py` |
| **IEC 60364** | اختيار وتحديد مقاطع الكابلات وجهد الهبوط | `agents/cable_sizing_agent.py` | `tests/scenarios/test_cable_sizing_scenario.py` |
| **IEEE 141** | توزيع القدرة في المنشآت الصناعية (الكتاب الأحمر) | `agents/etap_expert/simulator.py` | `tests/test_standards_compliance_audit.py` |
| **IEEE 242** | تنسيق أنظمة الحماية الصناعية (الكتاب الأصفر) | `coordination/chain_coordinator.py` | `tests/test_standards_compliance_audit.py` |
| **NFPA 70E** | مستويات مهمات الوقاية الشخصية (PPE Categories) | `fault_analysis/arc_flash_labels.py` | `tests/test_arcflash_1584_st_cases.py` |
| **ANSI Z535** | ألوان ونصوص لوحات التحذير والسلامة الهندسية | `fault_analysis/arc_flash_labels.py` | `tests/test_standards_compliance_audit.py` |

---

## 4. نموذج استخدام مفاتيح الذكاء الاصطناعي الخاصة بالمستخدم (BYOK)

لحماية خصوصية البيانات الهندسية للمؤسسات وعدم الاعتماد الإجباري على مفاتيح الخادم المركزية:
1. يستطيع المهندس إدخال مفتاحه الخاص بأمان عبر شاشة الإعدادات (`Settings -> Provider Keys`).
2. تُرسل المفاتيح عبر ترويسات مشفرة ومؤقتة (`X-User-LLM-Key`).
3. تطبق المنصة خاصية التطهير التلقائي الفوري (`sanitize_error_text`) لمنع تسجيل المفتاح في أي سجلات خطأ أو خوادم وسيطة.

---

## 5. ضوابط الأمان الفوري (Fail-Closed Controls)

- **حظر أدوات النظام الحساسة**: جميع محاولات تشغيل سطر الأوامر أو تنفيذ أكواد خارج الصندوق الآمن (`node-tool`, `powershell-tool`) محظورة نهائياً برمز رفض `HTTP 403 HARD_DENIED`.
- **التحكم الثنائي (Maker-Checker)**: القرارات الهندسية الحساسة كإرسال أوامر فصل القواطع تتطلب اعتماد طرفين قبل التنفيذ.
- **عزل بيانات المشروعات (Tenant Isolation)**: عزل تام لكل مشروع وبياناته لمنع أي تسرب بين الشركات أو الهيئات المشتركة.

---

## 6. التحقق والتشغيل المحلي

### فحص الاعتماد الصارم للمعايير:
```powershell
python scripts/claims_audit.py --strict
```

### تشغيل الاختبارات القياسية الدولية (IEEE Benchmarks):
```powershell
python scripts/run_ieee_benchmarks.py
```

### تشغيل واجهة المستخدم التفاعلية:
```powershell
pnpm -C ui dev
```
تفتح الواجهة على المنفذ الافتراضي `http://localhost:5173`، ويمكن الدخول إما عبر الواجهة المحادثية الحديثة أو العودة للواجهة الكلاسيكية عند الحاجة.
