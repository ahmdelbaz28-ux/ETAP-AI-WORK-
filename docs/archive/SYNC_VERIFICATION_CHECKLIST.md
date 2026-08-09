# ✅ قائمة فحص التزامن الشامل

## 📋 قبل البدء

- [ ] جميع الأسرار أضيفت في GitHub Secrets
- [ ] ملف `.mcp.json` محلي محدث
- [ ] ملف `.gitignore` يتجاهل جميع الملفات الحساسة

---

## 🌐 مراحل التزامن

### 1️⃣ GitHub → Vercel
- [ ] Push إلى `main` يُشغّل Vercel تلقائيًا
- [ ] يبني الـ UI بنجاح
- [ ] يظهر Deployment جديد في Vercel

### 2️⃣ GitHub → HuggingFace Space
- [ ] يُقوم بنسخ جميع الملفات إلى HF Space
- [ ] يظهر Commit جديد في HF: "🔄 Auto-sync from GitHub main @ ..."
- [ ] البناء في HF ينجح

### 3️⃣ GitHub → LangWatch
- [ ] يتم إعلام LangWatch بالـ Deployment الجديد
- [ ] مفتاح API صالح (HTTP 200)

### 4️⃣ GitHub → Smithery
- [ ] يتم التحقق من إمكانية الوصول إلى Smithery
- [ ] مفتاح API صالح (UUID)

### 5️⃣ HF → GitHub (Drift Detection)
- [ ] يتم تشغيله يوميًا في 03:00 UTC
- [ ] يكتشف التغييرات على HF ويقوم بإنشاء PR

---

## 🔒 الأمان

- [ ] لا يتم رفع `.mcp.json` إلى Git
- [ ] لا يتم رفع `.env` إلى Git
- [ ] جميع الأسرار في GitHub Secrets فقط
- [ ] ملف Backup موجود: `.mcp.json.backup`

---

## 📂 ملفات المشروع

- [ ] `.github/workflows/sync-platforms.yml` موجود
- [ ] `.github/workflows/sync-hf-space.yml` موجود
- [ ] `.mcp.json` محلي مع جميع الأسرار
- [ ] `README.hf.md` موجود لـ HuggingFace
- [ ] `Dockerfile` موجود لـ HF Space

---

## 🧪 الاختبار السريع

1. عدل أي ملف (مثل `README.md`)
2. رفعه إلى `main`
3. اذهب إلى GitHub → Actions
4. شاهد سير عمل "Cross-Platform Sync" يعمل ✅
5. تحقق من Vercel + HF + LangWatch
