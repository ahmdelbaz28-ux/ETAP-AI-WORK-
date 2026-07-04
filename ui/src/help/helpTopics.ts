import type { HelpTopic } from './types';

export const helpTopics: HelpTopic[] = [
  // ─── Getting Started ──────────────────────────────────────────────
  {
    id: 'dashboard.overview',
    category: 'getting-started',
    title: { en: 'Dashboard Overview', ar: 'نظرة عامة على لوحة التحكم' },
    description: {
      en: 'Navigate the main dashboard and understand system status',
      ar: 'التنقل في لوحة التحكم الرئيسية وفهم حالة النظام',
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
    tags: ['dashboard', 'overview', 'home', 'لوحة تحكم', 'نظرة عامة'],
    navigateTo: '/dashboard',
    relatedTopics: ['projects.manage', 'studies.load-flow'],
  },
  {
    id: 'keyboard-shortcuts',
    category: 'getting-started',
    title: { en: 'Keyboard Shortcuts', ar: 'اختصارات لوحة المفاتيح' },
    description: {
      en: 'Essential keyboard shortcuts for faster workflow',
      ar: 'اختصارات لوحة المفاتيح الأساسية لسرعة العمل',
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
    tags: ['keyboard', 'shortcuts', 'hotkeys', 'keys', 'لوحة مفاتيح', 'اختصارات'],
    relatedTopics: ['dashboard.overview', 'magic-help.inspector'],
  },
  {
    id: 'magic-help.inspector',
    category: 'getting-started',
    title: { en: 'Magic Help Inspector', ar: 'فاحص المساعدة السحرية' },
    description: {
      en: 'Click any element to instantly see its documentation',
      ar: 'انقر على أي عنصر لرؤية شرحه فوراً',
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
    tags: ['magic', 'help', 'inspector', 'inspect', 'سحري', 'مساعدة', 'فحص'],
    relatedTopics: ['keyboard-shortcuts', 'dashboard.overview'],
  },

  // ─── Projects ─────────────────────────────────────────────────────
  {
    id: 'projects.create',
    category: 'projects',
    title: { en: 'Creating a Project', ar: 'إنشاء مشروع' },
    description: {
      en: 'How to create and configure a new engineering project',
      ar: 'كيفية إنشاء وتكوين مشروع هندسي جديد',
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
    tags: ['project', 'create', 'new', 'مشروع', 'إنشاء', 'جديد'],
    navigateTo: '/projects',
    relatedTopics: ['projects.manage', 'studies.load-flow'],
  },
  {
    id: 'projects.manage',
    category: 'projects',
    title: { en: 'Managing Projects', ar: 'إدارة المشاريع' },
    description: {
      en: 'Open, edit, archive, and delete projects',
      ar: 'فتح وتعديل وأرشفة وحذف المشاريع',
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
      'project',
      'manage',
      'open',
      'edit',
      'archive',
      'delete',
      'مشروع',
      'إدارة',
      'فتح',
      'تعديل',
    ],
    navigateTo: '/projects',
    relatedTopics: ['projects.create', 'studies.load-flow'],
  },

  // ─── Studies (per type) ───────────────────────────────────────────
  {
    id: 'studies.overview',
    category: 'engineering',
    title: { en: 'Studies Overview', ar: 'نظرة عامة على الدراسات' },
    description: {
      en: 'All available engineering study types and how to run them',
      ar: 'جميع أنواع الدراسات الهندسية المتاحة وكيفية تشغيلها',
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
    tags: ['studies', 'overview', 'all', 'دراسات', 'نظرة عامة'],
    navigateTo: '/studies',
    relatedTopics: ['studies.load-flow', 'studies.short-circuit', 'studies.arc-flash'],
  },
  {
    id: 'studies.load-flow',
    category: 'engineering',
    title: { en: 'Load Flow Study', ar: 'دراسة تدفق الحمل' },
    description: {
      en: 'Newton-Raphson power flow analysis per IEEE 3002.7',
      ar: 'تحليل تدفق القدرة بطريقة نيوتن-رافسون حسب IEEE 3002.7',
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
    tags: ['load', 'flow', 'newton', 'raphson', 'power', 'تدفق', 'حمل', 'قدرة'],
    navigateTo: '/studies/load_flow',
    relatedTopics: ['studies.overview', 'studies.short-circuit'],
  },
  {
    id: 'studies.short-circuit',
    category: 'engineering',
    title: { en: 'Short Circuit Study', ar: 'دراسة الدائرة القصيرة' },
    description: { en: 'IEC 60909 fault current calculation', ar: 'حساب تيار العطل حسب IEC 60909' },
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
    tags: ['short', 'circuit', 'fault', 'iec', '60909', 'قصر', 'دائرة', 'عطل'],
    navigateTo: '/studies/short_circuit',
    relatedTopics: ['studies.overview', 'studies.arc-flash', 'studies.protection'],
  },
  {
    id: 'studies.arc-flash',
    category: 'engineering',
    title: { en: 'Arc Flash Study', ar: 'دراسة شرارة القوس' },
    description: {
      en: 'IEEE 1584-2018 incident energy analysis',
      ar: 'تحليل طاقة الحادث حسب IEEE 1584-2018',
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
    tags: ['arc', 'flash', 'ieee', '1584', 'incident', 'energy', 'قوس', 'شرارة', 'حادث'],
    navigateTo: '/studies/arc_flash',
    relatedTopics: ['studies.short-circuit', 'studies.protection', 'studies.overview'],
  },
  {
    id: 'studies.protection',
    category: 'engineering',
    title: { en: 'Protection Coordination', ar: 'تنسيق الحماية' },
    description: { en: 'IEC 60255 relay curve coordination', ar: 'تنسيق منحنيات المُرحّل IEC 60255' },
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
    tags: ['protection', 'relay', 'coordination', 'iec', '60255', 'حماية', 'مُرحّل', 'تنسيق'],
    navigateTo: '/studies/protection_coordination',
    relatedTopics: ['studies.short-circuit', 'studies.overview'],
  },
  {
    id: 'studies.harmonic',
    category: 'engineering',
    title: { en: 'Harmonic Analysis', ar: 'تحليل التوافقيات' },
    description: { en: 'IEEE 519-2022 distortion study', ar: 'دراسة التشوه IEEE 519-2022' },
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
    tags: ['harmonic', 'thd', 'ieee', '519', 'distortion', 'توافقيات', 'تشوه'],
    navigateTo: '/studies/harmonic',
    relatedTopics: ['studies.overview'],
  },
  {
    id: 'studies.motor-starting',
    category: 'engineering',
    title: { en: 'Motor Starting Study', ar: 'دراسة بدء المحرك' },
    description: { en: 'IEEE 399 transient analysis', ar: 'تحليل عابر IEEE 399' },
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
    tags: ['motor', 'starting', 'ieee', '399', 'voltage', 'dip', 'محرك', 'بدء'],
    navigateTo: '/studies/motor_starting',
    relatedTopics: ['studies.overview', 'studies.load-flow'],
  },
  {
    id: 'studies.cable-sizing',
    category: 'engineering',
    title: { en: 'Cable Sizing', ar: 'تحديد مقاس الكابلات' },
    description: {
      en: 'IEC 60364 current-carrying capacity',
      ar: 'القدرة على حمل التيار IEC 60364',
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
    tags: ['cable', 'sizing', 'iec', '60364', 'كابل', 'مقاس'],
    navigateTo: '/studies/cable_sizing',
    relatedTopics: ['studies.overview'],
  },
  {
    id: 'studies.earth-grid',
    category: 'engineering',
    title: { en: 'Earth Grid Design', ar: 'تصميم شبكة التأريض' },
    description: { en: 'IEEE 80 ground grid design', ar: 'تصميم شبكة التأريض IEEE 80' },
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
    tags: ['earth', 'grid', 'ground', 'ieee', '80', 'تأريض', 'شبكة'],
    navigateTo: '/studies/earth_grid',
    relatedTopics: ['studies.short-circuit', 'studies.overview'],
  },
  {
    id: 'studies.stability',
    category: 'engineering',
    title: { en: 'Transient Stability', ar: 'الاستقرار العابر' },
    description: {
      en: 'Power system transient stability analysis',
      ar: 'تحليل الاستقرار العابر لنظام القدرة',
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
    tags: ['stability', 'transient', 'rotor', 'angle', 'استقرار', 'عابر'],
    navigateTo: '/studies/stability',
    relatedTopics: ['studies.overview', 'studies.load-flow'],
  },
  {
    id: 'studies.opf',
    category: 'engineering',
    title: { en: 'Optimal Power Flow (OPF)', ar: 'تدفق القدرة الأمثل' },
    description: { en: 'Cost-optimized generation dispatch', ar: 'إرسال توليد أمثل للتكلفة' },
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
    tags: ['opf', 'optimal', 'power', 'flow', 'cost', 'أمثل', 'تكلفة'],
    navigateTo: '/studies/opf',
    relatedTopics: ['studies.overview', 'studies.load-flow'],
  },

  // ─── AI Assistant ─────────────────────────────────────────────────
  {
    id: 'ai-assistant.overview',
    category: 'getting-started',
    title: { en: 'AI Assistant', ar: 'المساعد الذكي' },
    description: {
      en: 'Chat with the ETAP Expert AI agent for engineering guidance',
      ar: 'تحدث مع وكيل ETAP Expert الذكي للحصول على إرشادات هندسية',
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
    tags: ['ai', 'assistant', 'chat', 'agent', 'ذكاء', 'اصطناعي', 'مساعد'],
    navigateTo: '/assistant',
    relatedTopics: ['dashboard.overview', 'code-guard.overview'],
  },

  // ─── Asset Management ─────────────────────────────────────────────
  {
    id: 'asset-management.overview',
    category: 'engineering',
    title: { en: 'Asset Management', ar: 'إدارة الأصول' },
    description: {
      en: 'Track physical equipment across your power system',
      ar: 'تتبع المعدات الفيزيائية في نظام القدرة',
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
    tags: ['asset', 'management', 'equipment', 'أصول', 'معدات'],
    navigateTo: '/asset-management',
    relatedTopics: ['dashboard.overview'],
  },

  // ─── ETAP Integration ─────────────────────────────────────────────
  {
    id: 'etap-integration.overview',
    category: 'engineering',
    title: { en: 'ETAP Integration', ar: 'تكامل ETAP' },
    description: {
      en: 'Connect to ETAP desktop software for native study execution',
      ar: 'اتصل ببرنامج ETAP المكتبي لتنفيذ الدراسات الأصلية',
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
    tags: ['etap', 'integration', 'worker', 'windows', 'تكامل', 'عامل'],
    navigateTo: '/etap',
    relatedTopics: ['studies.overview', 'settings.backend'],
  },

  // ─── GIS Integration ──────────────────────────────────────────────
  {
    id: 'gis-integration.overview',
    category: 'engineering',
    title: { en: 'GIS Integration', ar: 'تكامل GIS' },
    description: {
      en: 'Connect to ArcGIS / QGIS / PostGIS for geospatial power system data',
      ar: 'اتصل بـ ArcGIS / QGIS / PostGIS لبيانات نظام القدرة الجغرافية',
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
    tags: ['gis', 'arcgis', 'qgis', 'postgis', 'geo', 'جغرافي'],
    navigateTo: '/gis',
    relatedTopics: ['asset-management.overview', 'digital-twin.overview'],
  },

  // ─── Reports ──────────────────────────────────────────────────────
  {
    id: 'reports.generate',
    category: 'reports',
    title: { en: 'Generating Reports', ar: 'إنشاء التقارير' },
    description: {
      en: 'How to generate and customize engineering reports',
      ar: 'كيفية إنشاء وتخصيص التقارير الهندسية',
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
    tags: ['report', 'generate', 'pdf', 'compliance', 'تقرير', 'إنشاء', 'امتثال'],
    navigateTo: '/reports',
    relatedTopics: ['projects.manage', 'studies.overview'],
  },

  // ─── Digital Twin ─────────────────────────────────────────────────
  {
    id: 'digital-twin.overview',
    category: 'digital-twin',
    title: { en: 'Digital Twin Overview', ar: 'نظرة عامة على التوأم الرقمي' },
    description: {
      en: 'Real-time virtual replica of your physical power system',
      ar: 'نسخة افتراضية في الوقت الفعلي من نظام القدرة الفيزيائي',
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
    tags: ['digital', 'twin', 'sync', 'real-time', 'توأم', 'رقمي', 'مزامنة'],
    navigateTo: '/digital-twin',
    relatedTopics: ['dashboard.overview', 'integration.scada'],
  },

  // ─── Settings ─────────────────────────────────────────────────────
  {
    id: 'settings.backend',
    category: 'settings',
    title: { en: 'Backend Configuration', ar: 'تكوين الخادم' },
    description: {
      en: 'Configure the engineering service backend connection',
      ar: 'تكوين اتصال خادم الخدمة الهندسية',
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
    tags: ['settings', 'backend', 'config', 'api', 'إعدادات', 'خادم', 'تكوين'],
    navigateTo: '/settings',
    relatedTopics: ['troubleshooting.backend', 'settings.external-services'],
  },
  {
    id: 'settings.external-services',
    category: 'settings',
    title: {
      en: 'External Services (LangWatch, Smithery, HF, GitHub, Vercel)',
      ar: 'الخدمات الخارجية (LangWatch, Smithery, HF, GitHub, Vercel)',
    },
    description: {
      en: 'Configure and test third-party integrations',
      ar: 'تكوين واختبار التكاملات الخارجية',
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
      'settings',
      'external',
      'services',
      'langwatch',
      'smithery',
      'huggingface',
      'github',
      'vercel',
      'إعدادات',
      'خدمات',
      'خارجية',
    ],
    navigateTo: '/settings',
    relatedTopics: ['settings.backend', 'integration.scada'],
  },
  {
    id: 'settings.ai-providers',
    category: 'settings',
    title: { en: 'AI Providers Configuration', ar: 'تكوين مزودي الذكاء الاصطناعي' },
    description: {
      en: 'Connect to OpenAI, Anthropic, Gemini, DeepSeek, Groq, Cohere, Hugging Face',
      ar: 'اتصل بـ OpenAI، Anthropic، Gemini، DeepSeek، Groq، Cohere، Hugging Face',
    },
    content: {
      en: `**The AI Providers tab lets you connect to 7 popular LLM providers:**

**Supported Providers:**
1. **OpenAI** — GPT-4o, GPT-4o-mini, o1-mini, o1-preview
2. **Anthropic** — Claude 3.5 Sonnet, Claude 3 Opus, Claude 3.5 Haiku
3. **Google Gemini** — Gemini 1.5 Pro/Flash, Gemini 2.0 Flash
4. **DeepSeek** — DeepSeek Chat, DeepSeek Coder
5. **Groq** — Llama 3.3 70B, Mixtral 8x7B, Gemma 2 9B
6. **Cohere** — Command R+, Command R
7. **Hugging Face** — Llama 3.3 70B, Mixtral 8x7B

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
- API keys are stored in localStorage (obfuscated)
- You can configure multiple providers simultaneously
- The AI Assistant page lets you select which provider to use per chat`,
      ar: `**تبويب مزودي الذكاء الاصطناعي يتيح لك الاتصال بـ 7 مزودين LLM شائعين:**

**المزودون المدعومون:**
1. **OpenAI** — GPT-4o، GPT-4o-mini، o1-mini، o1-preview
2. **Anthropic** — Claude 3.5 Sonnet، Claude 3 Opus، Claude 3.5 Haiku
3. **Google Gemini** — Gemini 1.5 Pro/Flash، Gemini 2.0 Flash
4. **DeepSeek** — DeepSeek Chat، DeepSeek Coder
5. **Groq** — Llama 3.3 70B، Mixtral 8x7B، Gemma 2 9B
6. **Cohere** — Command R+، Command R
7. **Hugging Face** — Llama 3.3 70B، Mixtral 8x7B

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
- مفاتيح API محفوظة في localStorage (مشوّهة)
- يمكنك تكوين مزودين متعددين في نفس الوقت
- تتيح لك صفحة المساعد الذكي اختيار المزود المستخدم لكل دردشة`,
    },
    tags: [
      'ai',
      'provider',
      'openai',
      'anthropic',
      'gemini',
      'deepseek',
      'groq',
      'cohere',
      'مزود',
      'ذكاء',
    ],
    navigateTo: '/settings',
    relatedTopics: ['ai-assistant.overview', 'settings.backend'],
  },

  // ─── Code Guard ───────────────────────────────────────────────────
  {
    id: 'code-guard.overview',
    category: 'engineering',
    title: { en: 'Code Guard', ar: 'حارس الكود' },
    description: {
      en: 'AI-powered code review for engineering calculations',
      ar: 'مراجعة أكواد بالذكاء الاصطناعي للحسابات الهندسية',
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
    tags: ['code', 'guard', 'review', 'ai', 'كود', 'حارس', 'مراجعة'],
    navigateTo: '/code-guard',
    relatedTopics: ['ai-assistant.overview'],
  },

  // ─── Data Import / Export ─────────────────────────────────────────
  {
    id: 'data-import.overview',
    category: 'engineering',
    title: { en: 'Data Import', ar: 'استيراد البيانات' },
    description: {
      en: 'Import engineering data from CSV, JSON, Excel, ETAP files',
      ar: 'استيراد بيانات هندسية من CSV، JSON، Excel، ملفات ETAP',
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
    tags: ['import', 'csv', 'json', 'excel', 'data', 'استيراد', 'بيانات'],
    navigateTo: '/data-import',
    relatedTopics: ['data-export.overview', 'projects.create'],
  },
  {
    id: 'data-export.overview',
    category: 'engineering',
    title: { en: 'Data Export', ar: 'تصدير البيانات' },
    description: {
      en: 'Export engineering data to CSV, JSON, Excel, PDF',
      ar: 'تصدير بيانات هندسية إلى CSV، JSON، Excel، PDF',
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
    tags: ['export', 'csv', 'json', 'excel', 'pdf', 'data', 'تصدير', 'بيانات'],
    navigateTo: '/data-export',
    relatedTopics: ['data-import.overview', 'reports.generate'],
  },

  // ─── Administration ───────────────────────────────────────────────
  {
    id: 'administration.overview',
    category: 'settings',
    title: { en: 'Administration', ar: 'الإدارة' },
    description: {
      en: 'User management, roles, and system administration',
      ar: 'إدارة المستخدمين والأدوار وإدارة النظام',
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
    tags: ['admin', 'user', 'management', 'role', 'إدارة', 'مستخدم', 'دور'],
    navigateTo: '/admin',
    relatedTopics: ['settings.backend', 'troubleshooting.auth'],
  },

  // ─── Diagnostics ──────────────────────────────────────────────────
  {
    id: 'diagnostics.overview',
    category: 'troubleshooting',
    title: { en: 'Diagnostics', ar: 'التشخيص' },
    description: {
      en: 'System health checks, logs, and performance metrics',
      ar: 'فحوصات صحة النظام والسجلات ومقاييس الأداء',
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
    tags: ['diagnostics', 'health', 'logs', 'metrics', 'تشخيص', 'صحة', 'سجلات'],
    navigateTo: '/diagnostics',
    relatedTopics: ['troubleshooting.backend', 'troubleshooting.api'],
  },

  // ─── Logs Page ────────────────────────────────────────────────────
  {
    id: 'logs.overview',
    category: 'troubleshooting',
    title: { en: 'Logs', ar: 'السجلات' },
    description: {
      en: 'Real-time application logs with filtering',
      ar: 'سجلات التطبيق المباشرة مع الفلترة',
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
    tags: ['logs', 'stream', 'filter', 'debug', 'سجلات', 'تصحيح'],
    navigateTo: '/logs',
    relatedTopics: ['diagnostics.overview', 'troubleshooting.backend'],
  },

  // ─── Troubleshooting ──────────────────────────────────────────────
  {
    id: 'troubleshooting.backend',
    category: 'troubleshooting',
    title: { en: 'Backend Unavailable', ar: 'الخادم غير متاح' },
    description: {
      en: 'The engineering service is not responding',
      ar: 'خدمة الخدمة الهندسية لا تستجيب',
    },
    content: {
      en: `**Symptoms:**
- "Backend Unavailable" error in the UI
- Studies fail to execute
- Status indicator shows red

**Solutions:**

**1. Check if the backend is running:**
\`\`\`bash
curl http://localhost:8000/healthz
\`\`\`
Should return \`{"status": "alive"}\`

**2. Start the backend:**
\`\`\`bash
# Modular service (recommended)
python -m api.refactored_service

# Or legacy monolith
python engineering_service.py --port 8000
\`\`\`

**3. Check the URL in Settings:**
- Navigate to Settings → Engineering Service
- Verify the URL matches your backend (e.g. http://localhost:8000)
- Verify the API key matches your ENGINEERING_SERVICE_API_KEY env var

**4. Check firewall:**
- Port 8000 should be open for both inbound and outbound
- On Windows: \`netsh advfirewall firewall add rule name="ETAP" dir=in action=allow protocol=TCP localport=8000\`

**5. Check Docker (if using containers):**
\`\`\`bash
docker compose ps
docker compose logs api
\`\`\`

**6. For HF Space deployment:**
- Check the Space status at https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP
- The Space may be sleeping (free tier sleeps after 48h of inactivity)
- Visit the Space URL to wake it up`,
      ar: `**الأعراض:**
- خطأ "الخادم غير متاح" في واجهة المستخدم
- فشل تنفيذ الدراسات
- مؤشر الحالة يظهر بالأحمر

**الحلول:**

**1. تحقق من تشغيل الخادم:**
\`\`\`bash
curl http://localhost:8000/healthz
\`\`\`
يجب أن يُرجع \`{"status": "alive"}\`

**2. تشغيل الخادم:**
\`\`\`bash
# الخدمة المعيارية (موصى بها)
python -m api.refactored_service

# أو الأحادي القديم
python engineering_service.py --port 8000
\`\`\`

**3. تحقق من الرابط في الإعدادات:**
- انتقل إلى الإعدادات → الخدمة الهندسية
- تحقق من أن الرابط يطابق خادمك (مثل http://localhost:8000)
- تحقق من أن مفتاح API يطابق متغير البيئة ENGINEERING_SERVICE_API_KEY

**4. تحقق من جدار الحماية:**
- يجب أن يكون المنفذ 8000 مفتوحاً للداخل والخارج
- على Windows: \`netsh advfirewall firewall add rule name="ETAP" dir=in action=allow protocol=TCP localport=8000\`

**5. تحقق من Docker (إذا كنت تستخدم الحاويات):**
\`\`\`bash
docker compose ps
docker compose logs api
\`\`\`

**6. لنشر HF Space:**
- تحقق من حالة المساحة على https://huggingface.co/spaces/ahmdelbaz28/AHMEDETAP
- قد تكون المساحة نائمة (الطبقة المجانية تنام بعد 48 ساعة من عدم النشاط)
- قم بزيارة رابط المساحة لإيقاظها`,
    },
    tags: ['backend', 'unavailable', 'error', 'connection', 'خادم', 'غير متاح', 'خطأ'],
    navigateTo: '/diagnostics',
    relatedTopics: ['settings.backend', 'troubleshooting.api'],
  },
  {
    id: 'troubleshooting.api',
    category: 'troubleshooting',
    title: { en: 'API Errors', ar: 'أخطاء API' },
    description: {
      en: 'Common API error codes and their solutions',
      ar: 'أكواد أخطاء API الشائعة وحلولها',
    },
    content: {
      en: `**Common Error Codes:**

**400 Bad Request** — Invalid input data
- Check required fields are present
- Verify data types match expected format
- Look at the error detail for the specific field

**401 Unauthorized** — Authentication failed
- Verify API key is correct (Settings → Engineering Service)
- Check if JWT token has expired (login again)
- For HF Space: verify HF_API_KEY is set as a Space secret

**403 Forbidden** — Insufficient permissions
- Your role may not have access (admin only?)
- Contact administrator for role elevation

**404 Not Found** — Resource doesn't exist
- Check the resource ID in the URL
- Verify the endpoint path is correct
- The project/study may have been deleted

**422 Unprocessable Entity** — Pydantic validation failed
- Check the response body for the validation error details
- Each error tells you which field failed and why

**429 Too Many Requests** — Rate limited
- Wait before retrying (Retry-After header tells you how long)
- Default limit: 100 requests per minute
- For higher limits, contact admin

**500 Internal Server Error** — Server-side issue
- Check backend logs at /logs
- Look at the trace_id in the response to find the specific log entry
- Restart the service if persistent

**503 Service Unavailable** — Backend starting up
- Wait a few seconds and retry
- The service may be initializing or restarting`,
      ar: `**أكواد الأخطاء الشائعة:**

**400 طلب سيئ** — بيانات إدخال غير صالحة
- تحقق من وجود الحقول المطلوبة
- تأكد من تطابق أنواع البيانات
- انظر إلى تفاصيل الخطأ للحقل المحدد

**401 غير مصرح** — فشل المصادقة
- تحقق من صحة مفتاح API (الإعدادات → الخدمة الهندسية)
- تحقق من انتهاء صلاحية رمز JWT (سجل الدخول مرة أخرى)
- لـ HF Space: تحقق من تعيين HF_API_KEY كسر للمساحة

**403 محظور** — صلاحيات غير كافية
- قد لا يكون لدورك وصول (للمسؤولين فقط؟)
- تواصل مع المسؤول لرفع الدور

**404 غير موجود** — المورد غير موجود
- تحقق من معرّف المورد في URL
- تحقق من صحة مسار النقطة
- قد يكون المشروع/الدراسة قد حُذف

**422 كيان غير قابل للمعالجة** — فشل التحقق من Pydantic
- تحقق من جسم الاستجابة لتفاصيل خطأ التحقق
- يخبرك كل خطأ بأي حقل فشل ولماذا

**429 طلبات كثيرة جداً** — تم تقييد المعدل
- انتظر قبل إعادة المحاولة (ترويسة Retry-After تخبرك بالمدة)
- الحد الافتراضي: 100 طلب في الدقيقة
- للحدود الأعلى، تواصل مع المسؤول

**500 خطأ داخلي في الخادم** — مشكلة في الخادم
- تحقق من سجلات الخادم في /logs
- ابحث عن trace_id في الاستجابة للعثور على إدخال السجل المحدد
- أعد تشغيل الخدمة إذا استمر

**503 الخدمة غير متاحة** — الخادم يبدأ
- انتظر بضع ثوانٍ وأعد المحاولة
- قد تكون الخدمة قيد التهيئة أو إعادة التشغيل`,
    },
    tags: ['api', 'error', '400', '401', '403', '404', '429', '500', 'api', 'خطأ'],
    relatedTopics: ['troubleshooting.backend', 'troubleshooting.auth'],
  },
  {
    id: 'troubleshooting.auth',
    category: 'troubleshooting',
    title: { en: 'Authentication Issues', ar: 'مشاكل المصادقة' },
    description: { en: 'Login failures and token problems', ar: 'فشل تسجيل الدخول ومشاكل الرمز' },
    content: {
      en: `**Common Issues:**

**Login fails immediately:**
- Verify username and password (case-sensitive)
- Check for account lockout (5 failed attempts in 15 minutes → locked for 15 min)
- Ensure backend is running (login requires backend connectivity)

**"Account is deactivated":**
- An admin has deactivated your account
- Contact admin to reactivate

**Token expired:**
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- The app auto-refreshes; if it fails, you'll be redirected to login

**JWT validation error:**
- Token may be malformed
- Secret key may have changed (admin rotated keys)
- Clear browser localStorage and re-login:
  - Open DevTools (F12) → Application → Local Storage → Clear

**MFA issues:**
- TOTP codes are time-sensitive (30-second window)
- Verify your authenticator app's time is synced
- Use a backup code if you've lost your device
- Contact admin to reset MFA if all else fails

**Password reset:**
- Click "Forgot password?" on the login page
- Enter your email — a reset token is generated
- Use the reset token to set a new password (token expires in 30 minutes)`,
      ar: `**المشكلات الشائعة:**

**فشل تسجيل الدخول فوراً:**
- تحقق من اسم المستخدم وكلمة المرور (حساس للحالة)
- تحقق من حظر الحساب (5 محاولات فاشلة في 15 دقيقة → محظور لـ 15 دقيقة)
- تأكد من تشغيل الخادم (تسجيل الدخول يتطلب اتصال الخادم)

**"الحساب معطل":**
- قام مسؤول بتعطيل حسابك
- تواصل مع المسؤول لإعادة التفعيل

**انتهت صلاحية الرمز:**
- تنتهي صلاحية رموز الوصول بعد 30 دقيقة
- تنتهي صلاحية رموز التحديث بعد 7 أيام
- التطبيق يحدّث تلقائياً؛ إذا فشل، سيتم توجيهك لتسجيل الدخول

**خطأ في التحقق من JWT:**
- قد يكون الرمز مشوّهاً
- قد يكون المفتاح السري قد تغير (قام المسؤول بتدوير المفاتيح)
- امسح localStorage في المتصفح وأعد تسجيل الدخول:
  - افتح DevTools (F12) → Application → Local Storage → Clear

**مشاكل MFA:**
- رموز TOTP حساسة للوقت (نافذة 30 ثانية)
- تحقق من أن وقت تطبيق المصادقة متزامن
- استخدم رمز النسخ الاحتياطي إذا فقدت جهازك
- تواصل مع المسؤول لإعادة تعيين MFA إذا فشل كل شيء آخر

**إعادة تعيين كلمة المرور:**
- انقر على "نسيت كلمة المرور؟" في صفحة تسجيل الدخول
- أدخل بريدك الإلكتروني — يتم إنشاء رمز إعادة التعيين
- استخدم رمز إعادة التعيين لتعيين كلمة مرور جديدة (ينتهي الرمز في 30 دقيقة)`,
    },
    tags: ['auth', 'login', 'token', 'jwt', 'mfa', 'مصادقة', 'دخول', 'رمز'],
    navigateTo: '/settings',
    relatedTopics: ['settings.backend', 'troubleshooting.api', 'administration.overview'],
  },
  {
    id: 'integration.scada',
    category: 'settings',
    title: { en: 'SCADA System Integration (zenon)', ar: 'ربط نظام الإسكادا (زينون)' },
    description: {
      en: 'Configure and monitor Copa-Data zenon SCADA system connection',
      ar: 'تكوين ومراقبة اتصال نظام إسكادا زينون (zenon)',
    },
    content: {
      en: `**zenon SCADA Connectivity:**
Copa-Data zenon SCADA is integrated directly with the AhmedETAP platform via the SCADA Agent, facilitating real-time status monitoring, state estimation, and IEC 61850 data model mapping.

**Configuration Parameters (Settings → Integration):**
- **SCADA System Type** — Copa-Data zenon SCADA (default)
- **SCADA Server URL** — HTTP endpoint of the zenon REST API/Web Server
- **Project Name** — Name of the active zenon project to synchronize variables from
- **Sync Interval** — Interval in seconds for pulling real-time variables (default: 10s)
- **SCADA API Key** — Authorization secret token for secure data transfer

**Common Operations:**
1. **Tag Mapping** — Map zenon tags to ETAP nodes (buses, breakers, generators)
2. **Real-time Alarm Monitoring** — Stream alarms from zenon to AhmedETAP
3. **Single-Line Diagram Animation** — Animate breaker states based on live data
4. **State Estimation** — Use SCADA measurements to estimate unobserved states

**IEC 61850 Logical Nodes:**
- MMXU — Voltage, current, power measurements
- MSQI — Sequence components & imbalance
- XCBR — Circuit breaker positions
- XSWI — Switch/disconnector positions

**Tips:**
- Test connectivity with the "Test Connection" button before saving
- Use a low sync interval (5-10s) for near-real-time monitoring
- Higher intervals (30-60s) reduce server load but may miss transient events`,
      ar: `**ربط نظام إسكادا زينون (zenon SCADA):**
يتكامل نظام Copa-Data zenon SCADA مباشرة مع منصة AhmedETAP عبر وكيل الإسكادا، مما يسهل مراقبة الحالة الحية وتقدير حالة النظام ومطابقة نموذج بيانات المعيار IEC 61850.

**محددات التكوين (الإعدادات → التكامل):**
- **نوع نظام الإسكادا** — Copa-Data zenon SCADA (افتراضي)
- **رابط الخادم** — الرابط الشبكي لخدمة zenon REST API/Web Server
- **اسم المشروع** — اسم مشروع zenon النشط لمزامنة المتغيرات منه
- **معدل المزامنة** — الوقت بالثواني لجلب قيم المتغيرات في الوقت الفعلي (افتراضي: 10 ثوانٍ)
- **مفتاح API** — رمز التفويض السري لنقل البيانات الآمن

**العمليات الشائعة:**
1. **تعيين الوسوم** — مطابقة وسوم (tags) زينون مع عقد شبكة إيتاب
2. **مراقبة الإنذارات في الوقت الفعلي** — بث الإنذارات من زينون إلى AhmedETAP
3. **تحريك مخطط الخط الواحد** — تحريك حالات القواطع بناءً على البيانات الحية
4. **تقدير الحالة** — استخدام قياسات SCADA لتقدير الحالات غير المرصودة

**العقد المنطقية IEC 61850:**
- MMXU — قياسات الجهد، التيار، القدرة
- MSQI — مركبات التسلسل وعدم الاتزان
- XCBR — مواقع القواطع الكهربية
- XSWI — مواقع المفاتيح/المفاصل

**نصائح:**
- اختبر الاتصال بزر "اختبار الاتصال" قبل الحفظ
- استخدم معدل مزامنة منخفض (5-10 ثوانٍ) للمراقبة شبه المباشرة
- المعدلات الأعلى (30-60 ثانية) تقلل حمل الخادم لكن قد تفوت الأحداث العابرة`,
    },
    tags: ['scada', 'zenon', 'integration', 'iec61850', 'إسكادا', 'زينون', 'ربط'],
    navigateTo: '/settings',
    relatedTopics: ['digital-twin.overview', 'settings.backend'],
  },
];

export const helpCategories = [
  { id: 'all' as const, label: { en: 'All Topics', ar: 'جميع المواضيع' } },
  { id: 'getting-started' as const, label: { en: 'Getting Started', ar: 'البدء' } },
  { id: 'projects' as const, label: { en: 'Projects', ar: 'المشاريع' } },
  { id: 'fire-alarm' as const, label: { en: 'Fire Alarm', ar: 'إنذار الحريق' } },
  { id: 'engineering' as const, label: { en: 'Engineering', ar: 'الهندسة' } },
  { id: 'reports' as const, label: { en: 'Reports', ar: 'التقارير' } },
  { id: 'digital-twin' as const, label: { en: 'Digital Twin', ar: 'التوأم الرقمي' } },
  { id: 'settings' as const, label: { en: 'Settings', ar: 'الإعدادات' } },
  { id: 'troubleshooting' as const, label: { en: 'Troubleshooting', ar: 'استكشاف الأخطاء' } },
  {
    id: 'keyboard-shortcuts' as const,
    label: { en: 'Keyboard Shortcuts', ar: 'اختصارات لوحة المفاتيح' },
  },
] as const;
