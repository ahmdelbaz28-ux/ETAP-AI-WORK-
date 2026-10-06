---
title: "دليل البدء السريع لمنصة AhmedETAP"
version: "2.1.0"
last_updated: "2026-10-06"
maintainer: "Eng. Ahmed Elbaz / Platform Core Team"
---

# 🚀 منصة AhmedETAP — دليل البدء السريع

**منصة الذكاء الاصطناعي وهندسة القوى الكهربائية الافتراضية الإصدار v2.1.0**

[English](QUICKSTART.md) | [العربية](QUICKSTART.ar.md)

---

## 📋 جدول المحتويات

- [1. المتطلبات الأساسية للنظام](#1-المتطلبات-الأساسية-للنظام)
- [2. خطوات التثبيت والإعداد](#2-خطوات-التثبيت-والإعداد)
- [3. تنفيذ أول دراسة هندسية](#3-تنفيذ-أول-دراسة-هندسية)
- [4. الدروس التعليمية وخطوات العمل التفصيلية](#4-الدروس-التعليمية-وخطوات-العمل-التفصيلية)
- [5. التشغيل البرمجي عبر API](#5-التشغيل-البرمجي-عبر-api)
- [6. التحقق واستكشاف الأخطاء](#6-التحقق-واستكشاف-الأخطاء)
- [7. المراجع والروابط المفيدة](#7-المراجع-والروابط-المفيدة)

---

## 1. المتطلبات الأساسية للنظام

- **Python**: الإصدار 3.12 أو 3.13 (معمارية 64-بت)
- **Node.js**: الإصدار 20 فما فوق (مع مدير الحزم `pnpm` أو `npm`)
- **Git**: 2.30+
- **Docker و Docker Compose**: (اختياري، لنشر الحاويات المؤسسية)

---

## 2. خطوات التثبيت والإعداد

### الطريقة الأولى: بيئة التطوير المحلية (Local Development)

1. **استنساخ المستودع البرمجي:**
   ```bash
   git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
   cd ETAP-AI-WORK-
   ```

2. **تهيئة ملف المتغيرات البيئية:**
   ```bash
   cp .env.example .env
   # قم بتعديل المفاتيح السرية مثل JWT_SECRET_KEY و ENGINEERING_SERVICE_API_KEY
   ```

3. **تثبيت حزم بايثون في بيئة افتراضية:**
   ```bash
   python -m venv .venv
   # في نظام ويندوز:
   .venv\Scripts\activate
   # في أنظمة لينكس وماك:
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. **تشغيل خادم FastAPI للواجهة الخلفية:**
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **تشغيل واجهة المستخدم Chat-First v3.0:**
   ```bash
   cd ui
   pnpm install
   pnpm run dev
   # تصفح المنصة عبر الرابط: http://localhost:5173
   ```

### الطريقة الثانية: باستخدام Docker Compose

```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
docker compose up -d
# الوصول إلى المنصة عبر: http://localhost:8000
```

---

## 3. تنفيذ أول دراسة هندسية

### استفسار باللغة الطبيعية عبر واجهة المحادثة
افتح واجهة المحادثة الهندسية في المتصفح واكتب:
```text
قم بتشغيل دراسة سريان الأحمال على مغذي IEEE 9-bus WSCC بدقة تقارب 0.001 ميجا فولت أمبير.
```
سيقوم وكيل التنسيق (Coordinator Agent) بتحليل طلبك وتوجيهه إلى وكيل سريان الأحمال (Load Flow Agent) الذي ينفذ معادلات Newton-Raphson عبر `engine/dispatch.py`، ثم يعيد جدول الجهد الكهربائي، نسب تحميل الخطوط، وتدقيق التوافق مع المعايير.

---

## 4. الدروس التعليمية وخطوات العمل التفصيلية

للاطلاع على أدلة هندسية متكاملة مدعومة بأمثلة الإدخال وتحليل الأخطاء، تصفح مجلد الدروس في [`docs/TUTORIALS/`](docs/TUTORIALS/):

1. **[الدرس 01: سريان الأحمال $\rightarrow$ القصر الكهربائي $\rightarrow$ تنسيق الحماية](docs/TUTORIALS/01_load_flow_short_circuit_protection.md)**  
   *المعايير المعتمدة:* [IEEE 3002.7](docs/GLOSSARY.md#ieee-30027), [IEC 60909](docs/GLOSSARY.md#iec-60909), [IEC 60255](docs/GLOSSARY.md#iec-60255).  
   *النطاق:* المحاكاة الكاملة لسريان القدرة، حساب تيارات العطل المتماثلة وغير المتماثلة ($I_k''$, $I_p$, $I_b$)، وتدقيق فترات التنسيق الزمني (CTI) لمنحنيات TCC.

2. **[الدرس 02: بدء تشغيل المحركات وتحليل هبوط الجهد](docs/TUTORIALS/02_motor_starting_voltage_drop.md)**  
   *المعايير المعتمدة:* [IEEE 399](docs/GLOSSARY.md#ieee-399), IEC 60034-12.  
   *النطاق:* مقارنة الإقلاع المباشر بالبادئ الناعم (Soft Starter)، فحص هبوط الجهد اللحظي على القضبان ($\Delta V \le 15\%$)، وهوامش عزم تسارع المحرك.

3. **[الدرس 03: تقييم مخاطر وميض القوس الكهربائي](docs/TUTORIALS/03_arc_flash_hazard_evaluation.md)**  
   *المعايير المعتمدة:* [IEEE 1584](docs/GLOSSARY.md#ieee-1584), [NFPA 70E](docs/GLOSSARY.md#ppe).  
   *النطاق:* نموذج IEEE 1584-2018 المعتمد للهندسة الفراغية (VCB/HCB)، احتساب طاقة الوميض ($cal/cm^2$)، وتصنيف معدات الوقاية الشخصية وطباعة ملصقات التحذير.

---

## 5. التشغيل البرمجي عبر API

يمكنك إرسال أمر دراسة مباشرة باستخدام `curl`:
```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $ENGINEERING_SERVICE_API_KEY" \
  -d '{
    "study_type": "load_flow",
    "parameters": {
      "system_id": "ieee_9bus",
      "max_iterations": 20,
      "tolerance": 0.001
    }
  }'
```

راجع [جدول المرجع السريع للـ API](docs/API_QUICKREF.md) و [مرجع الـ API الأساسي](docs/API_REFERENCE.md).

---

## 6. التحقق واستكشاف الأخطاء

لتشغيل الاختبارات التشخيصية الأساسية:
```bash
pytest tests/ -q -k "test_health or test_load_flow or test_short_circuit"
```

في حال واجهتك أي صعوبات:
- تحقق من سلامة واجهة الخدمة عبر: `http://localhost:8000/api/v1/health`.
- راجع [دليل العمليات والتشغيل](docs/OPERATIONS_RUNBOOK.md) و [دليل استكشاف الأعطال](docs/TROUBLESHOOTING_GUIDE.md).

---

## 7. المراجع والروابط المفيدة

- [قاموس المصطلحات والمفاهيم الهندسية](docs/GLOSSARY.md)
- [المرجع الشامل لواجهات برمجة التطبيقات](docs/API_REFERENCE.md)
- [المرجع السريع للـ API](docs/API_QUICKREF.md)
- [إرشادات المساهمة في المشروع](CONTRIBUTING.ar.md)
