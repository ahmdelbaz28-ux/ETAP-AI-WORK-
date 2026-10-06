---
title: "منصة AhmedETAP للهندسة الكهربائية والذكاء الاصطناعي"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

<div align="center">

[English](README.md) | [العربية](README.ar.md)

<br/>

<h1>⚡ منصة AhmedETAP للهندسة الكهربائية</h1>
<h3>المنصة الذكية المستقلة لهندسة أنظمة القوى والذكاء الاصطناعي المؤسسي</h3>

<p>
  منصة هندسية ذكية متقدمة تجمع بين <strong>27 وكيلاً متخصصاً من وكلاء الذكاء الاصطناعي</strong>
  مع محركات حسابية رياضية معتمدة وفق المعايير الدولية IEC و IEEE — تمكّن المهندسين من الانتقال
  من استفسار باللغة الطبيعية إلى تقرير هندسي تدقيقي معتمد في ثوانٍ معدودة.
</p>

<br/>

[![Version](https://img.shields.io/badge/الإصدار-2.1.0-gold?style=for-the-badge&logo=semantic-release&logoColor=white)](README.md)
[![Python](https://img.shields.io/badge/بايثون-3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/رياكت-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/تايب_سscript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://typescriptlang.org)
[![License](https://img.shields.io/badge/الترخيص-MIT-22c55e?style=for-the-badge&logo=open-source-initiative&logoColor=white)](LICENSE)

<br/>

**[🚀 واجهة المستخدم المباشرة — Vercel](https://etap-ai-work.vercel.app)** &nbsp;•&nbsp;
**[🧠 واجهة برمجة التطبيقات — Hugging Face](https://ahmdelbaz28-ahmedetap-platform.hf.space/docs)** &nbsp;•&nbsp;
**[📚 مستندات التوثيق](docs/)** &nbsp;•&nbsp;
**[🔧 المرجع السريع للـ API](docs/API_QUICKREF.md)** &nbsp;•&nbsp;
**[📖 دليل البدء السريع](QUICKSTART.ar.md)**

</div>

---

## 📋 جدول المحتويات (Table of Contents)

- [نظرة عامة على المنصة](#-نظرة-عامة-على-المنصة)
- [المعايير الهندسية المعتمدة](#-المعايير-الهندسية-المعتمدة)
- [هيكلية الوكلاء الأذكياء (27 وكيلاً معتمداً)](#-هيكلية-الوكلاء-الأذكياء)
- [البدء السريع](#-البدء-السريع)
- [الدروس التعليمية وخطوات العمل](#-الدروس-التعليمية-وخطوات-العمل)
- [الأمان المؤسسي والتحكم المزدوج](#-الأمان-المؤسسي-والتحكم-المزدوج)
- [المساهمة وإدارة الديون التقنية](#-المساهمة-وإدارة-الديون-التقنية)
- [الترخيص](#-الترخيص)

---

## 🎯 نظرة عامة على المنصة

منصة **AhmedETAP** هي بيئة متكاملة ثنائية المحرك (Dual-Runtime Architecture) تجمع بين بيئة التشغيل الحسابية الصارمة في بايثون لضمان مطابقة قوانين الفيزياء والرياضيات، وبيئة Mastra (TypeScript) لإدارة تدفق المحادثات وتوجيه الوكلاء الأذكياء.

### القدرات الهندسية الأساسية
1. **سريان الأحمال (Load Flow):** محرك Newton-Raphson مع الجاكوبي التحليلي ومحرك Fast Decoupled وفق IEEE 3002.7.
2. **تحليل القصر الكهربائي (Short-Circuit):** احتساب تيارات القصر المتناظرة وغير المتناظرة ($I_k''$, $I_p$, $I_b$) وفق IEC 60909-0:2016.
3. **تقييم وميض القوس الكهربائي (Arc Flash):** نموذج IEEE 1584-2018 بجميع التكوينات الهندسية وتحديد درجات الوقاية وفق NFPA 70E-2024.
4. **تنسيق أجهزة الحماية (Protection Coordination):** منحنيات الزمن والتيار (TCC) وتدقيق هوامش الفصل الانتقائي (CTI) وفق IEC 60255 و IEEE 242.
5. **بدء تشغيل المحركات (Motor Starting):** محاكاة ديناميكية في المجال الزمني وفق IEEE 399 وتقييم هبوط الجهد اللحظي.
6. **التحليل التوافقي (Harmonic Analysis):** تدقيق تشوه الجهد التوافقي الكلي THD والـ TDD وفق معيار IEEE 519-2022.
7. **الطاقات المتجددة والتخزين (Renewables & BESS):** دمج الطاقة الشمسية والرياح وفق IEEE 1547 وتحسين شحن وتفريغ البطاريات وفق IEC 62933.
8. **الأتمتة التفاعلية ونظم سكادا (SCADA & ADMS):** تكامل مع بروتوكولات IEC 61850 وتكامل رقمي وتوأمة جغرافية مع نظم GIS و ETAP COM.

---

## 📐 المعايير الهندسية المعتمدة

| المعيار الهندسي | المجال التطبيقي | طريقة الحساب المتبعة | حالة الاعتماد |
| :--- | :--- | :--- | :---: |
| **IEEE 3002.7** | سريان الأحمال المستقر | Newton-Raphson مع Analytical Jacobian | 🟢 معتمد وموثق |
| **IEC 60909-0:2016** | حسابات القصر المتماثل وغير المتماثل | Driving-point Zbus & Sparse LU Factorization | 🟢 معتمد وموثق |
| **IEEE 1584-2018** | تقييم طاقة الوميض الكهربائي والمسافات | Two-stage empirical model (VCB/VCBB/HCB/VOA/HOA) | 🟢 معتمد وموثق |
| **NFPA 70E-2024** | مستويات معدات الوقاية الشخصية (PPE) | Table 130.5(G) Category Classification (0 to 4) | 🟢 معتمد وموثق |
| **IEC 60255** | خصائص ومرحلات الحماية الكهربائية | IEC Standard Inverse, Very, Extremely & Long Time | 🟢 معتمد وموثق |
| **IEEE 399 (Brown Book)** | بدء تشغيل المحركات واستقرار الجهد | Dynamic Runge-Kutta 4th Order / Voltage Sag Drop | 🟢 معتمد وموثق |
| **IEEE 519-2022** | التوافق الكهرومغناطيسي والتوافقيات | Voltage & Current Distortion / PCC Limits | 🟢 معتمد وموثق |
| **IEEE 80-2013** | شبكات التأريض الأرضية | أقصى جهود التلامس والخطوة (Touch/Step Potentials) | 🟢 معتمد وموثق |
| **IEC 60364 / 60287** | تحديد مقاطع الكابلات الكهربائية | حساب السعة الحرارية وهبوط الجهد المستمر | 🟢 معتمد وموثق |
| **IEC 61850** | بروتوكولات ونماذج بيانات المحطات | SCL / CID / GOOSE Modeling | 🟢 معتمد وموثق |

---

## 🤖 هيكلية الوكلاء الأذكياء

تعتمد المنصة رسمياً على **27 وكيلاً معتمداً (Canonical Specialist Agents)**:
- **وكلاء الحسابات الهندسية (13 وكيلاً):** Load Flow, Short Circuit, Arc Flash, Protection, Harmonic, OPF, Motor Starting, Stability, Cable Sizing, Earth Grid, Renewable, Battery Storage, Generative Design.
- **وكلاء العمليات والبيئة التحتية (5 وكلاء):** SCADA, Digital Twin, Weather, Anomaly Detection, Predictive Analytics.
- **وكلاء التوجيه والحوكمة والرقابة (9 وكلاء):** Goal Planner, Power System Coordinator, ETAP Expert Skill, ETAP GUI, Code Guard, Validation Agent, Report Generation Agent, Optimization Agent, AhmedETAP Orchestrator.

---

## 🚀 البدء السريع

### 1. المتطلبات الأساسية
- **Python**: 3.12 أو 3.13
- **Node.js**: 20 أو أحدث
- **Git** و **pnpm**

### 2. التثبيت والتشغيل المحلي
```bash
# استنساخ المستودع
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-

# تجهيز البيئة الافتراضية للبايثون
python -m venv .venv
source .venv/bin/activate  # في ويندوز: .venv\Scripts\activate
pip install -r requirements.txt

# تشغيل خادم الواجهة الخلفية
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# تشغيل واجهة المستخدم التفاعلية
cd ui
pnpm install
pnpm dev
# فتح المتصفح على: http://localhost:5173
```

للمزيد من خيارات التثبيت (مثل Docker و Helm)، راجع [دليل البدء السريع الكامل (QUICKSTART.ar.md)](QUICKSTART.ar.md).

---

## 📚 الدروس التعليمية وخطوات العمل

توفر المنصة أدلة عمل تدريجية تفصيلية في المجلد [`docs/TUTORIALS/`](docs/TUTORIALS/):
1. **[الدرس الأول: من سريان الأحمال إلى القصر وتنسيق الحماية](docs/TUTORIALS/01_load_flow_short_circuit_protection.md):** تدفق هندسي متكامل لربط الشبكة واختبار الفصل الانتقائي.
2. **[الدرس الثاني: بدء تشغيل المحركات وهبوط الجهد](docs/TUTORIALS/02_motor_starting_voltage_drop.md):** دراسة الإقلاع المباشر والناعم وتحليل عزم الدوران.
3. **[الدرس الثالث: تقييم وميض القوس الكهربائي](docs/TUTORIALS/03_arc_flash_hazard_evaluation.md):** حساب طاقات الوميض ومسافات الأمان وملصقات السلامة.

---

## 🔐 الأمان المؤسسي والتحكم المزدوج

- **مبدأ الصانع والمدقق (Maker-Checker):** العمليات الحساسة في الشبكة تتطلب موافقة مهندس معتمد.
- **عزل الكود (Hard Denied):** يتم حظر أي استدعاءات خارجية غير آمنة لنظام التشغيل أو أدوات الأوامر.
- **تتبع البيانات (Data Provenance):** لا يُسمح بتخمين أي قيم هندسية؛ كل قيمة ترتبط بمصدر صريح (إدخال مستخدم، بيانات مشروع، أو معيار معتمد).

---

## 🤝 المساهمة وإدارة الديون التقنية

نرحب بجميع المساهمات الهندسية والبرمجية!
- للاطلاع على معايير وقواعد المساهمة: راجع [`CONTRIBUTING.ar.md`](CONTRIBUTING.ar.md).
- للعمل على بنود الديون التقنية: راجع قسم [العمل على الديون التقنية في CONTRIBUTING.md](CONTRIBUTING.md#working-on-technical-debt) واستشر الجدول في [`docs/STATUS.md`](docs/STATUS.md).

---

## 📄 الترخيص

مرخص تحت رخصة [MIT License](LICENSE).
