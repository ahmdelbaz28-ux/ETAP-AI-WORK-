@echo off
cd /d "c:\Users\Repair SC\Desktop\ETAP-AI-WORK--main"
python -m pytest tests/test_cache_service.py tests/test_study_service.py tests/test_worker_tasks.py tests/test_etap_adapter.py --cov=services --cov=worker --cov=etap_integration.etap_adapter --cov-report=term-missing --no-header -q
