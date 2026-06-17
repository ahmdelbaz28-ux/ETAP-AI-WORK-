# مرجع واجهة البرمجة — منصة AhmedETAP للهندسة الكهربائية

## نظرة عامة

توفر منصة AhmedETAP واجهة برمجة تطبيقات (API) شاملة تعمل عبر بروتوكول HTTP و WebSocket لإجراء دراسات أنظمة الطاقة الكهربائية، وتنسيق الوكلاء الذكيين، والتكامل مع أنظمة SCADA، والتحليلات التنبؤية، وإدارة النظام. يقدم هذا المستند مواصفات كاملة لكل نقطة نهاية، بما في ذلك مخططات الطلب والاستجابة، ومتطلبات المصادقة، وحدود المعدل، وأمثلة الاستخدام.

### عناوين URL الأساسية

| البيئة | العنوان |
|--------|---------|
| التطوير | `http://localhost:8000` |
| الإنتاج | `https://etap.yourdomain.com` |

---

## المصادقة

تتطلب جميع نقاط النهاية (باستثناء فحوصات الصحة وتسجيل الدخول) رمز JWT صالح في رأس `Authorization`.

```
Authorization: Bearer <رمز_jwt>
```

### تسجيل الدخول — POST /api/auth/login

**الطلب:**
```json
{
  "username": "engineer@example.com",
  "password": "كلمة-المرور-الآمنة"
}
```

**الاستجابة:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 28800,
  "user": {
    "id": "usr-001",
    "username": "engineer@example.com",
    "role": "engineer",
    "permissions": ["studies:run", "reports:generate", "agents:list"]
  }
}
```

---

## نقاط نهاية الصحة والجاهزية

### GET /health

فحص شامل لحالة النظام مع حالة التبعيات. لا يتطلب مصادقة.

**الاستجابة:**
```json
{
  "status": "healthy",
  "timestamp": "2026-03-04T14:30:00Z",
  "version": "1.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "engineering_engine": "ready"
  },
  "agents_available": 14
}
```

### GET /healthz

فحص بسيط لحيوية النظام (لـ Kubernetes). لا يتطلب مصادقة.

### GET /readyz

فحص جاهزية النظام مع التحقق من جميع التبعيات. لا يتطلب مصادقة.

### GET /metrics

نقطة نهاية مقاييس متوافقة مع Prometheus. تتطلب مصادقة.

---

## نقاط نهاية الدراسات الهندسية

### POST /api/v1/studies/run

تنفيذ دراسة هندسية لأنظمة الطاقة. هذه هي النقطة الرئيسية لتشغيل جميع أنواع التحليل عبر المحرك الأصلي أو أتمتة ETAP.

**أنواع الدراسات المدعومة:**

| نوع الدراسة | الوصف | المحرك |
|-------------|-------|--------|
| `load_flow` | تحليل تدفق القدرة (نيوتن-رافسون/الفصل السريع) | أصلي |
| `short_circuit` | تحليل دائرة القصر (IEC 60909) | أصلي |
| `arc_flash` | تحليل مخاطر الوميض القوسي (IEEE 1584) | أصلي |
| `harmonic_analysis` | تحليل التوافقيات (IEEE 519) | أصلي |
| `optimal_power_flow` | التدفق الأمثل للقدرة | أصلي |
| `protection_coordination` | تنسيق الحماية | أصلي |
| `motor_starting` | تحليل بدء المحرك | أصلي |

**مثال على طلب تحليل تدفق القدرة:**
```json
{
  "study_type": "load_flow",
  "system": {
    "base_mva": 100.0,
    "buses": [
      {"bus_id": 1, "voltage_magnitude": 1.05, "bus_type": "slack", "base_kv": 138.0},
      {"bus_id": 2, "voltage_magnitude": 1.0, "bus_type": "pq", "load_power_real": 50.0, "load_power_imag": 20.0, "base_kv": 13.8}
    ],
    "lines": [
      {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05, "bshunt1": 0.02}
    ]
  },
  "parameters": {
    "method": "newton_raphson",
    "max_iterations": 50,
    "tolerance": 1e-6
  }
}
```

**الاستجابة:**
```json
{
  "task_id": "task-20260304-001",
  "study_type": "load_flow",
  "status": "completed",
  "converged": true,
  "iterations": 5,
  "execution_time_ms": 85.2,
  "results": {
    "buses": {
      "1": {"voltage_magnitude_pu": 1.05, "voltage_angle_deg": 0.0, "power_generated_mw": 55.2},
      "2": {"voltage_magnitude_pu": 0.982, "voltage_angle_deg": -5.23, "power_consumed_mw": 50.0}
    },
    "losses_mw": 0.52
  },
  "validation": {
    "all_voltages_within_limits": true,
    "all_lines_thermal_ok": true
  }
}
```

### POST /api/v1/system/validate

التحقق من نموذج نظام الطاقة دون تشغيل دراسة. يتحقق من سلامة البيانات والاتصال والجدوى.

**الاستجابة:**
```json
{
  "valid": true,
  "warnings": [],
  "errors": [],
  "statistics": {
    "bus_count": 2,
    "line_count": 1,
    "has_slack_bus": true,
    "connected": true
  }
}
```

---

## تحليل دائرة القصر

### أنواع الأعطال المدعومة

- `three_phase` — عطل ثلاثي الأطوار (3ph)
- `line_to_line` — عطل بين خطين (L-L)
- `single_line_to_ground` — عطل أحادي للأرض (L-G)
- `line_to_line_to_ground` — عطل مزدوج للأرض (L-L-G)

**مثال على طلب تحليل دائرة القصر:**
```json
{
  "study_type": "short_circuit",
  "system": {"base_mva": 100.0, "buses": [...], "lines": [...]},
  "parameters": {
    "fault_location": 2,
    "fault_type": "three_phase",
    "standards": "iec_60909",
    "voltage_factor_c": 1.1
  }
}
```

**الاستجابة:**
```json
{
  "results": {
    "fault_bus": 2,
    "fault_type": "three_phase",
    "symmetrical_fault_current_ka": 25.5,
    "peak_current_ka": 65.2,
    "x_r_ratio": 12.5,
    "compliance": {"iec_60909": true}
  }
}
```

---

## تحليل الوميض القوسي

### POST /api/v1/studies/run (arc_flash)

تحليل مخاطر الوميض القوسي حسب IEEE 1584-2018 و NFPA 70E.

**التكوينات المدعومة للأقطاب الكهربائية (IEEE 1584-2018):**
- `VCB` — أقطاب عمودية داخل صندوق معدني
- `VCBB` — أقطاب عمودية منتهية بحاجز عازل داخل صندوق معدني
- `HCB` — أقطاب أفقية داخل صندوق معدني
- `VOA` — أقطاب عمودية في الهواء الطلق
- `HOA` — أقطاب أفقية في الهواء الطلق

**مثال على الطلب:**
```json
{
  "study_type": "arc_flash",
  "system": {"base_mva": 100.0, "buses": [...]},
  "parameters": {
    "voltage_kv": 4.16,
    "bolted_fault_current_ka": 20.0,
    "arc_duration_sec": 0.5,
    "working_distance_mm": 610.0,
    "equipment_type": "switchgear",
    "electrode_configuration": "VCB",
    "grounding_type": "solidly_grounded"
  }
}
```

**الاستجابة:**
```json
{
  "results": {
    "arcing_current_ka": 16.8,
    "incident_energy_cal_cm2": 8.5,
    "arc_flash_boundary_mm": 1500,
    "ppe_level": "Category 2",
    "minimum_ppe_rating_cal_cm2": 8.0,
    "recommendations": [
      "استخدم معدات حماية شخصية من الفئة ٢ كحد أدنى",
      "حافظ على مسافة عمل آمنة ٦١٠ مم",
      "حد الوميض القوسي: ١.٥ م — مطلوب حواجز"
    ]
  }
}
```

---

## نقاط نهاية إدارة الوكلاء

### GET /api/v1/agents

قائمة جميع الوكلاء الهندسيين المتاحين وقدراتهم.

**الاستجابة:**
```json
{
  "agents": [
    {
      "id": "load-flow-agent",
      "name": "وكيل تدفق القدرة",
      "study_types": ["load_flow"],
      "standards": ["IEEE 141", "IEEE 399"],
      "status": "available"
    }
  ]
}
```

### POST /api/v1/agents/{agent_id}/chat

إرسال رسالة إلى وكيل محدد للحصول على مساعدة هندسية تفاعلية.

---

## نقاط نهاية SCADA في الوقت الفعلي

### GET /api/v1/scada/measurements

استرجاع بيانات القياس في الوقت الفعلي من تكامل SCADA.

**معلمات الاستعلام:**

| المعلمة | النوع | الافتراضي | الوصف |
|---------|------|----------|-------|
| `bus_id` | عدد صحيح | الكل | تصفية حسب رقم الناقل |
| `measurement_type` | نص | الكل | V, I, P, Q, f |
| `time_range` | نص | 5m | النطاق الزمني |

**الاستجابة:**
```json
{
  "measurements": [
    {
      "bus_id": 1,
      "logical_node": "MMXU1",
      "voltage_kv": 138.2,
      "current_a": 425.5,
      "power_mw": 55.2,
      "frequency_hz": 60.01,
      "quality": "good"
    }
  ]
}
```

### GET /api/v1/scada/alarms

استرجاع إنذارات SCADA النشطة والأحداث.

### POST /api/v1/scada/state-estimation

تشغيل تقدير الحالة على قياسات SCADA الحالية.

---

## نقاط نهاية التحليلات التنبؤية

### POST /api/v1/predictive/load-forecast

إنشاء توقعات الأحمال باستخدام نماذج التعلم الآلي (LSTM أو الانحدار الخطي).

### POST /api/v1/predictive/anomaly-detect

كشف الشذوذ في تدفقات بيانات القياس باستخدام خوارزمية غابة العزل (Isolation Forest).

### POST /api/v1/predictive/fault-predict

التنبؤ بنوع العطل من توقيعات القياس باستخدام تصنيف الغابة العشوائية (Random Forest).

---

## نقاط نهاية WebSocket

### WS /ws/study/{study_id}

الاشتراك في تحديثات الوقت الفعلي لدراسة قيد التشغيل.

**أنواع الرسائل (الخادم → العميل):**

- `progress` — تحديث التقدم مع النسبة المئوية
- `completed` — إشعار اكتمال الدراسة
- `failed` — إشعار فشل الدراسة مع رسالة الخطأ
- `agent_status` — تحديث حالة الوكيل

**مثال على اتصال:**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/study/task-001');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(`التقدم: ${update.progress_percent}%`);
};
```

---

## إنشاء التقارير

### POST /api/v1/reports/generate

إنشاء تقرير هندسي من نتائج التحليل.

**الطلب:**
```json
{
  "analysis_results": {"study_type": "load_flow", "converged": true},
  "formats": ["pdf", "docx", "xlsx"],
  "template": "ieee_standard",
  "title": "دراسة تدفق القدرة للمصنع الصناعي",
  "include_charts": true,
  "include_recommendations": true
}
```

### GET /api/v1/reports/download/{filename}

تنزيل ملف التقرير المُنشأ.

---

## قاعدة المعرفة

### POST /api/v1/knowledge/search

البحث في قاعدة المعرفة الهندسية باستخدام نظام RAG (التوليد المعزز بالاسترجاع).

### POST /api/v1/knowledge/add

إضافة مستند إلى قاعدة المعرفة الهندسية. يتطلب دور المسؤول.

---

## تحديد المعدل

| المستوى | الحد | ينطبق على |
|---------|------|----------|
| قياسي | ١٠٠ طلب/دقيقة | جميع نقاط النهاية المصادق عليها |
| ثقيل | ١٠ طلبات/دقيقة | التدفق الأمثل، تحليل التوافقيات |
| التقارير | ٥ طلبات/دقيقة | إنشاء التقارير |
| الصحة | غير محدود | `/health`, `/healthz`, `/readyz` |

---

## تنسيق الاستجابة للخطأ

جميع الأخطاء تتبع بنية JSON موحدة:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "وصف الخطأ",
    "details": [],
    "timestamp": "2026-03-04T14:30:00Z",
    "request_id": "req-12345"
  }
}
```

### رموز الخطأ الشائعة

| الرمز | حالة HTTP | الوصف |
|-------|-----------|-------|
| `AUTHENTICATION_REQUIRED` | 401 | رمز المصادقة مفقود أو غير صالح |
| `FORBIDDEN` | 403 | صلاحيات غير كافية |
| `VALIDATION_ERROR` | 400 | بيانات إدخال غير صالحة |
| `NOT_FOUND` | 404 | المورد غير موجود |
| `RATE_LIMIT_EXCEEDED` | 429 | عدد الطلبات يتجاوز الحد |
| `STUDY_FAILED` | 422 | فشل حساب التحليل |
| `INTERNAL_ERROR` | 500 | خطأ داخلي في الخادم |

---

## أمثلة SDK

### Python

```python
import requests

api_key = "مفتاح-الواجهة-الخاص-بك"
base_url = "http://localhost:8000/api/v1"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# تشغيل تحليل تدفق القدرة
response = requests.post(
    f"{base_url}/studies/run",
    json={
        "study_type": "load_flow",
        "system": {"base_mva": 100, "buses": [...], "lines": [...]},
        "parameters": {"method": "newton_raphson"}
    },
    headers=headers
)
result = response.json()
print(f"تقارب: {result['converged']}")
```

### JavaScript/TypeScript

```typescript
const baseURL = 'http://localhost:8000/api/v1';
const headers = {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
};

// تشغيل تحليل الوميض القوسي
const response = await fetch(`${baseURL}/studies/run`, {
  method: 'POST',
  headers,
  body: JSON.stringify({
    study_type: 'arc_flash',
    system: { base_mva: 100, buses: [...] },
    parameters: { voltage_kv: 4.16, bolted_fault_current_ka: 20 }
  })
});
const result = await response.json();
```
