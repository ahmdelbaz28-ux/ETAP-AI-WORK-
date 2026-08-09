import type { HelpTopic } from "./types";

export const helpTopics: HelpTopic[] = [
  // ─── Getting Started ──────────────────────────────────────────────
  {
    id: "dashboard.overview",
    category: "getting-started",
    title: { en: "Dashboard Overview", ar: "نظرة عامة على لوحة التحكم" },
    description: {
      en: "Navigate the main dashboard and understand system status",
      ar: "التنقل في لوحة التحكم الرئيسية وفهم حالة النظام",
    },
    content: {
      en: `The Dashboard is your central hub for monitoring the AhmedETAP Platform.

**Key Areas:**
- **Status Cards** — Real-time system health, active agents, and study metrics
- **Charts** — API activity, study distribution, and resource utilization
- **Quick Actions** — Shortcut buttons for common engineering tasks
- **Recent Studies** — Your latest study results and their status

**How to Use:**
1. On page load, the dashboard fetches health data from the backend
2. The green/red indicator in the top-right shows backend connection status
3. Click any chart to drill down into detailed metrics
4. Use the quick-action buttons to jump to a specific study type

**Tips:**
- The sidebar provides access to all modules
- Press Ctrl+K to open the command palette
- Press F1 anywhere for contextual help
- Click the Sparkles (✨) icon in the top bar to activate Magic Help`,
      ar: `لوحة التحكم هي مركزك المركزي لمراقبة منصة AhmedETAP.

**المناطق الرئيسية:**
- **بطاقات الحالة** — صحة النظام في الوقت الفعلي والوكلاء النشطين ومقاييس الدراسة
- **الرسوم البيانية** — نشاط API وتوزيع الدراسات واستخدام الموارد
- **الإجراءات السريعة** — أزرار اختصار للمهام الهندسية الشائعة
- **الدراسات الأخيرة** — أحدث نتائج دراساتك وحالتها

**كيفية الاستخدام:**
1. عند تحميل الصفحة، تجلب لوحة التحكم بيانات الحالة من الخادم
2. المؤشر الأخضر/الأحمر في الأعلى يُظهر حالة اتصال الخادم
3. انقر على أي رسم بياني للتفاصيل
4. استخدم أزرار الإجراءات السريعة للانتقال لنوع دراسة محدد

**نصائح:**
- يوفر الشريط الجانبي الوصول إلى جميع الوحدات
- اضغط Ctrl+K لفتح لوحة الأوامر
- اضغط F1 في أي مكان للمساعدة السياقية
- اضغط على أيقونة البريق (✨) في الشريط العلوي لتفعيل المساعدة السحرية`,
    },
    tags: ["dashboard", "overview", "home", "لوحة تحكم", "نظرة عامة"],
    navigateTo: "/dashboard",
    relatedTopics: ["projects.manage", "studies.load-flow"],
  },
  {
    id: "keyboard-shortcuts",
    category: "getting-started",
    title: { en: "Keyboard Shortcuts", ar: "اختصارات لوحة المفاتيح" },
    description: {
      en: "Essential keyboard shortcuts for faster workflow",
      ar: "اختصارات لوحة المفاتيح الأساسية لسرعة العمل",
    },
    content: {
      en: `**Global Shortcuts:**
- \`F1\` — Open Smart Help (context-aware)
- \`Ctrl+K\` — Command Palette (search & navigate)
- \`Ctrl+H\` — Toggle Help Panel
- \`Esc\` — Close any open modal/drawer

**Magic Help Inspector:**
- Click the ✨ Sparkles icon in the top bar to start
- The cursor changes to a help cursor
- Click any element on screen to get its documentation
- Press \`Esc\` to exit inspector mode

**Navigation:**
- Use the sidebar (left side) to switch between modules
- Click the AhmedETAP logo to return to the dashboard
- Use breadcrumbs (top of content area) to navigate back

**Settings:**
- \`Ctrl+S\` — Save current settings (when on Settings page)`,
      ar: `**الاختصارات العامة:**
- \`F1\` — فتح المساعدة الذكية (حسب السياق)
- \`Ctrl+K\` — لوحة الأوامر (بحث وتنقل)
- \`Ctrl+H\` — إظهار/إخفاء لوحة المساعدة
- \`Esc\` — إغلاق أي نافذة مفتوحة

**فاحص المساعدة السحرية:**
- اضغط على أيقونة ✨ البريق في الشريط العلوي للبدء
- يتغير المؤشر إلى مؤشر مساعدة
- انقر على أي عنصر في الشاشة للحصول على شرحه
- اضغط \`Esc\` للخروج من وضع الفحص

**التنقل:**
- استخدم الشريط الجانبي (يسار) للتبديل بين الوحدات
- انقر على شعار AhmedETAP للعودة للوحة التحكم
- استخدم فتات الخبز (أعلى المحتوى) للرجوع للخلف

**الإعدادات:**
- \`Ctrl+S\` — حفظ الإعدادات الحالية (عند وجودك في صفحة الإعدادات)`,
    },
    tags: ["keyboard", "shortcuts", "hotkeys", "keys", "لوحة مفاتيح", "اختصارات"],
    relatedTopics: ["dashboard.overview", "magic-help.inspector"],
  },
  {
    id: "magic-help.inspector",
    category: "getting-started",
    title: { en: "Magic Help Inspector", ar: "فاحص المساعدة السحرية" },
    description: {
      en: "Click any element to instantly see its documentation",
      ar: "انقر على أي عنصر لرؤية شرحه فوراً",
    },
    content: {
      en: `**What is Magic Help?**
Magic Help is an interactive inspector that lets you click on ANY element in the application and instantly see its documentation.

**How to Activate:**
1. Click the ✨ Sparkles icon in the top-right of the navbar
2. OR open the Help drawer (F1) and click "Magic Inspect"
3. The cursor changes to a help cursor
4. A floating banner appears: "Help Inspector Active"

**How to Use:**
1. Move your mouse over the page — elements highlight with a dashed cyan border
2. Click any element (button, card, icon, input) to open its help topic
3. The Smart Help drawer opens with detailed documentation
4. Press \`Esc\` or click anywhere to exit inspector mode

**What Gets Highlighted:**
- Buttons and links
- Cards and panels
- Form inputs and selects
- Headings (h1-h4)
- List items
- Any element with \`data-help-context\` attribute

**Tips:**
- If an element doesn't have specific docs, the inspector falls back to the page-level help
- The inspector works on every page in the application
- Use it to learn what each button does before clicking it`,
      ar: `**ما هي المساعدة السحرية؟**
المساعدة السحرية هي فاحص تفاعلي يتيح لك النقر على أي عنصر في التطبيق ورؤية شرحه فوراً.

**كيفية التفعيل:**
1. انقر على أيقونة ✨ البريق في أعلى يمين الشريط العلوي
2. أو افتح درج المساعدة (F1) وانقر "الفحص الذكي"
3. يتغير المؤشر إلى مؤشر مساعدة
4. يظهر شريط عائم: "وضع فحص المساعدة نشط"

**كيفية الاستخدام:**
1. حرّك الماوس فوق الصفحة — تتميز العناصر بحدود متقطعة سماوية
2. انقر على أي عنصر (زر، بطاقة، أيقونة، حقل) لفتح موضوع مساعدته
3. يفتح درج المساعدة الذكية مع الشرح التفصيلي
4. اضغط \`Esc\` أو انقر في أي مكان للخروج

**ما الذي يتم تمييزه:**
- الأزرار والروابط
- البطاقات واللوحات
- حقول الإدخال والقوائم
- العناوين (h1-h4)
- عناصر القائمة
- أي عنصر يحمل السمة \`data-help-context\`

**نصائح:**
- إذا لم يكن للعنصر شرح محدد، يلجأ الفاحص لمساعدة الصفحة العامة
- الفاحص يعمل في كل صفحات التطبيق
- استخدمه لتعلم وظيفة كل زر قبل النقر عليه`,
    },
    tags: ["magic", "help", "inspector", "inspect", "سحري", "مساعدة", "فحص"],
    relatedTopics: ["keyboard-shortcuts", "dashboard.overview"],
  },

  // ─── Projects ─────────────────────────────────────────────────────
  {
    id: "projects.create",
    category: "projects",
    title: { en: "Creating a Project", ar: "إنشاء مشروع" },
    description: {
      en: "How to create and configure a new engineering project",
      ar: "كيفية إنشاء وتكوين مشروع هندسي جديد",
    },
    content: {
      en: `**Steps to Create a Project:**
1. Navigate to **Projects** from the sidebar
2. Click the **"New Project"** button (top-right)
3. Fill in the form:
   - **Name** (required) — descriptive name, e.g. "IEEE 14-Bus Load Flow Study"
   - **Description** (optional) — what the project is for
   - **System Config** (optional) — JSON definition of buses, lines, generators
4. Click **Create**

**Project Status:**
- \`active\` — currently being worked on
- \`archived\` — completed and stored
- \`deleted\` — soft-deleted (recoverable)

**Tips:**
- Use descriptive names including the standard (IEEE/IEC) and bus count
- Add tags for better organization
- Projects are auto-saved as you work
- Each project can have multiple studies`,
      ar: `**خطوات إنشاء مشروع:**
1. انتقل إلى **المشاريع** من الشريط الجانبي
2. انقر على زر **"مشروع جديد"** (أعلى اليمين)
3. املأ النموذج:
   - **الاسم** (مطلوب) — اسم وصفي، مثل "دراسة تدفق حمل IEEE 14 باص"
   - **الوصف** (اختياري) — الغرض من المشروع
   - **تكوين النظام** (اختياري) — تعريف JSON للباصات والخطوط والمولدات
4. انقر على **إنشاء**

**حالة المشروع:**
- \`نشط\` — قيد العمل حالياً
- \`مؤرشف\` — مكتمل ومخزن
- \`محذوف\` — حذف ناعم (قابل للاسترجاع)

**نصائح:**
- استخدم أسماء وصفية تشمل المعيار (IEEE/IEC) وعدد الباصات
- أضف وسوماً لتنظيم أفضل
- تُحفظ المشاريع تلقائياً أثناء العمل
- كل مشروع يمكن أن يحتوي على دراسات متعددة`,
    },
    tags: ["project", "create", "new", "مشروع", "إنشاء", "جديد"],
    navigateTo: "/projects",
    relatedTopics: ["projects.manage", "studies.load-flow"],
  },
  {
    id: "projects.manage",
    category: "projects",
    title: { en: "Managing Projects", ar: "إدارة المشاريع" },
    description: {
      en: "Open, edit, archive, and delete projects",
      ar: "فتح وتعديل وأرشفة وحذف المشاريع",
    },
    content: {
      en: `**Project Management Actions:**

**Open a Project:**
- Click anywhere on a project card to open it
- The project dashboard shows its studies, settings, and history

**Edit a Project:**
- Click the pencil (✏️) icon on a project card
- Modify name, description, or system configuration
- Click **Save** to persist changes

**Archive a Project:**
- Click the archive (📦) icon
- Archived projects are hidden from the default list
- Use the status filter to view archived projects
- Archived projects can be restored

**Delete a Project:**
- Click the trash (🗑️) icon
- Confirm the deletion in the modal
- This is a soft-delete — the project is marked as \`deleted\` but not removed from the database
- Only admins can permanently delete projects

**Filter & Search:**
- Use the search box to find projects by name
- Use the status filter (active/archived/deleted) to narrow the list
- Sort by created date, name, or last activity`,
      ar: `**إجراءات إدارة المشاريع:**

**فتح مشروع:**
- انقر في أي مكان على بطاقة المشروع لفتحه
- تعرض لوحة تحكم المشروع دراساته وإعداداته وسجله

**تعديل مشروع:**
- انقر على أيقونة القلم (✏️) على بطاقة المشروع
- عدّل الاسم أو الوصف أو تكوين النظام
- انقر على **حفظ** للاحتفاظ بالتغييرات

**أرشفة مشروع:**
- انقر على أيقونة الأرشفة (📦)
- المشاريع المؤرشفة مخفية من القائمة الافتراضية
- استخدم فلتر الحالة لعرض المشاريع المؤرشفة
- يمكن استعادة المشاريع المؤرشفة

**حذف مشروع:**
- انقر على أيقونة سلة المهملات (🗑️)
- أكد الحذف في النافذة المنبثقة
- هذا حذف ناعم — يُعلَّم المشروع كـ \`محذوف\` لكن لا يُزال من قاعدة البيانات
- فقط المسؤولون يمكنهم حذف المشاريع نهائياً

**الفلترة والبحث:**
- استخدم صندوق البحث للعثور على مشاريع بالاسم
- استخدم فلتر الحالة (نشط/مؤرشف/محذوف) لتضييق القائمة
- رتّب حسب تاريخ الإنشاء أو الاسم أو آخر نشاط`,
    },
    tags: [
      "project",
      "manage",
      "open",
      "edit",
      "archive",
      "delete",
      "مشروع",
      "إدارة",
      "فتح",
      "تعديل",
    ],
    navigateTo: "/projects",
    relatedTopics: ["projects.create", "studies.load-flow"],
  },

  // ─── Studies (per type) ───────────────────────────────────────────
  {
    id: "studies.overview",
    category: "engineering",
    title: { en: "Studies Overview", ar: "نظرة عامة على الدراسات" },
    description: {
      en: "All available engineering study types and how to run them",
      ar: "جميع أنواع الدراسات الهندسية المتاحة وكيفية تشغيلها",
    },
    content: {
      en: `**Available Study Types:**

1. **Load Flow** — Newton-Raphson power flow analysis (IEEE 3002.7)
2. **Short Circuit** — IEC 60909 fault current calculation
3. **Arc Flash** — IEEE 1584-2018 incident energy analysis
4. **Harmonic Analysis** — IEEE 519-2022 distortion study
5. **Motor Starting** — IEEE 399 transient analysis
6. **Protection Coordination** — IEC 60255 relay curves
7. **Cable Sizing** — IEC 60364 current-carrying capacity
8. **Earth Grid** — IEEE 80 ground grid design
9. **Stability** — Transient stability analysis
10. **Optimal Power Flow (OPF)** — Cost-optimized dispatch

**How to Run a Study:**
1. Navigate to **Studies** from the sidebar
2. Click the study-type card you want to run
3. Configure the system (buses, lines, generators, loads)
4. Set study parameters (tolerance, max iterations, etc.)
5. Click **Run Study**
6. View results in the results panel
7. Optionally export to PDF/CSV

**Tips:**
- Each study type has its own input schema
- Studies can be run with the native engine or via ETAP (if connected)
- Results are cached for repeated runs with the same inputs
- Use the projects page to organize studies by project`,
      ar: `**أنواع الدراسات المتاحة:**

1. **تدفق الحمل** — تحليل تدفق القدرة بطريقة نيوتن-رافسون (IEEE 3002.7)
2. **الدائرة القصيرة** — حساب تيار العطل IEC 60909
3. **شرارة القوس** — تحليل طاقة الحادث IEEE 1584-2018
4. **تحليل التوافقيات** — دراسة التشوه IEEE 519-2022
5. **بدء المحرك** — تحليل عابر IEEE 399
6. **تنسيق الحماية** — منحنيات المُرحّل IEC 60255
7. **تحديد مقاس الكابلات** — القدرة على حمل التيار IEC 60364
8. **شبكة التأريض** — تصميم شبكة التأريض IEEE 80
9. **الاستقرار** — تحليل الاستقرار العابر
10. **تدفق القدرة الأمثل (OPF)** — إرسال أمثل للتكلفة

**كيفية تشغيل دراسة:**
1. انتقل إلى **الدراسات** من الشريط الجانبي
2. انقر على بطاقة نوع الدراسة التي تريد تشغيلها
3. قم بتكوين النظام (باصات، خطوط، مولدات، أحمال)
4. اضبط معلمات الدراسة (التسامح، أقصى تكرارات، إلخ)
5. انقر على **تشغيل الدراسة**
6. اعرض النتائج في لوحة النتائج
7. اخترياً صدّرها إلى PDF/CSV

**نصائح:**
- كل نوع دراسة له مخطط إدخال خاص به
- يمكن تشغيل الدراسات بالمحرك الأصلي أو عبر ETAP (إذا كان متصلاً)
- تُحفظ النتائج مؤقتاً للتشغيل المتكرر بنفس المدخلات
- استخدم صفحة المشاريع لتنظيم الدراسات حسب المشروع`,
    },
    tags: ["studies", "overview", "all", "دراسات", "نظرة عامة"],
    navigateTo: "/studies",
    relatedTopics: ["studies.load-flow", "studies.short-circuit", "studies.arc-flash"],
  },
  {
    id: "studies.load-flow",
    category: "engineering",
    title: { en: "Load Flow Study", ar: "دراسة تدفق الحمل" },
    description: {
      en: "Newton-Raphson power flow analysis per IEEE 3002.7",
      ar: "تحليل تدفق القدرة بطريقة نيوتن-رافسون حسب IEEE 3002.7",
    },
    content: {
      en: `**What it does:**
Calculates bus voltages, branch power flows, and system losses under steady-state conditions.

**Required Inputs:**
- **Buses** — at least one slack (swing) bus, plus PV and PQ buses
- **Lines** — with R1, X1, B1 parameters in per-unit or ohms
- **Transformers** — with R1, X1, tap ratio, phase shift
- **Generators** — at PV buses, with P and V setpoints
- **Loads** — at PQ buses, with P and Q values

**Parameters:**
- \`tolerance\` — convergence tolerance (default 1e-6)
- \`max_iterations\` — max Newton-Raphson iterations (default 50)
- \`method\` — \`newton_raphson\`, \`fast_decoupled\`, or \`dc\`

**Results:**
- Bus voltage magnitudes and angles
- Real and reactive power flows on each branch
- Total system losses
- Convergence report

**Common Issues:**
- "Singular Jacobian" — usually means a bus is disconnected; check line connectivity
- "Did not converge" — try a different initial guess or relax tolerance
- Negative losses — check per-unit base consistency`,
      ar: `**ما يفعله:**
يحسب جهود الباصات وتدفقات القدرة في الفروع وخسائر النظام في ظل الحالة المستقرة.

**المدخلات المطلوبة:**
- **الباصات** — باص slack واحد على الأقل، بالإضافة إلى باصات PV و PQ
- **الخطوط** — بمعلمات R1, X1, B1 بنظام per-unit أو أوم
- **المحولات** — بـ R1, X1، نسبة التحويل، إزاحة الطور
- **المولدات** — في باصات PV، مع قيم P و V المحددة
- **الأحمال** — في باصات PQ، مع قيم P و Q

**المعلمات:**
- \`tolerance\` — تسامح التقارب (افتراضي 1e-6)
- \`max_iterations\` — أقصى تكرارات نيوتن-رافسون (افتراضي 50)
- \`method\` — \`newton_raphson\` أو \`fast_decoupled\` أو \`dc\`

**النتائج:**
- جهود الباصات (القيمة والزاوية)
- تدفقات القدرة الفعلية والتفاعلية في كل فرع
- إجمالي خسائر النظام
- تقرير التقارب

**مشاكل شائعة:**
- "Jacobian مفرد" — عادةً يعني أن باص غير متصل؛ تحقق من اتصال الخطوط
- "لم يتقارب" — جرّب تخمين مبدئي مختلف أو تساهل في التسامح
- خسائر سلبية — تحقق من اتساق قاعدة per-unit`,
    },
    tags: ["load", "flow", "newton", "raphson", "power", "تدفق", "حمل", "قدرة"],
    navigateTo: "/studies/load_flow",
    relatedTopics: ["studies.overview", "studies.short-circuit"],
  },
  {
    id: "studies.short-circuit",
    category: "engineering",
    title: { en: "Short Circuit Study", ar: "دراسة الدائرة القصيرة" },
    description: { en: "IEC 60909 fault current calculation", ar: "حساب تيار العطل حسب IEC 60909" },
    content: {
      en: `**What it does:**
Calculates three-phase, line-to-ground, line-to-line, and double-line-to-ground fault currents at every bus.

**Required Inputs:**
- Same as Load Flow, PLUS:
- Generator subtransient reactance (\`X''d\`)
- Negative-sequence and zero-sequence reactances (X2, X0)
- Transformer connections (Yg, Y, D) for ground fault analysis
- Neutral grounding impedance

**IEC 60909 Parameters:**
- \`c_factor\` — voltage factor (1.1 for max, 1.0 for min)
- \`decayed_dc\` — true/false (compute asymmetrical peak)
- \`fault_type\` — \`3p\`, \`LG\`, \`LL\`, \`LLG\`

**Results:**
- Initial symmetrical short-circuit current (I''k)
- Peak short-circuit current (ip)
- DC component (idc)
- Breaking current (Ib) at contact opening time

**Standards:**
- IEC 60909-0:2016 — Calculation of currents
- IEC 60909-1:2002 — Factors for calculations`,
      ar: `**ما يفعله:**
يحسب تيارات العطل ثلاثية الطور، خط-أرض، خط-خط، وخط-خط-أرض في كل باص.

**المدخلات المطلوبة:**
- نفس تدفق الحمل، بالإضافة إلى:
- مفاعلة العبور الجزئية للمولد (\`X''d\`)
- مفاعلات التسلسل السالبة والصفرية (X2، X0)
- توصيلات المحولات (Yg، Y، D) لتحليل عطل الأرض
- مقاومة تأريض النقطة المحايدة

**معلمات IEC 60909:**
- \`c_factor\` — معامل الجهد (1.1 للأقصى، 1.0 للأدنى)
- \`decayed_dc\` — true/false (احسب القمة غير المتماثلة)
- \`fault_type\` — \`3p\`، \`LG\`، \`LL\`، \`LLG\`

**النتائج:**
- تيار القصر التماثلي الابتدائي (I''k)
- تيار ذروة القصر (ip)
- مركبة التيار المستمر (idc)
- تيار القطع (Ib) عند وقت فتح التلامس

**المعايير:**
- IEC 60909-0:2016 — حساب التيارات
- IEC 60909-1:2002 — معاملات الحسابات`,
    },
    tags: ["short", "circuit", "fault", "iec", "60909", "قصر", "دائرة", "عطل"],
    navigateTo: "/studies/short_circuit",
    relatedTopics: ["studies.overview", "studies.arc-flash", "studies.protection"],
  },
  {
    id: "studies.arc-flash",
    category: "engineering",
    title: { en: "Arc Flash Study", ar: "دراسة شرارة القوس" },
    description: {
      en: "IEEE 1584-2018 incident energy analysis",
      ar: "تحليل طاقة الحادث حسب IEEE 1584-2018",
    },
    content: {
      en: `**What it does:**
Calculates incident energy (cal/cm²) and arc-flash boundary at each bus, used to specify PPE (Personal Protective Equipment) levels.

**Required Inputs:**
- Bolted fault current (from Short Circuit study)
- Arc duration (clearing time of protective device)
- Working distance (typical: 18" for LV, 24" for MV)
- System voltage
- Equipment type (panel, switchgear, open air)
- Electrode configuration (VCB, VCBB, HCB, etc.)

**IEEE 1584-2018 Parameters:**
- \`electrode_gap\` — typical gaps by voltage class
- \`arc_current_variation_factor\` — 1.0 default, 0.85 for reduced current
- \`enclosure_size\` — for medium-voltage equipment

**Results:**
- Incident energy (cal/cm²) at working distance
- Arc-flash boundary (inches)
- PPE category (0, 1, 2, 3, 4, or "Dangerous")
- Reduced incident energy at lower current (if applicable)

**Safety Notes:**
- Always round UP the PPE category
- Use the higher of: (a) bolted fault current, (b) reduced current calculation
- Document all assumptions for audit compliance`,
      ar: `**ما يفعله:**
يحسب طاقة الحادث (cal/cm²) وحدود شرارة القوس في كل باص، تُستخدم لتحديد مستويات معدات الحماية الشخصية (PPE).

**المدخلات المطلوبة:**
- تيار العطل الملحوم (من دراسة الدائرة القصيرة)
- مدة القوس (وقت تطهير جهاز الحماية)
- مسافة العمل (نموذجية: 18" للجهد المنخفض، 24" للمتوسط)
- جهد النظام
- نوع المعدة (لوحة، switchgear، هواء مفتوح)
- تكوين القطب (VCB، VCBB، HCB، إلخ)

**معلمات IEEE 1584-2018:**
- \`electrode_gap\` — فجوات نموذجية حسب فئة الجهد
- \`arc_current_variation_factor\` — 1.0 افتراضي، 0.85 للتيار المخفض
- \`enclosure_size\` — لمعدات الجهد المتوسط

**النتائج:**
- طاقة الحادث (cal/cm²) عند مسافة العمل
- حدود شرارة القوس (بوصة)
- فئة PPE (0، 1، 2، 3، 4، أو "خطير")
- طاقة الحادث المخفضة عند تيار أقل (إن وجدت)

**ملاحظات السلامة:**
- دائماً قرّب للأعلى فئة PPE
- استخدم الأعلى من: (أ) تيار العطل الملحوم، (ب) حساب التيار المخفض
- وثّق جميع الافتراضات للامتثال للتدقيق`,
    },
    tags: ["arc", "flash", "ieee", "1584", "incident", "energy", "قوس", "شرارة", "حادث"],
    navigateTo: "/studies/arc_flash",
    relatedTopics: ["studies.short-circuit", "studies.protection", "studies.overview"],
  },
  {
    id: "studies.protection",
    category: "engineering",
    title: { en: "Protection Coordination", ar: "تنسيق الحماية" },
    description: { en: "IEC 60255 relay curve coordination", ar: "تنسيق منحنيات المُرحّل IEC 60255" },
    content: {
      en: `**What it does:**
Analyzes time-current curves of protective relays (overcurrent, earth fault) to ensure proper coordination — upstream devices should clear faults slower than downstream devices.

**Required Inputs:**
- Relay types (IEC 60255 standard curves: Standard Inverse, Very Inverse, Extremely Inverse)
- Pick-up current (Ip) for each relay
- Time Multiplier Setting (TMS)
- Fault currents at each relay location (from Short Circuit study)

**IEC 60255 Curve Equations:**
- Standard Inverse: t = TMS × (0.14 / ((I/Ip)^0.02 - 1))
- Very Inverse: t = TMS × (13.5 / ((I/Ip) - 1))
- Extremely Inverse: t = TMS × (80 / ((I/Ip)^2 - 1))

**Results:**
- Operating time for each relay at each fault current
- Coordination intervals (CTI — should be ≥ 0.3 seconds)
- Curve plot showing all relays on a log-log graph
- Miscoordination warnings

**Tips:**
- Standard CTI (Coordination Time Interval) is 0.3-0.4 seconds
- Check fuse-relay coordination as well as relay-relay
- Consider cold-load pickup when setting pick-up current`,
      ar: `**ما يفعله:**
يحلل منحنيات الوقت-التيار للمُرحّلات الحماية (زيادة التيار، عطل الأرض) لضمان التنسيق الصحيح — يجب أن تطهّر الأجهزة المنبع الأعطال أبطأ من الأجهزة المصب.

**المدخلات المطلوبة:**
- أنواع المُرحّلات (منحنيات IEC 60255 القياسية: عكسية قياسية، عكسية جداً، عكسية للغاية)
- تيار الالتقاط (Ip) لكل مُرحّل
- إعداد مضاعف الوقت (TMS)
- تيارات العطل عند كل موقع مُرحّل (من دراسة الدائرة القصيرة)

**معادلات منحنيات IEC 60255:**
- عكسية قياسية: t = TMS × (0.14 / ((I/Ip)^0.02 - 1))
- عكسية جداً: t = TMS × (13.5 / ((I/Ip) - 1))
- عكسية للغاية: t = TMS × (80 / ((I/Ip)^2 - 1))

**النتائج:**
- وقت التشغيل لكل مُرحّل عند كل تيار عطل
- فواصل التنسيق (CTI — يجب أن يكون ≥ 0.3 ثانية)
- رسم بياني للمنحنيات يُظهر جميع المُرحّلات على رسم log-log
- تحذيرات عدم التنسيق

**نصائح:**
- CTI القياسي (فاصل وقت التنسيق) هو 0.3-0.4 ثانية
- تحقق من تنسيق الفيوز-المُرحّل وكذلك المُرحّل-المُرحّل
- اعتبر التقاط الحمل البارد عند ضبط تيار الالتقاط`,
    },
    tags: ["protection", "relay", "coordination", "iec", "60255", "حماية", "مُرحّل", "تنسيق"],
    navigateTo: "/studies/protection_coordination",
    relatedTopics: ["studies.short-circuit", "studies.overview"],
  },
  {
    id: "studies.harmonic",
    category: "engineering",
    title: { en: "Harmonic Analysis", ar: "تحليل التوافقيات" },
    description: { en: "IEEE 519-2022 distortion study", ar: "دراسة التشوه IEEE 519-2022" },
    content: {
      en: `**What it does:**
Calculates harmonic voltage and current distortion at each bus, with frequency sweep and resonance detection.

**Required Inputs:**
- Harmonic current spectrum of nonlinear loads (VFDs, rectifiers, etc.)
- System impedance at fundamental frequency
- Capacitor bank locations and sizes (for resonance check)

**IEEE 519-2022 Limits:**
- Voltage THD: ≤ 5% for general systems (≤ 8% for dedicated)
- Current TDD at PCC: depends on Isc/IL ratio (5% to 20%)

**Results:**
- Voltage THD at each bus
- Current TDD at each branch
- Frequency scan plot showing parallel/series resonances
- Recommended mitigation (filters, reactor sizing)`,
      ar: `**ما يفعله:**
يحسب تشوه الجهد والتيار التوافقي في كل باص، مع مسح التردد وكشف الرنين.

**المدخلات المطلوبة:**
- طيف التيار التوافقي للأحمال غير الخطية (VFDs، المقومات، إلخ)
- مقاومة النظام عند التردد الأساسي
- مواقع وأحجام مكثفات البنك (للتحقق من الرنين)

**حدود IEEE 519-2022:**
- THD الجهد: ≤ 5% للأنظمة العامة (≤ 8% للمخصصة)
- TDD التيار عند PCC: يعتمد على نسبة Isc/IL (5% إلى 20%)

**النتائج:**
- THD الجهد في كل باص
- TDD التيار في كل فرع
- رسم المسح الترددي يُظهر الرنين المتوازي/المتسلسل
- التخفيف الموصى به (فلاتر، تحديد مقاومة المفاعل)`,
    },
    tags: ["harmonic", "thd", "ieee", "519", "distortion", "توافقيات", "تشوه"],
    navigateTo: "/studies/harmonic",
    relatedTopics: ["studies.overview"],
  },
  {
    id: "studies.motor-starting",
    category: "engineering",
    title: { en: "Motor Starting Study", ar: "دراسة بدء المحرك" },
    description: { en: "IEEE 399 transient analysis", ar: "تحليل عابر IEEE 399" },
    content: {
      en: `**What it does:**
Simulates the voltage dip and recovery during motor starting, ensuring the dip stays within acceptable limits (typically ≤ 15% at the motor terminals).

**Required Inputs:**
- Motor parameters (rated kW, voltage, LRT, LRM, inertia)
- Motor starting method (DOL, star-delta, soft starter, VFD)
- Source impedance (transformer + grid)
- Other running loads

**Results:**
- Voltage dip at motor terminals and at all buses
- Motor acceleration time
- Effect on other running motors
- Recommendation for starting method if dip is excessive`,
      ar: `**ما يفعله:**
يحاكي انخفاض الجهد واستعادته أثناء بدء المحرك، مع التأكد من بقاء الانخفاض ضمن الحدود المقبولة (عادة ≤ 15% عند أطراف المحرك).

**المدخلات المطلوبة:**
- معلمات المحرك (kW المقدّر، الجهد، LRT، LRM، القصور الذاتي)
- طريقة بدء المحرك (مباشرة DOL، نجمة-دلتا، مشغل ناعم، VFD)
- مقاومة المصدر (محول + شبكة)
- الأحمال الأخرى المشغّلة

**النتائج:**
- انخفاض الجهد عند أطراف المحرك وفي جميع الباصات
- وقت تسارع المحرك
- التأثير على المحركات الأخرى المشغّلة
- التوصية لطريقة البدء إذا كان الانخفاض مفرطاً`,
    },
    tags: ["motor", "starting", "ieee", "399", "voltage", "dip", "محرك", "بدء"],
    navigateTo: "/studies/motor_starting",
    relatedTopics: ["studies.overview", "studies.load-flow"],
  },
  {
    id: "studies.cable-sizing",
    category: "engineering",
    title: { en: "Cable Sizing", ar: "تحديد مقاس الكابلات" },
    description: {
      en: "IEC 60364 current-carrying capacity",
      ar: "القدرة على حمل التيار IEC 60364",
    },
    content: {
      en: `**What it does:**
Determines the minimum cable cross-section based on load current, installation method, ambient temperature, and voltage drop constraints.

**Required Inputs:**
- Load current (A)
- Cable length (m)
- Installation method (in air, in conduit, direct buried, on tray)
- Ambient temperature (°C)
- Number of loaded conductors
- Insulation type (PVC, XLPE)
- Voltage drop limit (%)

**IEC 60364 Tables:**
- Table B.52.4 — PVC insulation, single-core
- Table B.52.5 — PVC insulation, multi-core
- Table B.52.8 — XLPE insulation, single-core
- Table B.52.9 — XLPE insulation, multi-core

**Results:**
- Minimum cable cross-section (mm²)
- Actual current-carrying capacity (after derating)
- Voltage drop (% and V)
- Recommended cable size (next standard size up)`,
      ar: `**ما يفعله:**
يحدد الحد الأدنى لمقطع الكابل بناءً على تيار الحمل وطريقة التركيب ودرجة حرارة المحيط وقيود انخفاض الجهد.

**المدخلات المطلوبة:**
- تيار الحمل (A)
- طول الكابل (m)
- طريقة التركيب (في الهواء، في الأنبوب، مدفون مباشرة، على صينية)
- درجة حرارة المحيط (°C)
- عدد الموصلات المحمّلة
- نوع العزل (PVC، XLPE)
- حد انخفاض الجهد (%)

**جداول IEC 60364:**
- الجدول B.52.4 — عزل PVC، أحادي القلب
- الجدول B.52.5 — عزل PVC، متعدد القلوب
- الجدول B.52.8 — عزل XLPE، أحادي القلب
- الجدول B.52.9 — عزل XLPE، متعدد القلوب

**النتائج:**
- الحد الأدنى لمقطع الكابل (mm²)
- القدرة الفعلية على حمل التيار (بعد التخفيض)
- انخفاض الجهد (% و V)
- مقاس الكابل الموصى به (المقاس القياسي الأعلى التالي)`,
    },
    tags: ["cable", "sizing", "iec", "60364", "كابل", "مقاس"],
    navigateTo: "/studies/cable_sizing",
    relatedTopics: ["studies.overview"],
  },
  {
    id: "studies.earth-grid",
    category: "engineering",
    title: { en: "Earth Grid Design", ar: "تصميم شبكة التأريض" },
    description: { en: "IEEE 80 ground grid design", ar: "تصميم شبكة التأريض IEEE 80" },
    content: {
      en: `**What it does:**
Designs a substation grounding grid that limits touch and step voltages to safe levels during ground faults.

**Required Inputs:**
- Fault current (A) — from Short Circuit study
- Fault duration (s) — typically 1 second
- Soil resistivity (Ω·m) — measured via Wenner 4-pin method
- Grid area (m²)
- Grid depth (m) — typically 0.5m
- Conductor spacing (m)

**IEEE 80-2013 Calculations:**
- Touch voltage limit: E_t = (116 + 0.7ρ) / √t
- Step voltage limit: E_s = (116 + 0.7ρ) / √t (different coefficient)
- Ground Potential Rise (GPR): I × Rg

**Results:**
- Grid resistance (Ω)
- Touch and step voltages (actual vs limits)
- GPR (Ground Potential Rise)
- Recommended conductor size (per IEEE 80 thermal capacity)`,
      ar: `**ما يفعله:**
يصمم شبكة تأريض محطة فرعية تحدّ من جهود اللمس والخطوة لمستويات آمنة أثناء أعطال الأرض.

**المدخلات المطلوبة:**
- تيار العطل (A) — من دراسة الدائرة القصيرة
- مدة العطل (s) — عادة 1 ثانية
- مقاومة التربة (Ω·m) — تُقاس بطريقة Wenner 4-pin
- مساحة الشبكة (m²)
- عمق الشبكة (m) — عادة 0.5m
- تباعد الموصل (m)

**حسابات IEEE 80-2013:**
- حد جهد اللمس: E_t = (116 + 0.7ρ) / √t
- حد جهد الخطوة: E_s = (116 + 0.7ρ) / √t (معامل مختلف)
- ارتفاع جهد التأريض (GPR): I × Rg

**النتائج:**
- مقاومة الشبكة (Ω)
- جهود اللمس والخطوة (الفعلية مقابل الحدود)
- ارتفاع جهد التأريض (GPR)
- مقاس الموصل الموصى به (حسب السعة الحرارية IEEE 80)`,
    },
    tags: ["earth", "grid", "ground", "ieee", "80", "تأريض", "شبكة"],
    navigateTo: "/studies/earth_grid",
    relatedTopics: ["studies.short-circuit", "studies.overview"],
  },
  {
    id: "studies.opf",
    category: "engineering",
    title: { en: "Optimal Power Flow (OPF)", ar: "تدفق القدرة الأمثل" },
    description: { en: "Cost-optimized generation dispatch", ar: "إرسال توليد أمثل للتكلفة" },
    content: {
      en: `**What it does:**
Finds the optimal generation dispatch that minimizes total generation cost while satisfying all power flow constraints and limits.

**Required Inputs:**
- Same as Load Flow
- Generator cost curves (quadratic: aP² + bP + c)
- Generator limits (Pmin, Pmax)
- Line flow limits (MVA)
- Bus voltage limits

**Objective Functions:**
- \`min_cost\` — minimize total generation cost (default)
- \`min_losses\` — minimize transmission losses
- \`min_emissions\` — minimize CO2 emissions

**Results:**
- Optimal P for each generator
- Total generation cost ($/h)
- Marginal prices at each bus ($/MWh)
- Binding constraints (lines/generators at limits)
- Comparison with base case`,
      ar: `**ما يفعله:**
يجد الإرسال الأمثل للتوليد الذي يقلل من إجمالي تكلفة التوليد مع تلبية جميع قيود تدفق القدرة والحدود.

**المدخلات المطلوبة:**
- نفس تدفق الحمل
- منحنيات تكلفة المولد (تربيعية: aP² + bP + c)
- حدود المولد (Pmin، Pmax)
- حدود تدفق الخط (MVA)
- حدود جهد الباص

**دوال الهدف:**
- \`min_cost\` — تقليل إجمالي تكلفة التوليد (افتراضي)
- \`min_losses\` — تقليل خسائر النقل
- \`min_emissions\` — تقليل انبعاثات CO2

**النتائج:**
- P المثلى لكل مولد
- إجمالي تكلفة التوليد ($/h)
- الأسعار الحدية في كل باص ($/MWh)
- القيود المُلزِمة (خطوط/مولدات عند الحدود)
- المقارنة مع الحالة الأساسية`,
    },
    tags: ["opf", "optimal", "power", "flow", "cost", "أمثل", "تكلفة"],
    navigateTo: "/studies/opf",
    relatedTopics: ["studies.overview", "studies.load-flow"],
  },
  {
    id: "studies.stability",
    category: "engineering",
    title: { en: "Transient Stability", ar: "الاستقرار العابر" },
    description: {
      en: "Power system transient stability analysis",
      ar: "تحليل الاستقرار العابر لنظام القدرة",
    },
    content: {
      en: `**What it does:**
Simulates the dynamic response of generators and loads to large disturbances (3-phase faults, line trips, generator outages) to verify the system remains stable.

**Required Inputs:**
- Generator dynamic models (H constant, Xd, Xd', Td0', etc.)
- AVR and governor models
- Load model (constant power, constant current, constant impedance)
- Disturbance specification (fault location, duration, clearing)

**Results:**
- Rotor angle vs time plot
- Frequency vs time plot
- Critical Clearing Time (CCT)
- Stability margin
- Recommendation for corrective actions if unstable`,
      ar: `**ما يفعله:**
يحاكي الاستجابة الديناميكية للمولدات والأحمال للاضطرابات الكبيرة (أعطال ثلاثية الطور، قطع الخطوط، خروج المولدات) للتحقق من بقاء النظام مستقراً.

**المدخلات المطلوبة:**
- نماذج ديناميكية للمولدات (ثابت H، Xd، Xd'، Td0'، إلخ)
- نماذج AVR والحاكم
- نموذج الحمل (قدرة ثابتة، تيار ثابت، مقاومة ثابتة)
- مواصفات الاضطراب (موقع العطل، المدة، التطهير)

**النتائج:**
- رسم زاوية الدوار مقابل الزمن
- رسم التردد مقابل الزمن
- وقت التطهير الحرج (CCT)
- هامش الاستقرار
- التوصية للإجراءات التصحيحية إذا كان غير مستقر`,
    },
    tags: ["stability", "transient", "rotor", "angle", "استقرار", "عابر"],
    navigateTo: "/studies/stability",
    relatedTopics: ["studies.overview", "studies.load-flow"],
  },
  {
    id: "ai-assistant.overview",
    category: "getting-started",
    title: { en: "AI Assistant", ar: "المساعد الذكي" },
    description: {
      en: "Chat with the ETAP Expert AI agent for engineering guidance",
      ar: "تحدث مع وكيل ETAP Expert الذكي للحصول على إرشادات هندسية",
    },
    content: {
      en: `**What it does:**
The AI Assistant page lets you chat with specialized AI agents (ETAP Expert, ETAP GUI, Load Flow Agent, etc.) to get engineering guidance, code suggestions, and step-by-step instructions.

**How to Use:**
1. Navigate to **AI Assistant** from the sidebar
2. Select an agent from the dropdown at the top (default: ETAP Expert)
3. Type your question in the textarea at the bottom
4. Press Enter (or click Send) to submit
5. The agent's response appears in the chat history

**Available Agents:**
- **ETAP Expert** — General ETAP knowledge and best practices
- **ETAP GUI** — ETAP user interface guidance
- **Load Flow Agent** — Specialized in load flow analysis
- **Short Circuit Agent** — IEC 60909 fault calculations
- **Arc Flash Agent** — IEEE 1584 incident energy
- **Protection Agent** — Relay coordination
- **Code Guard** — Code review for engineering calculations

**Tips:**
- Be specific in your questions (include bus count, voltage, standard)
- Reference standards explicitly (IEEE 1584-2018, not just "arc flash")
- The agent has access to a knowledge base of ETAP manuals and IEEE/IEC standards
- For complex problems, break them into multiple smaller questions`,
      ar: `**ما يفعله:**
تتيح لك صفحة المساعد الذكي الدردشة مع وكلاء ذكاء اصطناعي متخصصين (ETAP Expert، ETAP GUI، وكيل تدفق الحمل، إلخ) للحصول على إرشادات هندسية واقتراحات أكواد وتعليمات خطوة بخطوة.

**كيفية الاستخدام:**
1. انتقل إلى **المساعد الذكي** من الشريط الجانبي
2. اختر وكيلاً من القائمة المنسدلة في الأعلى (افتراضي: ETAP Expert)
3. اكتب سؤالك في منطقة النص السفلية
4. اضغط Enter (أو انقر إرسال) للتقديم
5. تظهر استجابة الوكيل في سجل الدردشة

**الوكلاء المتاحون:**
- **ETAP Expert** — معرفة ETAP العامة وأفضل الممارسات
- **ETAP GUI** — إرشادات واجهة مستخدم ETAP
- **وكيل تدفق الحمل** — متخصص في تحليل تدفق الحمل
- **وكيل الدائرة القصيرة** — حسابات عطل IEC 60909
- **وكيل شرارة القوس** — طاقة الحادث IEEE 1584
- **وكيل الحماية** — تنسيق المُرحّل
- **حارس الكود** — مراجعة الكود للحسابات الهندسية

**نصائح:**
- كن محدداً في أسئلتك (اذكر عدد الباصات، الجهد، المعيار)
- اذكر المعايير صراحةً (IEEE 1584-2018، ليس فقط "شرارة القوس")
- للوكيل وصول إلى قاعدة معرفية لأدلة ETAP ومعايير IEEE/IEC
- للمشاكل المعقدة، قسّمها لأسئلة أصغر متعددة`,
    },
    tags: ["ai", "assistant", "chat", "agent", "ذكاء", "اصطناعي", "مساعد"],
    navigateTo: "/assistant",
    relatedTopics: ["dashboard.overview", "code-guard.overview"],
  },

  // ─── Asset Management ─────────────────────────────────────────────
  {
    id: "asset-management.overview",
    category: "engineering",
    title: { en: "Asset Management", ar: "إدارة الأصول" },
    description: {
      en: "Track physical equipment across your power system",
      ar: "تتبع المعدات الفيزيائية في نظام القدرة",
    },
    content: {
      en: `**What it does:**
The Asset Management page tracks physical equipment (transformers, breakers, cables, generators) across your power system. Each asset has metadata (manufacturer, model, install date), maintenance history, and links to the engineering model.

**Key Features:**
- Asset list with filter by type, location, status
- Asset detail view with maintenance history
- Add/edit/delete assets
- Import assets from CSV
- Export asset register to Excel/PDF

**Asset Types:**
- Transformers (with test results)
- Circuit breakers (with timing tests)
- Cables (with insulation tests)
- Generators (with capability curves)
- Motors (with starting characteristics)
- Protective relays (with settings)`,
      ar: `**ما يفعله:**
تتبع صفحة إدارة الأصول المعدات الفيزيائية (محولات، قواطع، كابلات، مولدات) في نظام القدرة. لكل أصل بيانات وصفية (الشركة المصنعة، الموديل، تاريخ التركيب)، سجل الصيانة، وروابط للنموذج الهندسي.

**الميزات الرئيسية:**
- قائمة الأصول مع الفلترة حسب النوع، الموقع، الحالة
- عرض تفاصيل الأصل مع سجل الصيانة
- إضافة/تعديل/حذف الأصول
- استيراد الأصول من CSV
- تصدير سجل الأصول إلى Excel/PDF

**أنواع الأصول:**
- المحولات (مع نتائج الاختبار)
- القواطع الكهربية (مع اختبارات التوقيت)
- الكابلات (مع اختبارات العزل)
- المولدات (مع منحنيات القدرة)
- المحركات (مع خصائص البدء)
- المُرحّلات الحماية (مع الإعدادات)`,
    },
    tags: ["asset", "management", "equipment", "أصول", "معدات"],
    navigateTo: "/asset-management",
    relatedTopics: ["dashboard.overview"],
  },

  // ─── ETAP Integration ─────────────────────────────────────────────
  {
    id: "etap-integration.overview",
    category: "engineering",
    title: { en: "ETAP Integration", ar: "تكامل ETAP" },
    description: {
      en: "Connect to ETAP desktop software for native study execution",
      ar: "اتصل ببرنامج ETAP المكتبي لتنفيذ الدراسات الأصلية",
    },
    content: {
      en: `**What it does:**
The ETAP Integration page configures the connection between AhmedETAP and the ETAP desktop software running on Windows. This allows running studies using the real ETAP engine instead of the native Python engine.

**Prerequisites:**
- ETAP licensed and installed on a Windows machine
- ETAP Worker Service running on the Windows machine (port 8080 by default)
- Network connectivity between AhmedETAP server and the Windows worker

**Configuration:**
1. **ETAP Worker URL** — IP:port of the Windows worker (e.g. http://192.168.1.100:8080)
2. **ETAP License Path** — path to the ETAP license file on the Windows machine
3. **Use ETAP** — toggle to enable ETAP execution (vs native Python)

**Worker Status:**
- 🟢 Online — worker is registered and responding
- 🟡 Degraded — worker responding but slow
- 🔴 Offline — worker not registered or unreachable

**Tips:**
- Use ETAP for studies that require ETAP-specific features (e.g., IEEE 1584 with specific equipment)
- Use native Python for faster iteration during development
- The worker can be load-balanced across multiple Windows machines`,
      ar: `**ما يفعله:**
تقوم صفحة تكامل ETAP بتكوين الاتصال بين AhmedETAP وبرنامج ETAP المكتبي الذي يعمل على Windows. هذا يسمح بتشغيل الدراسات باستخدام محرك ETAP الحقيقي بدلاً من محرك Python الأصلي.

**المتطلبات المسبقة:**
- ETAP مرخص ومثبت على جهاز Windows
- ETAP Worker Service يعمل على جهاز Windows (المنفذ 8080 افتراضياً)
- اتصال شبكة بين خادم AhmedETAP وعامل Windows

**التكوين:**
1. **رابط عامل ETAP** — IP:منفذ عامل Windows (مثل http://192.168.1.100:8080)
2. **مسار ترخيص ETAP** — المسار لملف ترخيص ETAP على جهاز Windows
3. **استخدام ETAP** — تبديل لتمكين تنفيذ ETAP (مقابل Python الأصلي)

**حالة العامل:**
- 🟢 متصل — العامل مسجل ويستجيب
- 🟡 متدهور — العامل يستجيب لكن ببطء
- 🔴 غير متصل — العامل غير مسجل أو لا يمكن الوصول إليه

**نصائح:**
- استخدم ETAP للدراسات التي تتطلب ميزات ETAP محددة (مثل IEEE 1584 مع معدات محددة)
- استخدم Python الأصلي للتكرار الأسرع أثناء التطوير
- يمكن موازنة حمل العامل عبر أجهزة Windows متعددة`,
    },
    tags: ["etap", "integration", "worker", "windows", "تكامل", "عامل"],
    navigateTo: "/etap",
    relatedTopics: ["studies.overview", "settings.backend"],
  },

  // ─── GIS Integration ──────────────────────────────────────────────
  {
    id: "gis-integration.overview",
    category: "engineering",
    title: { en: "GIS Integration", ar: "تكامل GIS" },
    description: {
      en: "Connect to ArcGIS / QGIS / PostGIS for geospatial power system data",
      ar: "اتصل بـ ArcGIS / QGIS / PostGIS لبيانات نظام القدرة الجغرافية",
    },
    content: {
      en: `**What it does:**
The GIS Integration page connects AhmedETAP to Geographic Information Systems (ArcGIS, QGIS, PostGIS) to import geospatial data for power system assets (lines, substations, transformers with coordinates).

**Supported Providers:**
- **ArcGIS Pro** — ESRI's desktop GIS (via ArcPy)
- **QGIS** — open-source desktop GIS (via PyQGIS)
- **PostGIS** — PostgreSQL spatial database extension

**Configuration:**
1. Select the GIS provider from the dropdown
2. Provide connection parameters (file path, server URL, or DB connection string)
3. Click **Test Connection** to verify
4. Click **Import** to load GIS data into the engineering model

**What Gets Imported:**
- Substation locations (latitude, longitude)
- Line routes (polylines)
- Transformer positions
- Service area boundaries

**Validation:**
- CRS (Coordinate Reference System) check
- Topology validation (no dangling lines, no overlapping)
- Electrical connectivity validation

**Tips:**
- Use WGS84 (EPSG:4326) for cross-platform compatibility
- Run validation after every import to catch GIS-to-electrical mismatches`,
      ar: `**ما يفعله:**
تقوم صفحة تكامل GIS بربط AhmedETAP بأنظمة المعلومات الجغرافية (ArcGIS، QGIS، PostGIS) لاستيراد البيانات الجغرافية لأصول نظام القدرة (الخطوط، المحطات الفرعية، المحولات بالإحداثيات).

**المزودون المدعومون:**
- **ArcGIS Pro** — GIS المكتبي من ESRI (عبر ArcPy)
- **QGIS** — GIS المكتبي مفتوح المصدر (عبر PyQGIS)
- **PostGIS** — امتداد قاعدة بيانات PostgreSQL المكاني

**التكوين:**
1. اختر مزود GIS من القائمة المنسدلة
2. قدّم معلمات الاتصال (مسار الملف، رابط الخادم، أو سلسلة اتصال DB)
3. انقر على **اختبار الاتصال** للتحقق
4. انقر على **استيراد** لتحميل بيانات GIS في النموذج الهندسي

**ما يتم استيراده:**
- مواقع المحطات الفرعية (خط العرض، خط الطول)
- مسارات الخطوط (خطوط متعددة)
- مواقع المحولات
- حدود منطقة الخدمة

**التحقق:**
- التحقق من CRS (نظام الإحداثيات المرجعي)
- التحقق من الطوبولوجيا (لا خطوط معلقة، لا تداخل)
- التحقق من الاتصال الكهربائي

**نصائح:**
- استخدم WGS84 (EPSG:4326) للتوافق عبر المنصات
- شغّل التحقق بعد كل استيراد لالتقاط عدم التطابق بين GIS والكهرباء`,
    },
    tags: ["gis", "arcgis", "qgis", "postgis", "geo", "جغرافي"],
    navigateTo: "/gis",
    relatedTopics: ["asset-management.overview", "digital-twin.overview"],
  },

  // ─── Reports ──────────────────────────────────────────────────────
  {
    id: "reports.generate",
    category: "reports",
    title: { en: "Generating Reports", ar: "إنشاء التقارير" },
    description: {
      en: "How to generate and customize engineering reports",
      ar: "كيفية إنشاء وتخصيص التقارير الهندسية",
    },
    content: {
      en: `**Report Types:**
- **Compliance Report** — Standards verification (IEEE 1584, IEC 60909, etc.)
- **Calculation Report** — Detailed analysis results with formulas
- **Summary Report** — Executive overview (1-2 pages)
- **Audit Report** — System configuration audit trail

**Steps:**
1. Navigate to **Reports** from the sidebar
2. Click **New Report**
3. Select report type
4. Choose source project and study
5. Configure report options:
   - Format (PDF, DOCX, CSV, JSON)
   - Include sections (executive summary, methodology, results, recommendations)
   - Language (English or Arabic)
   - Logo and branding
6. Click **Generate Report**
7. Download the file when ready

**Export Formats:**
- PDF — primary, with formatted tables and figures
- DOCX — editable in Microsoft Word
- CSV — data only (for spreadsheet analysis)
- JSON — for API integration with other tools

**Tips:**
- Compliance reports include a cover page with standard references
- Use the audit report for ISO 9001 / IEC quality management
- Reports are generated server-side; allow 10-30 seconds for large reports`,
      ar: `**أنواع التقارير:**
- **تقرير الامتثال** — التحقق من المعايير (IEEE 1584، IEC 60909، إلخ)
- **تقرير الحسابات** — نتائج التحليل التفصيلية مع الصيغ
- **تقرير الملخص** — نظرة عامة تنفيذية (1-2 صفحة)
- **تقرير التدقيق** — سجل تدقيق تكوين النظام

**الخطوات:**
1. انتقل إلى **التقارير** من الشريط الجانبي
2. انقر على **تقرير جديد**
3. حدد نوع التقرير
4. اختر المشروع والدراسة المصدر
5. قوم خيارات التقرير:
   - التنسيق (PDF، DOCX، CSV، JSON)
   - الأقسام المضمنة (الملخص التنفيذي، المنهجية، النتائج، التوصيات)
   - اللغة (الإنجليزية أو العربية)
   - الشعار والعلامة التجارية
6. انقر على **إنشاء التقرير**
7. نزّل الملف عندما يكون جاهزاً

**تنسيقات التصدير:**
- PDF — أساسي، مع جداول وأشكال منسقة
- DOCX — قابل للتعديل في Microsoft Word
- CSV — بيانات فقط (لتحليل جداول البيانات)
- JSON — لتكامل API مع أدوات أخرى

**نصائح:**
- تقارير الامتثال تشمل صفحة غلاف مع مراجع المعايير
- استخدم تقرير التدقيق لإدارة الجودة ISO 9001 / IEC
- تُنشأ التقارير من جانب الخادم؛ اسمح بـ 10-30 ثانية للتقارير الكبيرة`,
    },
    tags: ["report", "generate", "pdf", "compliance", "تقرير", "إنشاء", "امتثال"],
    navigateTo: "/reports",
    relatedTopics: ["projects.manage", "studies.overview"],
  },

  // ─── Digital Twin ─────────────────────────────────────────────────
  {
    id: "digital-twin.overview",
    category: "digital-twin",
    title: { en: "Digital Twin Overview", ar: "نظرة عامة على التوأم الرقمي" },
    description: {
      en: "Real-time virtual replica of your physical power system",
      ar: "نسخة افتراضية في الوقت الفعلي من نظام القدرة الفيزيائي",
    },
    content: {
      en: `**What is a Digital Twin?**
A digital twin is a real-time virtual replica of your physical power system. It syncs with SCADA, BMS, and IoT sensors to provide a live view of system state.

**Features:**
- Real-time state synchronization (every 1-10 seconds)
- Predictive maintenance alerts
- What-if scenario simulation
- Historical data comparison
- Automated compliance monitoring

**Getting Started:**
1. Connect to your SCADA system (Copa-Data zenon, others via OPC UA)
2. Map SCADA tags to ETAP entities (buses, breakers, generators)
3. Enable real-time sync
4. Monitor the dashboard for anomalies
5. Set up alerts for threshold violations

**Supported Sync Protocols:**
- IEC 61850 (via zenon)
- IEC 60870-5-104
- Modbus TCP
- OPC UA
- DNP3 (future)

**Tips:**
- Start with a small subset of tags and expand gradually
- Use the validation gateway to verify commands before sending to SCADA
- Historical comparison lets you detect performance drift over time`,
      ar: `**ما هو التوأم الرقمي؟**
التوأم الرقمي هو نسخة افتراضية في الوقت الفعلي من نظام القدرة الفيزيائي. يتزامن مع SCADA و BMS و IoT sensors لتوفير عرض مباشر لحالة النظام.

**الميزات:**
- مزامنة الحالة في الوقت الفعلي (كل 1-10 ثوانٍ)
- تنبيهات الصيانة التنبؤية
- محاكاة سيناريو ماذا لو
- مقارنة البيانات التاريخية
- مراقبة الامتثال التلقائية

**البدء:**
1. اتصل بنظام SCADA (Copa-Data zenon، أخرى عبر OPC UA)
2. عيّن وسوم SCADA لكيانات ETAP (باصات، قواطع، مولدات)
3. فعّل المزامنة المباشرة
4. راقب لوحة التحكم للشذوذ
5. اعداد تنبيهات لانتهاكات العتبة

**بروتوكولات المزامنة المدعومة:**
- IEC 61850 (عبر zenon)
- IEC 60870-5-104
- Modbus TCP
- OPC UA
- DNP3 (مستقبلاً)

**نصائح:**
- ابدأ بمجموعة صغيرة من الوسوم ووسّع تدريجياً
- استخدم بوابة التحقق للتحقق من الأوامر قبل الإرسال إلى SCADA
- تتيح المقارنة التاريخية كشف انحراف الأداء بمرور الوقت`,
    },
    tags: ["digital", "twin", "sync", "real-time", "توأم", "رقمي", "مزامنة"],
    navigateTo: "/digital-twin",
    relatedTopics: ["dashboard.overview", "integration.scada"],
  },

  // ─── Settings ─────────────────────────────────────────────────────
  {
    id: "settings.backend",
    category: "settings",
    title: { en: "Backend Configuration", ar: "تكوين الخادم" },
    description: {
      en: "Configure the engineering service backend connection",
      ar: "تكوين اتصال خادم الخدمة الهندسية",
    },
    content: {
      en: `**Backend Settings (Engineering Service tab):**
- **Service URL** — URL of the FastAPI engineering service (default: http://localhost:8000)
- **API Key** — Authentication key sent in the X-API-Key header
- **Timeout** — Request timeout in milliseconds (default: 30000)

**Connection Status:**
- 🟢 Connected — Backend is healthy
- 🟡 Degraded — Backend responding slowly (>2s)
- 🔴 Disconnected — Backend unavailable

**How to Test:**
1. Save the URL and API key
2. The status indicator updates automatically
3. If red, check:
   - Is the backend running? (\`curl http://localhost:8000/healthz\`)
   - Is the URL correct?
   - Is the API key correct?
   - Is there a firewall blocking the port?

**Tips:**
- For local development: http://localhost:8000
- For HF Space deployment: use the full hf.space URL
- The API key is stored in localStorage (obfuscated, NOT encrypted)`,
      ar: `**إعدادات الخادم (تبويب الخدمة الهندسية):**
- **رابط الخدمة** — رابط خدمة FastAPI الهندسية (افتراضي: http://localhost:8000)
- **مفتاح API** — مفتاح المصادقة المُرسل في ترويسة X-API-Key
- **المهلة** — مهلة الطلب بالمللي ثانية (افتراضي: 30000)

**حالة الاتصال:**
- 🟢 متصل — الخادم يعمل بشكل صحيح
- 🟡 متدهور — الخادم يستجيب ببطء (>2s)
- 🔴 غير متصل — الخادم غير متاح

**كيفية الاختبار:**
1. احفظ الرابط ومفتاح API
2. يتم تحديث مؤشر الحالة تلقائياً
3. إذا كان أحمر، تحقق من:
   - هل الخادم يعمل؟ (\`curl http://localhost:8000/healthz\`)
   - هل الرابط صحيح؟
   - هل مفتاح API صحيح؟
   - هل يوجد جدار حماية يحظر المنفذ؟

**نصائح:**
- للتطوير المحلي: http://localhost:8000
- لنشر HF Space: استخدم رابط hf.space الكامل
- مفتاح API محفوظ في localStorage (مشوّه، وليس مشفّراً)`,
    },
    tags: ["settings", "backend", "config", "api", "إعدادات", "خادم", "تكوين"],
    navigateTo: "/settings",
    relatedTopics: ["troubleshooting.backend", "settings.external-services"],
  },
  {
    id: "settings.external-services",
    category: "settings",
    title: {
      en: "External Services (LangWatch, Smithery, HF, GitHub, Vercel)",
      ar: "الخدمات الخارجية (LangWatch, Smithery, HF, GitHub, Vercel)",
    },
    description: {
      en: "Configure and test third-party integrations",
      ar: "تكوين واختبار التكاملات الخارجية",
    },
    content: {
      en: `**The External Services tab lets you configure 5 third-party integrations:**

**1. LangWatch** — LLM observability dashboard
- API Key, Project Name, Endpoint URL
- Test button calls /api/v1/projects (with CORS fallback)
- Status: ✓ green = connected, ✗ red = invalid key or network error

**2. Smithery MCP** — Model Context Protocol server registry
- API Key, Base URL
- Test button calls /v1/servers (Bearer auth)

**3. Hugging Face** — Model hub & Spaces deployment
- Access Token, Space Name, Space URL
- Test button calls /api/whoami-v2 (returns your username)

**4. GitHub** — Repository access & CI/CD
- Personal Access Token, Repository (owner/repo)
- Test button calls /api/user (returns your login)

**5. Vercel** — Frontend deployment
- Project ID, Access Token
- Test button calls /v9/projects/{id} (returns project name)

**How to Use:**
1. Enter your credentials for each service
2. Click "Test Connection" — a real API call is made
3. The status badge updates: ✓/✗/spinner
4. The detail message tells you exactly what happened
5. Click the external-link icon to open the service's dashboard

**Privacy:**
- Tokens are stored in browser localStorage (obfuscated)
- They are NEVER sent to our backend
- For backend runtime use, copy them to your .env or HF Space secrets`,
      ar: `**تبويب الخدمات الخارجية يتيح لك تكوين 5 تكاملات خارجية:**

**1. LangWatch** — لوحة مراقبة LLM
- مفتاح API، اسم المشروع، رابط النقطة
- زر الاختبار يستدعي /api/v1/projects (مع بديل CORS)
- الحالة: ✓ أخضر = متصل، ✗ أحمر = مفتاح غير صحيح أو خطأ شبكة

**2. Smithery MCP** — سجل خوادم بروتوكول السياق النموذجي
- مفتاح API، الرابط الأساسي
- زر الاختبار يستدعي /v1/servers (مصادقة Bearer)

**3. Hugging Face** — مركز النماذج ونشر المساحات
- رمز الوصول، اسم المساحة، رابط المساحة
- زر الاختبار يستدعي /api/whoami-v2 (يُرجع اسم المستخدم)

**4. GitHub** — الوصول للمستودعات و CI/CD
- رمز الوصول الشخصي، المستودع (المالك/المستودع)
- زر الاختبار يستدعي /api/user (يُرجع تسجيل الدخول)

**5. Vercel** — نشر الواجهة
- معرف المشروع، رمز الوصول
- زر الاختبار يستدعي /v9/projects/{id} (يُرجع اسم المشروع)

**كيفية الاستخدام:**
1. أدخل بيانات الاعتماد لكل خدمة
2. انقر على "اختبار الاتصال" — يتم إجراء استدعاء API حقيقي
3. يتم تحديث شارة الحالة: ✓/✗/spinner
4. تخبرك الرسالة التفصيلية بما حدث بالضبط
5. انقر على أيقونة الرابط الخارجي لفتح لوحة الخدمة

**الخصوصية:**
- الرموز محفوظة في localStorage بالمتصفح (مشوّهة)
- لا يتم إرسالها أبداً إلى الخادم
- للاستخدام في الخادم، انسخها إلى .env أو أسرار HF Space`,
    },
    tags: [
      "settings",
      "external",
      "services",
      "langwatch",
      "smithery",
      "huggingface",
      "github",
      "vercel",
      "إعدادات",
      "خدمات",
      "خارجية",
    ],
    navigateTo: "/settings",
    relatedTopics: ["settings.backend", "integration.scada"],
  },
  {
    id: "settings.ai-providers",
    category: "settings",
    title: { en: "AI Providers Configuration", ar: "تكوين مزودي الذكاء الاصطناعي" },
    description: {
      en: "Connect to OpenAI, Anthropic, Gemini, DeepSeek, Groq, Cohere, Hugging Face, OpenRouter, etc.",
      ar: "اتصل بـ OpenAI و Anthropic و Gemini و DeepSeek و Groq و Cohere و Hugging Face و OpenRouter",
    },
    content: {
      en: `**The AI Providers tab lets you connect to 17+ popular LLM providers:**

**Built-in Providers (one-click):**
- **OpenAI** — GPT-4o, GPT-4o-mini, o1-mini, o1-preview
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku
- **Google Gemini** — Gemini 1.5 Pro/Flash, Gemini 2.0 Flash
- **DeepSeek** — DeepSeek Chat, DeepSeek Coder, DeepSeek Reasoner
- **Groq** — Llama 3.3 70B, Mixtral 8x7B, Gemma 2 9B (free tier)
- **Cohere** — Command R+, Command R
- **Hugging Face** — Llama 3.3 70B, Mixtral 8x7B (free tier)
- **NVIDIA NIM** — Llama 3.1 8B/70B/405B (free tier)
- **OpenRouter** — 340+ models including GPT-OSS, Llama, Claude (26 free)
- **Fireworks AI** — Llama, Mixtral, Qwen Coder
- **Cloudflare Workers AI** — Llama, Mistral, Gemma (free tier)
- **Zhipu AI (GLM)** — GLM-4 Flash/Plus (free tier)
- **GitHub Models** — GPT-4o, Phi-3.5, Llama 3.1 (free tier)
- **OpenModel** — GPT-4o, GPT-5.4, Claude 3.5 Sonnet
- **Modal** — GLM-5.1, GLM-4.5 (free research)
- **Bynara Router** — Kimi K2.6, GPT-5.4, Claude Sonnet 5
- **KiloCode** — KiloCode Coder (free), Standard
- **OpenCode Zen** — DeepSeek V4 Flash (free), GPT-5.4, Claude Sonnet 5
- **OpenClaude** — Claude 3.5 Sonnet (free, proxy)
- **Claude Code** — Anthropic direct API

**How to Connect:**
1. Click the provider card you want to configure
2. Enter your API key in the field that appears
3. Select the model from the dropdown
4. Click "Connect"
5. A success toast confirms the connection

**Custom Provider (Advanced):**
- Use the "Custom Provider" section to connect to any OpenAI-compatible API
- Paste a curl command and click "Parse" to auto-fill fields
- Examples: Ollama (http://localhost:11434/v1), LM Studio (http://localhost:1234/v1)

**Tips:**
- API keys are stored in localStorage (obfuscated with XOR + base64)
- You can configure multiple providers simultaneously
- The AI Assistant page lets you select which provider to use per chat
- Free tier providers are marked with "(free)" in the model list`,
      ar: `**تبويب مزودي الذكاء الاصطناعي يتيح لك الاتصال بـ 17+ مزودين LLM شائعين:**

**المزودون المدمجون (بنقرة واحدة):**
- **OpenAI** — GPT-4o، GPT-4o-mini، o1-mini، o1-preview
- **Anthropic** — Claude 3.5 Sonnet، Claude 3 Opus، Claude 3.5 Haiku
- **Google Gemini** — Gemini 1.5 Pro/Flash، Gemini 2.0 Flash
- **DeepSeek** — DeepSeek Chat، DeepSeek Coder، DeepSeek Reasoner
- **Groq** — Llama 3.3 70B، Mixtral 8x7B، Gemma 2 9B (مجاني)
- **Cohere** — Command R+، Command R
- **Hugging Face** — Llama 3.3 70B، Mixtral 8x7B (مجاني)
- **NVIDIA NIM** — Llama 3.1 8B/70B/405B (مجاني)
- **OpenRouter** — 340+ نموذج包括 GPT-OSS و Llama و Claude (26 مجاني)
- **Fireworks AI** — Llama، Mixtral، Qwen Coder
- **Cloudflare Workers AI** — Llama، Mistral، Gemma (مجاني)
- **Zhipu AI (GLM)** — GLM-4 Flash/Plus (مجاني)
- **GitHub Models** — GPT-4o، Phi-3.5، Llama 3.1 (مجاني)
- **OpenModel** — GPT-4o، GPT-5.4، Claude 3.5 Sonnet
- **Modal** — GLM-5.1، GLM-4.5 (بحث مجاني)
- **Bynara Router** — Kimi K2.6، GPT-5.4، Claude Sonnet 5
- **KiloCode** — KiloCode Coder (مجاني)، Standard
- **OpenCode Zen** — DeepSeek V4 Flash (مجاني)، GPT-5.4، Claude Sonnet 5
- **OpenClaude** — Claude 3.5 Sonnet (مجاني، بروكسي)
- **Claude Code** — Anthropic API مباشر

**كيفية الاتصال:**
1. انقر على بطاقة المزود الذي تريد تكوينه
2. أدخل مفتاح API في الحقل الذي يظهر
3. اختر النموذج من القائمة المنسدلة
4. انقر على "اتصال"
5. تؤكد رسالة نجاح الاتصال

**المزود المخصص (متقدم):**
- استخدم قسم "المزود المخصص" للاتصال بأي API متوافق مع OpenAI
- الصق أمر curl وانقر على "تحليل" لتعبئة الحقول تلقائياً
- أمثلة: Ollama (http://localhost:11434/v1)، LM Studio (http://localhost:1234/v1)

**نصائح:**
- مفاتيح API محفوظة في localStorage (مشوّهة بـ XOR + base64)
- يمكنك تكوين مزودين متعددين في نفس الوقت
- تتيح لك صفحة المساعد الذكي اختيار المزود المستخدم لكل دردشة
- المزودون المجانين مميزون بـ "(مجاني)" في قائمة النماذج`,
    },
    tags: [
      "ai",
      "provider",
      "openai",
      "anthropic",
      "gemini",
      "deepseek",
      "groq",
      "cohere",
      "huggingface",
      "openrouter",
      "مزود",
      "ذكاء",
    ],
    navigateTo: "/settings",
    relatedTopics: ["ai-assistant.overview", "settings.backend"],
  },
  {
    id: "settings.mcp",
    category: "settings",
    title: { en: "MCP Servers", ar: "خوادم MCP" },
    description: {
      en: "Model Context Protocol server configuration and exposed tools",
      ar: "تكوين خوادم بروتوكول السياق النموذجي والأدوات المعروضة",
    },
    content: {
      en: `**What it does:**
The MCP Servers tab shows which Model Context Protocol (MCP) servers are running and what tools they expose to AI agents.

**Built-in MCP Servers:**
1. **Weather MCP Server** — Real-time weather and temperature for renewable energy planning
   - Tool: \`weatherTool\`
   - Status: Active

2. **QGIS Map Service MCP Server** — Bridges GIS data (coordinates, lines, substations)
   - Tools: \`load_gis_features\`, \`sync_gis_telemetry\`
   - Status: Active

3. **SCADA zenon Telemetry MCP Server** — Subscribes to SCADA alerts and live telemetry (I, V, P, Q)
   - Tools: \`fetch_live_telemetry\`, \`trigger_zenon_alarm\`
   - Status: Active

4. **ETAP COM Automation MCP Server** — Executes COM automation scripts for Newton-Raphson studies
   - Tools: \`run_etap_study\`, \`export_etap_one_line\`
   - Status: Standby (requires Windows + ETAP installed)

5. **AI Code Guard MCP Server** — Validates generated code for safety and compliance
   - Tool: \`validate_code\`
   - Status: Active

**How It Works:**
- MCP servers expose local files, databases, and APIs as secure tools
- AI agents (in AI Assistant) can call these tools with user consent
- Each server has a status: Active, Standby, or Offline

**Tips:**
- MCP is automatically configured — no user action needed
- To add a custom MCP server, restart the backend with the server config in .env
- Tool calls are logged for audit purposes`,
      ar: `**ما يفعله:**
تبويب خوادم MCP يُظهر خوادم بروتوكول السياق النموذجي (MCP) النشطة والأدوات التي تعرضها لوكلاء الذكاء الاصطناعي.

**خوادم MCP المدمجة:**
1. **خادم MCP للطقس** — طقس ودرجة حرارة في الوقت الفعلي لتخطيط الطاقة المتجددة
   - الأداة: \`weatherTool\`
   - الحالة: نشط

2. **خادم MCP لخدمة الخرائط QGIS** — يربط بيانات GIS (إحداثيات، خطوط، محطات)
   - الأدوات: \`load_gis_features\`، \`sync_gis_telemetry\`
   - الحالة: نشط

3. **خادم MCP لبث الإسكادا زينون** — يشترك في إنذارات الإسكادا والبيانات القياسية الحية (I, V, P, Q)
   - الأدوات: \`fetch_live_telemetry\`، \`trigger_zenon_alarm\`
   - الحالة: نشط

4. **خادم MCP لأتمتة ETAP COM** — ينفذ سكريبتات أتمتة COM لدراسات نيوتن-رافسون
   - الأدوات: \`run_etap_study\`، \`export_etap_one_line\`
   - الحالة: standby (يتطلب Windows + ETAP مثبت)

5. **خادم MCP لحارس الكود AI** — يتحقق من الكود المولد للسلامة والامتثال
   - الأداة: \`validate_code\`
   - الحالة: نشط

**كيف يعمل:**
- خوادم MCP تعرض الملفات المحلية وقواعد البيانات وAPIs كأدوات آمنة
- وكلاء الذكاء الاصطناعي (في المساعد الذكي) يمكنهم استدعاء هذه الأدوات بموافقة المستخدم
- كل خادم له حالة: نشط، standby، أو غير متصل

**نصائح:**
- MCP مُكوّن تلقائياً — لا يحتاج إجراء من المستخدم
- لإضافة خادم MCP مخصص، أعد تشغيل الخادم مع تكوين الخادم في .env
- استدعاءات الأدوات مسجلة لأغراض التدقيق`,
    },
    tags: ["mcp", "server", "protocol", "context", "tool", "خادم", "بروتوكول"],
    navigateTo: "/settings",
    relatedTopics: ["settings.ai-providers", "ai-assistant.overview"],
  },
  {
    id: "settings.coding-agents",
    category: "settings",
    title: {
      en: "Coding Agents (OpenHands, OpenCode, KiloCode)",
      ar: "وكلاء البرمجة (OpenHands, OpenCode, KiloCode)",
    },
    description: {
      en: "Configure autonomous coding agent integrations",
      ar: "تكوين تكاملات وكلاء البرمجة المستقلين",
    },
    content: {
      en: `**What it does:**
The Coding Agents tab configures integrations with autonomous coding agents that can write, review, and execute engineering code.

**Supported Agents:**
1. **OpenHands** (formerly OpenDevin) — Full autonomous software engineering agent
   - URL: http://localhost:3000 (default)
   - Enable: Set \`OPENHANDS_ENABLED=true\`
   - Workspace: Directory for agent files

2. **OpenCode** — CLI coding agent with zen-powered models
   - URL: http://localhost:8080 (default)
   - Enable: Set \`OPENCODE_ENABLED=true\`
   - Supports DeepSeek V4 Flash (free) via OpenCode Zen

3. **KiloCode** — Code generation agent
   - URL: http://localhost:8090 (default)
   - Enable: Set \`KILOCODE_ENABLED=true\`
   - Model: KiloCode Coder (free) or Standard

**How to Use:**
1. Enable the agent by setting the \`*_ENABLED\` flag to \`true\`
2. Set the URL where the agent runtime is running
3. Optionally configure a workspace directory
4. Save settings
5. Use the agent from the AI Assistant page by selecting it from the agent dropdown

**Security Notes:**
- Agents run in isolated sandboxes
- All code execution is logged
- Users must approve code before it runs on their system`,
      ar: `**ما يفعله:**
تبويب وكلاء البرمجة يكوّن تكاملات مع وكلاء برمجة مستقلين يمكنهم كتابة ومراجعة وتنفيذ كود هندسي.

**الوكلاء المدعومون:**
1. **OpenHands** (سابقاً OpenDevin) — وكيل برمجة مستقل كامل
   - الرابط: http://localhost:3000 (افتراضي)
   - التفعيل: تعيين \`OPENHANDS_ENABLED=true\`
   - مساحة العمل: مجلد ملفات الوكيل

2. **OpenCode** — وكيل برمجة CLI مع نماذج مدعومة بـ zen
   - الرابط: http://localhost:8080 (افتراضي)
   - التفعيل: تعيين \`OPENCODE_ENABLED=true\`
   - يدعم DeepSeek V4 Flash (مجاني) عبر OpenCode Zen

3. **KiloCode** — وكيل توليد كود
   - الرابط: http://localhost:8090 (افتراضي)
   - التفعيل: تعيين \`KILOCODE_ENABLED=true\`
   - النموذج: KiloCode Coder (مجاني) أو Standard

**كيفية الاستخدام:**
1. فعّل الوكيل بتعيين العلم \`*_ENABLED\` إلى \`true\`
2. عيّن الرابط حيث يعمل الوكيل
3. اخترياً عيّن مجلد مساحة العمل
4. احفظ الإعدادات
5. استخدم الوكيل من صفحة المساعد الذكي باختياره من القائمة المنسدلة

**ملاحظات الأمان:**
- الوكلاء يعملون في حاويات معزولة
- كل تنفيذ كود مسجل
- المستخدمون يجب他们 بالموافقة على الكود قبل تشغيله`,
    },
    tags: ["coding", "agent", "openhands", "opencode", "kilocode", "وكيل", "برمجة"],
    navigateTo: "/settings",
    relatedTopics: ["settings.ai-providers", "code-guard.overview"],
  },
  {
    id: "settings.database",
    category: "settings",
    title: { en: "Database & Cache Configuration", ar: "تكوين قاعدة البيانات والذاكرة المؤقتة" },
    description: {
      en: "Configure database connection and cache settings",
      ar: "تكوين اتصال قاعدة البيانات وإعدادات الذاكرة المؤقتة",
    },
    content: {
      en: `**What it does:**
The Database & Cache tab configures the PostgreSQL database connection and Redis cache for the engineering service.

**Database Settings:**
- **MASTRA_DB_URL** — SQLite database for workflow state (default: file:./mastra.db)
- **DATABASE_URL** — PostgreSQL connection string (e.g. postgresql://user:pass@host:5432/etap)
- **REDIS_URL** — Redis connection string (e.g. redis://localhost:6379/0)

**Cache Settings:**
- **CACHE_SIZE_MB** — Maximum cache size in MB (default: 512)
- **CACHE_DEFAULT_TTL** — Time-to-live for cached items in seconds (default: 3600 = 1 hour)
- **MAX_WORKERS** — Number of parallel worker processes (default: 4)

**How to Configure:**
1. Enter your PostgreSQL connection string (if using Postgres instead of SQLite)
2. Enter your Redis URL (if using Redis for caching)
3. Adjust cache size and TTL based on your workload
4. Set MAX_WORKERS based on your CPU cores (2-8 recommended)
5. Click **Save**

**Recommendations:**
- Use PostgreSQL for production (better concurrency)
- Use Redis for caching study results (faster repeat runs)
- Set CACHE_TTL to 3600 for normal use, 86400 for rarely-changing data
- MAX_WORKERS = CPU cores - 1 (leave one core for OS)`,
      ar: `**ما يفعله:**
تبويب قاعدة البيانات والذاكرة المؤقتة يكوّن اتصال قاعدة بيانات PostgreSQL والذاكرة المؤقتة Redis للخدمة الهندسية.

**إعدادات قاعدة البيانات:**
- **MASTRA_DB_URL** — رابط قاعدة بيانات SQLite لحالة سير العمل (افتراضي: file:./mastra.db)
- **DATABASE_URL** — سلسلة اتصال PostgreSQL (مثل postgresql://user:pass@host:5432/etap)
- **REDIS_URL** — سلسلة اتصال Redis (مثل redis://localhost:6379/0)

**إعدادات الذاكرة المؤقتة:**
- **CACHE_SIZE_MB** — الحد الأقصى لحجم الذاكرة المؤقتة بالميجابايت (افتراضي: 512)
- **CACHE_DEFAULT_TTL** — مدة البقاء للعناصر المخزنة مؤقتاً بالثواني (افتراضي: 3600 = ساعة واحدة)
- **MAX_WORKERS** — عدد عمليات العامل المتوازية (افتراضي: 4)

**كيفية التكوين:**
1. أدخل سلسلة اتصال PostgreSQL (إذا كنت تستخدم Postgres بدلاً من SQLite)
2. أدخل رابط Redis (إذا كنت تستخدم Redis للذاكرة المؤقتة)
3. اضبط حجم الذاكرة المؤقتة و TTL بناءً على عبء العمل
4. عيّن MAX_WORKERS بناءً على أنوية CPU (2-8 موصى به)
5. انقر **حفظ**

**التوصيات:**
- استخدم PostgreSQL للإنتاج (تزامن أفضل)
- استخدم Redis للذاكرة المؤقتة لنتائج الدراسات (تشغيل متكرر أسرع)
- عيّن CACHE_TTL إلى 3600 للاستخدام العادي، 86400 للبيانات نادرة التغيير
- MAX_WORKERS = أنوية CPU - 1 (اترك نواة للنظام)`,
    },
    tags: ["database", "postgres", "redis", "cache", "قاعدة بيانات", "ذاكرة مؤقتة"],
    navigateTo: "/settings",
    relatedTopics: ["settings.backend", "diagnostics.overview"],
  },
  {
    id: "settings.security",
    category: "settings",
    title: { en: "Security & Secrets Management", ar: "الأمان وإدارة الأسرار" },
    description: {
      en: "Configure authentication keys, JWT secrets, and Vault integration",
      ar: "تكوين مفاتيح المصادقة وأسرار JWT وتكامل Vault",
    },
    content: {
      en: `**What it does:**
The Security tab configures authentication keys, JWT secrets, and optional HashiCorp Vault integration for secrets management.

**Authentication Settings:**
- **API_KEY_SECRET** — Secret key for validating API requests (X-API-Key header)
- **JWT_SECRET_KEY** — Secret key for signing/verifying JWT tokens

**Vault Integration (Optional):**
- **VAULT_ADDR** — HashiCorp Vault server URL (e.g. https://vault.example.com)
- **VAULT_TOKEN** — Vault authentication token

**How to Configure:**
1. Generate strong random secrets (use a password manager or \`openssl rand -hex 32\`)
2. Enter the API_KEY_SECRET (used by the frontend to authenticate to the backend)
3. Enter the JWT_SECRET_KEY (used for login sessions)
4. Optionally configure Vault for centralized secrets management
5. Click **Save**

**Security Best Practices:**
- Use secrets that are at least 32 characters long
- Rotate secrets every 90 days
- Never commit secrets to git
- Use Vault in production for automatic secret rotation
- Enable MFA for all admin accounts

**Vault Benefits:**
- Centralized secrets management
- Automatic secret rotation
- Audit logging of secret access
- Dynamic secrets (database credentials that expire)`,
      ar: `**ما يفعله:**
تبويب الأمان يكوّن مفاتيح المصادقة وأسرار JWT وتكامل HashiCorp Vault الاختياري لإدارة الأسرار.

**إعدادات المصادقة:**
- **API_KEY_SECRET** — المفتاح السري للتحقق من طلبات API (ترويسة X-API-Key)
- **JWT_SECRET_KEY** — المفتاح السري لتوقيع/التحقق من رموز JWT

**تكامل Vault (اختياري):**
- **VAULT_ADDR** — رابط خادم HashiCorp Vault (مثل https://vault.example.com)
- **VAULT_TOKEN** — رمز مصادقة Vault

**كيفية التكوين:**
1. توليد أسرار عشوائية قوية (استخدم مدير كلمات مرور أو \`openssl rand -hex 32\`)
2. أدخل API_KEY_SECRET (تستخدمه الواجهة للمصادقة على الخادم)
3. أدخل JWT_SECRET_KEY (تستخدم لجلسات تسجيل الدخول)
4. اخترياً عيّن Vault لإدارة الأسرار المركزية
5. انقر **حفظ**

**أفضل ممارسات الأمان:**
- استخدم أسرار بطول 32 حرف على الأقل
- دور الأسرار كل 90 يوماً
- لا ترفع الأسرار إلى git أبداً
- استخدم Vault في الإنتاج للتدوير التلقائي للأسرار
- فعّل MFA لجميع حسابات المسؤولين

**فوائد Vault:**
- إدارة أسرار مركزية
- تدوير أسرار تلقائي
- سجل تدقيق للوصول للأسرار
- أسرار ديناميكية (بيانات اعتماد قاعدة البيانات تنتهي)`,
    },
    tags: ["security", "vault", "jwt", "api-key", "secret", "أمان", "أسرار"],
    navigateTo: "/settings",
    relatedTopics: ["settings.backend", "troubleshooting.auth"],
  },
  {
    id: "settings.integration",
    category: "settings",
    title: {
      en: "System Integration (ETAP, SCADA, Email)",
      ar: "تكامل النظام (ETAP, SCADA, البريد)",
    },
    description: {
      en: "Configure ETAP desktop, SCADA zenon, and email alert integrations",
      ar: "تكوين تكاملات ETAP المكتبي و SCADA zenon وتنبيهات البريد",
    },
    content: {
      en: `**What it does:**
The Integration tab configures connections to external engineering systems: ETAP desktop, SCADA zenon, and email alerts.

**ETAP Integration:**
- **ETAP_LICENSE_PATH** — Path to the ETAP license file on the Windows worker
- **ETAP_WORKER_URL** — URL of the ETAP Worker Service (e.g. http://192.168.1.100:8080)
- Requires: ETAP licensed and installed on Windows, ETAP Worker Service running

**SCADA Integration (Copa-Data zenon):**
- **SCADA_SYSTEM_TYPE** — Type of SCADA system (default: Copa-Data zenon SCADA)
- **SCADA_SERVER_URL** — HTTP endpoint of the zenon REST API (e.g. http://localhost:8080/zenon)
- **SCADA_PROJECT_NAME** — Active zenon project name (default: ETAP_Zenon_Sync)
- **SCADA_SYNC_INTERVAL_SEC** — Polling interval in seconds (default: 10)
- **SCADA_API_KEY** — Authorization token for secure SCADA data transfer

**Email Alerts:**
- **SMTP_SERVER** — SMTP server hostname (e.g. smtp.gmail.com)
- **SMTP_PORT** — SMTP port (587 for TLS, 465 for SSL)
- **SMTP_USERNAME** — Email account username
- **ALERT_EMAIL_TO** — Recipient email for system alerts

**Tips:**
- Test each integration with its respective "Test Connection" button before saving
- For SCADA, use a low sync interval (5-10s) for near-real-time monitoring
- For email, use an app-specific password if your provider supports it`,
      ar: `**ما يفعله:**
تبويب التكامل يكوّن الاتصالات بأنظمة هندسية خارجية: ETAP المكتبي و SCADA zenon وتنبيهات البريد.

**تكامل ETAP:**
- **ETAP_LICENSE_PATH** — مسار ملف ترخيص ETAP على عامل Windows
- **ETAP_WORKER_URL** — رابط خدمة ETAP العاملة (مثل http://192.168.1.100:8080)
- متطلبات: ETAP مرخص ومثبت على Windows، خدمة ETAP العاملة تعمل

**تكامل SCADA (Copa-Data zenon):**
- **SCADA_SYSTEM_TYPE** — نوع نظام الإسكادا (افتراضي: Copa-Data zenon SCADA)
- **SCADA_SERVER_URL** — رابط نقطة نهاية zenon REST API (مثل http://localhost:8080/zenon)
- **SCADA_PROJECT_NAME** — اسم مشروع zenon النشط (افتراضي: ETAP_Zenon_Sync)
- **SCADA_SYNC_INTERVAL_SEC** — فترة الاقتراع بالثواني (افتراضي: 10)
- **SCADA_API_KEY** — رمز تفويض لنقل بيانات SCADA الآمن

**تنبيهات البريد:**
- **SMTP_SERVER** — خادم SMTP (مثل smtp.gmail.com)
- **SMTP_PORT** — منفذ SMTP (587 لـ TLS، 465 لـ SSL)
- **SMTP_USERNAME** — اسم مستخدم البريد
- **ALERT_EMAIL_TO** — بريد المستلم لتنبيهات النظام

**نصائح:**
- اختبر كل تكامل بزر "اختبار الاتصال" قبل الحفظ
- لـ SCADA، استخدم فترة مزامنة منخفضة (5-10 ثواني) لمراقبة شبه مباشرة
- للبريد، استخدم كلمة مرور خاصة بالتطبيق إذا كان مزودك يدعمها`,
    },
    tags: ["integration", "etap", "scada", "zenon", "email", "smtp", "تكامل", "إسكادا"],
    navigateTo: "/settings",
    relatedTopics: ["etap-integration.overview", "scada-integration.overview"],
  },
  {
    id: "settings.performance",
    category: "settings",
    title: { en: "Performance & Observability", ar: "الأداء والمراقبة" },
    description: {
      en: "Configure rate limiting, circuit breaker, caching, and Prometheus metrics",
      ar: "تكوين تقييد المعدل وقاطع الدائرة والذاكرة المؤقتة ومقاييس Prometheus",
    },
    content: {
      en: `**What it does:**
The Performance tab configures observability, rate limiting, circuit breaker, and feature flags for the engineering service.

**Observability:**
- **HEALTH_CHECK_API_URL** — External health check endpoint (leave empty to skip)
- **PROMETHEUS_ENABLED** — Enable Prometheus metrics export (true/false)
- **PROMETHEUS_PORT** — Port for Prometheus metrics server (default: 9090)

**Rate Limiting & Circuit Breaker:**
- **RATE_LIMIT_REQUESTS_PER_MINUTE** — Max API requests per minute per user (default: 60)
- **CIRCUIT_BREAKER_FAILURE_THRESHOLD** — Failures before circuit opens (default: 3)
- **MAX_BODY_SIZE** — Max request body size in bytes (default: 100000)

**Feature Flags:**
- **ENABLE_ASYNC_EXECUTION** — Run studies asynchronously (true/false, default: true)
- **ENABLE_CACHING** — Cache study results (true/false, default: true)
- **ENABLE_OBSERVABILITY** — Log metrics and traces (true/false, default: true)

**How to Configure:**
1. Set RATE_LIMIT to prevent abuse (60 req/min is typical)
2. Set CIRCUIT_BREAKER to 3-5 for resilience
3. Enable Prometheus for production monitoring
4. Toggle feature flags based on your needs
5. Click **Save**

**Tips:**
- Disable caching during development for fresh results
- Enable async execution for long-running studies
- Prometheus metrics are available at /metrics endpoint`,
      ar: `**ما يفعله:**
تبويب الأداء يكوّن المراقبة وتقييد المعدل وقاطع الدائرة وأعلام الميزات للخدمة الهندسية.

**المراقبة:**
- **HEALTH_CHECK_API_URL** — رابط نقطة نهاية فحص الصحة الخارجية (اترك فارغاً للتخطي)
- **PROMETHEUS_ENABLED** — تفعيل تصدير مقاييس Prometheus (true/false)
- **PROMETHEUS_PORT** — منفذ خادم مقاييس Prometheus (افتراضي: 9090)

**تقييد المعدل وقاطع الدائرة:**
- **RATE_LIMIT_REQUESTS_PER_MINUTE** — أقصى طلبات API في الدقيقة لكل مستخدم (افتراضي: 60)
- **CIRCUIT_BREAKER_FAILURE_THRESHOLD** — حالات فشل قبل فتح الدائرة (افتراضي: 3)
- **MAX_BODY_SIZE** — الحد الأقصى لحجم جسم الطلب بالبايت (افتراضي: 100000)

**أعلام الميزات:**
- **ENABLE_ASYNC_EXECUTION** — تشغيل الدراسات بشكل غير متزامن (true/false، افتراضي: true)
- **ENABLE_CACHING** — تخزين نتائج الدراسات مؤقتاً (true/false، افتراضي: true)
- **ENABLE_OBSERVABILITY** — تسجيل المقاييس والتتبع (true/false، افتراضي: true)

**كيفية التكوين:**
1. عيّن RATE_LIMIT لمنع الاستغلال (60 req/min نموذجي)
2. عيّن CIRCUIT_BREAKER إلى 3-5 للصلابة
3. فعّل Prometheus لمراقبة الإنتاج
4. بدّل أعلام الميزات بناءً على احتياجاتك
5. انقر **حفظ**

**نصائح:**
- عطّل التخزين المؤقت أثناء التطوير لنتائج جديدة
- فعّل التنفيذ غير المتزامن للدراسات طويلة التشغيل
- مقاييس Prometheus متاحة عند نقطة نهاية /metrics`,
    },
    tags: ["performance", "prometheus", "rate-limit", "circuit-breaker", "cache", "أداء", "مراقبة"],
    navigateTo: "/settings",
    relatedTopics: ["diagnostics.overview", "settings.backend"],
  },
  {
    id: "settings.vision",
    category: "settings",
    title: { en: "Vision API Keys", ar: "مفاتيح API الرؤية" },
    description: {
      en: "Configure vision-capable LLM provider API keys",
      ar: "تكوين مفاتيح مزودي LLM القادرون على الرؤية",
    },
    content: {
      en: `**What it does:**
The Vision API Keys tab configures API keys for LLM providers that support image/multimodal inputs. These are used by features like "snap-to-analyze" in the Grid Editor and asset photo recognition.

**Supported Vision Providers:**
- **OpenAI** — GPT-4o, GPT-4o-mini (vision enabled by default)
- **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus (vision enabled)
- **Google Gemini** — Gemini 1.5 Pro/Flash (vision enabled)
- **Groq** — Llama 3.3 70B (vision via Groq)
- **OpenRouter** — Models with vision capabilities

**Configuration:**
1. Navigate to the Vision API Keys tab in Settings
2. Select a vision provider from the list
3. Enter your API key
4. Click **Save Vision Key**
5. The key is validated and stored (obfuscated)

**How to Use:**
- In Grid Editor: Click the camera icon on any component to analyze its image
- In Asset Management: Upload a photo of equipment for AI-powered identification
- The vision model returns: equipment type, likely model, and maintenance notes

**Privacy:**
- Images are sent to the vision provider's API for analysis
- Images are not stored on our servers
- Review your provider's privacy policy`,
      ar: `**ما يفعله:**
تبويب مفاتيح API الرؤية يكوّن مفاتيح API لمزودي LLM الذين يدعمون المدخلات متعددة الوسائط (صور). تُستخدم هذه الميزات مثل "التقاط للتحليل" في محرر الشبكة والتعرف على صور الأصول.

**مزودو الرؤية المدعومون:**
- **OpenAI** — GPT-4o، GPT-4o-mini (الرؤية مفعلة افتراضياً)
- **Anthropic** — Claude 3.5 Sonnet، Claude 3 Opus (الرؤية مفعلة)
- **Google Gemini** — Gemini 1.5 Pro/Flash (الرؤية مفعلة)
- **Groq** — Llama 3.3 70B (رؤية عبر Groq)
- **OpenRouter** — النماذج ذات قدرات الرؤية

**التكوين:**
1. انتقل إلى تبويب مفاتيح API الرؤية في الإعدادات
2. اختر مزود رؤية من القائمة
3. أدخل مفتاح API
4. انقر **حفظ مفتاح الرؤية**
5. يتم التحقق من المفتاح وحفظه (مشوّه)

**كيفية الاستخدام:**
- في محرر الشبكة: انقر على أيقونة الكاميرا على أي مكون لتحليل صورته
- في إدارة الأصول: ارفع صورة المعدة untuk التعرف عليها بالذكاء الاصطناعي
- نموذج الرؤية يُرجع: نوع المعدة، الموديل المحتمل، وملاحظات الصيانة

**الخصوصية:**
- الصور مرسلة إلى API مزود الرؤية للتحليل
- الصور لا تُخزن على خوادمنا
- راجع سياسة الخصوصية لمزودك`,
    },
    tags: ["vision", "image", "multimodal", "gpt-4o", "claude", "gemini", "رؤية", "صورة"],
    navigateTo: "/settings",
    relatedTopics: ["settings.ai-providers", "grid-editor.overview"],
  },

  // ─── Code Guard ───────────────────────────────────────────────────
  {
    id: "code-guard.overview",
    category: "engineering",
    title: { en: "Code Guard", ar: "حارس الكود" },
    description: {
      en: "AI-powered code review for engineering calculations",
      ar: "مراجعة أكواد بالذكاء الاصطناعي للحسابات الهندسية",
    },
    content: {
      en: `**What it does:**
Code Guard reviews your engineering Python/code for correctness, safety, and compliance with IEEE/IEC standards. It catches common bugs (unit conversion errors, missing factors, wrong formulas) before they cause real-world failures.

**How to Use:**
1. Navigate to **Code Guard** from the sidebar
2. Paste your code in the editor (Python, MATLAB, or pseudo-code)
3. Optionally select a specific standard (IEEE 1584, IEC 60909, etc.)
4. Click **Review Code**
5. The agent returns:
   - Issues found (with severity: error/warning/info)
   - Suggested fixes (with code snippets)
   - Standard references (clause numbers)

**Common Issues Detected:**
- Unit conversion errors (per-unit vs. actual ohms)
- Missing c-factors in IEC 60909
- Wrong electrode configuration in IEEE 1584
- Off-by-one in bus indexing
- Floating-point precision issues
- Missing validation for negative values

**Tips:**
- Be explicit about units in comments (e.g. "# voltage in kV")
- Reference the standard you're targeting
- The reviewer has access to the same IEEE/IEC knowledge base as the AI Assistant`,
      ar: `**ما يفعله:**
يراجع حارس الكود أكوادك الهندسية (Python/أكواد) للتأكد من الصحة والسلامة والامتثال لمعايير IEEE/IEC. يلتقط الأخطاء الشائعة (أخطاء تحويل الوحدات، العوامل المفقودة، الصيغ الخاطئة) قبل أن تسبب فشلاً في العالم الحقيقي.

**كيفية الاستخدام:**
1. انتقل إلى **حارس الكود** من الشريط الجانبي
2. الصق الكود في المحرر (Python، MATLAB، أو شبه كود)
3. اخترياً حدد معياراً محدداً (IEEE 1584، IEC 60909، إلخ)
4. انقر على **مراجعة الكود**
5. يُرجع الوكيل:
   - المشاكل المكتشفة (مع الشدة: خطأ/تحذير/معلومة)
   - الإصلاحات المقترحة (مع مقتطفات الكود)
   - مراجع المعايير (أرقام البنود)

**المشاكل الشائعة المكتشفة:**
- أخطاء تحويل الوحدات (per-unit مقابل أوم فعلية)
- عوامل c مفقودة في IEC 60909
- تكوين القطب الخاطئ في IEEE 1584
- خطأ بمقدار واحد في فهرسة الباص
- مشاكل دقة الفاصلة العائمة
- التحقق المفقود للقيم السالبة

**نصائح:**
- كن صريحاً بشأن الوحدات في التعليقات (مثل "# الجهد بـ kV")
- اذكر المعيار الذي تستهدفه
- للمراجع وصول إلى نفس قاعدة المعرفة IEEE/IEC مثل المساعد الذكي`,
    },
    tags: ["code", "guard", "review", "ai", "كود", "حارس", "مراجعة"],
    navigateTo: "/code-guard",
    relatedTopics: ["ai-assistant.overview"],
  },

  // ─── Data Import / Export ─────────────────────────────────────────
  {
    id: "data-import.overview",
    category: "engineering",
    title: { en: "Data Import", ar: "استيراد البيانات" },
    description: {
      en: "Import engineering data from CSV, JSON, Excel, ETAP files",
      ar: "استيراد بيانات هندسية من CSV، JSON، Excel، ملفات ETAP",
    },
    content: {
      en: `**What it does:**
The Data Import page lets you bulk-import engineering data (buses, lines, generators, loads, assets) from external files.

**Supported Formats:**
- CSV — comma-separated values
- JSON — structured nested data
- Excel (.xlsx, .xls) — with sheet selection
- ETAP (.etap, .etapz) — ETAP project files
- CIM (.xml) — Common Information Model (IEC 61970)

**How to Use:**
1. Navigate to **Data Import** from the sidebar
2. Select the data type to import (buses, lines, generators, etc.)
3. Choose the file format
4. Click **Choose File** and select your file
5. Preview the parsed data in the table
6. Map columns to ETAP fields if needed
7. Click **Import** to load into the current project

**Validation:**
- Required fields check
- Data type validation (numbers, ranges)
- Reference integrity (e.g. line.from_bus_id must exist)
- Duplicate detection

**Tips:**
- Download the CSV template for each data type to ensure correct column names
- For large imports (>1000 rows), use CSV (faster than Excel)
- Imports are transactional — if any row fails, the entire import is rolled back`,
      ar: `**ما يفعله:**
تتيح لك صفحة استيراد البيانات استيراد بيانات هندسية مجمّعة (باصات، خطوط، مولدات، أحمال، أصول) من ملفات خارجية.

**التنسيقات المدعومة:**
- CSV — قيم مفصولة بفواصل
- JSON — بيانات متداخلة منظمة
- Excel (.xlsx، .xls) — مع اختيار الورقة
- ETAP (.etap، .etapz) — ملفات مشروع ETAP
- CIM (.xml) — نموذج المعلومات الشائع (IEC 61970)

**كيفية الاستخدام:**
1. انتقل إلى **استيراد البيانات** من الشريط الجانبي
2. اختر نوع البيانات للاستيراد (باصات، خطوط، مولدات، إلخ)
3. اختر تنسيق الملف
4. انقر على **اختر ملف** واختر ملفك
5. عاين البيانات المحللة في الجدول
6. عيّن الأعمدة لحقول ETAP إن لزم
7. انقر على **استيراد** للتحميل في المشروع الحالي

**التحقق:**
- التحقق من الحقول المطلوبة
- التحقق من نوع البيانات (أرقام، نطاقات)
- سلامة المرجع (مثل line.from_bus_id يجب أن يكون موجوداً)
- كشف التكرار

**نصائح:**
- نزّل قالب CSV لكل نوع بيانات لضمان أسماء الأعمدة الصحيحة
- للاستيرادات الكبيرة (>1000 صف)، استخدم CSV (أسرع من Excel)
- الاستيرادات معاملاتية — إذا فشل أي صف، يتم التراجع عن الاستيراد بالكامل`,
    },
    tags: ["import", "csv", "json", "excel", "data", "استيراد", "بيانات"],
    navigateTo: "/data-import",
    relatedTopics: ["data-export.overview", "projects.create"],
  },
  {
    id: "data-export.overview",
    category: "engineering",
    title: { en: "Data Export", ar: "تصدير البيانات" },
    description: {
      en: "Export engineering data to CSV, JSON, Excel, PDF",
      ar: "تصدير بيانات هندسية إلى CSV، JSON، Excel، PDF",
    },
    content: {
      en: `**What it does:**
The Data Export page lets you export your engineering data and study results to various formats for sharing, archiving, or importing into other tools.

**Supported Formats:**
- CSV — for spreadsheet analysis
- JSON — for API integration
- Excel (.xlsx) — formatted with headers and styling
- PDF — formatted reports with tables and figures
- CIM XML — for interchange with other utility systems

**How to Use:**
1. Navigate to **Data Export** from the sidebar
2. Select the data to export:
   - Project configuration
   - Study results (current or all)
   - Asset register
   - Audit log
3. Choose the export format
4. Configure options (date range, include secrets, etc.)
5. Click **Export**
6. The file downloads to your browser

**Tips:**
- For compliance audits, export to PDF with the audit log included
- For sharing with team members who don't have AhmedETAP, use Excel
- For backup, use JSON (preserves all data structures)
- Exported files never include secrets (API keys, tokens) — those stay in your browser`,
      ar: `**ما يفعله:**
تتيح لك صفحة تصدير البيانات تصدير بياناتك الهندسية ونتائج الدراسات إلى تنسيقات مختلفة للمشاركة أو الأرشفة أو الاستيراد في أدوات أخرى.

**التنسيقات المدعومة:**
- CSV — لتحليل جداول البيانات
- JSON — لتكامل API
- Excel (.xlsx) — منسق مع الترويسات والتنسيق
- PDF — تقارير منسقة مع جداول وأشكال
- CIM XML — للتبادل مع أنظمة المرافق الأخرى

**كيفية الاستخدام:**
1. انتقل إلى **تصدير البيانات** من الشريط الجانبي
2. اختر البيانات للتصدير:
   - تكوين المشروع
   - نتائج الدراسة (الحالية أو الكل)
   - سجل الأصول
   - سجل التدقيق
3. اختر تنسيق التصدير
4. قوم الخيارات (النطاق الزمني، تضمين الأسرار، إلخ)
5. انقر على **تصدير**
6. يتم نزول الملف إلى متصفحك

**نصائح:**
- لتدقيق الامتثال، صدّر إلى PDF مع سجل التدقيق المضمن
- للمشاركة مع أعضاء الفريق الذين ليس لديهم AhmedETAP، استخدم Excel
- للنسخ الاحتياطي، استخدم JSON (يحفظ جميع هياكل البيانات)
- الملفات المصدّرة لا تتضمن أبداً الأسرار (مفاتيح API، الرموز) — تبقى في متصفحك`,
    },
    tags: ["export", "csv", "json", "excel", "pdf", "data", "تصدير", "بيانات"],
    navigateTo: "/data-export",
    relatedTopics: ["data-import.overview", "reports.generate"],
  },

  // ─── Administration ───────────────────────────────────────────────
  {
    id: "administration.overview",
    category: "settings",
    title: { en: "Administration", ar: "الإدارة" },
    description: {
      en: "User management, roles, and system administration",
      ar: "إدارة المستخدمين والأدوار وإدارة النظام",
    },
    content: {
      en: `**What it does:**
The Administration page (admin-only) lets you manage users, roles, and system-wide settings.

**Features (admin role required):**
- **User List** — view all registered users
- **Deactivate User** — soft-delete a user (set is_active = false)
- **View Audit Log** — see all user actions (login, study runs, settings changes)
- **System Metrics** — request counts, error rates, response times

**Roles:**
- \`admin\` — full access including user management
- \`engineer\` — default role, can run studies and manage own projects
- \`viewer\` — read-only access (cannot run studies or modify settings)

**Permissions Matrix:**
| Action | admin | engineer | viewer |
|--------|-------|----------|--------|
| View dashboard | ✓ | ✓ | ✓ |
| Run studies | ✓ | ✓ | ✗ |
| Create projects | ✓ | ✓ | ✗ |
| Delete projects | ✓ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ |
| View audit log | ✓ | ✗ | ✗ |

**Tips:**
- Only admins can access /admin route
- Deactivated users cannot log in but their data is preserved
- Audit log is retained for 90 days`,
      ar: `**ما يفعله:**
تتيح لك صفحة الإدارة (للمسؤولين فقط) إدارة المستخدمين والأدوار والإعدادات على مستوى النظام.

**الميزات (تتطلب دور المسؤول):**
- **قائمة المستخدمين** — عرض جميع المستخدمين المسجلين
- **تعطيل مستخدم** — حذف ناعم (تعيين is_active = false)
- **عرض سجل التدقيق** — رؤية جميع إجراءات المستخدم (تسجيل الدخول، تشغيل الدراسات، تغييرات الإعدادات)
- **مقاييس النظام** — عدد الطلبات، معدلات الأخطاء، أوقات الاستجابة

**الأدوار:**
- \`admin\` — وصول كامل بما في ذلك إدارة المستخدمين
- \`engineer\` — الدور الافتراضي، يمكن تشغيل الدراسات وإدارة مشاريعه الخاصة
- \`viewer\` — وصول للقراءة فقط (لا يمكن تشغيل الدراسات أو تعديل الإعدادات)

**مصفوفة الصلاحيات:**
| الإجراء | admin | engineer | viewer |
|--------|-------|----------|--------|
| عرض لوحة التحكم | ✓ | ✓ | ✓ |
| تشغيل الدراسات | ✓ | ✓ | ✗ |
| إنشاء المشاريع | ✓ | ✓ | ✗ |
| حذف المشاريع | ✓ | ✗ | ✗ |
| إدارة المستخدمين | ✓ | ✗ | ✗ |
| عرض سجل التدقيق | ✓ | ✗ | ✗ |

**نصائح:**
- فقط المسؤولون يمكنهم الوصول إلى مسار /admin
- المستخدمون المعطلون لا يمكنهم تسجيل الدخول لكن بياناتهم محفوظة
- سجل التدقيق محفوظ لمدة 90 يوماً`,
    },
    tags: ["admin", "user", "management", "role", "إدارة", "مستخدم", "دور"],
    navigateTo: "/admin",
    relatedTopics: ["settings.backend", "troubleshooting.auth"],
  },

  // ─── Diagnostics ──────────────────────────────────────────────────
  {
    id: "diagnostics.overview",
    category: "troubleshooting",
    title: { en: "Diagnostics", ar: "التشخيص" },
    description: {
      en: "System health checks, logs, and performance metrics",
      ar: "فحوصات صحة النظام والسجلات ومقاييس الأداء",
    },
    content: {
      en: `**What it does:**
The Diagnostics page provides real-time system health monitoring, log viewing, and performance metrics for troubleshooting.

**Sections:**
1. **Health Checks** — live status of all subsystems
   - Backend connectivity
   - Database connection
   - Redis cache
   - ETAP worker (if configured)
   - External services (LangWatch, Smithery, etc.)

2. **Logs** — real-time log stream
   - Filter by level (INFO, WARN, ERROR, DEBUG)
   - Filter by source (api, engine, agent, integration)
   - Search by text
   - Export to file

3. **Performance Metrics**
   - API response times (p50, p95, p99)
   - Request rates (req/sec)
   - Error rates (% by status code)
   - Memory and CPU usage

4. **Trace IDs** — search for a specific request trace

**How to Use:**
- When something fails, check Health Checks first
- Then check Logs for the error message
- Use the trace_id from the error response to find related log entries
- Performance metrics help identify slow endpoints`,
      ar: `**ما يفعله:**
توفر صفحة التشخيص مراقبة صحة النظام في الوقت الفعلي وعرض السجلات ومقاييس الأداء لاستكشاف الأخطاء وإصلاحها.

**الأقسام:**
1. **فحوصات الصحة** — الحالة المباشرة لجميع الأنظمة الفرعية
   - اتصال الخادم
   - اتصال قاعدة البيانات
   - ذاكرة التخزين المؤقت Redis
   - عامل ETAP (إذا تم تكوينه)
   - الخدمات الخارجية (LangWatch، Smithery، إلخ)

2. **السجلات** — تدفق السجلات المباشر
   - الفلترة حسب المستوى (INFO، WARN، ERROR، DEBUG)
   - الفلترة حسب المصدر (api، engine، agent، integration)
   - البحث بالنص
   - التصدير إلى ملف

3. **مقاييس الأداء**
   - أوقات استجابة API (p50، p95، p99)
   - معدلات الطلبات (req/sec)
   - معدلات الأخطاء (% حسب كود الحالة)
   - استخدام الذاكرة و CPU

4. **معرفات التتبع** — البحث عن تتبع طلب محدد

**كيفية الاستخدام:**
- عند فشل شيء، تحقق من فحوصات الصحة أولاً
- ثم تحقق من السجلات لرسالة الخطأ
- استخدم trace_id من استجابة الخطأ للعثور على إدخالات السجل ذات الصلة
- تساعد مقاييس الأداء في تحديد النقاط البطيئة`,
    },
    tags: ["diagnostics", "health", "logs", "metrics", "تشخيص", "صحة", "سجلات"],
    navigateTo: "/diagnostics",
    relatedTopics: ["troubleshooting.backend", "troubleshooting.api"],
  },

  // ─── Logs Page ────────────────────────────────────────────────────
  {
    id: "logs.overview",
    category: "troubleshooting",
    title: { en: "Logs", ar: "السجلات" },
    description: {
      en: "Real-time application logs with filtering",
      ar: "سجلات التطبيق المباشرة مع الفلترة",
    },
    content: {
      en: `**What it does:**
The Logs page shows a real-time stream of application logs with powerful filtering.

**Features:**
- Live log stream (auto-refresh)
- Filter by level: INFO, WARN, ERROR, DEBUG
- Filter by source: api, engine, agent, security, integration
- Full-text search
- Timestamp range filter
- Click a log entry for full details
- Export filtered logs to JSON or text file

**Log Levels:**
- \`DEBUG\` — verbose diagnostic info (typically off in production)
- \`INFO\` — normal operation events
- \`WARN\` — unexpected but non-fatal conditions
- \`ERROR\` — failures that need attention

**Tips:**
- When debugging, start with ERROR level, then expand to WARN
- The trace_id field lets you follow a single request across services
- Logs are kept for 7 days by default (configurable in admin settings)
- Use the search box to find specific error messages or user IDs`,
      ar: `**ما يفعله:**
تعرض صفحة السجلات تدفقاً مباشراً لسجلات التطبيق مع فلترة قوية.

**الميزات:**
- تدفق السجلات المباشر (تحديث تلقائي)
- الفلترة حسب المستوى: INFO، WARN، ERROR، DEBUG
- الفلترة حسب المصدر: api، engine، agent، security، integration
- بحث نصي كامل
- فلتر النطاق الزمني
- انقر على إدخال السجل للتفاصيل الكاملة
- تصدير السجلات المفلترة إلى JSON أو ملف نصي

**مستويات السجل:**
- \`DEBUG\` — معلومات تشخيصية مطوّلة (عادةً مغلقة في الإنتاج)
- \`INFO\` — أحداث التشغيل العادية
- \`WARN\` — ظروف غير متوقعة لكن غير قاتلة
- \`ERROR\` — فشل يحتاج اهتماماً

**نصائح:**
- عند التصحيح، ابدأ بمستوى ERROR، ثم وسّع إلى WARN
- يتيح لك حقل trace_id متابعة طلب واحد عبر الخدمات
- تُحفظ السجلات لمدة 7 أيام افتراضياً (قابلة للتكوين في إعدادات المسؤول)
- استخدم صندوق البحث للعثور على رسائل خطأ محددة أو معرفات المستخدم`,
    },
    tags: ["logs", "stream", "filter", "debug", "سجلات", "تصحيح"],
    navigateTo: "/logs",
    relatedTopics: ["diagnostics.overview", "troubleshooting.backend"],
  },

  // ─── SCADA Integration ─────────────────────────────────────────────
  {
    id: "scada-integration.overview",
    category: "digital-twin",
    title: { en: "SCADA Integration (zenon)", ar: "تكامل الإسكادا (زينون)" },
    description: {
      en: "Connect and sync with Copa-Data zenon SCADA system",
      ar: "الاتصال والمزامنة مع نظام إسكادا زينون من كوبا-داتا",
    },
    content: {
      en: `**What it does:**
The SCADA Integration page connects AhmedETAP with a Copa-Data zenon SCADA server to stream real-time telemetry (voltages, currents, frequencies) and receive alarms/events.

**Required Configuration:**
- **Zenon Server URL** — e.g. \`http://localhost:8080/zenon\`
- **API Key / Token** — authentication token for the SCADA API
- **Project Name** — zenon project identifier (default: \`ETAP_Zenon_Sync\`)
- **Sync Rate (sec)** — polling interval in seconds (default: 2)

**Features:**
1. **Live Telemetry Sync** — WebSocket or HTTP fallback polling
2. **Alarm Stream** — real-time alarm ingestion with severity levels
3. **Connection Trace Logs** — debug logs for connection lifecycle
4. **Offline Simulation** — local simulated feed when zenon is unreachable

**How to Use:**
1. Enter your zenon server URL and API token
2. Click **Save SCADA Configuration** to persist to localStorage
3. Click **Ping Server** to verify connectivity and measure latency
4. Click **Start Live** to begin streaming data
5. Monitor telemetry table, alarm stream, and connection logs

**Simulation Mode:**
Enable the **Offline Simulation Mode** checkbox to test without a real zenon runtime. The system generates fluctuating values and random alarms for demonstration.

**Troubleshooting:**
- "Connection failed" — ensure zenon runtime is running and CORS is configured
- WebSocket fails — falls back automatically to HTTP polling
- No telemetry data — check API key permissions and project name`,
      ar: `**ما يفعله:**
تتصل صفحة تكامل الإسكادا بخادم إسكادا زينون من كوبا-داتا لبث البيانات القياسية الحية (جهود، تيارات، ترددات) واستقبال الإنذارات/الأحداث.

**التكوين المطلوب:**
- **رابط خادم زينون** — مثل \`http://localhost:8080/zenon\`
- **مفتاح API / رمز** — رمز مصادقة لـ API الإسكادا
- **اسم المشروع** — معرف مشروع زينون (افتراضي: \`ETAP_Zenon_Sync\`)
- **معدل التحديث (ثانية)** — فترة الاقتراع بالثواني (افتراضي: 2)

**الميزات:**
1. **مزامنة البيانات الحية** — WebSocket أو اقتراع HTTP احتياطي
2. **بث الإنذارات** — استهلاك إنذارات فورية بمستويات خطورة
3. **سجلات تتبع الاتصال** — سجلات تشخيص لدورة حياة الاتصال
4. **محاكاة غير متصلة** — تغذية محلية محاكاة عند عدم توفر زينون

**كيفية الاستخدام:**
1. أدخل رابط خادم زينون ورمز API
2. انقر **حفظ إعدادات الربط** للتخزين المحلي
3. انقر **فحص الاتصال** للتحقق من الاتصال وقياس زمن الاستجابة
4. انقر **تشغيل البث** لبدء تدفق البيانات
5. راقب جدول البيانات القياسية وبث الإنذارات وسجلات الاتصال

**وضع المحاكاة:**
فعّل خانة **تفعيل بيئة المحاكاة المحلية** للاختبار بدون تشغيل زينون فعلي. يولد النظام قيمًا متقلبة وإنذارات عشوائية للعرض.

**استكشاف الأخطاء:**
- "فشل الاتصال" — تأكد من تشغيل zenon وتكوين CORS
- WebSocket يفشل — يحول تلقائيًا لاقتراع HTTP
- لا توجد بيانات — تحقق من صلاحيات مفتاح API واسم المشروع`,
    },
    tags: [
      "scada",
      "zenon",
      "copa-data",
      "telemetry",
      "websocket",
      "alarm",
      "إسكادا",
      "زينون",
      "هاتف",
    ],
    navigateTo: "/scada",
    relatedTopics: ["digital-twin.overview", "integration.scada"],
  },
  {
    id: "grid-editor.overview",
    category: "engineering",
    title: { en: "Grid Editor", ar: "محرر الشبكة" },
    description: {
      en: "Interactive power system diagram editor for buses, lines, and transformers",
      ar: "محرر رسومي تفاعلي لنظام القدرة: باصات، خطوط، محولات",
    },
    content: {
      en: `**What it does:**
The Grid Editor provides a visual canvas for building and editing single-line diagrams (SLDs) of power systems. Drag components from the palette, connect them with lines, and configure electrical parameters.

**Component Palette:**
- **Buses** — Slack, PV, PQ bus types with voltage/power setpoints
- **Lines** — Transmission/distribution lines with R, X, B parameters
- **Transformers** — Two-winding and three-winding with tap ratios
- **Generators** — Synchronous machines with P/Q/V setpoints
- **Loads** — Constant power/current/impedance models
- **Capacitors/Reactors** — Shunt compensation devices

**How to Use:**
1. Select a component from the left palette
2. Click on the canvas to place it
3. Drag from a component's port to another to connect
4. Click a placed component to edit its properties in the right panel
5. Use the toolbar actions: Save, Undo/Redo, Zoom, Export

**Keyboard Shortcuts:**
- \`Delete\` — remove selected component
- \`Ctrl+Z\` — undo
- \`Ctrl+Shift+Z\` — redo
- \`Ctrl+S\` — save diagram
- \`Ctrl+A\` — select all

**Tips:**
- Snap-to-grid keeps diagram tidy
- Ports highlight when dragging a connection near them
- The properties panel shows context-sensitive fields based on component type`,
      ar: `**ما يفعله:**
يوفر محرر الشبكة لوحة رسم مرئية لبناء وتعديل المخططات أحادية الخط (SLD) لأنظمة القدرة. اسحب المكونات من اللوحة، اربطها بالخطوط، وقم بتكوين المعلمات الكهربية.

**لوحة المكونات:**
- **الباصات** — أنواع slack و PV و PQ مع تحديد الجهد/القدرة
- **الخطوط** — خطوط نقل/توزيع بمعاملات R و X و B
- **المحولات** — ثنائي وثلاثي اللفات مع نسب التحويل
- **المولدات** — آلات تزامنية مع تحديد P/Q/V
- **الأحمال** — نماذج قدرة/تيار/مقاومة ثابتة
- **مكثفات/مفاعلات** — أجهزة تعويض موازٍ

**كيفية الاستخدام:**
1. اختر مكونًا من اللوحة اليسرى
2. انقر على اللوحة لوضعه
3. اسحب من منفذ المكون إلى آخر للاتصال
4. انقر على المكون الموجود لتعديل خصائصه في اللوحة اليمنى
5. استخدم أزرار شريط الأدوات: حفظ، تراجع/إعادة، تكبير، تصدير

**نصائح:**
- المحاذاة للشبكة تحافظ على ترتيب الرسم
- تظهر المنافذ عند السحب قربها
- تعرض لوحة الخصائص حقول حساسة لنوع المكون`,
    },
    tags: ["grid", "editor", "sld", "diagram", "canvas", "محرر", "شبكة", "رسم"],
    navigateTo: "/grid-editor",
    relatedTopics: ["studies.load-flow", "asset-management.overview"],
  },
];

export const helpCategories = [
  { id: "all" as const, label: { en: "All Topics", ar: "جميع المواضيع" } },
  { id: "getting-started" as const, label: { en: "Getting Started", ar: "البدء" } },
  { id: "projects" as const, label: { en: "Projects", ar: "المشاريع" } },
  { id: "fire-alarm" as const, label: { en: "Fire Alarm", ar: "إنذار الحريق" } },
  { id: "engineering" as const, label: { en: "Engineering", ar: "الهندسة" } },
  { id: "reports" as const, label: { en: "Reports", ar: "التقارير" } },
  { id: "digital-twin" as const, label: { en: "Digital Twin", ar: "التوأم الرقمي" } },
  { id: "settings" as const, label: { en: "Settings", ar: "الإعدادات" } },
  { id: "troubleshooting" as const, label: { en: "Troubleshooting", ar: "استكشاف الأخطاء" } },
  {
    id: "keyboard-shortcuts" as const,
    label: { en: "Keyboard Shortcuts", ar: "اختصارات لوحة المفاتيح" },
  },
] as const;
