# خطة المرحلة M4 — السياق والحدود (Context & Boundaries)

**المشروع:** منصة أحمد إيتاب (AhmedETAP AI Engineering Platform)  
**المرحلة:** M4 — Context Fabric, Mastra/Python Boundaries, Fallback Elimination, ML Provenance, Unified Provider Policy  
**نقطة الأساس الحية:** `main @ 852007b03` (بعد دمج M0–M3 عبر PR #609 / #610 / #611)  
**فرع العمل:** `feat/ai-m4-context-boundaries`  
**تاريخ الإعداد:** 2026-09-29  
**البنود المرجعية:** 8 (Context Fabric)، 9 (حدود Mastra/Python)، 10 (إزالة fallback العام)، 13 (provenance للـML)، 14 (سياسة مزودين واحدة)

> **قاعدة التحقق الحي:** كل رقم سطر في برومبت الخطة الرئيسية مأخوذ من تدقيق `43fdd481f`. هذا المستند يمثل **تدقيق الانحراف (Drift Audit)** قبل أي تعديل — حيث اختلف الكود الحي عن الوصف، ثُبّت الحي وتوثق الفجوة أدناه قبل التنفيذ (بروتوكول المفاجآت).

---

## 1. تدقيق الانحراف الحي (Live Drift Audit)

| البند | وصف الخطة (عند `43fdd481f`) | الحقيقة الحية (`852007b03`) | القرار المنفَّذ |
|---|---|---|---|
| **M4.3** | `src/core/agents.ts:157-165` يبني `systemPrompt` من `agent.name + agent.description` ويضخه في `generateWithFailover` الخام بلا tools/schema | `src/core/agents.ts` أصبح **سجلاً بياناتياً خالصاً** (26 وكيلاً) بعد M2.3/M3.4 — لا يوجد فيه أي كود fallback. المكافئ الوظيفي الحي انتقل إلى `src/routes/agents.ts:149-227`: `ENGINEERING_GROUNDING_DIRECTIVE` + `getGroundedSystemPrompt` + `runDirectAi` (يستخدم برومبت YAML القانوني بدل name/description — تحسين P3 — لكنه **ما زال يضخ البرومبت في `/chat/completions` خاماً بلا tools/schema ووسم `grounded_direct_ai_fallback`**) | يُطبَّق **قصد** البند على الحي: حذف مسار الإجابة الهندسية الخام من `src/routes/agents.ts` كاملاً (runDirectAi + التوجيه + باني البرومبت)، والقدرة غير المتاحة ⇒ `SPECIALIZED_EXECUTION_UNAVAILABLE` (503 مغلق). إبقاء `generateWithFailover` للمسار الحافظ للقدرة فقط (Mastra proxy) |
| **M4.1** | `retriever.py:131` يمرر `tenant_id` لكن adapter `:147` يسقطه | ✅ مؤكد حياً بالضبط: `ai_context_engine/retriever.py:131-132` يمرر `where={"tenant_id": ...}`؛ `ai_context_engine/rag_blueprint_adapter.py:147` يستدعي `retrieve(query, top_k=top_k * 2)` **دون** `tenant_id` | إصلاح دقيق: تمرير `tenant_id` عبر كامل سلسلة adapter + ContextFabric |
| **M4.1** | `services/memory_service.py:433` `add_texts` عارية بلا metadata | ✅ مؤكد: `vector_db.add_texts([fact_text])` — لا محتوى provenance/tenant | توسيع `save_to_vector_memory(fact_text, index_name, tenant_id, provenance)` وتمرير `metadatas` كاملة |
| **M4.4** | `predictive/anomaly/digital_twin` مسجلة في `registry.py:1449-1451` وغير قابلة للتنفيذ عبر StudyExecutor | ✅ `registry.py:1449-1451` = سطر تسجيل الوكلاء الثلاثة في `create_agent_registry`. الحقائق الحية: مفاتيح السجل = **30** (27 أصلياً + 3 أسماء مستعارة `harmonic/opf/protection`). `digital_twin` **عضو StudyType حي** (`agents/models.py:61`، أُضيف 2026-07-26 لمنع سقوط صامت إلى LOAD_FLOW) ومدخل `STUDY_DISPATCH` مشتق عبر `STUDY_TYPE_AGENT_MAP`، وتنفيذه يرفع `SpecializedExecutionUnavailableError` (fail-closed). `predictive/anomaly` **ليسا** StudyType وليسا مدخلاً في الجدول | **تسوية موثقة بأصغر نطاق:** لا يُزال عضو `DIGITAL_TWIN` من enum (إزالته تعيد باگ السقوط الصامت الموثق + تكسر بوابة M1)؛ بدلاً من ذلك: تُثبَّت اختبارات انحدار تمنع تسجيل `predictive/anomaly` كـStudyType، وتمنع أي تنفيذ صامت لـ`digital_twin` (يبقى fail-closed حصراً)، وتُربط الثلاثة بـContextFabric كمزوّدي سياق |
| **M4.5** | cascade معطل بالعلم في `integrations/model_router.py` | ✅ موضع التعطيل الحي: `integrations/langfuse_llm.py:466-477` يحرس `ModelCascadeRouter` بعلم `use_model_cascade` (`api/feature_flags.py:151-156`). التطبيقات المتنافسة الخمس: `src/core/providers.ts:88-105` (10 مزودين)، `src/mastra/lib/model-config.ts` (openai فقط)، `api/chat_stream.py:80` (3 مزودين + BYOK)، `ui/src/lib/llm-chat.ts` + `ui/src/lib/providers.ts` (localStorage)، `integrations/model_router.py` (معطل) | إزالة حارس العلم ورفع `model_router` إلى **نقطة السياسة الواحدة** عبر بيان مشترك `config/llm-provider-policy.json`، وتوجيه المستهلكين إليه/اختبار تزامن صارم |
| **M4.2** | prompts.json (33 handle) عقد عابر للحدود؛ مفاتيح Python 27 (+3 أسماء مستعارة) مقابل docstring يقول 24 | ✅ مؤكد: `prompts.json` = 33 مدخلاً؛ `create_agent_registry()` حياً = **30 مفتاحاً** (27 + 3 aliases)؛ docstring `agents/registry.py:1424` يقول "24" و`agents/__init__.py` يقول "15" | إعلان مصدر واحد للمفاتيح: `CANONICAL_AGENT_KEYS` (27) + `AGENT_KEY_ALIASES` (3) + دالة تحقق fail-fast؛ تحديث docstrings؛ اختبار تزامن مع دوال البرومبت |


## 2. نطاق التنفيذ (M4.1 → M4.5)

### M4.1 — ContextFabric (ستة أنواع فوق المكونات القائمة)
- حزمة جديدة `context_fabric/`: `ContextType` (ENGINEERING_KNOWLEDGE / ENGINEERING_HISTORY / PROJECT_STATE / CODE_CONTEXT / STANDARDS / USER_CONTEXT)، `ContextEvidence` (يفرض `source_type` + `content_hash` (sha256) + `tenant_id` إلزامياً)، `ContextFabric` بتسجيل مزوّدين لكل نوع.
- مزوّدات فوق المكونات القائمة **لا إعادة بناء**: `MemoryKnowledgeProvider` → `services/memory_service.py`؛ `CodeContextProvider` → `ai_context_engine`؛ `StandardsProvider` → `skills/etap-expert.md`؛ شرائح HISTORY/PROJECT_STATE/USER_CONTEXT قابلة للحقن (injectable) وتعلن عدم التوفر صراحةً عند غياب المزوّد — **لا بيانات مزيفة**.
- إصلاحا التسريب/الـmetadata (M4.1 أعلاه) + اختبارات.

### M4.2 — حدود «Mastra يخطط وPython ينفذ»
- `CANONICAL_AGENT_KEYS`/`AGENT_KEY_ALIASES`/`validate_agent_keys()` في `agents/registry.py` + استخدامها في فحص الإقلاع.
- `ChiefEngineeringOrchestrator.execute_execution_plan(plan)` كـadapter خلف الحدود: يستهلك `ExecutionPlanContract` (عبر `custom_nodes` القائمة في WorkflowEngine) وينتج `ExecutionTraceContract` — إعادة استخدام كاملة لجدولة M3.
- اختبار تزامن دوال البرومبت: كل `prompt_handle` في Python و`promptHandle` في TS ⊆ مفاتيح `prompts.json` (توسيع لا استبدال).

### M4.3 — إزالة fallback الـLLM العام
- حذف `runDirectAi` + `getGroundedSystemPrompt` + `ENGINEERING_GROUNDING_DIRECTIVE` من `src/routes/agents.ts`.
- تعذّر المسار الحافظ للقدرة (Mastra proxy غير مهيأ/فاشل) ⇒ `503 {code: "SPECIALIZED_EXECUTION_UNAVAILABLE"}` — لا إجابة هندسية من مسار خام.
- فاحص حرماني دائم في meta-CI (`scripts/check_ai_fallback_guard.py`) + اختبار زرع خرق يفشل.

### M4.4 — ML provenance + السياق
- `predictive_agent`: تعطيل `allow_synthetic` في prod (فحص بيئة `ENV`/`APP_ENV` غير dev/test)، وإلزام `model_version`/`input_window`/`drift_state` في مخرجات التنبؤ.
- توصيل بوابة الحقائق الثلاث (`digital_twin/validation_gateway.py`) في مسار `DigitalTwinAgent.execute`.
- إصلاح الإقرار الذاتي في `orchestrator.py`: `all_validated` يشترط تحققاً خارجياً (نتيجة ValidationAgent مستقلة) لا مجرد أعلام ذاتية.
- اختبارات سلبية.

### M4.5 — سياسة المزودين الموحدة
- `config/llm-provider-policy.json`: نقطة السياسة الواحدة (المزودون، الطبقات، النماذج المسموحة).
- `integrations/model_router.py`: تحميل البيان + `get_provider_policy()` + `resolve_model()` والتحقق fail-closed.
- إزالة علم `use_model_cascade` من `api/feature_flags.py` وإزالة الحارس من `langfuse_llm.py`.
- `api/chat_stream.py`: قائمة السماح من البيان. `src/core/providers.ts`: اشتقاق/مصادقة ضد البيان عند الإقلاع + اختبار vitest بمحاكاة تعديل البيان.
- اختبار أن تغيير البيان (النقطة الواحدة) يغيّر سلوك كل المستهلكين.

---

## 3. بوابات قبول M4 (من الخطة الرئيسية)

| البوابة | الشرط | آلية التحقق |
|---|---|---|
| **G1** | مسار fallback الخام محذوف + فاحص حرماني في meta-CI يمنع عودته | حذف `src/routes/agents.ts` + `check_ai_fallback_guard` + اختبار زرع |
| **G2** | كل Evidence من ContextFabric يحمل `source_type` + `hash` + `tenant_id` | اختبار بنيوي/سلوكي |
| **G3** | `allow_synthetic=false` في prod مثبتة باختبار | اختبار سلبي ببيئة prod |
| **G4** | قرار المزود من نقطة واحدة (model_router) — تغيير السياسة يغيّر السلوك كله | اختبار Python + vitest |

**قيد دائم:** Fail-Closed — لا مسارات إجابة صامتة، لا بيانات مزيفة، لا كسر لبوابات M0–M3 (reachability/registry/assertions).

**التوقيع:** الوكيل المنفذ — منصة أحمد إيتاب  
**التاريخ:** 2026-09-29

---
