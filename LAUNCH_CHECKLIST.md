# قائمة التحقق قبل الإطلاق — AhmedETAP

## ✅ ما قبل الإطلاق

- [ ] تشغيل `python scripts/security_scan.py` — يجب أن يمر بدون أخطاء
- [ ] تشغيل `pytest tests/` — يجب أن يمر بدون أخطاء
- [ ] تشغيل `docker build -t ahmedetap:test .` — يجب أن ينجح
- [ ] تشغيل `docker-compose up -d` والتحقق من http://localhost:8000/health
- [ ] التحقق من عدم وجود أسرار: `grep -r "password123\|admin123\|admin" docker-compose*.yml`
- [ ] التحقق من `.env.example` يحتوي على كل المتغيرات المطلوبة
- [ ] التحقق من CI/CD يمر على GitHub Actions

## 🚀 الإطلاق

- [ ] دمج الفرع إلى main
- [ ] وضع tag: `git tag -a v1.0.0 -m "Production launch"`
- [ ] دفع التاغ: `git push origin v1.0.0`

## 📊 ما بعد الإطلاق

- [ ] مراقبة Grafana Dashboards
- [ ] مراقبة Error logs
- [ ] مراجعة أداء API (response time < 500ms)
