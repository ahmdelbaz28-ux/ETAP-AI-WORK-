# Chat-First UI Patterns — Agent Task Brief

> ملف توجيه للوكيل: مراجعة كتالوج أنماط واجهة AI-native وتنفيذ الأنسب لمنصة AhmedETAP الهندسية،
> مع حصر إلزامي لإصلاحات LIGHT MODE قبل أي عمل بصري.

---

## 0. هوية المشروع (غير قابلة للتفاوض)

منصة هندسية **Chat-First v3.0** حرجة للسلامة:
- ثنائية اللغة (EN/AR) مع RTL سليم
- معايير IEC 60909 / IEEE 1584 / IEEE 3002.7 / IEC 60255 / IEEE 399 / IEEE 519
- **Maker-Checker** (Dual-Control) على الأفعال الحرجة
- **EmergencyStop** (Kill-Switch) — أحمر = إيقاف فقط
- **PE Review Hash** — أي نتيجة هندسية تتطلب مراجعة مهندس محترف
- **MathGuard Zero Hallucination** — ممنوع اختلاق قيم أو مصادر أو ثقة من جانب العميل

---

## 1. مصدر الأنماط (راجعه أولاً)

**الموقع**: https://www.beautifului.dev/
مكتبة 21 primitive جاهزة لواجهات شات AI-native، ترخيص **MIT** (مسموح الاستلهام).
الديمو معمول على محل آيس كريم — مرح وملون. **نأخذ الأنماط فقط، لا الألوان ولا الروح.**

الـ primitives المتاحة: Loading State, Thinking, Streaming Text, Approval Card, Tool Chips,
Task Rows, Chat, Prompt Bar, Recommendation Card, Context Cards, Diff Table, Records Table,
Filter Table, Sidebar Nav, Search, Flowchart, Insight Cards, Code Block, Fine-tune Card,
Selection Actions, Agent Screen.

**صلاحية الوكيل**: القائمة أدناه نقطة انطلاق. **إذا وجدت أي تأثير آخر في الموقع مناسباً**
لهوية المنصة الهندسية ويلتزم بالقيود في §4/§5، **نفّذه أيضاً** مع تبرير سطر واحد لماذا
يناسب منصة سلامة حرجة. رفض أي نمط لا يلتزم بالقيود مهما كان جذاباً.

---

## 2. الأنماط المعتمدة (مرتبة قيمة/مجهود)

### 1) Thinking + Task Rows — الأعلى قيمة
- **الحالة الفعلية**: Task Rows موجودة فعلاً في `ui/src/components/chat/ActivityDrawer.tsx:76-105`
  (صفوف phase + Progress + زر Stop) وبياناتها في `chatStore.activity`
  (`ui/src/store/chatStore.ts:82-88`). **لا تبنِ من الصفر — حسّن.**
- المطلوب: traces قابلة للطي (collapsible)، chips مضغوطة (`Load Flow F-07 > Completed` +
  `tools: 4, messages: 2`)، و**elapsed timer** لكل صف.
- **تصحيح**: الـ elapsed timer **غير موجود** في `EmergencyStopButton.tsx` (يوجد spinner فقط
  في السطر 81-86). هو كود جديد — يجب أن يحترم `prefers-reduced-motion` وينظّف الـ interval.

### 2) Approval Card
- **الحالة الفعلية**: مصفوفة `decisions` في `chatStore.ts:423` (أحداث `decision_request`)
  **غير مستغلة** — تُعرض كقائمة مسطحة فقط في ActivityDrawer. هنا الفرصة الحقيقية.
- النمط: سؤال واضح + 2-3 خيارات + Skip/Continue + مؤشر `1 / 3`.
- **قيد أمني**: الكارت **يعكس** قرار Approval Gateway فقط — **ممنوع تجاوز Maker-Checker**
  (`ui/src/pages/DualControl.tsx`) أو تنفيذ أي فعل حرج من العميل.

### 3) Streaming Text + inline sources + Follow-ups
- المصادر تُشتق من بيانات موجودة: `StructuredAnswer.findings[].standard_reference` و
  `standard_clause` في `ui/src/components/chat/MessageList.tsx:58-80` — بلا backend جديد.
- **قيد MathGuard**: Follow-ups **من السيرفر فقط** أو قائمة deterministic. ممنوع أن يولدها
  العميل (vector هلوسة مباشر).
- عدد المصادر حقيقي، لا زخرفي (لا "10 sources" ديمو).

### 4) Prompt Bar
- `ENGINEERING_COMMANDS` موجود في `ui/src/components/chat/MessageInput.tsx:30` مع
  Tab-completion. أضف @chips (`@project`) فوق حقل الكتابة فقط.
- **ممنوع**: model picker (إعدادات الـ provider admin-only عبر `AISettingsModal`) و dictation.

### 5) Loading State + elapsed time
- spinner + elapsed timer + cancel للدراسات الطويلة (Newton-Raphson).
- زر الإيقاف موجود (`EmergencyStopButton.tsx`) — أضف الـ timer فقط.

### 6) Recommendation Card + confidence
- **شرط هندسي إلزامي**: الثقة **قيمة محسوبة** (NR residual، iterations، tolerance 0.01%)
  من السيرفر — **ممنوع** "High confidence" ثابتة في الـ UI (تزوير هندسي).
- جنبها دائماً: `Requires human PE review`.

### 7) Context Cards + Filter Table (CSS-only)
- `AuditLogs.tsx:17` و `AssetManagement.tsx:319` عندهم status chips فعلاً — وحّد النمط.
- `AssetLibrary.tsx` يستخدم select dropdown — حوّله chips (CSS فقط).

### 8) Diff Table (Level 2 — لاحقاً)
- مقارنة دراستين من `results[].summary` — مفيد قبل/بعد إعادة التشكيل.

---

## 3. إصلاحات LIGHT MODE — حصر إلزامي (نفّذه أولاً قبل أي نمط جديد)

**الجذر**: نظام الثيم سليم (`ui/src/context/ThemeContext.tsx:28-29` يبدّل `dark`/`light`
على `documentElement`، و`ui/src/index.css:234-270` يحتوي كامل توكنات `.light`).
المشكلة أن ~15 ملفاً تستخدم ألوان hex داكنة **ثابتة** تتجاوز التوكنات، فتظهر كخلفيات
سوداء ونصوص شبه بيضاء غير مقروءة في Light Mode.

### A. شاشات سوداء كاملة (أسوأ المخالفات)
| الملف | السطر | المشكلة | البديل |
|---|---|---|---|
| `pages/Login.tsx` | 240 | `bg-[#070b14]` | `bg-[var(--bg-primary)]` |
| `pages/Register.tsx` | 147 | `bg-[#070b14]` | `bg-[var(--bg-primary)]` |
| `pages/ResetPassword.tsx` | 55, 119, 144 | `bg-[#070b14]` | `bg-[var(--bg-primary)]` |
| `components/LoginBackground.tsx` | 305 | `bg-[#070b14]` | `bg-[var(--bg-primary)]` (احتفظ بالتدرج) |

### B. Chrome مساحة الشات (لوحات داكنة ثابتة)
| الملف | السطر | المشكلة | البديل |
|---|---|---|---|
| `app/ChatWorkspace.tsx` | 162 | header `bg-[#161B22]` | `bg-[var(--bg-elevated)]` |
| `app/ChatWorkspace.tsx` | 287 | شريط breadcrumb `bg-[#12161D]` | `bg-[var(--bg-input)]` |
| `app/ChatWorkspace.tsx` | 348, 354 | لوحة جانبية `bg-[#14181F]` | `bg-[var(--bg-card)]` |
| `app/ChatWorkspace.tsx` | 365, 391 | درج موبايل `bg-[#161B22]` | `bg-[var(--bg-elevated)]` |
| `app/ChatWorkspace.tsx` | 249, 259 | أزرار أيقونات `bg-[#1E2530]` | `bg-[var(--bg-hover)]` |
| `components/chat/MessageInput.tsx` | 398 | اقتراحات الأوامر `bg-[#161B22]` | `bg-[var(--bg-elevated)]` |
| `components/chat/MessageInput.tsx` | 403, 414 | kbd/chips `bg-[#20262E]` | `bg-[var(--bg-hover)]` |
| `components/chat/MessageList.tsx` | 374 | صفوف findings `bg-[#151A22]` | `bg-[var(--bg-card)]` |
| `components/chat/MessageList.tsx` | 387 | badges `bg-[#202734]` | `bg-[var(--bg-hover)]` |
| `components/chat/QuickActionsBar.tsx` | 148 | الشريط `bg-[#12161D]/90` | `bg-[var(--bg-input)]` |
| `components/chat/QuickActionsBar.tsx` | 189, 193 | chips `bg-[#1A202A]` / `bg-[#14181F]` | `bg-[var(--bg-hover)]` / `bg-[var(--bg-card)]` |

### C. مودالات وأدراج الشات
| الملف | السطر | المشكلة | البديل |
|---|---|---|---|
| `components/chat/AISettingsModal.tsx` | 43, 45, 73, 105, 111 | `bg-[#14181F]` / `bg-[#1A1F26]` / `bg-[#161B22]` / `bg-[#0F1318]` | `var(--bg-card)` / `var(--bg-elevated)` / `var(--bg-input)` |
| `components/chat/ParametersDrawer.tsx` | 120, 130, 264, 272 | `bg-[#1A1F26]` / `bg-[#14181F]` / `bg-[#20262E]` | نفس الخريطة |
| `components/chat/ProjectSelector.tsx` | 138, 144, 152, 214, 244 | `bg-[#1A1F26]` / `bg-[#14181F]` / `bg-[#20262E]` | نفس الخريطة |
| `components/chat/IntegrationStatusPills.tsx` | 229, 230, 260, 286, 304 | `bg-[#1A1F26]` / `bg-[#14181F]` / `bg-[#20262E]` | نفس الخريطة |
| `components/chat/AutoViewPanel.tsx` | 35, 42, 186, 223 + بطاقات داخلية | `bg-[#12161D]` / `bg-[#181E26]` / `bg-[#0F1318]` | `var(--bg-input)` / `var(--bg-elevated)` / `var(--bg-input)` |
| `components/cards/ApprovalCard.tsx` | 151 | `bg-[#181E26]` | `bg-[var(--bg-elevated)]` |

### D. ResultViewer (أكبر ملف مخالف)
`components/viewer/ResultViewer.tsx` — الأسطر: 775, 804, 808, 848, 858, 992, 994, 1005,
1192, 1232, 1259, 1271, 1283, 1295 — كلها `bg-[#181E26]` / `bg-[#14181F]` /
`bg-[#20262E]` / `bg-[#101318]` / `bg-[#1A1F26]` + borders `#2E3846` / `#26303D` /
`#334155` / `#2A3441` → نفس خريطة التوكنات، وحقول الإدخال (1259-1295) →
`bg-[var(--bg-input)] border-[var(--border-primary)]`.

### E. كتل الأكواد في AIAssistant
`pages/AIAssistant.tsx` — الأسطر 99, 100, 581: `bg-[#1e1e1e]` / `bg-[#2d2d2d]`.
**قرار مطلوب**: إما الإبقاء عليها داكنة (معتاد في VS Code) **أو** تكييفها
(`bg-[var(--bg-tertiary)]` + `border-[var(--border-primary)]`). اختر **التكييف** لأن
المستخدم اشتكى صراحة من "مكان الكتابة أسود".

### F. نصوص ثابتة غير متكيفة (فشل تباين في Light Mode)
- `text-slate-400` على أبيض = تباين ~2.9:1 (**يفشل 4.5:1**) → `text-[var(--text-tertiary)]`
- `text-slate-100/200/300` = شبه أبيض على أبيض (غير مرئي) → `text-[var(--text-primary)]`
- `hover:text-white` = غير مرئي على خلفية فاتحة → `hover:text-[var(--text-primary)]`
- موجودة في: AutoViewPanel, AISettingsModal, QuickActionsBar, ProjectSelector,
  ResultViewer, MessageList, ChatWorkspace.

### G. حدود ثابتة
`border-[#334155]` / `border-[#2A3441]` / `border-[#26303D]` / `border-[#2E3846]` /
`border-[#2A3544]` → `border-[var(--border-primary)]` (أو `border-[var(--border-secondary)]`
للحدود الأقوى).

### H. خريطة الاستبدال الموحدة
```
#070b14 / #0F1318 / #101318 / #12161D  →  var(--bg-input)
#14181F / #151A22                       →  var(--bg-card)
#161B22 / #181E26 / #1A1F26             →  var(--bg-elevated)
#1E2530 / #1A202A / #20262E / #202734   →  var(--bg-hover)
#2A3441 / #2A3544 / #26303D / #2E3846 / #334155  →  var(--border-primary)
text-slate-100/200/300                  →  var(--text-primary)
text-slate-400                          →  var(--text-tertiary)
text-slate-500                          →  var(--text-muted)
hover:text-white                        →  hover:text-[var(--text-primary)]
```

### I. **لا تلمس** (ليست مشكلة)
- `bg-black/50` … `bg-black/80` (scrims/overlays) — قياسية وتعمل في الاتجاهين
- `bg-black/20` في Settings/ProvidersTab — translucent مقبولة
- QR `fgColor="#000000"` (`MFASetup.tsx:82`, `Mfa.tsx:421`) — مطلوب لقراءة QR
- مكونات تستخدم `dark:` variants (`TokenBudgetIndicator.tsx`, أجزاء من `AIAssistant.tsx`) — متكيفة أصلاً

---

## 4. قواعد الهوية البصرية

- **اللون الأساسي brand هو سماوي/كحلي صناعي** (`--accent-primary: #00d4ff` داكن /
  `#0284c7` فاتح — `index.css:208,249`) — **ليس كهرمانياً**. الكهرمان (`--current` /
  amber) محجوز لـ "needs review / pending" فقط.
- أحمر = إيقاف/خطر فقط. أخضر = verified/success فقط. كهرمان = needs review فقط.
- تباين 4.5:1 كحد أدنى، مقاس لمس 44×44px، خط أساسي 16px و line-height 1.5.
- أرقام هندسية بـ `tabular-nums` + `font-mono` (مطبق في `index.css:690`).
- موشن هادي 150-200ms + احترام `prefers-reduced-motion` (مطبق `index.css:1469`).
- أيقونات **lucide-react فقط** — ممنوع الإيموجي كأيقونات.
- RTL: اختبر كل نمط جديد بالعربية (i18next موجود — `MessageList.tsx:20`).

## 5. قيود هندسية وأمنية

- **ممنوع مكتبات جديدة** — كل الأنماط CSS + حقول store موجودة.
- Thinking traces: **sanitize** — لا paths ولا secrets (المشروع يتجنب
  `dangerouslySetInnerHTML` — حافظ).
- Approval Card لا ينفذ شيئاً بنفسه — يعكس قرار الـ gateway فقط.
- Confidence/ثقة = قيمة محسوبة من السيرفر، لا ثابت UI.
- Follow-ups/sources = بيانات حقيقية من السيرفر، لا اختلاق عميل.
- الحركات: ممنوع GSAP و Agent Screen recording (ثقيلة + مخاطر أمنية/أداء).
  framer-motion موجود (`AIAssistant.tsx:3`) — استخدمه باعتدال فقط.

## 6. خارج النطاق

- ألوان الباستيل، الرسوم التوضيحية المرحة، Fine-tune Card (ضبط ألوان/radius)،
  Agent Screen recording، model picker، dictation، إيموجي كأيقونات.

## 7. التعريف بالإنجاز (Definition of Done)

1. كل ملف في §3 يمر على الخريطة في §3-H — **صفر hex داكن ثابت** في المكونات المتأثرة.
2. التحقق اليدوي: فتح كل شاشة في **الاتجاهين** (dark + light) — لا خلفية سوداء ولا نص غير مقروء.
3. اختبار تباين 4.5:1 على النصوص الثانوية في Light Mode.
4. اختبار RTL بالعربية لكل نمط جديد.
5. `npm run lint` + `npm run typecheck` + اختبارات الواجهة (`ui/tests/`) ناجحة.
6. `prefers-reduced-motion` معطّل الحركات الجديدة.
7. لكل نمط جديد من §2: تبرير سطر واحد + عدم إضافة dependency جديدة في `package.json`.

---

**ترتيب التنفيذ**: §3 (Light Mode) أولاً → ثم §2 بالترتيب 1→7 → §2.8 (Diff Table) لاحقاً.
