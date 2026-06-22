# تعليمات الذكاء الاصطناعي للتعامل مع نظام الفهرسة

## المبدأ الأساسي

عند تلقي أي استعلام متعلق بـ ArcGIS Pro أو QGIS أو أدوات نظم المعلومات الجغرافية (GIS) أو دمج أنظمة SCADA مع ETAP/QGIS/ArcGIS Pro، يجب أن تكون الفهرسة المُعدة مرجعيك الأول والوحيد لاتخاذ القرارات والتنفيذ والتفكير والتخطيط. هذه الفهرسة تم إعدادها بعناية لتكون دليلاً شاملاً ودقيقاً لجميع الوظائف والواجهات البرمجية والوثائق.

## الأولويات في الاستخدام

### 1. الفهرسة كمرجع أساسي
- استخدم دائمًا [arcgis_pro_documentation_index.json](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/arcgis_pro_documentation_index.json) و [qgis_comprehensive_documentation_index.json](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/qgis_comprehensive_documentation_index.json) كمصادر موثوقة ودقيقة.
- رتب المعلومات حسب الفئات (fundamentals، api، python، tools، advanced، etc.) لضمان استرجاع المعلومات ذات الصلة.
- استخدم الوسوم (tags) لتحديد نوع المحتوى (beginner، advanced، tutorial، reference، etc.).

### 2. استرجاع المعلومات
- عند استلام استعلام، قم أولاً بتحليل الفهرسة للعثور على القسم أو الوظيفة المقابلة.
- استخدم معلومات المستوى (level) والعلاقات الأبوية (parent) لفهم السياق الهرمي للمعلومات.
- راجع الروابط (URLs) للحصول على معلومات مفصلة من الوثائق الأصلية.

### 3. تجنب الهلوسة
- لا تقدّم معلومات غير موجودة في الفهرسة.
- إذا لم تتمكن من العثور على معلومات محددة في الفهرسة، أقر دائمًا بأن المعلومات غير متوفرة في المراجع الحالية.
- استخدم دائمًا معلومات التحقق من الجودة (quality_assurance) لتأكيد دقة المحتوى.

## مثال على الاستخدام

### 1. عندما يتم طرح سؤال:
"كيف يمكنني إنشاء إضافة (Add-in) لـ ArcGIS Pro؟"

### الإجابة يجب أن تأتي من:
- قسم "Build Your First Add-in" (القسم 4) في الفهرسة
- مع معلومات مفصلة من الخطوة 1 إلى الخطوة 13
- مع رابط مباشر: https://doc.esri.com/en/arcgis-pro/latest/sdk/api-reference/conceptdocs/docs/ProGuide-Build-your-first-add-in.html

### 2. عندما يتم طرح سؤال:
"كيف يمكنني ربط PyScada مع ArcGIS Pro؟"

### الإجابة يجب أن تأتي من:
- البحث في قسم "ArcPy" في فهرس ArcGIS Pro
- مع معلومات مفصلة من واجهة البرمجة (API) المتوفرة في الفهرس
- مع رابط مباشر إلى الوثائق الأصلية وفقًا للمعلومات في الفهرس

### 3. عندما يتم طرح سؤال:
"كيف يمكنني دمج ETAP مع QGIS و ArcGIS Pro عبر SCADA؟"

### الإجابة يجب أن تأتي من:
- [scada_etap_gis_integration_guide.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_etap_gis_integration_guide.md): دليل شامل لدمج SCADA مع ETAP/QGIS/ArcGIS Pro
- [etap_scada_bridge.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/etap_scada_bridge.py): واجهة الربط بين ETAP ونظام SCADA
- [scada_etap_consumer.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_etap_consumer.py): مستهلك بيانات ETAP في نظام SCADA
- [qgis_scada_layer.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/qgis_scada_layer.py): إنشاء طبقات SCADA لـ QGIS

## تعليمات التنفيذ

### 1. التفكير:
- قبل تقديم أي إجابة، تحقق من الفهرسة للعثور على المعلومات الدقيقة.
- استخدم معلومات الفئة لتحديد نوع الوظيفة أو المفهوم المطلوب.

### 2. التخطيط:
- خطط للإجابة بناءً على هيكل الفهرسة (المستوى 1، 2، 3، إلخ).
- رتب المعلومات من الأعموم إلى الخاص.

### 3. التنفيذ:
- قدّم روابط مباشرة إلى أجزاء الوثائق الأصلية.
- استخدم الوسوم لتصنيف نوع المحتوى المقدّم.
- تأكد من دقة المعلومات من خلال مقارنتها مع معلومات الجودة في الفهرسة.

## مكونات النظام

### 1. محرك الفهرسة (MCP Server)
- [arcgis_pro_indexing_workflow.json](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/arcgis_pro_indexing_workflow.json): يحدد خطوات سير العمل لفهرسة وثائق ArcGIS Pro
- يحتوي على 5 خطوات رئيسية: FetchData → CleanData → TransformData → IndexData → PostProcess
- يستخدم نموذج التضمين "sentence-transformers/all-mpnet-base-v2" لتحويل النصوص إلى متجهات

### 2. تعليمات الذكاء الاصطناعي
- [scada_integration_instructions.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_integration_instructions.md): تعليمات مفصلة للذكاء الاصطناعي لدمج SCADA مع ETAP/QGIS/ArcGIS Pro
- [scada_etap_gis_integration_guide.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_etap_gis_integration_guide.md): دليل شامل لدمج SCADA مع ETAP/QGIS/ArcGIS Pro
- [ai_agent_instructions.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/ai_agent_instructions.md): تعليمات مفصلة للذكاء الاصطناعي
- [ai_quick_reference.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/ai_quick_reference.md): مرجع سريع للذكاء الاصطناعي

### 3. ملفات التنفيذ
- [etap_scada_bridge.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/etap_scada_bridge.py): واجهة الربط بين ETAP ونظام SCADA
- [scada_etap_consumer.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_etap_consumer.py): مستهلك بيانات ETAP في نظام SCADA
- [qgis_scada_layer.py](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/qgis_scada_layer.py): إنشاء طبقات SCADA لـ QGIS
- [requirements.txt](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/requirements.txt): قائمة المكتبات المطلوبة

## التحقق من الصحة

- تأكد دائمًا من أن المعلومات تتطابق مع معلومات الفهرسة.
- استخدم حقل "quality_assurance" للتحقق من دقة المحتوى.
- إذا كانت المعلومات غير مؤكدة، قم بالإشارة إلى ذلك بصراحة.

## ملاحظات إضافية

- الفهرسة مُعدة بطريقة تدعم أنظمة الذكاء الاصطناعي الحديثة.
- تحتوي على معلومات مُنسقة لدعم البحث.semantic.
- مُعدة لتجنب الهلوسة وزيادة دقة النتائج.
- جميع الملفات تم التحقق من صحتها النحوية وتعمل بشكل صحيح.
- عند الإجابة عن أسئلة متعلقة بالربط بين SCADA وGIS، استخدم دائمًا معلومات من قسم "Integrations" في الفهارس
- عند الإجابة عن أسئلة متعلقة بالواجهات البرمجية (API)، استخدم دائمًا معلومات من قسم "API Reference" في الفهرسة
- عند الإجابة عن أسئلة متعلقة بالبرمجة النصية (Python)، استخدم دائمًا معلومات من قسم "ArcPy Reference" في الفهرسة
- عند التعامل مع دمج أنظمة SCADA مع ETAP/QGIS/ArcGIS Pro، استخدم دائمًا معلومات من [scada_integration_instructions.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_integration_instructions.md) و[scada_etap_gis_integration_guide.md](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/scada_etap_gis_integration_guide.md)