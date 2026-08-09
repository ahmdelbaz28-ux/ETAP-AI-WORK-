# 🚀 إعداد الأسرار لـ GitHub Actions
=====================================

هذا الدليل يوضح كيفية إضافة الأسرار في GitHub Repository Secrets لتفعيل التزامن التلقائي بين جميع المنصات.

---

## 📋 الأسرار المطلوبة

اذهب إلى: `GitHub Repo → Settings → Secrets and variables → Actions → New repository secret

| Secret Name          | القيمة                                                                 |
|---------------------|-------------------------------------------------------------------------|
| `VERCEL_TOKEN`      | `vcp_your_vercel_token_here` |
| `VERCEL_PROJECT_ID`| `prj_your_project_id_here`                                 |
| `HF_TOKEN`         | `hf_your_huggingface_token_here`                            |
| `LANGWATCH_API_KEY`| `sk-lw-your_langwatch_key_here`            |
| `SMITHERY_API_KEY` | `your_smithery_key_here`                              |
| `GH_PAT`           | (Personal Access Token من GitHub - يحتاج صلاحيات Read+Write للمحتوى والـ Pull Requests) |

---

## 🛠️ كيفية الحصول على كل مفتاح:

### 1. VERCEL_TOKEN
- اذهب إلى: https://vercel.com/account/tokens
- أنشئ توكن جديد باسم "GitHub Sync"
- اختر صلاحيات: `Full Account`

### 2. VERCEL_PROJECT_ID
- اذهب إلى مشروعك على Vercel
- Settings → General
- تجده تحت "Project ID"

### 3. HF_TOKEN
- https://huggingface.co/settings/tokens
- أنشئ توكن جديد باسم "GitHub Sync"
- صلاحيات: `Write`

### 4. LANGWATCH_API_KEY
- https://app.langwatch.ai/
- Settings → API Keys

### 5. SMITHERY_API_KEY
- https://smithery.ai/console/api-keys

### 6. GH_PAT
- https://github.com/settings/tokens
- أنشئ Fine-grained token
- Repository access: اختر مشروعك
- صلاحيات:
  - `Contents`: Read and write
  - `Pull requests`: Read and write

---

## 🔄 كيف يعمل التزامن تلقائياً:

| الحدث                      | ماذا يحدث؟                                                              |
|---------------------------|--------------------------------------------------------------------------|
| Push إلى `main`            | Vercel ينشر تلقائيًا + HF Space يتزامن + LangWatch يتم إعلامه           |
| تحرير يدوياً على HF     | يتم اكتشافه يوميًا ويتم إنشاء PR على GitHub تلقائيًا                     |
| تشغيل يدوياً من Actions | يمكن تشغيل التزامن يدوياً في أي وقت                                   |

---

## ✅ التأكد من العمل:

بعد إضافة الأسرار:
1. اضف أي تغيير صغير (مثل تعديل ملف .md)
2. رفعه إلى `main`
3. اذهب إلى: GitHub → Actions
4. شاهد سير عمل "Cross-Platform Sync" يعمل ✅

---

## 📂 ملفات التزامن:

- `.github/workflows/sync-platforms.yml → التزامن الشامل
- `.github/workflows/sync-hf-space.yml → تزامن HF فقط
