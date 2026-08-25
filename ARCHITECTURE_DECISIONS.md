# Architecture Decisions — AhmedETAP

سجلّ القرارات المعمارية المقصودة (Architecture Decision Records). كل قرار يُوثّق
السياق، والاختيار، والبدائل المُهملة، وعواقب التنفيذ — وفق الفصل P0 من خطة التنفيذ
الآمن v3.x. تُنشر مراحل التنفيذ المحددة لكل قرار في قسم "المرتبط بالخطة".

---

## ADR-001 — مصدر واحد لمسارات Data Migrations (Alembic)

**الحالة:** مقرَّر (P0) — نُفِّذ.

### السياق
كان المستودع يحوي مجلّدي هجرة متقاطعين:
- `migrations/` — المجلد الفعلي المستخدَم (فيه `env.py` المخصّص غير المتزامن، و8 مراجعات
  001→008، و`__init__.py`)، وهو ما تشير إليه `alembic.ini:22 → script_location = migrations`.
- `alembic/` — مجلد ميت/متقادم يحتوي `env.py` متزامن قديماً (SQLite-only) + `script.py.mako`
  + نسخة قديمة مكررة من مراجعة `001_initial_schema.py` وحدها. لا يخدمه أي شيء في `script_location`.

التحقق (قبل الحذف):
- `alembic.ini` → `script_location = migrations` ✅
- سلسلة الهجرة في `migrations/versions/` خطّية ورأس واحد:
  `001 → 002 → 003 → 004 → 005 → 006_scada_gis_email → 007_fix_study_results_orm → 008_add_tenant_id_and_rls` ✅
- فحص `git grep` لم يرصد أي إشارة استيراد سليمة إلى `alembic/` (سوى مراجع وثائقية/تعليقية
  ومسار-fliters في workflow قديم).

### القرار
اعتماد **`migrations/`** كمصدر وحيد لمسارات Alembic، وحذف مجلد `alembic/` الميت بالكامل.

### عواقب
- `script_location` بلا تغيير (كان يُشير أصلاً إلى `migrations`).
- حُذف `alembic/**` من path-filters في `.github/workflows/alembic-migrations.yml`
  (أصبح يشغّل على `migrations/**` و`alembic.ini` فقط) — فيُجنَّب CI تشغيلاً بلا داعٍ على مسار ميت.
- أي مرجع وثائقي قديم إلى `alembic/` (مثل `docs/DEV_PIPELINE.md`, `docs/NEON_DATABASE.md`)
  يُعدّ متقادماً؛ تُهذَّب الوثائق في مرحلة لاحقة دون أن يغيّر ذلك من سلوك الهجرة.

### ملاحظة عن "الرأسَين"
بدأنا من ملاحظة REMEDIATION_PLAN (بند C1) التي ذكرت رأسَين (`006_scada_gis_email` +
`006_add_tenant_id_and_rls`). التحقق الفعلي أثبت أن المسألة **أُصلحت مسبقاً**: الإصدار
`007` أُدرج بينهما فأصبحت السلسلة خطّية ذات رأس واحد (`008_add_tenant_id_and_rls`).
لا حاجة لتغيير `down_revision` في P0.

---

## ADR-002 — إزالة تكرار تسجيل المسارات (Router Registration Duplicates)

**الحالة:** مقرَّر (P0) — نُفِّذ.

### السياق
رصد الفحص تكرار تسجيل نفس الـ APIRouter أكثر من مرة، ما يُسبب
سلوكاً غير محسوم في المسار/التوثيق الحسابي، بل يُعدّ خطأً في بعض الحالات:
- `feature_flags_router` مضمّن مرتين في `api/routes.py` (السطر الأصلي 771 + 794).
- `autodesk_connectors_router` مضمّن مرتين في `api/routes.py` (السطر الأصلي 780-782 + 786-788).
- `email-digest` مسجَّل كمسارين متطابقين في `ui/src/App.tsx` (السطران 218 + 227).

### القرار
إبقاء التسجيل الأول/المرجعي وحذف كل التكرارات.

### عواقب
- لا تغيير في الواجهة أو السلوك؛ مجرد إزالة التكرار.
- `SearchRemedy` — تم التحقق بعد الحذف من بقاء مرجع واحد فقط لكل مكوّن.

---

## ADR-003 — مخطط المراحل ومبدأ "نطاق الملفي المحترم"

**الحالة:** مرجعي (لا يتطلب تعديل ملفات في P0 ذاتها).

ترتيب مراحل البناء المُعتمد والأساس الكودي لكل مرحلة:

```
P0   → P0b → P1 → P2 → P3 → P4a → P4b → P5 → P6 → P7a-d → P8 → P9 → P10
```

| مرحلة | الملفات/المسؤولية | الأساس الكودي |
|-------|-------------------|---------------|
| P0  | تحضيرات موحدة (تكرارات + مسار Alembic) + هذا الملف | `ui/src/App.tsx`, `api/routes.py`, `alembic.ini`, `.github/workflows/alembic-migrations.yml` |
| P0b | آلية rollout نسبي `evaluate_flag_with_rollout()` | `api/feature_flags.py` |
| P1  | Tool Policy Engine (`api/tool_policy.py`) — deny-by-default | `src/mastra/tools/*` |
| P2  | بوابة موافقة + idempotency + maker-checker (`api/approvals.py`) | `api/dual_control.py` |
| P3  | `api/session_stream.py` — SessionStreamHub + ticket 60s | `api/websocket.py`, `api/cua_confirmation_ws.py` |
| P4a | Agent Executor (`api/agent_executor.py`) — `agent-exec/plan` بفرض `source` (422) | `api/routes.py` |
| P4b | `api/chat_stream.py` — LLM خادمي + إنشاء `ProvidersTab.tsx` (stub) | `ui/src/lib/llm-chat.ts`, `ui/src/pages/settings/` |
| P5  | `api/results_store.py` — ResultStore (حد 10MB + TTL) | `api/routes.py` (`studies/run`) |
| P6  | `ui/src/app/ChatWorkspace.tsx` + مكوّنات chat/cards/viewer | مسار `ui/src/pages/settings/Settings.tsx` (2909 سطراً) |
| P7a-d | تقسيم Settings (Providers/Agents/Skills/ MCP/Import-Export/Security) | `ui/src/pages/Settings.tsx` |
| P8  | نقل صفحات قديمة إلى `/advanced` (`<Navigate replace />`) | `ui/src/App.tsx` |
| P9  | استيراد/تصدير داخل الشات | `api/import` + `api/export` |
| P10 | تفعيل `chat_first_ui` تدريجياً | `api/feature_flags.py` |

### مبادئ ملزمة عبر كل المراحل
- لا تعديل لأي ملف خارج نطاق المرحلة الجارية.
- `npm run typecheck` و`pytest api/` و`npm run build` خضراء قبل دمج أي مرحلة.
- كل مسار جديد يخضع لـ Rate Limiting (نمط `api/routes.py` السطر ~248-269) و tenant-scoping.
- مفاتيح LLM لا تصل إلى المتصفح (تُغلق ثغرة `localStorage["etap-settings"]` في P4b).
- تُضاف فحوصات Prompt-Injection (Validation على معاملات الأدوات) في نطاق P1.

---

*آخر تحديث: أثناء تنفيذ P0 من خطة التنفيذ الآمن v3.x.*
