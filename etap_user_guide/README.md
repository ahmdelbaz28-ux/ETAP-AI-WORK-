# ETAP User Guide Integration
# دليل مستخدم ETAP - التكامل مع المنصة

## 📚 نظرة عامة

هذا المجلد يحتوي على **دليل مستخدم ETAP الرسمي** المدمج في المنصة ليكون **المرجع الأساسي والموثوق** لجميع عمليات ETAP.

**المحتوى:**
- 62 ملف PDF (Part 1-62)
- 55 ملف AC Element
- **الإجمالي: 117 ملف PDF**

---

## ⚠️ قواعد إلزامية لجميع الوكلاء

### القاعدة #1: الدليل هو المرجع الأساسي

**دليل مستخدم ETAP هو المرجع الأول والأوحد لجميع عمليات ETAP.**

يجب على كل وكيل:
1. ✅ **استشارة الدليل** قبل أي عملية ETAP
2. ✅ **اتباع الخطوات** كما هي موثقة في الدليل
3. ✅ **عدم الانحراف** عن الإجراءات الموثقة
4. ✅ **الاستشهاد** بالقسم/الصفحة المحدد
5. ✅ **الإفصاح بوضوح** إذا لم تكن المعلومات موجودة في الدليل

### القاعدة #2: سير العمل الإلزامي

قبل تنفيذ أي عملية ETAP:

```
1. استعلم من محرك RAG
   → استخدم: ETAPGuideRAG.get_etap_procedure()
   
2. تحقق من الخطوات المقترحة
   → استخدم: ETAPGuideRAG.validate_etap_operation()
   
3. نفذ فقط إذا نجح التحقق
   → إذا فشل التحقق، توقف واطلب التوضيح
   
4. وثّق المصدر
   → اذكر دائماً أي قسم من الدليل اتبعت
```

---

## 🛠️ كيفية الاستخدام

### 1. استخراج النصوص من PDF

```bash
# تشغيل سكربت الاستخراج
python etap_user_guide/extract_guide.py
```

**المخرجات:**
- `etap_user_guide/extracted/*.txt` - النصوص المستخرجة
- `etap_user_guide/chunks/*.json` - أجزاء النص للبحث
- `etap_user_guide/index/master_index.json` - الفهرس الرئيسي

### 2. استخدام محرك RAG

```python
from etap_user_guide.etap_guide_rag import ETAPGuideRAG

# تهيئة المحرك
rag = ETAPGuideRAG()

# الحصول على إجراء عملية
procedure = rag.get_etap_procedure("load flow analysis")
print(f"Official procedure: {procedure}")

# التحقق من الخطوات المقترحة
validation = rag.validate_etap_operation(
    "load flow analysis",
    ["Open ETAP", "Create project", "Run study"]
)

if validation["valid"]:
    print("✓ Steps validated - proceed with operation")
else:
    print(f"✗ Validation failed: {validation['issues']}")

# الاستعلام عن سؤال محدد
answer = rag.query("How to add a transformer?")
print(f"Answer: {answer['answer']}")
```

### 3. الوصول المباشر للملفات

```python
# قراءة نص مستخرج
with open('etap_user_guide/extracted/ETAP USER GUIDE_Part1.txt', 'r') as f:
    content = f.read()

# تحميل الفهرس الرئيسي
import json
with open('etap_user_guide/index/master_index.json', 'r') as f:
    index = json.load(f)
    print(f"Total documents: {index['total_documents']}")
    print(f"Total chunks: {index['total_chunks']}")
```

---

## 📖 محتويات الدليل

### الأجزاء الرئيسية (Part 1-62)

| الجزء | الموضوع | الحجم |
|-------|---------|-------|
| Part 1 | مقدمة وواجهة المستخدم | 284 KB |
| Part 2-10 | العمليات الأساسية | ~50 MB |
| Part 11 | AC Elements (مفصل) | 16 MB |
| Part 12 | AC Elements (مفصل) | 16 MB |
| Part 13-20 | دراسات أنظمة القدرة | ~80 MB |
| Part 21-40 | التحليلات المتقدمة | ~100 MB |
| Part 41-62 | مواضيع متخصصة | ~80 MB |
| **All Parts** | **الدليل الكامل** | **196 MB** |

### مجلد AC Element

يحتوي على 55 ملف PDF مفصل لعناصر AC:
- 11.41 - 11.446: وثائق تفصيلية
- كل ملف يغطي عنصر أو وظيفة محددة

---

## 🔍 البحث والاسترجاع

### البحث بالكلمات المفتاحية

```python
results = rag.search("transformer tap settings", top_k=5)

for result in results:
    print(f"Document: {result['metadata']['document']}")
    print(f"Score: {result['score']}")
    print(f"Content: {result['chunk'][:200]}...")
```

### الاستعلام الدلالي

```python
answer = rag.query("What are the steps to run a short circuit analysis?")

if answer["answered"]:
    print(f"Answer: {answer['answer']}")
    print(f"Sources: {answer['sources']}")
    print(f"Confidence: {answer['confidence']}")
```

---

## ✅ التحقق من الامتثال

### التحقق من صحة العملية

```python
validation = rag.validate_etap_operation(
    operation="short circuit analysis",
    proposed_steps=[
        "Open ETAP project",
        "Select Short Circuit module",
        "Configure fault parameters",
        "Run analysis",
        "Review results"
    ]
)

print(f"Valid: {validation['valid']}")
print(f"Official steps: {validation['official_steps']}")
print(f"Issues: {validation['issues']}")
```

### التحقق من التوافق مع المعايير

```python
# التحقق من أن العملية تتبع الدليل
if validation["valid"]:
    print("✓ Operation follows official ETAP procedures")
else:
    print("✗ Operation deviates from official procedures")
    for issue in validation["issues"]:
        print(f"  - {issue}")
```

---

## 📊 الإحصائيات

بعد استخراج النصوص:

```python
import json

with open('etap_user_guide/extraction_summary.json', 'r') as f:
    summary = json.load(f)
    
print(f"Total files: {summary['total_files']}")
print(f"Successful: {summary['successful']}")
print(f"Failed: {summary['failed']}")
print(f"Total pages: {summary['total_pages']}")
print(f"Total characters: {summary['total_characters']:,}")
```

---

## 🚨 التعامل مع الحالات الاستثنائية

### إذا لم تكن المعلومات في الدليل

```python
answer = rag.query("How to use ETAP GIS module?")

if not answer["answered"]:
    print("⚠️ Information not found in ETAP User Guide")
    print("Recommendation:")
    print("  1. Consult ETAP technical support")
    print("  2. Check ETAP official website")
    print("  3. Review ETAP training materials")
```

### إذا فشلت عملية التحقق

```python
if not validation["valid"]:
    print("❌ Validation failed - DO NOT PROCEED")
    print("Issues found:")
    for issue in validation["issues"]:
        print(f"  - {issue}")
    print("\nRecommended actions:")
    print("  1. Review the ETAP User Guide")
    print("  2. Correct the proposed steps")
    print("  3. Re-validate before proceeding")
```

---

## 📝 أمثلة عملية

### مثال 1: تشغيل Load Flow

```python
from etap_user_guide.etap_guide_rag import ETAPGuideRAG
from etap_integration.etap_com import ETAPAutomation

# 1. استشارة الدليل
rag = ETAPGuideRAG()
procedure = rag.get_etap_procedure("load flow analysis")

print("Official procedure:")
for step in procedure["steps"]:
    print(f"  {step}")

# 2. التحقق من الخطوات
proposed_steps = [
    "Launch ETAP",
    "Open project file",
    "Verify input data",
    "Configure load flow settings",
    "Run study",
    "Check convergence",
    "Extract results"
]

validation = rag.validate_etap_operation("load flow analysis", proposed_steps)

if validation["valid"]:
    # 3. تنفيذ العملية
    with ETAPAutomation(visible=True) as etap:
        project = etap.open_project("C:\\Projects\\MyProject.edb")
        result = project.run_study("load_flow")
        
        if result.success:
            print(f"✓ Study completed successfully")
            print(f"Results: {result.data}")
        else:
            print(f"✗ Study failed: {result.error}")
else:
    print("✗ Validation failed - cannot proceed")
```

### مثال 2: إضافة محول

```python
# الاستعلام عن الإجراء
rag = ETAPGuideRAG()
answer = rag.query("How to add a transformer to the one-line diagram?")

if answer["answered"]:
    print("Official procedure from ETAP User Guide:")
    print(answer["answer"])
    
    # استخراج المصادر
    print("\nSources:")
    for source in answer["sources"]:
        print(f"  - {source['document']} (relevance: {source['relevance']})")
else:
    print("⚠️ Procedure not found in ETAP User Guide")
    print("Recommendation: Consult ETAP support")
```

### مثال 3: استكشاف الأخطاء

```python
# استعلام عن مشكلة
rag = ETAPGuideRAG()
answer = rag.query("Load flow does not converge - what to do?")

if answer["answered"]:
    print("Troubleshooting steps from ETAP User Guide:")
    print(answer["answer"])
    
    # التحقق من وجود تحذيرات
    procedure = rag.get_etap_procedure("load flow troubleshooting")
    if procedure["warnings"]:
        print("\n⚠️ Warnings:")
        for warning in procedure["warnings"]:
            print(f"  - {warning}")
else:
    print("⚠️ Troubleshooting not documented")
```

---

## 🔗 التكامل مع الوكلاء

### وكيل ETAP Engineer

يجب على وكيل ETAP Engineer:

```python
# في بداية كل مهمة
from etap_user_guide.etap_guide_rag import ETAPGuideRAG

rag = ETAPGuideRAG()

# عرض التعليمات الإلزامية
print(rag.get_mandatory_instructions())

# قبل أي عملية
procedure = rag.get_etap_procedure(operation_name)

# التحقق من الخطوات
validation = rag.validate_etap_operation(operation_name, proposed_steps)

# التنفيذ فقط إذا نجح التحقق
if validation["valid"]:
    # تنفيذ العملية
    pass
else:
    # التوقف والإبلاغ
    raise ValueError(f"Validation failed: {validation['issues']}")
```

### وكلاء آخرون

جميع الوكلاء الذين يتعاملون مع ETAP يجب أن:

1. ✅ يستشيروا الدليل قبل أي عملية
2. ✅ يتحققوا من صحة الخطوات
3. ✅ يستشهدوا بالمصدر
4. ✅ يبلغوا إذا لم تكن المعلومات متاحة

---

## 📚 المراجع

### الملفات الرئيسية

- **دليل المستخدم**: `etap_user_guide/pdfs/`
- **النصوص المستخرجة**: `etap_user_guide/extracted/`
- **أجزاء النص**: `etap_user_guide/chunks/`
- **الفهرس الرئيسي**: `etap_user_guide/index/master_index.json`

### الأدوات

- **استخراج النصوص**: `etap_user_guide/extract_guide.py`
- **محرك RAG**: `etap_user_guide/etap_guide_rag.py`
- **برومبت الوكيل**: `prompts/etap_engineer_agent_v2.yaml`

### الوثائق

- **README**: `etap_user_guide/README.md` (هذا الملف)
- **دليل التكامل**: `docs/ETAP_GUIDE_INTEGRATION.md`
- **سياسة الأمان**: `SECURITY.md`

---

## ✨ الميزات

✅ **مرجع موثوق**: دليل ETAP الرسمي الكامل  
✅ **بحث دلالي**: استرجاع المعلومات باستخدام RAG  
✅ **تحقق تلقائي**: التحقق من صحة العمليات  
✅ **استشهاد**: تتبع المصادر والمراجع  
✅ **تكامل**: يعمل مع جميع الوكلاء  
✅ **إلزامي**: قواعد صارمة للاستخدام  

---

## 🎯 الأهداف

1. **ضمان الدقة**: جميع العمليات تتبع الدليل الرسمي
2. **منع الأخطاء**: التحقق من الخطوات قبل التنفيذ
3. **التوثيق**: استشهاد المصادر والمراجع
4. **الشفافية**: الإفصاح عن المعلومات غير الموثقة
5. **الجودة**: اتباع أفضل الممارسات الموثقة

---

## 📞 الدعم

للحصول على المساعدة:

1. **استخدم محرك RAG**: `ETAPGuideRAG.query()`
2. **راجع الدليل مباشرة**: `etap_user_guide/pdfs/`
3. **اتصل بدعم ETAP**: إذا لم تكن المعلومات في الدليل
4. **راجع الوثائق**: `docs/ETAP_GUIDE_INTEGRATION.md`

---

**تذكير نهائي:**

**دليل مستخدم ETAP هو مرجعك الأول والأوحد. اتبعه بدقة واستشره دائماً.**

**لا تخمن. تحقق دائماً. استشهد دائماً.**

---

*آخر تحديث: 7 يونيو 2026*  
*الإصدار: 1.0.0*  
*الحالة: ✅ جاهز للاستخدام*
