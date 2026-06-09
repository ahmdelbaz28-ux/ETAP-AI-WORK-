# ETAP User Guide Integration Guide
# دليل تكامل دليل مستخدم ETAP

## 📋 نظرة عامة

تم دمج **دليل مستخدم ETAP الرسمي** (117 ملف PDF) في المنصة ليكون **المرجع الأساسي والموثوق** لجميع عمليات ETAP.

**المحتوى المدمج:**
- 62 ملف PDF رئيسي (Part 1-62)
- 55 ملف AC Element
- إجمالي: 196 MB من الوثائق الرسمية

---

## 🎯 الأهداف

1. ✅ **المرجعية المطلقة**: جعل دليل ETAP المرجع الأول لجميع العمليات
2. ✅ **التحقق التلقائي**: التحقق من صحة جميع العمليات قبل التنفيذ
3. ✅ **منع الأخطاء**: منع العمليات غير الموثقة أو الخاطئة
4. ✅ **التوثيق**: توثيق جميع الإجراءات مع الاستشهاد بالمصادر
5. ✅ **الجودة**: ضمان اتباع أفضل الممارسات الموثقة

---

## 🏗️ المعمارية

```
┌─────────────────────────────────────────────────────────┐
│                    ETAP User Guide                       │
│              (117 PDF Files - 196 MB)                    │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────▼────────────┐
        │   PDF Text Extractor    │
        │   (extract_guide.py)    │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   Extracted Text        │
        │   (extracted/*.txt)     │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   Text Chunker          │
        │   (chunks/*.json)       │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   RAG Engine            │
        │   (etap_guide_rag.py)   │
        └────────────┬────────────┘
                     │
        ┌────────────▼────────────┐
        │   Agent Prompts         │
        │   (Mandatory Rules)     │
        └─────────────────────────┘
```

---

## 📦 المكونات

### 1. ملفات PDF الأصلية

**الموقع:** `etap_user_guide/pdfs/`

**المحتوى:**
- Part 1-62: الدليل الرئيسي الشامل
- AC Element: 55 ملف تفصيلي

**الحجم:** ~196 MB

### 2. سكربت استخراج النصوص

**الملف:** `etap_user_guide/extract_guide.py`

**الوظائف:**
- استخراج النصوص من جميع ملفات PDF
- تنظيف وتطبيع النصوص
- تقسيم النص إلى أجزاء للبحث
- إنشاء الفهرس الرئيسي

**الاستخدام:**
```bash
python etap_user_guide/extract_guide.py
```

### 3. محرك RAG

**الملف:** `etap_user_guide/etap_guide_rag.py`

**الوظائف:**
- تحميل النصوص المستخرجة
- البحث الدلالي باستخدام embeddings
- استرجاع الإجراءات الرسمية
- التحقق من صحة العمليات المقترحة
- الإجابة على الأسئلة مع الاستشهاد

**الاستخدام:**
```python
from etap_user_guide.etap_guide_rag import ETAPGuideRAG

rag = ETAPGuideRAG()

# الحصول على إجراء
procedure = rag.get_etap_procedure("load flow analysis")

# التحقق من الخطوات
validation = rag.validate_etap_operation(
    "load flow analysis",
    ["Step 1", "Step 2", "Step 3"]
)

# الاستعلام
answer = rag.query("How to add a transformer?")
```

### 4. برومبت الوكيل

**الملف:** `prompts/etap_engineer_agent_v2.yaml`

**المحتوى:**
- القواعد الإلزامية لاستخدام الدليل
- سير العمل الإلزامي لكل عملية
- أمثلة عملية
- الحالات الاستثنائية

### 5. التوثيق

**الملفات:**
- `etap_user_guide/README.md` - دليل الاستخدام
- `docs/ETAP_GUIDE_INTEGRATION.md` - هذا الملف
- `etap_user_guide/integration_summary.json` - ملخص التكامل

---

## 🚀 البدء السريع

### الخطوة 1: تثبيت المتطلبات

```bash
pip install -r requirements.txt
```

**المكتبات المطلوبة:**
- PyPDF2>=3.0.0
- pdfplumber>=0.7.0
- sentence-transformers>=2.2.0
- chromadb>=0.4.0
- tqdm>=4.62.0

### الخطوة 2: تشغيل سكربت الإعداد

```bash
python etap_user_guide/setup_etap_guide.py
```

**هذا السكربت يقوم بـ:**
1. ✅ التحقق من بنية المجلدات
2. ✅ عد ملفات PDF
3. ✅ تثبيت المتطلبات
4. ✅ استخراج النصوص من PDFs
5. ✅ التحقق من النتائج
6. ✅ اختبار محرك RAG
7. ✅ إنشاء ملخص التكامل

### الخطوة 3: التحقق من النجاح

```bash
# التحقق من الملفات المستخرجة
ls etap_user_guide/extracted/

# التحقق من أجزاء النص
ls etap_user_guide/chunks/

# التحقق من الفهرس
cat etap_user_guide/index/master_index.json
```

### الخطوة 4: اختبار محرك RAG

```bash
python etap_user_guide/etap_guide_rag.py
```

**النتيجة المتوقعة:**
```
======================================================================
ETAP User Guide RAG Engine - Test
======================================================================

[MANDATORY INSTRUCTIONS DISPLAYED]

Testing queries:
----------------------------------------------------------------------

Query: How to create a new project in ETAP?
✓ Answered (confidence: 15.00)
  Sources: 5 documents
  Answer preview: ...

Query: How to run load flow analysis?
✓ Answered (confidence: 12.00)
  Sources: 5 documents
  Answer preview: ...

======================================================================
RAG Engine Test Complete!
======================================================================
```

---

## 📖 الاستخدام

### للاستعلام عن إجراء

```python
from etap_user_guide.etap_guide_rag import ETAPGuideRAG

rag = ETAPGuideRAG()

# الحصول على إجراء عملية
procedure = rag.get_etap_procedure("short circuit analysis")

if procedure["found"]:
    print("Official procedure:")
    for step in procedure["steps"]:
        print(f"  {step}")
    
    if procedure["warnings"]:
        print("\nWarnings:")
        for warning in procedure["warnings"]:
            print(f"  ⚠️ {warning}")
else:
    print("Procedure not found in ETAP User Guide")
```

### للتحقق من خطوات مقترحة

```python
validation = rag.validate_etap_operation(
    operation="load flow analysis",
    proposed_steps=[
        "Open ETAP",
        "Create project",
        "Add components",
        "Run study"
    ]
)

if validation["valid"]:
    print("✓ Steps validated - proceed with operation")
else:
    print("✗ Validation failed")
    for issue in validation["issues"]:
        print(f"  - {issue}")
```

### للاستعلام عن سؤال

```python
answer = rag.query("How to configure transformer tap settings?")

if answer["answered"]:
    print(f"Answer: {answer['answer']}")
    print(f"\nSources:")
    for source in answer["sources"]:
        print(f"  - {source['document']} (relevance: {source['relevance']})")
else:
    print("Information not found in ETAP User Guide")
```

---

## ⚠️ القواعد الإلزامية

### القاعدة #1: الدليل هو المرجع الأساسي

**جميع الوكلاء يجب أن:**
- ✅ يستشيروا الدليل قبل أي عملية ETAP
- ✅ يتبعوا الخطوات كما هي موثقة
- ✅ لا ينحرفوا عن الإجراءات الموثقة
- ✅ يستشهدوا بالقسم/الصفحة
- ✅ يفصحوا إذا لم تكن المعلومات موجودة

### القاعدة #2: سير العمل الإلزامي

```
1. استعلم من محرك RAG
   → ETAPGuideRAG.get_etap_procedure()
   
2. تحقق من الخطوات المقترحة
   → ETAPGuideRAG.validate_etap_operation()
   
3. نفذ فقط إذا نجح التحقق
   → إذا فشل، توقف واطلب التوضيح
   
4. وثّق المصدر
   → اذكر دائماً أي قسم من الدليل اتبعت
```

### القاعدة #3: المحظورات

❌ تنفيذ عمليات بدون استشارة الدليل  
❌ استخدام إجراءات غير موثقة  
❌ التخمين أو الافتراض  
❌ تقديم تعليمات بدون استشهاد  
❌ تخطي خطوات التحقق  
❌ الانحراف عن الإجراءات الموثقة  

---

## 🔍 البحث والاسترجاع

### البحث بالكلمات المفتاحية

```python
results = rag.search("transformer impedance", top_k=5)

for result in results:
    print(f"Document: {result['metadata']['document']}")
    print(f"Score: {result['score']}")
    print(f"Content: {result['chunk'][:200]}...")
```

### الاستعلام الدلالي

```python
answer = rag.query("What are the steps to run a harmonic analysis?")

if answer["answered"]:
    print(f"Answer: {answer['answer']}")
    print(f"Confidence: {answer['confidence']}")
    print(f"Sources: {len(answer['sources'])}")
```

---

## 📊 الإحصائيات

بعد التشغيل الناجح لسكربت الإعداد:

```python
import json

with open('etap_user_guide/integration_summary.json', 'r') as f:
    summary = json.load(f)

print(f"Total PDFs: {summary['statistics']['total_pdfs']}")
print(f"AC Element PDFs: {summary['statistics']['total_ac_pdfs']}")
print(f"Extracted files: {summary['statistics']['extracted_files']}")
print(f"Chunk files: {summary['statistics']['chunk_files']}")
```

**النتيجة المتوقعة:**
```
Total PDFs: 62
AC Element PDFs: 55
Extracted files: 117
Chunk files: 117
```

---

## 🚨 التعامل مع الحالات الاستثنائية

### إذا لم تكن المعلومات في الدليل

```python
answer = rag.query("How to use ETAP GIS module?")

if not answer["answered"]:
    print("⚠️ Information not found in ETAP User Guide")
    print("\nRecommendations:")
    print("  1. Consult ETAP technical support")
    print("  2. Check ETAP official website")
    print("  3. Review ETAP training materials")
    print("  4. Contact ETAP customer service")
```

### إذا فشلت عملية التحقق

```python
if not validation["valid"]:
    print("❌ Validation failed - DO NOT PROCEED")
    print("\nIssues found:")
    for issue in validation["issues"]:
        print(f"  - {issue}")
    
    print("\nRecommended actions:")
    print("  1. Review the ETAP User Guide")
    print("  2. Correct the proposed steps")
    print("  3. Re-validate before proceeding")
    print("  4. Consult ETAP support if needed")
```

---

## 🔄 التكامل مع الوكلاء

### وكيل ETAP Engineer

```python
# في بداية كل مهمة
from etap_user_guide.etap_guide_rag import ETAPGuideRAG

rag = ETAPGuideRAG()

# عرض التعليمات الإلزامية
print(rag.get_mandatory_instructions())

# قبل أي عملية ETAP
procedure = rag.get_etap_procedure(operation_name)

if procedure["found"]:
    # التحقق من الخطوات
    validation = rag.validate_etap_operation(
        operation_name,
        proposed_steps
    )
    
    if validation["valid"]:
        # تنفيذ العملية
        execute_operation()
    else:
        # التوقف والإبلاغ
        raise ValueError(f"Validation failed: {validation['issues']}")
else:
    print("⚠️ Operation not documented")
```

### وكلاء آخرون

جميع الوكلاء الذين يتعاملون مع ETAP يجب أن:

1. ✅ يستشيروا الدليل قبل أي عملية
2. ✅ يتحققوا من صحة الخطوات
3. ✅ يستشهدوا بالمصدر
4. ✅ يبلغوا إذا لم تكن المعلومات متاحة

---

## 📝 أمثلة عملية

### مثال 1: تشغيل Load Flow

```python
from etap_user_guide.etap_guide_rag import ETAPGuideRAG
from etap_integration.etap_com import ETAPAutomation

# 1. استشارة الدليل
rag = ETAPGuideRAG()
procedure = rag.get_etap_procedure("load flow analysis")

print("Official procedure from ETAP User Guide:")
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
    for issue in validation["issues"]:
        print(f"  - {issue}")
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
    
    # تنفيذ الإجراء
    # ... ETAP COM automation code ...
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
    print("⚠️ Troubleshooting not documented in ETAP User Guide")
    print("Recommendation: Contact ETAP technical support")
```

---

## 🎯 معايير النجاح

تم دمج دليل ETAP بنجاح عندما:

✅ تم استخراج النصوص من جميع ملفات PDF (117 ملف)  
✅ تم إنشاء أجزاء النص للبحث  
✅ تم إنشاء الفهرس الرئيسي  
✅ يعمل محرك RAG بدون أخطاء  
✅ يمكن الاستعلام عن الإجراءات  
✅ يمكن التحقق من الخطوات  
✅ تم تحديث برومبت الوكلاء  
✅ تم توثيق جميع المكونات  

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
- **سكربت الإعداد**: `etap_user_guide/setup_etap_guide.py`
- **برومبت الوكيل**: `prompts/etap_engineer_agent_v2.yaml`

### الوثائق

- **README**: `etap_user_guide/README.md`
- **دليل التكامل**: `docs/ETAP_GUIDE_INTEGRATION.md` (هذا الملف)
- **ملخص التكامل**: `etap_user_guide/integration_summary.json`

---

## 🐛 استكشاف الأخطاء

### المشكلة: لا توجد ملفات مستخرجة

**الحل:**
```bash
# تحقق من وجود ملفات PDF
ls etap_user_guide/pdfs/

# شغل سكربت الاستخراج
python etap_user_guide/extract_guide.py
```

### المشكلة: محرك RAG لا يعمل

**الحل:**
```bash
# تحقق من تثبيت المتطلبات
pip install -r requirements.txt

# تحقق من وجود الفهرس
ls etap_user_guide/index/

# أعد تشغيل سكربت الإعداد
python etap_user_guide/setup_etap_guide.py
```

### المشكلة: الاستعلامات لا تُجاب

**الحل:**
```bash
# تحقق من وجود أجزاء النص
ls etap_user_guide/chunks/

# أعد استخراج النصوص
python etap_user_guide/extract_guide.py

# اختبر محرك RAG مباشرة
python etap_user_guide/etap_guide_rag.py
```

---

## ✨ الميزات

✅ **مرجع موثوق**: دليل ETAP الرسمي الكامل  
✅ **بحث دلالي**: استرجاع المعلومات باستخدام RAG  
✅ **تحقق تلقائي**: التحقق من صحة العمليات  
✅ **استشهاد**: تتبع المصادر والمراجع  
✅ **تكامل**: يعمل مع جميع الوكلاء  
✅ **إلزامي**: قواعد صارمة للاستخدام  
✅ **شامل**: 117 ملف PDF مدمج  
✅ **سهل الاستخدام**: واجهة برمجة بسيطة  

---

## 🎓 أفضل الممارسات

1. **استشر الدليل دائماً**: قبل أي عملية ETAP
2. **تحقق من الخطوات**: استخدم `validate_etap_operation()`
3. **استشهد بالمصدر**: اذكر القسم/الصفحة دائماً
4. **لا تخمن**: إذا لم تكن المعلومات متاحة، صرح بذلك
5. **وثّق الاستثناءات**: سجل أي انحراف عن الدليل
6. **اختبر بانتظام**: تأكد من عمل محرك RAG
7. **حدث الدليل**: عند توفر إصدار جديد من ETAP

---

## 📞 الدعم

للحصول على المساعدة:

1. **استخدم محرك RAG**: `ETAPGuideRAG.query()`
2. **راجع الدليل مباشرة**: `etap_user_guide/pdfs/`
3. **اتصل بدعم ETAP**: إذا لم تكن المعلومات في الدليل
4. **راجع الوثائق**: `etap_user_guide/README.md`

---

**تذكير نهائي:**

**دليل مستخدم ETAP هو مرجعك الأول والأوحد. اتبعه بدقة واستشره دائماً.**

**لا تخمن. تحقق دائماً. استشهد دائماً.**

---

*آخر تحديث: 7 يونيو 2026*  
*الإصدار: 1.0.0*  
*الحالة: ✅ جاهز للاستخدام*
