# قرارات التصميم الهندسي للعقود (M2.1) — Contracts Name Disambiguation Decisions

**المرحلة:** M2.1 — فك تصادمات الأسماء الأربعة وإنشاء `contracts/ai/`  
**الصادر عن:** رئيس مهندسي النظم البرمجية — منصة أحمد إيتاب  
**التاريخ:** 2026-09-27  

---

## 1. خلفية المشكلة (Problem Context)

عند تصميم طبقة العقود الموحدة للتنفيذ الهندسي بالذكاء الاصطناعي، رُصدت أربعة رموز برمجية متصادمة تحمل أسماء مطابقة لرموز موجودة مسبقاً في فروع مختلفة من قاعدة الكود. الإبقاء على الأسماء القصيرة كان يعني خطر الاستيراد الملتبس (`ImportError`) وغموض النوع في كلا الـ runtime.

---

## 2. جدول التصادمات وقرارات الـ Namespace (Disambiguation Table)

| اسم العقد الجديد | الاسم القصير المتصادم | الرمز المتصادم في قاعدة الكود | السطر | نوع الرمز |
|---|---|---|---|---|
| `ExecutionPlanContract` | `ExecutionPlan` | [`engine/scalability.py:695`](../../engine/scalability.py) | L695 | `@dataclass` Python |
| `ExecutionContextContract` | `ExecutionContext` | [`src/core/types.ts:84`](../../src/core/types.ts) | L84 | TypeScript `interface` |
| `ValidationResultContract` | `ValidationResult` | [`digital_twin/validation_gateway.py:64`](../../digital_twin/validation_gateway.py) | L64 | `@dataclass` Python |
| `StudyResultContract` | `StudyResult` | [`core_model/specs.py:431`](../../core_model/specs.py) | L431 | Pydantic model |

---

## 3. القرار الهندسي المعتمد: Suffix `Contract`

### المبرر الهندسي
- **صفر تعارض في الاستيراد:** اللاحقة `Contract` تجعل كل رمز فريداً عبر كامل قاعدة الكود دون الحاجة لاستيراد مؤهل (`from contracts.ai import ...` مقابل `from engine.scalability import ...`).
- **توافق عكسي:** الرموز الأصلية في `engine/scalability.py` و`digital_twin/validation_gateway.py` و`core_model/specs.py` و`src/core/types.ts` لم تُمَس ولا تحتاج تعديلاً؛ هي تخدم مجالاتها الخاصة.
- **اتساق الـ namespace:** جميع العقود تعيش في `contracts.ai.*` — مما يجعل `grep` واحد يجد كل عقود الـ AI pipeline فوراً.
- **توثيق الهدف المعماري:** الـ `Contract` suffix يعلن صراحةً أن هذه النماذج هي **عقود اتصال بين runtimes**، وليست نماذج بيانات domain-specific.

### البدائل المرفوضة
| البديل | سبب الرفض |
|---|---|
| Prefix `AI` (مثل `AIExecutionPlan`) | يبدو مصطنعاً؛ الـ `contracts.ai` namespace يوفر السياق كافياً |
| Suffix `Schema` | مُحتل بالفعل بمعنى Pydantic validation schema في أجزاء أخرى |
| Suffix `Wire` | أقل تعبيراً عن الهدف التعاقدي |
| Prefix مسار كامل (`ContractsAI`) | طويل للغاية ويؤثر على قابلية القراءة |

---

## 4. قاعدة المتطابقة بين Python و TypeScript (Cross-Runtime Parity)

كل عقد Python محدد في `contracts/ai/models.py` (Pydantic `BaseModel`) له مرآة متطابقة هيكلياً في `src/core/contracts/ai.ts` (TypeScript `interface`).

| عقد Python | مرآة TypeScript |
|---|---|
| `ProvenanceContract` | `ProvenanceContract` |
| `EvidenceContract` | `EvidenceContract` |
| `PlanNodeContract` | `PlanNodeContract` |
| `ExecutionPlanContract` | `ExecutionPlanContract` |
| `ExecutionContextContract` | `ExecutionContextContract` |
| `ExecutionRequestContract` | `ExecutionRequestContract` |
| `ValidationResultContract` | `ValidationResultContract` |
| `StudyResultContract` | `StudyResultContract` |
| `ApprovalStateContract` | `ApprovalStateContract` |
| `ExecutionTraceContract` | `ExecutionTraceContract` |

**القانون الصارم:** أي تعديل على أحد الجانبين يستوجب تعديلاً متزامناً على الجانب الآخر. يتحقق من ذلك اختبار التزامن في `tests/test_contract_sync.py` (M2 Gate Test 2).

---

## 5. توسيع `agents/models.py` بحقول الربط (M2.2 Wire Linkage)

تمت إضافة حقول الربط التالية إلى `AgentResult` و`EngineeringTask` بدون كسر التوافقية:
- `run_id: str | None = None` — معرف الـ run الذي أطلق هذه المهمة.
- `plan_id: str | None = None` — معرف الـ plan الذي ينتمي إليه.
- `node_id: str | None = None` — معرف العقدة المقابلة في الـ plan (لـ `AgentResult` فقط).

جميع الحقول اختيارية (`None`) لضمان التوافق العكسي الكامل مع كل الاختبارات والكود الحالي.
