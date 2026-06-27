import type { HelpTopic } from './types'

export const helpTopics: HelpTopic[] = [
  // ─── Getting Started ──────────────────────────────────────────────
  {
    id: 'dashboard.overview',
    category: 'getting-started',
    title: { en: 'Dashboard Overview', ar: 'نظرة عامة على لوحة التحكم' },
    description: { en: 'Navigate the main dashboard and understand system status', ar: 'التنقل في لوحة التحكم الرئيسية وفهم حالة النظام' },
    content: {
      en: `The Dashboard is your central hub for monitoring the Ahmed etap Platform.\n\n**Key Areas:**\n- **Status Cards** — Real-time system health, active agents, and study metrics\n- **Charts** — API activity, study distribution, and resource utilization\n- **Quick Actions** — Shortcut buttons for common engineering tasks\n- **Recent Studies** — Your latest study results and their status\n\n**Tips:**\n- The sidebar provides access to all modules\n- Press Ctrl+K to open the command palette\n- Press F1 anywhere for contextual help`,
      ar: `لوحة التحكم هي مركزك المركزي لمراقبة منصة Ahmed etap.\n\n**المناطق الرئيسية:**\n- **بطاقات الحالة** — صحة النظام في الوقت الفعلي والوكلاء النشطين ومقاييس الدراسة\n- **الرسوم البيانية** — نشاط API وتوزيع الدراسات واستخدام الموارد\n- **الإجراءات السريعة** — أزرار اختصار للمهام الهندسية الشائعة\n- **الدراسات الأخيرة** — أحدث نتائج دراساتك وحالتها\n\n**نصائح:**\n- يوفر الشريط الجانبي الوصول إلى جميع الوحدات\n- اضغط Ctrl+K لفتح لوحة الأوامر\n- اضغط F1 في أي مكان للحصول على المساعدة السياقية`,
    },
    tags: ['dashboard', 'overview', 'home', 'لوحة تحكم', 'نظرة عامة'],
    navigateTo: '/dashboard',
    relatedTopics: ['projects.manage', 'fire-alarm.detector-placement'],
  },
  {
    id: 'keyboard-shortcuts',
    category: 'getting-started',
    title: { en: 'Keyboard Shortcuts', ar: 'اختصارات لوحة المفاتيح' },
    description: { en: 'Essential keyboard shortcuts for faster workflow', ar: 'اختصارات لوحة المفاتيح الأساسية لسرعة العمل' },
    content: {
      en: `**Global Shortcuts:**\n- \`F1\` — Open Smart Help\n- \`Ctrl+K\` — Command Palette (coming soon)\n- \`Ctrl+H\` — Toggle Help Panel\n- \`Ctrl+S\` — Save current work\n- \`Ctrl+N\` — New project\n\n**Navigation:**\n- \`G\` then \`D\` — Go to Dashboard\n- \`G\` then \`P\` — Go to Projects\n- \`G\` then \`S\` — Go to Studies\n- \`G\` then \`R\` — Go to Reports\n\n**Fire Alarm Designer:**\n- \`Delete\` — Remove selected element\n- \`Ctrl+Z\` — Undo\n- \`Ctrl+Y\` — Redo\n- \`Space\` — Pan canvas\n- \`Scroll\` — Zoom in/out`,
      ar: `**الاختصارات العامة:**\n- \`F1\` — فتح المساعدة الذكية\n- \`Ctrl+K\` — لوحة الأوامر (قريباً)\n- \`Ctrl+H\` — إظهار/إخفاء لوحة المساعدة\n- \`Ctrl+S\` — حفظ العمل الحالي\n- \`Ctrl+N\` — مشروع جديد\n\n**التنقل:**\n- \`G\` ثم \`D\` — الذهاب إلى لوحة التحكم\n- \`G\` ثم \`P\` — الذهاب إلى المشاريع\n- \`G\` ثم \`S\` — الذهاب إلى الدراسات\n- \`G\` ثم \`R\` — الذهاب إلى التقارير\n\n**مصمم إنذار الحريق:**\n- \`Delete\` — حذف العنصر المحدد\n- \`Ctrl+Z\` — تراجع\n- \`Ctrl+Y\` — إعادة\n- \`Space\` — تحريك اللوحة\n- \`Scroll\` — تكبير/تصغير`,
    },
    tags: ['keyboard', 'shortcuts', 'hotkeys', 'keys', 'لوحة مفاتيح', 'اختصارات'],
    relatedTopics: ['dashboard.overview'],
  },

  // ─── Projects ─────────────────────────────────────────────────────
  {
    id: 'projects.create',
    category: 'projects',
    title: { en: 'Creating a Project', ar: 'إنشاء مشروع' },
    description: { en: 'How to create and configure a new engineering project', ar: 'كيفية إنشاء وتكوين مشروع هندسي جديد' },
    content: {
      en: `**Steps to Create a Project:**\n1. Navigate to **Projects** from the sidebar\n2. Click **"New Project"** button\n3. Enter project name and description\n4. Select project type (Power System, Fire Alarm, etc.)\n5. Configure basic system parameters\n6. Click **Create**\n\n**Project Types:**\n- **Power System** — Load flow, short circuit, arc flash studies\n- **Fire Alarm** — Detector placement, zone design, compliance\n- **Hybrid** — Combined power and fire alarm systems\n\n**Tips:**\n- Use descriptive names for easy identification\n- Add tags for better organization\n- Projects are auto-saved as you work`,
      ar: `**خطوات إنشاء مشروع:**\n1. انتقل إلى **المشاريع** من الشريط الجانبي\n2. انقر على زر **"مشروع جديد"**\n3. أدخل اسم المشروع والوصف\n4. حدد نوع المشروع (نظام قدرة، إنذار حريق، إلخ)\n5. قيم المعلمات الأساسية للنظام\n6. انقر على **إنشاء**\n\n**أنواع المشاريع:**\n- **نظام قدرة** — دراسات تدفق الحمل، الدائرة القصيرة، شرارة القوس\n- **إنذار الحريق** — وضع أجهزة الاستشعار، تصميم المناطق، الامتثال\n- **هجين** — أنظمة القدرة وإنذار الحريق المجمعة\n\n**نصائح:**\n- استخدم أسماء وصفية للتعرف السهل\n- أضف وسوم لتنظيم أفضل\n- تُحفظ المشاريع تلقائيًا أثناء العمل`,
    },
    tags: ['project', 'create', 'new', 'مشروع', 'إنشاء', 'جديد'],
    navigateTo: '/projects',
    relatedTopics: ['projects.manage', 'dashboard.overview'],
  },
  {
    id: 'projects.manage',
    category: 'projects',
    title: { en: 'Managing Projects', ar: 'إدارة المشاريع' },
    description: { en: 'Open, edit, archive, and delete projects', ar: 'فتح وتعديل وأرشفة وحذف المشاريع' },
    content: {
      en: `**Project Management:**\n- **Open** — Click a project card to open it\n- **Edit** — Click the settings icon on a project\n- **Archive** — Move completed projects to archive\n- **Delete** — Remove projects permanently (with confirmation)\n\n**Project Dashboard:**\n- View study history and results\n- Access project-specific settings\n- Export project data\n- Share with team members\n\n**Bulk Actions:**\n- Select multiple projects for batch operations\n- Export selected projects\n- Bulk archive or delete`,
      ar: `**إدارة المشاريع:**\n- **فتح** — انقر على بطاقة المشروع لفتحه\n- **تعديل** — انقر على أيقونة الإعدادات في مشروع\n- **أرشفة** — نقل المشاريع المكتملة إلى الأرشيف\n- **حذف** — إزالة المشاريع بشكل دائم (مع التأكيد)\n\n**لوحة تحكم المشروع:**\n- عرض سجل الدراسات والنتائج\n- الوصول إلى إعدادات المشروع\n- تصدير بيانات المشروع\n- المشاركة مع أعضاء الفريق\n\n**الإجراءات المجمعة:**\n- تحديد مشاريع متعددة للعمليات الدفعية\n- تصدير المشاريع المحددة\n- أرشفة أو حذف جماعي`,
    },
    tags: ['project', 'manage', 'open', 'edit', 'مشروع', 'إدارة', 'فتح'],
    navigateTo: '/projects',
    relatedTopics: ['projects.create', 'reports.generate'],
  },

  // ─── Fire Alarm ───────────────────────────────────────────────────
  {
    id: 'fire-alarm.detector-placement',
    category: 'fire-alarm',
    title: { en: 'Detector Placement', ar: 'وضع أجهزة الاستشعار' },
    description: { en: 'How to place and configure fire detectors on the canvas', ar: 'كيفية وضع وتكوين أجهزة استشعار الحريق على اللوحة' },
    content: {
      en: `**Detector Types:**\n- **Smoke Detector** — General area coverage\n- **Heat Detector** — Kitchen, mechanical rooms\n- **Beam Detector** — Large open spaces, warehouses\n- **Flame Detector** — High-value asset areas\n- **Gas Detector** — Industrial environments\n\n**Placement Rules:**\n1. Select detector type from the symbol library\n2. Click on the canvas to place\n3. Adjust coverage radius in properties panel\n4. Ensure overlap with adjacent detectors\n5. Check zone boundaries\n\n**Compliance:**\n- NFPA 72 for spacing requirements\n- BS 5839 for UK standards\n- Local code requirements may vary`,
      ar: `**أنواع أجهزة الاستشعار:**\n- **جهاز استشعار الدخان** — تغطية المنطقة العامة\n- **جهاز استشعار الحرارة** — المطبخ، غرف الآلات\n- **جهاز شعاعي** — المساحات المفتوحة الكبيرة، المستودعات\n- **جهاز استشعار اللهب** — مناطق الأصول عالية القيمة\n- **جهاز استشعار الغاز** — البيئات الصناعية\n\n**قواعد الوضع:**\n1. حدد نوع جهاز الاستشعار من مكتبة الرموز\n2. انقر على اللوحة للوضع\n3. تعديل نصف قطر التغطية في لوحة الخصائص\n4. التأكد من التداخل مع أجهزة الاستشعار المجاورة\n5. التحقق من حدود المنطقة\n\n**الامتثال:**\n- NFPA 72 لمتطلبات التباعد\n- BS 5839 للمعايير البريطانية\n- قد تختلف متطلبات الكود المحلي`,
    },
    tags: ['fire', 'detector', 'placement', 'smoke', 'heat', 'حريق', 'استشعار', 'وضع'],
    navigateTo: '/studies',
    relatedTopics: ['fire-alarm.zone-navigation', 'fire-alarm.symbol-library'],
  },
  {
    id: 'fire-alarm.zone-navigation',
    category: 'fire-alarm',
    title: { en: 'Zone Navigation', ar: 'التنقل بين المناطق' },
    description: { en: 'Understanding and navigating fire alarm zones', ar: 'فهم والتنقل بين مناطق إنذار الحريق' },
    content: {
      en: `**Zone Basics:**\n- Zones divide your fire alarm system into manageable areas\n- Each zone should cover a single floor or logical area\n- Zone boundaries are shown as colored overlays\n\n**Navigation:**\n- Click a zone to select it\n- Use the zone dropdown in the toolbar\n- Double-click to zoom to zone\n- Right-click for zone options\n\n**Zone Configuration:**\n- Zone name and number\n- Assigned detectors and modules\n- Circuit information\n- Emergency contact assignments`,
      ar: `**أسس المنطقة:**\n- تقسم المناطق نظام إنذار الحريق إلى مناطق قابلة للإدارة\n- يجب أن تغطي كل منطقة طابقًا واحدًا أو منطقة منطقية\n- تظهر حدود المناطق كتراكبات ملونة\n\n**التنقل:**\n- انقر على منطقة لتحديدها\n- استخدم قائمة المناطق المنسدلة في شريط الأدوات\n- انقر مرتين للتكبير على المنطقة\n- انقر بزر الماوس الأيمن لخيارات المنطقة\n\n**تكوين المنطقة:**\n- اسم المنطقة ورقمها\n- أجهزة الاستشعار والوحدات المعينة\n- معلومات الدائرة\n- تعيينات جهات الاتصال الطارئة`,
    },
    tags: ['zone', 'navigation', 'fire', 'area', 'منطقة', 'تنقل', 'حريق'],
    navigateTo: '/studies',
    relatedTopics: ['fire-alarm.detector-placement', 'fire-alarm.symbol-library'],
  },
  {
    id: 'fire-alarm.symbol-library',
    category: 'fire-alarm',
    title: { en: 'Symbol Library', ar: 'مكتبة الرموز' },
    description: { en: 'Available fire alarm symbols and how to use them', ar: 'رموز إنذار الحريق المتاحة وكيفية استخدامها' },
    content: {
      en: `**Symbol Categories:**\n- **Detectors** — Smoke, heat, beam, flame, gas\n- **Modules** — Input/output, relay, monitor\n- **Notification** — Horns, strobes, speakers\n- **Control** — Pull stations, panel interfaces\n- **Power** — Batteries, power supplies\n\n**Using Symbols:**\n1. Open the symbol library panel\n2. Browse or search for the symbol\n3. Drag and drop onto the canvas\n4. Configure properties in the right panel\n\n**Custom Symbols:**\n- Import SVG symbols for proprietary devices\n- Create symbol templates for reuse`,
      ar: `**فئات الرموز:**\n- **أجهزة الاستشعار** — دخان، حرارة، شعاع، لهب، غاز\n- **الوحدات** — إدخال/إخراج، مُرحّل، مراقب\n- **الإشعارات** — أبواق، وميضات، مكبرات صوت\n- **التحكم** — محطات السحب، واجهات اللوحة\n- **الطاقة** — بطاريات، مزودات طاقة\n\n**استخدام الرموز:**\n1. افتح لوحة مكتبة الرموز\n2. تصفح أو ابحث عن الرمز\n3. اسحب وأفلت على اللوحة\n4. قيم الخصائص في لوحة اليمين\n\n**الرموز المخصصة:**\n- استيراد رموز SVG للأجهزة الخاصة\n- إنشاء قوالب رموز لإعادة الاستخدام`,
    },
    tags: ['symbol', 'library', 'fire', 'detector', 'module', 'رمز', 'مكتبة', 'حريق'],
    navigateTo: '/studies',
    relatedTopics: ['fire-alarm.detector-placement', 'fire-alarm.zone-navigation'],
  },

  // ─── Reports ──────────────────────────────────────────────────────
  {
    id: 'reports.generate',
    category: 'reports',
    title: { en: 'Generating Reports', ar: 'إنشاء التقارير' },
    description: { en: 'How to generate and customize engineering reports', ar: 'كيفية إنشاء وتخصيص التقارير الهندسية' },
    content: {
      en: `**Report Types:**\n- **Compliance Report** — Standards verification (NFPA 72, BS 5839)\n- **Calculation Report** — Detailed analysis results\n- **Summary Report** — Executive overview\n- **Audit Report** — System configuration audit\n\n**Steps:**\n1. Navigate to **Reports** from the sidebar\n2. Select report type\n3. Choose source project and study\n4. Configure report options (format, sections)\n5. Click **Generate Report**\n\n**Export Formats:**\n- PDF (primary)\n- DOCX (editable)\n- CSV (data only)\n- JSON (API integration)`,
      ar: `**أنواع التقارير:**\n- **تقرير الامتثال** — التحقق من المعايير (NFPA 72، BS 5839)\n- **تقرير الحسابات** — نتائج التحليل التفصيلية\n- **تقرير الملخص** — نظرة عامة تنفيذية\n- **تقرير التدقيق** — تدقيق تكوين النظام\n\n**الخطوات:**\n1. انتقل إلى **التقارير** من الشريط الجانبي\n2. حدد نوع التقرير\n3. اختر المشروع والدراسة المصدر\n4. قيم خيارات التقرير (التنسيق، الأقسام)\n5. انقر على **إنشاء التقرير**\n\n**تنسيقات التصدير:**\n- PDF (أساسي)\n- DOCX (قابل للتعديل)\n- CSV (بيانات فقط)\n- JSON (تكامل API)`,
    },
    tags: ['report', 'generate', 'pdf', 'compliance', 'تقرير', 'إنشاء', 'امتثال'],
    navigateTo: '/reports',
    relatedTopics: ['projects.manage', 'fire-alarm.detector-placement'],
  },

  // ─── Digital Twin ─────────────────────────────────────────────────
  {
    id: 'digital-twin.overview',
    category: 'digital-twin',
    title: { en: 'Digital Twin Overview', ar: 'نظرة عامة على التوأم الرقمي' },
    description: { en: 'Understanding the digital twin synchronization', ar: 'فهم مزامنة التوأم الرقمي' },
    content: {
      en: `**What is a Digital Twin?**\nA digital twin is a real-time virtual replica of your physical power system or fire alarm network.\n\n**Features:**\n- Real-time state synchronization\n- Predictive maintenance alerts\n- What-if scenario simulation\n- Historical data comparison\n- Automated compliance monitoring\n\n**Getting Started:**\n1. Connect to your SCADA/BMS system\n2. Map devices to twin entities\n3. Enable real-time sync\n4. Monitor dashboards for anomalies`,
      ar: `**ما هو التوأم الرقمي؟**\nالتوأم الرقمي هو نسخة افتراضية في الوقت الفعلي من نظام القدرة_physical أو شبكة إنذار الحريق.\n\n**الميزات:**\n- مزامنة الحالة في الوقت الفعلي\n- تنبيهات الصيانة التنبؤية\n- محاكاة سيناريو ما إذا\n- مقارنة البيانات التاريخية\n- مراقبة الامتثال التلقائية\n\n**البدء:**\n1. الاتصال بنظام SCADA/BMS\n2. تعيين الأجهزة لكيانات التوأم\n3. تفعيل المزامنة المباشرة\n4. مراقبة لوحات التحكم للشذوذ`,
    },
    tags: ['digital', 'twin', 'sync', 'real-time', 'توأم', 'رقمي', 'مزامنة'],
    navigateTo: '/digital-twin',
    relatedTopics: ['dashboard.overview'],
  },

  // ─── Settings ─────────────────────────────────────────────────────
  {
    id: 'settings.backend',
    category: 'settings',
    title: { en: 'Backend Configuration', ar: 'تكوين الخادم' },
    description: { en: 'Configure the engineering service backend connection', ar: 'تكوين اتصال خادم الخدمة الهندسية' },
    content: {
      en: `**Backend Settings:**\n- **Service URL** — URL of the FastAPI engineering service\n- **API Key** — Authentication key for the backend\n- **Timeout** — Request timeout in seconds\n- **Auto-retry** — Enable automatic retry on failure\n\n**Connection Status:**\n- 🟢 Connected — Backend is healthy\n- 🟡 Degraded — Backend responding slowly\n- 🔴 Disconnected — Backend unavailable\n\n**Troubleshooting:**\n- Check if the backend service is running\n- Verify the API key is correct\n- Check network connectivity\n- Review firewall rules`,
      ar: `**إعدادات الخادم:**\n- **رابط الخدمة** — رابط خدمة FastAPI الهندسية\n- **مفتاح API** — مفتاح المصادقة للخادم\n- **مهلة الانتظار** — مهلة الطلب بالثواني\n- **إعادة المحاولة التلقائية** — تفعيل إعادة المحاولة التلقائية عند الفشل\n\n**حالة الاتصال:**\n- 🟢 متصل — الخادم يعمل بشكل طبيعي\n- 🟡 متدهور — الخادم يستجيب ببطء\n- 🔴 منقطع — الخادم غير متاح\n\n**استكشاف الأخطاء وإصلاحها:**\n- تحقق من تشغيل خدمة الخادم\n- تحقق من صحة مفتاح API\n- تحقق من اتصال الشبكة\n- مراجعة قواعد جدار الحماية`,
    },
    tags: ['settings', 'backend', 'config', 'api', 'إعدادات', 'خادم', 'تكوين'],
    navigateTo: '/settings',
    relatedTopics: ['troubleshooting.backend'],
  },

  // ─── Troubleshooting ──────────────────────────────────────────────
  {
    id: 'troubleshooting.backend',
    category: 'troubleshooting',
    title: { en: 'Backend Unavailable', ar: 'الخادم غير متاح' },
    description: { en: 'The engineering service is not responding', ar: 'خدمة الخدمة الهندسية لا تستجيب' },
    content: {
      en: `**Symptoms:**\n- "Backend Unavailable" error in the UI\n- Studies fail to execute\n- Status indicator shows red\n\n**Solutions:**\n1. **Check if the backend is running:**\n   \`\`\`bash\n   curl http://localhost:8000/healthz\n   \`\`\`\n2. **Start the backend:**\n   \`\`\`bash\n   python engineering_service.py --port 8000\n   \`\`\`\n3. **Check the URL in Settings**\n4. **Verify no firewall is blocking port 8000**\n5. **Check Docker if using containers:**\n   \`\`\`bash\n   docker compose ps\n   \`\`\``,
      ar: `**الأعراض:**\n- خطأ "الخادم غير متاح" في واجهة المستخدم\n- فشل تنفيذ الدراسات\n- مؤشر الحالة يظهر بالأحمر\n\n**الحلول:**\n1. **تحقق من تشغيل الخادم:**\n   \`\`\`bash\n   curl http://localhost:8000/healthz\n   \`\`\`\n2. **تشغيل الخادم:**\n   \`\`\`bash\n   python engineering_service.py --port 8000\n   \`\`\`\n3. **تحقق من الرابط في الإعدادات**\n4. **تأكد من عدم حظر جدار الحماية للمنفذ 8000**\n5. **تحقق من Docker إذا كنت تستخدم الحاويات:**\n   \`\`\`bash\n   docker compose ps\n   \`\`\``,
    },
    tags: ['backend', 'unavailable', 'error', 'connection', 'خادم', 'غير متاح', 'خطأ'],
    navigateTo: '/diagnostics',
    relatedTopics: ['settings.backend', 'troubleshooting.api'],
  },
  {
    id: 'troubleshooting.api',
    category: 'troubleshooting',
    title: { en: 'API Errors', ar: 'أخطاء API' },
    description: { en: 'Common API error codes and their solutions', ar: 'أكواد أخطاء API الشائعة وحلولها' },
    content: {
      en: `**Common Error Codes:**\n\n**400 Bad Request** — Invalid input data\n- Check required fields\n- Verify data types match expected format\n\n**401 Unauthorized** — Authentication failed\n- Verify API key is correct\n- Check token expiration\n\n**403 Forbidden** — Insufficient permissions\n- Your role may not have access\n- Contact administrator\n\n**404 Not Found** — Resource does not exist\n- Check the resource ID\n- Verify the endpoint URL\n\n**429 Too Many Requests** — Rate limited\n- Wait before retrying\n- Reduce request frequency\n\n**500 Internal Server Error** — Server-side issue\n- Check backend logs\n- Restart the service`,
      ar: `**أكواد الأخطاء الشائعة:**\n\n**400 طلب سيئ** — بيانات إدخال غير صالحة\n- تحقق من الحقول المطلوبة\n- تأكد من تطابق أنواع البيانات\n\n**401 غير مصرح** — فشل المصادقة\n- تحقق من صحة مفتاح API\n- تحقق من انتهاء صلاحية الرمز\n\n**403 محظور** — صلاحيات غير كافية\n- دورك قد لا يكون لديه وصول\n- تواصل مع المسؤول\n\n**404 غير موجود** — المورد غير موجود\n- تحقق من معرّف المورد\n- تحقق من عنوان URL\n\n**429 طلبات كثيرة جداً** — تم تقييد المعدل\n- انتظر قبل إعادة المحاولة\n- قلل تكرار الطلبات\n\n**500 خطأ داخلي في الخادم** — مشكلة في الخادم\n- تحقق من سجلات الخادم\n- أعد تشغيل الخدمة`,
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
      en: `**Common Issues:**\n\n**Login fails immediately:**\n- Verify username and password\n- Check for account lockout (5 failed attempts)\n- Ensure backend is running\n\n**Token expired:**\n- Tokens expire after 30 minutes\n- Refresh tokens expire after 7 days\n- Use the refresh endpoint to get new tokens\n\n**JWT validation error:**\n- Token may be malformed\n- Secret key may have changed\n- Clear browser storage and re-login\n\n**MFA issues:**\n- Check TOTP code timing\n- Verify authenticator app sync\n- Use backup codes if available`,
      ar: `**المشكلات الشائعة:**\n\n**فشل تسجيل الدخول فوراً:**\n- تحقق من اسم المستخدم وكلمة المرور\n- تحقق من حظر الحساب (5 محاولات فاشلة)\n- تأكد من تشغيل الخادم\n\n**انتهت صلاحية الرمز:**\n- تنتهي صلاحية الرموز بعد 30 دقيقة\n- تنتهي صلاحية رموز التحديث بعد 7 أيام\n- استخدم نقطة نهاية التحديث للحصول على رموز جديدة\n\n**خطأ في التحقق من JWT:**\n- قد يكون الرمز مشوهاً\n- قد تغير المفتاح السري\n- مسح التخزين المحلي وإعادة تسجيل الدخول\n\n**مشاكل MFA:**\n- تحقق من توقيت رمز TOTP\n- تحقق من مزامنة تطبيق المصادقة\n- استخدم رموز النسخ الاحتياطي إذا كانت متاحة`,
    },
    tags: ['auth', 'login', 'token', 'jwt', 'mfa', 'مصادقة', 'دخول', 'رمز'],
    navigateTo: '/settings',
    relatedTopics: ['settings.backend', 'troubleshooting.api'],
  },
  {
    id: 'integration.scada',
    category: 'settings',
    title: { en: 'SCADA System Integration (zenon)', ar: 'ربط نظام الإسكادا (زينون)' },
    description: { en: 'Configure and monitor Copa-Data zenon SCADA system connection', ar: 'تكوين ومراقبة اتصال نظام إسكادا زينون (zenon)' },
    content: {
      en: `**zenon SCADA Connectivity:**\nCopa-Data zenon SCADA is integrated directly with the Ahmed etap platform via the SCADA Agent, facilitating real-time status monitoring, state estimation, and IEC 61850 data model mapping.\n\n**Configuration Parameters:**\n- **SCADA System Type** — Copa-Data zenon SCADA (default)\n- **SCADA Server URL** — HTTP endpoint of the zenon REST API/Web Server\n- **Project Name** — Name of the active zenon project to synchronize variables from\n- **Sync Interval** — Interval in seconds for pulling real-time variables\n- **SCADA API Key** — Authorization secret token for secure data transfer\n\n**Common Operations:**\n1. Mapping zenon tags to ETAP nodes\n2. Real-time alarm monitoring\n3. Single-line diagram animation based on live breaker states`,
      ar: `**ربط نظام إسكادا زينون (zenon SCADA):**\nيتكامل نظام Copa-Data zenon SCADA مباشرة مع منصة Ahmed etap عبر وكيل الإسكادا، مما يسهل مراقبة الحالة الحية وتقدير حالة النظام ومطابقة نموذج بيانات المعيار IEC 61850.\n\n**محددات التكوين:**\n- **نوع نظام الإسكادا** — Copa-Data zenon SCADA (افتراضي)\n- **رابط الخادم** — الرابط الشبكي لخدمة zenon REST API/Web Server\n- **اسم المشروع** — اسم مشروع zenon النشط لمزامنة المتغيرات منه\n- **معدل المزامنة** — الوقت بالثواني لجلب قيم المتغيرات في الوقت الفعلي\n- **مفتاح API** — رمز التفويض السري لنقل البيانات الآمن\n\n**العمليات الشائعة:**\n1. مطابقة وسوم (tags) زينون مع عقد شبكة إيتاب\n2. مراقبة الإنذارات في الوقت الفعلي\n3. تحريك مخطط الخط الواحد بناءً على حالة المفاتيح الحية`,
    },
    tags: ['scada', 'zenon', 'integration', 'iec61850', 'إسكادا', 'زينون', 'ربط'],
    navigateTo: '/settings',
    relatedTopics: ['digital-twin.overview', 'settings.backend'],
  },
]

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
  { id: 'keyboard-shortcuts' as const, label: { en: 'Keyboard Shortcuts', ar: 'اختصارات لوحة المفاتيح' } },
] as const
