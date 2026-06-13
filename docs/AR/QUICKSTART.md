# دليل البدء السريع — منصة ETAP AI للهندسة الكهربائية

## المتطلبات الأساسية

قبل البدء في تثبيت وتشغيل المنصة، تأكد من توفر المتطلبات التالية على جهازك:

| المتطلب | الإصدار المطلوب | طريقة التثبيت |
|---------|----------------|---------------|
| Python | 3.13 أو أحدث | [python.org](https://www.python.org/) |
| Node.js | 22 أو أحدث | [nodejs.org](https://nodejs.org/) |
| pip | الأحدث | يأتي مع Python |
| pnpm | الأحدث | `npm install -g pnpm` |
| Git | 2.40 أو أحدث | [git-scm.com](https://git-scm.com/) |
| Docker (اختياري) | 24 أو أحدث | [docker.com](https://www.docker.com/) |

---

## التثبيت

### الخطوة ١: استنساخ المستودع

افتح موجه الأوامر (Terminal) وانسخ المستودع إلى جهازك المحلي:

```bash
git clone https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-.git
cd ETAP-AI-WORK-
```

### الخطوة ٢: تثبيت مكتبات Python

قم بتثبيت جميع المكتبات المطلوبة للخلفية البرمجية:

```bash
python3 -m pip install -r requirements.txt
```

تتضمن المكتبات الرئيسية:
- **FastAPI** — إطار عمل خادم الويب
- **Pydantic v2** — التحقق من البيانات
- **NumPy** — الحسابات العددية
- **SciPy** — الحلول الرياضية المتقدمة
- **scikit-learn** — نماذج التعلم الآلي
- **ChromaDB** — قاعدة بيانات المتجهات لنظام RAG

### الخطوة ٣: تثبيت مكتبات الواجهة

انتقل إلى مجلد الواجهة وقم بتثبيت المكتبات:

```bash
cd ui
pnpm install
cd ..
```

### الخطوة ٤: إعداد ملف البيئة

انسخ ملف القالب وعدّله حسب بيئتك:

```bash
cp .env.example .env
```

أهم المتغيرات التي يجب تعيينها في ملف `.env`:

```ini
# مفتاح JWT للتشفير (مطلوب)
JWT_SECRET_KEY=your-secret-key-here-at-least-32-characters

# عنوان خدمة الهندسة
ENGINEERING_SERVICE_URL=http://localhost:8000

# مفاتيح API لمزودي الذكاء الاصطناعي (اختياري)
OPENAI_API_KEY=sk-...
NVIDIA_NIM_API_KEY=nvapi-...

# إعدادات Redis (اختياري)
REDIS_URL=redis://localhost:6379
```

---

## التحقق من التثبيت

### التحقق من صحة الكود

قبل تشغيل المنصة، تحقق من أن جميع الملفات صالحة:

```bash
python3 validate_syntax.py
```

يجب أن ترى رسالة تأكيد بأن جميع الملفات (١٧٣+) اجتازت التحقق.

### تشغيل اختبارات التحقق الهندسي

شغّل مجموعة اختبارات التحقق الشاملة:

```bash
python3 validation_suite.py
```

يجب أن تجتاز جميع الاختبارات الـ ٣١ بنجاح.

### تشغيل اختبارات الوحدة

شغّل اختبارات Pytest للتأكد من عمل جميع المكونات:

```bash
pytest -q
```

يجب أن ترى نتائج تؤكد نجاح ٥٤٨ اختبار.

---

## تشغيل المنصة

### الطريقة ١: التشغيل المحلي

شغّل خدمة الهندسة (الخلفية):

```bash
python3 engineering_service.py --host 0.0.0.0 --port 8000
```

ثم في نافذة طرفية أخرى، شغّل الواجهة:

```bash
cd ui
pnpm dev
```

عناوين الوصول:
- **واجهة المستخدم**: http://localhost:3000
- **خادم API**: http://localhost:8000
- **توثيق API**: http://localhost:8000/docs

### الطريقة ٢: التشغيل عبر Docker

إذا كنت تفضل استخدام Docker:

```bash
docker compose up -d
```

سيتم تشغيل جميع الخدمات تلقائياً بما في ذلك Redis وقاعدة البيانات.

### الطريقة ٣: البدء السريع بنقرة واحدة

يمكنك استخدام سكربت البدء السريع:

**على Linux/macOS:**
```bash
chmod +x quickstart.sh
./quickstart.sh
```

**على Windows:**
```powershell
.\quickstart.ps1
```

---

## أول دراسة هندسية

بعد تشغيل المنصة، يمكنك إجراء أول دراسة تدفق قدرة عبر API:

### باستخدام cURL

```bash
curl -X POST http://localhost:8000/api/v1/studies/run \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key" \
  -d '{
    "study_type": "load_flow",
    "system": {
      "base_mva": 100.0,
      "buses": [
        {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
        {"bus_id": 2, "bus_type": "pq", "load_power_real": 50.0, "load_power_imag": 20.0}
      ],
      "lines": [
        {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
      ]
    },
    "parameters": {
      "method": "newton_raphson",
      "max_iterations": 50,
      "tolerance": 1e-6
    }
  }'
```

### باستخدام Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
HEADERS = {
    "Authorization": "Bearer your-api-key",
    "Content-Type": "application/json"
}

# تشغيل دراسة تدفق القدرة
response = requests.post(
    f"{BASE_URL}/studies/run",
    json={
        "study_type": "load_flow",
        "system": {
            "base_mva": 100.0,
            "buses": [
                {"bus_id": 1, "bus_type": "slack", "voltage_magnitude": 1.05},
                {"bus_id": 2, "bus_type": "pq", "load_power_real": 50.0}
            ],
            "lines": [
                {"line_id": 1, "from_bus_id": 1, "to_bus_id": 2, "r1": 0.01, "x1": 0.05}
            ]
        },
        "parameters": {"method": "newton_raphson"}
    },
    headers=HEADERS
)

result = response.json()
print(f"تقارب: {result['converged']}")
print(f"عدد التكرارات: {result['iterations']}")
print(f"الفقد: {result['results']['losses_mw']} ميجاواط")
```

---

## التحقق من حالة النظام

يمكنك التحقق من أن جميع الخدمات تعمل بشكل صحيح:

```bash
# فحص صحة النظام
curl http://localhost:8000/health

# فحص الجاهزية
curl http://localhost:8000/ready

# عرض المقاييس
curl -H "Authorization: Bearer your-api-key" http://localhost:8000/metrics
```

---

## استكشاف الأخطاء وإصلاحها

### مشكلة: لا يمكن الاتصال بخادم API

**الحل**: تأكد من أن خدمة الهندسة تعمل على المنفذ ٨٠٠٠:
```bash
lsof -i :8000  # Linux/macOS
netstat -ano | findstr :8000  # Windows
```

### مشكلة: فشل تثبيت مكتبات Python

**الحل**: استخدم بيئة افتراضية:
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### مشكلة: خطأ في مفتاح JWT

**الحل**: تأكد من تعيين `JWT_SECRET_KEY` في ملف `.env` بقيمة لا تقل عن ٣٢ حرفاً.

---

## الخطوات التالية

بعد التثبيت والتشغيل بنجاح، يمكنك:

1. 📖 قراءة [التوثيق الكامل للواجهة البرمجية](API.md)
2. 🏗️ مراجعة [البنية المعمارية](../ARCHITECTURE.md)
3. ✅ مراجعة [مصفوفة الامتثال](../COMPLIANCE.md)
4. 📊 تجربة [الدفاتر التفاعلية](../demos/)
5. 🔒 مراجعة [دليل الأمان](../../SECURITY.md)

---

## الحصول على المساعدة

- **البريد الإلكتروني**: ahmdelbaz28@gmail.com
- **GitHub Issues**: [إبلاغ عن مشكلة](https://github.com/ahmdelbaz28-ux/ETAP-AI-WORK-/issues)
- **GitHub**: [م. أحمد الباز](https://github.com/ahmdelbaz28-ux)
