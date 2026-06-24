# 📘 AhmedETAP — Complete Project Index

> Auto-generated on **2026-06-24T11:00:53.237200+00:00**. Re-run `python indexer.py` to refresh.

---

## 📊 Project Statistics

| Metric | Count |
|:---|---:|
| Python Packages | 25 |
| Python Files | 201 |
| Python Classes | 572 |
| Python Functions | 312 |
| UI Files (TSX/TS) | 50 |
| Test Files | 58 |
| Total Tests | 989 |

---

## 🗂️ Python Modules & Packages

### 📦 `agents/`

#### 📄 `agents/__init__.py` _3.9 KB_
> AI Agents - Multi-agent engineering orchestration system.

Provides 15 specialized engineering agents and a ChiefEngineeringOrchestrator
that coordina


#### 📄 `agents/anomaly_agent.py` _23.0 KB_
> AhmedETAP - Anomaly Detection Agent
=======================================================
Anomaly detection, classification, and diagnosis in power 

- **Class** `AnomalyAgent` (line 38)
  - Methods: `detect_spc_anomalies()`, `detect_cusum()`, `detect_ewma()`, `detect_threshold_violations()`, `cross_correlation_analysis()`, `detect_ml_anomaly()`, `execute()`, `validate_result()`

#### 📄 `agents/arc_flash_agent.py` _16.3 KB_
> AhmedETAP - Arc Flash Analysis Agent
=======================================================
Arc flash incident energy and boundary calculations per I

- **Class** `ArcFlashAgent` (line 95)
  - Methods: `calculate_arc_current()`, `calculate_incident_energy()`, `execute()`, `validate_result()`

#### 📄 `agents/battery_storage_agent.py` _36.9 KB_
> AhmedETAP - Battery Storage Agent
=====================================================
Battery Energy Storage System (BESS) analysis per IEC 62933.



- **Class** `BatteryStorageAgent` (line 35)
  - Methods: `size_bess()`, `optimize_dispatch()`, `calculate_roi()`, `analyze_cycle_life()`, `execute()`, `validate_result()`

#### 📄 `agents/cable_sizing_agent.py` _25.7 KB_
> AhmedETAP - Cable Sizing Agent
==================================================
Cable sizing and verification per IEC 60364 series.

Capabilities:
-

- **Class** `CableSizingAgent` (line 126)
  - Methods: `calculate_ampacity()`, `calculate_voltage_drop()`, `verify_short_circuit_rating()`, `recommend_cable()`, `execute()`, `validate_result()`

#### 📄 `agents/code_guard_agent.py` _6.6 KB_
> Code Guard Agent — AI-Powered Code Quality Review
====================================================
Integrates the guard-skills quality gates into 

- **Class** `CodeGuardAgent` (line 22)
  - Methods: `execute()`, `review_code()`, `detect_ai_failure_modes()`

#### 📄 `agents/coordination_agent.py` _21.0 KB_
> AhmedETAP - Protection Coordination Agent
=============================================================
Protection system coordination analysis per IE

- **Class** `CoordinationAgent` (line 58)
  - Methods: `calculate_relay_operating_time()`, `verify_coordination()`, `generate_tcc_data()`, `analyze_selectivity()`, `execute()`, `validate_result()`

#### 📄 `agents/digital_twin_agent.py` _16.9 KB_
> AhmedETAP - Digital Twin Agent
==================================================
Real-time synchronization between physical power system assets and
t

- **Class** `DigitalTwinAgent` (line 39)
  - Methods: `compute_model_deviation_index()`, `compute_data_quality_index()`, `compute_predictive_confidence()`, `execute()`, `validate_result()`

#### 📄 `agents/earth_grid_agent.py` _30.4 KB_
> AhmedETAP - Earth Grid Design Agent
=======================================================
Substation ground grid design and safety verification per 

- **Class** `EarthGridAgent` (line 32)
  - Methods: `calculate_mesh_voltage()`, `calculate_step_voltage()`, `calculate_touch_voltage()`, `design_ground_grid()`, `analyze_soil_resistivity()`, `verify_safety()`, `execute()`, `validate_result()`

#### 📄 `agents/etap_expert_agent.py` _26.7 KB_
> agents/etap_expert_agent.py — ETAP Expert Skill Agent

Implements the ETAP Expert skill as a runtime-active agent that:
  1. Loads its knowledge base 

- **Class** `CableSizingResult` (line 206)
- **Class** `ETAPExpertAgent` (line 543)
  - Methods: `answer()`, `execute()`, `get_agent_info()`
- **def** `classify()` (line 172)
- **def** `simulate_cable_sizing()` (line 244)

#### 📄 `agents/etap_gui_agent.py` _16.5 KB_
> agents/etap_gui_agent.py — ETAP GUI Agent Skill (Computer Use Agent)

Implements the ETAP GUI Agent skill as a runtime-active agent that:
  1. Loads i

- **Class** `ETAPGUIAgent` (line 327)
  - Methods: `answer()`, `execute()`, `get_agent_info()`
- **def** `classify()` (line 120)
- **def** `detect_target_app()` (line 164)

#### 📄 `agents/goal_planner_agent.py` _18.2 KB_
> AhmedETAP - Goal Planner Agent
===================================================
Goal decomposition, task extraction, and prioritized planning for
e

- **Class** `GoalPlannerAgent` (line 56)
  - Methods: `extract_tasks()`, `prioritize_tasks()`, `assess_risks()`, `execute()`, `validate_result()`

#### 📄 `agents/motor_starting_agent.py` _20.5 KB_
> AhmedETAP - Motor Starting Analysis Agent
=============================================================
Motor starting current, voltage dip, torque, a

- **Class** `MotorStartingAgent` (line 76)
  - Methods: `calculate_starting_current()`, `calculate_voltage_dip()`, `calculate_starting_torque()`, `calculate_acceleration_time()`, `execute()`, `validate_result()`

#### 📄 `agents/orchestrator.py` _70.4 KB_
> AhmedETAP - Multi-Agent Orchestrator
========================================================
Chief Engineering Orchestrator that coordinates all spec

- **Class** `AgentStatus` (line 40)
- **Class** `StudyType` (line 50)
- **Class** `AgentResult` (line 64)
- **Class** `EngineeringTask` (line 78)
- **Class** `BaseAgent` (line 91)
  - Methods: `system_prompt()`, `prompt_model()`, `prompt_temperature()`, `get_agent_info()`, `execute()`, `validate_result()`, `log_execution()`
- **Class** `LoadFlowAgent` (line 261)
  - Methods: `execute()`, `validate_result()`
- **Class** `ShortCircuitAgent` (line 379)
  - Methods: `execute()`, `validate_result()`
- **Class** `HarmonicAnalysisAgent` (line 504)
  - Methods: `execute()`, `validate_result()`
- **Class** `OptimalPowerFlowAgent` (line 610)
  - Methods: `execute()`, `validate_result()`
- **Class** `ProtectionCoordinationAgent` (line 726)
  - Methods: `execute()`, `validate_result()`
- **Class** `ETAPExecutionAgent` (line 823)
  - Methods: `execute()`, `validate_result()`
- **Class** `ValidationAgent` (line 930)
  - Methods: `execute()`
- **Class** `ReportGenerationAgent` (line 1083)
  - Methods: `execute()`
- **Class** `ChiefEngineeringOrchestrator` (line 1322)
  - Methods: `get_agents_info()`, `submit_task()`, `execute_autonomous_workflow()`, `get_study_type_mapping()`, `execute_parallel_studies()`, `get_task_status()`
- **def** `get_orchestrator()` (line 1890)

#### 📄 `agents/predictive_agent.py` _26.4 KB_
> AhmedETAP - Predictive Analytics Agent
=========================================================
Load forecasting, fault prediction, and predictive ma

- **Class** `PredictiveAgent` (line 39)
  - Methods: `forecast_short_term()`, `forecast_long_term()`, `predict_failure_probability()`, `compute_maintenance_schedule()`, `forecast_short_term_ml()`, `predict_fault_ml()`, `execute()`, `validate_result()`

#### 📄 `agents/prompt_loader.py` _10.5 KB_
> AhmedETAP - Prompt Loader
================================================

Mirrors the TypeScript ``getSystemPrompt()`` from ``src/mastra/prompts.ts`

- **def** `get_system_prompt()` (line 197)
- **def** `get_prompt_metadata()` (line 251)
- **def** `clear_prompt_cache()` (line 287)
- **def** `list_available_prompts()` (line 296)

#### 📄 `agents/renewable_agent.py` _32.5 KB_
> AhmedETAP - Renewable Integration Agent
===========================================================
Solar PV and wind turbine integration analysis per

- **Class** `RenewableAgent` (line 34)
  - Methods: `analyze_solar_pv()`, `analyze_wind()`, `check_ieee1547_compliance()`, `calculate_hosting_capacity()`, `execute()`, `validate_result()`

#### 📄 `agents/scada_agent.py` _33.3 KB_
> AhmedETAP - SCADA Integration Agent
=======================================================
IEC 61850 data model mapping and real-time measurement pro

- **Class** `SCADAMeasurement` (line 140)
  - Methods: `to_dict()`
- **Class** `SCADAConnection` (line 170)
  - Methods: `connect()`, `disconnect()`
- **Class** `SCADAAgent` (line 191)
  - Methods: `connect_scada()`, `read_measurements()`, `map_to_bus_data()`, `process_realtime_data()`, `get_iec61850_model()`, `execute()`, `validate_result()`

#### 📄 `agents/stability_agent.py` _24.8 KB_
> AhmedETAP - Stability Analysis Agent
========================================================
Transient and small-signal stability analysis per IEEE 3

- **Class** `StabilityAgent` (line 35)
  - Methods: `analyze_transient_stability()`, `analyze_small_signal_stability()`, `critical_clearing_time()`, `execute()`, `validate_result()`

#### 📄 `agents/weather_agent.py` _19.4 KB_
> AhmedETAP - Weather Impact Analysis Agent
=============================================================
Weather information retrieval and power system

- **Class** `WeatherAgent` (line 35)
  - Methods: `analyze_temperature_derating()`, `analyze_wind_impact()`, `process_weather_alert()`, `execute()`, `validate_result()`

### 📦 `api/`

#### 📄 `api/__init__.py` _0.1 KB_

#### 📄 `api/agents.py` _5.8 KB_
> Agent Information API Router
===========================
Handles all AI agent information endpoints.
Separated from main engineering service for bette

- **Class** `ETAPExpertChatRequest` (line 65)
- **Class** `ETAPGUIChatRequest` (line 122)
- **async def** `get_agents_info()` (line 20)
- **async def** `etap_expert_chat()` (line 75)
- **async def** `etap_gui_chat()` (line 132)

  **API Routes:**
  - `GET /info`
  - `POST /etap-expert/chat`
  - `POST /etap-gui/chat`

#### 📄 `api/ai_ml.py` _11.7 KB_
> AI/ML Endpoints API Router
==========================
Handles all AI/ML and predictive analytics endpoints.
Separated from main engineering service fo

- **async def** `ml_capabilities()` (line 24)
- **async def** `predict_load()` (line 36)
- **async def** `predict_fault()` (line 92)
- **async def** `train_fault_predictor()` (line 145)
- **async def** `detect_anomalies()` (line 191)
- **async def** `gnn_predict()` (line 238)
- **async def** `rag_query()` (line 295)

  **API Routes:**
  - `GET /ml/capabilities`
  - `POST /predict/load`
  - `POST /predict/fault`
  - `POST /predict/fault/train`
  - `POST /predict/anomaly`
  - `POST /gnn/predict`
  - `POST /rag/query`

#### 📄 `api/auth.py` _28.8 KB_
> api/auth.py — Authentication & user-management router.

Exposes the following endpoints under the ``/api/v1/auth`` prefix:

* ``POST /register``      

- **Class** `User` (line 156)
- **Class** `RegisterRequest` (line 189)
  - Methods: `validate_password_strength()`
- **Class** `LoginRequest` (line 214)
- **Class** `TokenResponse` (line 223)
- **Class** `RefreshRequest` (line 234)
- **Class** `ChangePasswordRequest` (line 242)
  - Methods: `validate_new_password()`
- **Class** `ForgotPasswordRequest` (line 261)
- **Class** `ResetPasswordRequest` (line 269)
  - Methods: `validate_new_password()`
- **Class** `UpdateProfileRequest` (line 287)
- **Class** `UserResponse` (line 296)
- **Class** `UserListResponse` (line 312)
- **async def** `register()` (line 417)
- **async def** `login()` (line 471)
- **async def** `refresh()` (line 518)
- **async def** `logout()` (line 582)
- **async def** `get_me()` (line 618)
- **async def** `update_me()` (line 650)
- **async def** `change_password()` (line 703)
- **async def** `forgot_password()` (line 766)
- **async def** `reset_password()` (line 807)
- **async def** `list_users()` (line 852)

#### 📄 `api/coverage_report.py` _31.8 KB_
> api/coverage_report.py — Test coverage analysis tool for the AhmedETAP.

Scans all Python source files, identifies functions/methods that have
corresp

- **Class** `CoverageLevel` (line 46)
- **Class** `FunctionInfo` (line 58)
  - Methods: `to_dict()`
- **Class** `ModuleCoverage` (line 80)
  - Methods: `to_dict()`
- **Class** `CoverageReport` (line 108)
  - Methods: `to_dict()`
- **Class** `_FunctionExtractor` (line 231)
  - Methods: `visit_ClassDef()`, `visit_FunctionDef()`, `visit_AsyncFunctionDef()`
- **Class** `CoverageAnalyzer` (line 352)
  - Methods: `run()`

#### 📄 `api/database.py` _4.3 KB_
> api/database.py — Async SQLAlchemy database configuration.

Provides the async engine, session factory, declarative base, and a
convenience ``init_db`

- **Class** `Base` (line 78)
- **async def** `get_db()` (line 91)
- **async def** `init_db()` (line 113)

#### 📄 `api/dependencies.py` _9.2 KB_
> api/dependencies.py — Shared FastAPI dependencies.

Provides reusable dependency callables for:

* JWT-based current-user resolution (``get_current_us

- **Class** `PaginationParams` (line 71)
  - Methods: `offset()`
- **Class** `CurrentUser` (line 103)
- **def** `pagination_params()` (line 90)
- **async def** `get_current_user()` (line 118)
- **async def** `get_current_user_from_header()` (line 195)
- **def** `require_role()` (line 213)
- **async def** `get_api_key()` (line 246)

  **API Routes:**
  - `GET /me`
  - `DELETE /users/{user_id}`

#### 📄 `api/digital_twin.py` _2.4 KB_
> Digital Twin Endpoints API Router
=================================
Handles all digital twin synchronization endpoints.
Separated from main engineerin

- **async def** `get_digital_twin_status()` (line 20)

  **API Routes:**
  - `GET /status`

#### 📄 `api/error_debugger.py` _33.4 KB_
> api/error_debugger.py — Structured error debugging and recovery module.

Provides:
  * Custom exception classes with unique error codes
  * Error-code

- **Class** `ErrorCategory` (line 46)
- **Class** `ErrorCode` (line 60)
- **Class** `ETAPPlatformError` (line 332)
  - Methods: `to_dict()`
- **Class** `StudyExecutionError` (line 371)
- **Class** `SystemValidationError` (line 400)
- **Class** `AuthenticationError` (line 430)
- **Class** `RateLimitError` (line 454)
- **Class** `DatabaseError` (line 481)
- **Class** `ErrorContextBuilder` (line 509)
  - Methods: `build()`, `build_sync()`
- **Class** `ErrorReport` (line 862)
  - Methods: `to_dict()`, `to_json()`
- **Class** `ErrorReportGenerator` (line 905)
  - Methods: `from_exception()`, `from_error_code()`
- **Class** `StructuredFormatter` (line 1016)
  - Methods: `format()`
- **def** `lookup_error_code()` (line 315)
- **def** `get_recovery_suggestions()` (line 831)
- **def** `setup_structured_logging()` (line 1101)

#### 📄 `api/health.py` _4.6 KB_
> Health and Metrics API Router
=============================
Handles all health check and metrics endpoints.
Separated from main engineering service fo

- **Class** `HealthResponse` (line 25)
- **Class** `ReadyResponse` (line 33)
- **Class** `MetricsResponse` (line 49)
- **async def** `root()` (line 67)
- **async def** `healthz()` (line 74)
- **async def** `readyz()` (line 81)
- **async def** `health_check()` (line 90)
- **async def** `readiness_check()` (line 101)
- **async def** `metrics()` (line 131)
- **async def** `prometheus_metrics()` (line 148)

  **API Routes:**
  - `GET /`
  - `GET /healthz`
  - `GET /readyz`
  - `GET /health`
  - `GET /ready`
  - `GET /metrics`
  - `GET /prometheus/metrics`

#### 📄 `api/mfa.py` _2.9 KB_
> MFA Endpoints API Router
=======================
Handles all multi-factor authentication endpoints.
Separated from main engineering service for better

- **async def** `setup_totp()` (line 15)
- **async def** `verify_totp()` (line 55)

  **API Routes:**
  - `POST /totp/setup`
  - `POST /totp/verify`

#### 📄 `api/projects.py` _23.2 KB_
> api/projects.py — Power-system project CRUD router.

Exposes the following endpoints under the ``/api/v1/projects`` prefix:

* ``POST /``             

- **Class** `ProjectStatus` (line 78)
- **Class** `StudyType` (line 86)
- **Class** `StudyStatus` (line 99)
- **Class** `Project` (line 113)
- **Class** `StudyResult` (line 135)
- **Class** `ProjectCreateRequest` (line 160)
- **Class** `ProjectUpdateRequest` (line 170)
  - Methods: `reject_deleted_status()`
- **Class** `ProjectResponse` (line 189)
- **Class** `ProjectListResponse` (line 204)
- **Class** `StudyRunRequest` (line 220)
- **Class** `StudyResultResponse` (line 229)
- **Class** `StudyListResponse` (line 246)
- **async def** `create_project()` (line 275)
- **async def** `list_projects()` (line 313)
- **async def** `get_project()` (line 370)
- **async def** `update_project()` (line 408)
- **async def** `delete_project()` (line 462)
- **async def** `run_study()` (line 502)
- **async def** `list_studies()` (line 590)

#### 📄 `api/refactored_service.py` _80.5 KB_
> api/refactored_service.py — Refactored Engineering Service with modular architecture.

This file demonstrates how the monolithic ``engineering_service

- **Class** `AppState` (line 151)
  - Methods: `increment_request()`, `increment_success()`, `increment_failed()`, `add_execution_time()`, `avg_execution_time_ms()`, `get_power_system_engine_cls()`, `get_etap_provider_factory()`
- **Class** `BusSpec` (line 227)
  - Methods: `validate_bus_type()`
- **Class** `LineSpec` (line 272)
- **Class** `TransformerSpec` (line 289)
- **Class** `GeneratorSpec` (line 303)
- **Class** `LoadSpec` (line 335)
- **Class** `SystemSpec` (line 350)
- **Class** `StudyRequest` (line 365)
  - Methods: `validate_study_type()`
- **Class** `StudyResult` (line 404)
- **Class** `HealthResponse` (line 416)
- **Class** `ReadyResponse` (line 423)
- **Class** `MetricsResponse` (line 431)
- **Class** `_BodySizeLimitMiddleware` (line 806)
  - Methods: `dispatch()`
- **Class** `_RequestLoggingMiddleware` (line 822)
  - Methods: `dispatch()`
- **Class** `ConnectionManager` (line 909)
  - Methods: `connect()`, `disconnect()`, `broadcast()`
- **async def** `lifespan()` (line 953)
- **async def** `trace_middleware()` (line 1077)
- **async def** `root()` (line 1186)
- **async def** `healthz()` (line 1193)
- **async def** `readyz()` (line 1200)
- **async def** `health_check()` (line 1209)
- **async def** `readiness_check()` (line 1221)
- **async def** `metrics()` (line 1249)
- **async def** `run_study()` (line 1267)
- **async def** `validate_system()` (line 1423)

  **API Routes:**
  - `GET /`
  - `GET /healthz`
  - `GET /readyz`
  - `GET /health`
  - `GET /ready`
  - `GET /metrics`
  - `POST /api/v1/studies/run`
  - `POST /api/v1/system/validate`
  - `GET /api/v1/agents/info`
  - `POST /api/v1/predict/load`
  - `POST /api/v1/predict/fault`
  - `POST /api/v1/predict/anomaly`
  - `POST /api/v1/rag/query`
  - `GET /api/v1/scada/live`
  - `GET /api/v1/digital-twin/status`
  - `POST /api/v1/auth/mfa/totp/setup`
  - `POST /api/v1/auth/mfa/totp/verify`
  - `POST /api/v1/auth/abac/check`
  - `GET /api/v1/security/rasp/stats`
  - `POST /api/v1/security/siem/event`
  - `GET /api/v1/benchmark`

#### 📄 `api/routes.py` _19.1 KB_
> API Routes module for the Engineering Service.
Handles all API endpoints, request validation, and response formatting.

- **Class** `_BodySizeLimitMiddleware` (line 106)
  - Methods: `dispatch()`
- **Class** `HealthResponse` (line 245)
- **Class** `ReadyResponse` (line 250)
- **async def** `trace_middleware()` (line 197)
- **def** `get_celery_components()` (line 298)
- **async def** `run_study_async()` (line 320)
- **async def** `get_task_status()` (line 351)
- **async def** `websocket_scada_endpoint_handler()` (line 386)
- **async def** `global_exception_handler()` (line 465)

  **API Routes:**
  - `GET /health`
  - `GET /ready`
  - `GET /metrics`
  - `GET /prometheus/metrics`
  - `POST /api/v1/studies/run`

#### 📄 `api/scada.py` _2.4 KB_
> SCADA Endpoints API Router
==========================
Handles all SCADA data model endpoints.
Separated from main engineering service for better modul

- **async def** `get_scada_live_data()` (line 15)

  **API Routes:**
  - `GET /live`

#### 📄 `api/security_audit.py` _51.1 KB_
> api/security_audit.py — Runtime security audit module for the AhmedETAP.

Performs comprehensive security analysis of the running service:

  1. Scan 

- **Class** `Severity` (line 43)
- **Class** `FindingCategory` (line 53)
- **Class** `SecurityFinding` (line 69)
  - Methods: `to_dict()`
- **Class** `SecurityAuditReport` (line 102)
  - Methods: `to_dict()`
- **Class** `SecurityAuditor` (line 259)
  - Methods: `run()`

#### 📄 `api/studies.py` _22.5 KB_
> Study Execution API Router
==========================
Handles all power system study execution endpoints.
Separated from main engineering service for 

- **Class** `BusSpec` (line 34)
  - Methods: `validate_bus_type()`
- **Class** `LineSpec` (line 79)
- **Class** `TransformerSpec` (line 96)
- **Class** `GeneratorSpec` (line 110)
- **Class** `LoadSpec` (line 142)
- **Class** `SystemSpec` (line 157)
- **Class** `StudyRequest` (line 172)
  - Methods: `validate_study_type()`
- **Class** `StudyResult` (line 215)
- **async def** `run_study()` (line 436)

  **API Routes:**
  - `POST /run`

#### 📄 `api/validation.py` _3.2 KB_
> System Validation API Router
============================
Handles all power system validation endpoints.
Separated from main engineering service for b

- **async def** `validate_system()` (line 18)

  **API Routes:**
  - `POST /validate`

#### 📄 `api/websocket.py` _7.8 KB_
> WebSocket endpoint for real-time SCADA data streaming.
Provides live updates to connected clients without requiring refresh.

- **Class** `SCADALiveFeed` (line 25)
  - Methods: `connect()`, `disconnect()`, `send_personal_message()`, `broadcast_message()`
- **async def** `scada_websocket_endpoint()` (line 192)

### 📦 `core/`

#### 📄 `core/__init__.py` _0.7 KB_

#### 📄 `core/bootstrap.py` _12.9 KB_
> Bootstrap module for the Engineering Service.
Handles initialization of logging, metrics, and core services with privacy controls.

- **Class** `_TraceFilter` (line 127)
  - Methods: `filter()`
- **Class** `_NoopMetric` (line 233)
  - Methods: `labels()`, `inc()`, `dec()`, `observe()`, `set()`, `info()`
- **Class** `_PromStub` (line 31)
  - Methods: `labels()`, `inc()`, `dec()`, `observe()`, `set()`, `info()`
- **async def** `lifespan()` (line 348)
- **def** `get_study_cache()` (line 414)
- **def** `get_logger()` (line 419)

#### 📄 `core/database.py` _18.9 KB_
> core/database.py — Universal Data Model database.

Thread-safe SQLite-backed storage for BIM elements with conflict detection.

- **Class** `UniversalDataModel` (line 37)
  - Methods: `add_element()`, `get_element()`, `get_all_elements()`, `update_element()`, `delete_element()`, `detect_conflicts()`, `resolve_conflict()`, `get_statistics()`

#### 📄 `core/extra_metrics.py` _0.9 KB_

#### 📄 `core/metrics.py` _9.0 KB_
> core/metrics.py — Prometheus instrumentation for the AhmedETAP platform.

Patterns drawn from prometheus/client_python:
- Counter, Gauge, Histogram, S

- **def** `set_app_info()` (line 83)
- **def** `track_skill_operation()` (line 166)
- **def** `track_execution_duration()` (line 218)
- **def** `count_executions()` (line 233)
- **def** `get_metrics_content_type()` (line 276)
- **def** `generate_metrics()` (line 281)
- **def** `observe_memory()` (line 286)
- **def** `set_cache_entries()` (line 291)
- **def** `record_validation_failure()` (line 296)

#### 📄 `core/models.py` _10.2 KB_
> core/models.py — Core data models for the Universal Data Model.

Combines standard dataclasses (for performance-sensitive paths) with
Pydantic BaseMod

- **Class** `PydanticPoint3D` (line 26)
- **Class** `PydanticGeometry` (line 34)
  - Methods: `area_must_be_positive()`
- **Class** `PydanticSemanticProperties` (line 50)
  - Methods: `element_type_must_be_valid()`
- **Class** `PydanticUniversalElement` (line 76)
  - Methods: `coerce_relationship_objects()`, `from_dataclass()`
- **Class** `ElementType` (line 131)
- **Class** `ChangeSource` (line 145)
- **Class** `ConflictType` (line 154)
- **Class** `Point3D` (line 163)
  - Methods: `to_dict()`
- **Class** `Geometry` (line 173)
  - Methods: `calculate_area()`, `to_dict()`
- **Class** `SemanticProperties` (line 205)
  - Methods: `to_dict()`
- **Class** `Relationship` (line 233)
  - Methods: `to_dict()`
- **Class** `UniversalElement` (line 253)
  - Methods: `to_dict()`
- **Class** `Conflict` (line 295)
  - Methods: `to_dict()`

#### 📄 `core/retry.py` _4.0 KB_
> core/retry.py — Reusable retry decorators for network, skill-loading,
and general fault-tolerant operations.

Patterns drawn from Tenacity/tenacity:
-

- **def** `network_retry()` (line 37)
- **def** `skill_retry()` (line 71)
- **def** `bounded_retry()` (line 102)

#### 📄 `core/tracing.py` _8.8 KB_
> core/tracing.py — OpenTelemetry observability for the AhmedETAP platform.

Patterns drawn from open-telemetry/opentelemetry-python:
- TracerProvider i

- **def** `setup_tracing()` (line 50)
- **def** `get_tracer()` (line 154)
- **def** `create_span()` (line 167)
- **def** `trace_operation()` (line 177)
- **def** `inject_context()` (line 250)
- **def** `extract_context()` (line 262)
- **def** `inject_traceparent()` (line 267)

### 📦 `engine/`

#### 📄 `engine/__init__.py` _4.6 KB_
> Engine - Core power system simulation engine.

Provides the main PowerSystemEngine along with supporting modules for
asynchronous execution, caching, 


#### 📄 `engine/async_executor.py` _24.5 KB_
> Async execution and concurrency module for the AhmedETAP Engineering Platform.

- **Class** `TaskPriority` (line 36)
- **Class** `TaskStatus` (line 43)
- **Class** `AsyncTask` (line 53)
- **Class** `_PriorityTaskQueue` (line 71)
  - Methods: `put()`, `get()`, `peek()`, `remove()`, `qsize()`, `qsize_unlocked()`
- **Class** `AsyncExecutor` (line 133)
  - Methods: `submit_task()`, `submit_coroutine()`, `run_parallel()`, `get_task()`, `cancel_task()`, `get_queue_size()`, `get_stats()`, `shutdown()`
- **Class** `ThreadPoolManager` (line 391)
  - Methods: `run_in_thread()`, `run_batch()`, `get_stats()`
- **Class** `ProcessPoolManager` (line 469)
  - Methods: `run_in_process()`, `get_stats()`
- **Class** `_TimeoutContext` (line 512)
  - Methods: `remaining()`, `expired()`
- **Class** `_RetryContext` (line 536)
- **Class** `_WorkflowStep` (line 575)
- **Class** `WorkflowOrchestrator` (line 589)
  - Methods: `define_workflow()`, `execute_workflow()`, `get_workflow_status()`
- **def** `async_timeout()` (line 567)
- **def** `async_retry()` (line 571)
- **def** `get_async_executor()` (line 729)
- **def** `get_thread_pool_manager()` (line 744)
- **def** `get_process_pool_manager()` (line 759)

#### 📄 `engine/cache_manager.py` _22.3 KB_
- **Class** `CacheStrategy` (line 31)
- **Class** `_CacheEntry` (line 38)
- **Class** `CalculationCache` (line 67)
  - Methods: `get()`, `set()`, `invalidate()`, `invalidate_by_tag()`, `clear()`, `get_stats()`, `get_cache_keys()`, `exists()`
- **Class** `CacheKeyBuilder` (line 285)
  - Methods: `build_key()`, `hash_params()`, `hash_system_state()`
- **Class** `SmartCacheStrategy` (line 335)
  - Methods: `should_cache()`, `get_cache_ttl()`, `pre_warm()`
- **Class** `MemoryManager` (line 419)
  - Methods: `get_memory_usage()`, `evict_if_needed()`, `optimize()`, `get_memory_report()`
- **def** `get_calculation_cache()` (line 540)
- **def** `get_smart_cache_strategy()` (line 557)
- **def** `get_memory_manager()` (line 566)
- **def** `cached()` (line 578)

#### 📄 `engine/caching.py` _16.8 KB_
> Redis Caching Layer for AhmedETAP Platform
==========================================
Provides an async Redis-backed caching layer for repeated study 

- **Class** `_InMemoryStore` (line 55)
  - Methods: `get()`, `set()`, `delete()`, `exists()`, `keys()`, `dbsize()`, `flushdb()`
- **Class** `StudyCache` (line 143)
  - Methods: `get()`, `set()`, `invalidate()`, `invalidate_study_type()`, `get_stats()`, `clear()`, `close()`
- **def** `get_study_cache()` (line 498)

#### 📄 `engine/data_optimizer.py` _29.3 KB_
> Memory-efficient data structures and optimization for large power system models.

- **Class** `SparseMatrixManager` (line 24)
  - Methods: `to_sparse()`, `to_dense()`, `build_sparse_ybus()`, `sparse_lu_solve()`, `sparse_factored_solve()`, `estimate_memory_savings()`
- **Class** `MemoryOptimizedSystem` (line 137)
  - Methods: `from_system()`, `get_bus_data()`, `get_all_bus_voltages()`, `get_ybus()`, `to_system()`, `get_bus_count()`, `estimate_memory_usage()`
- **Class** `BatchProcessor` (line 367)
  - Methods: `process_buses()`, `process_lines()`, `process_faults()`, `get_batch_statistics()`
- **Class** `DataCompressor` (line 425)
  - Methods: `compress_results()`, `decompress_results()`, `compress_system_state()`, `decompress_system_state()`, `get_compression_ratio()`
- **Class** `PerformanceProfiler` (line 573)
  - Methods: `profile_function()`, `profile_memory()`, `get_profile_report()`, `suggest_optimizations()`
- **Class** `LargeSystemAdapter` (line 676)
  - Methods: `run_load_flow_optimized()`, `run_fault_analysis_optimized()`, `get_optimization_strategy()`

#### 📄 `engine/engine.py` _13.2 KB_
- **Class** `PowerSystemEngine` (line 17)
  - Methods: `run_load_flow()`, `run_fault_analysis()`, `run_arc_flash()`, `run_protection_coordination()`, `run_study()`, `visualize_tcc()`, `visualize_coordination()`

#### 📄 `engine/error_handler.py` _26.1 KB_
> Error handling and alerting infrastructure for the AhmedETAP Engineering Platform.

Provides production-grade error tracking, alerting, automatic reco

- **Class** `ErrorSeverity` (line 36)
- **Class** `EngineSystemError` (line 52)
- **Class** `AlertManager` (line 91)
  - Methods: `configure_email()`, `configure_webhook()`, `add_alert_rule()`, `trigger_alert()`, `get_active_alerts()`
- **Class** `ErrorHandler` (line 314)
  - Methods: `set_alert_manager()`, `handle_error()`, `get_error_history()`, `get_error_by_id()`, `acknowledge_error()`, `resolve_error()`, `get_error_statistics()`
- **Class** `AutoRecoveryManager` (line 556)
  - Methods: `register_recovery_action()`, `attempt_recovery()`, `get_recovery_status()`
- **def** `component_guard()` (line 697)
- **def** `get_error_handler()` (line 751)
- **def** `get_alert_manager()` (line 761)
- **def** `get_auto_recovery_manager()` (line 771)

#### 📄 `engine/gpu_solver.py` _23.6 KB_
> GPU-Accelerated Power System Solver with Automatic CPU Fallback.

Provides a ``GPUSolver`` class that transparently uses CuPy (CUDA GPU)
when availabl

- **Class** `GPUSolver` (line 87)
  - Methods: `is_gpu_available()`, `device_name()`, `newton_raphson_gpu()`, `benchmark_cpu_vs_gpu()`

#### 📄 `engine/interfaces.py` _4.9 KB_
> Engine Interfaces — Abstract protocols for solver dependency injection.

Defines the contracts that all solvers must satisfy so ``PowerSystemEngine``


- **Class** `LoadFlowSolverProtocol` (line 34)
  - Methods: `solve()`
- **Class** `FaultAnalyzerProtocol` (line 56)
  - Methods: `three_phase_fault()`, `line_to_ground_fault()`, `line_to_line_fault()`, `double_line_to_ground_fault()`
- **Class** `ArcFlashEngineProtocol` (line 78)
  - Methods: `calculate()`
- **Class** `CoordinationEngineProtocol` (line 106)
  - Methods: `check_coordination()`, `check_coordination_range()`, `suggest_tms_adjustment()`
- **Class** `VisualizerProtocol` (line 141)
  - Methods: `plot_multiple_tcc()`, `plot_coordination_margin()`

#### 📄 `engine/numerical_safety.py` _20.7 KB_
> Numerical stability and safety utilities for power system calculation engines.

- **Class** `NumericalBounds` (line 26)
  - Methods: `get_bounds()`
- **Class** `NumericalGuard` (line 72)
  - Methods: `check_inf_nan()`, `check_divergence()`, `safe_log()`, `safe_sqrt()`, `safe_division()`, `safe_angle()`, `clamp_to_bounds()`, `is_within_bounds()`
- **Class** `ConvergenceMonitor` (line 199)
  - Methods: `add_iteration()`, `is_converged()`, `is_diverging()`, `get_convergence_rate()`, `reset()`, `get_statistics()`
- **Class** `ConsistencyCheck` (line 285)
  - Methods: `check_power_balance()`, `check_voltage_profile()`, `check_kirchhoff_current_law()`, `check_kirchhoff_voltage_law()`, `check_energy_conservation()`, `get_all_results()`, `clear_results()`
- **Class** `MatrixStabilizer` (line 422)
  - Methods: `regularize_matrix()`, `safe_inverse()`, `safe_solve()`, `is_symmetric()`, `is_positive_definite()`, `estimate_rank()`
- **def** `wrap_solver()` (line 495)
- **def** `safe_calculation()` (line 521)

#### 📄 `engine/resilience.py` _29.8 KB_
> Reliability and resilience patterns for the AhmedETAP Engineering Platform.

Provides production-grade retry handling, circuit breaker, multi-level re

- **Class** `RetryHandler` (line 54)
  - Methods: `total_calls()`, `total_retries()`, `execute()`, `async_execute()`
- **Class** `CircuitBreakerState` (line 296)
- **Class** `CircuitBreaker` (line 304)
  - Methods: `total_calls()`, `failed_calls()`, `last_failure_time()`, `state_changes()`, `get_state()`, `reset()`, `call()`, `async_call()`
- **Class** `CircuitBreakerOpenError` (line 547)
- **Class** `RecoveryResult` (line 556)
- **Class** `MultiLevelRecovery` (line 580)
  - Methods: `total_recoveries()`, `successful_recoveries()`, `add_strategy()`, `recover()`
- **Class** `StabilityEnforcer` (line 724)
  - Methods: `checks_performed()`, `violations_detected()`, `check_matrix_singularity()`, `safe_matrix_inverse()`, `check_convergence()`, `enforce_bounds()`, `validate_numerical_result()`
- **def** `register_circuit_breaker()` (line 31)
- **def** `get_circuit_breaker()` (line 37)
- **def** `get_all_circuit_breakers()` (line 43)
- **def** `with_retry()` (line 236)
- **def** `get_resilience_stats()` (line 911)

#### 📄 `engine/scalability.py` _28.1 KB_
> Scalability and distributed computing for the AhmedETAP Engineering Platform.

Provides horizontal scaling, load balancing, task queuing, cluster mana

- **Class** `LoadBalancingStrategy` (line 31)
- **Class** `WorkerNode` (line 39)
- **Class** `LoadBalancer` (line 50)
  - Methods: `register_worker()`, `unregister_worker()`, `get_next_worker()`, `get_worker_status()`, `get_all_workers_status()`, `set_strategy()`, `update_worker_load()`
- **Class** `TaskPriority` (line 146)
- **Class** `TaskItem` (line 156)
- **Class** `DistributedTaskQueue` (line 166)
  - Methods: `enqueue()`, `dequeue()`, `acknowledge()`, `requeue_failed()`, `get_queue_depth()`, `get_queue_statistics()`
- **Class** `ClusterNode` (line 264)
- **Class** `ClusterManager` (line 276)
  - Methods: `register_node()`, `discover_nodes()`, `get_active_nodes()`, `get_node_capabilities()`, `assign_study()`, `handle_node_failure()`, `register_failure_handler()`, `get_cluster_health()`
- **Class** `HorizontalScaler` (line 386)
  - Methods: `evaluate_scaling()`, `scale_up()`, `scale_down()`, `get_scaling_recommendation()`, `get_current_capacity()`, `on_scale_up()`, `on_scale_down()`
- **Class** `PartitionType` (line 474)
- **Class** `Partition` (line 481)
- **Class** `PartitionManager` (line 488)
  - Methods: `partition_system()`, `get_partition()`, `merge_results()`, `get_boundary_buses()`, `verify_partition_integrity()`
- **Class** `ExecutionStatus` (line 641)
- **Class** `ExecutionPlan` (line 650)
- **Class** `Execution` (line 660)
- **Class** `DistributedOrchestrator` (line 671)
  - Methods: `execute_distributed_study()`, `get_execution_plan()`, `monitor_execution()`, `cancel_execution()`

#### 📄 `engine/sparse_solver.py` _34.9 KB_
> Sparse Matrix Solver for Large-Scale Power System Analysis.

Provides memory-efficient sparse Y-bus construction and Newton-Raphson
load flow solving 

- **Class** `BranchData` (line 51)
- **Class** `BusData` (line 80)
- **Class** `SparseConvergenceResult` (line 128)
- **Class** `SparseYBus` (line 149)
  - Methods: `build_sparse_ybus()`, `sparse_newton_raphson()`, `compare_memory()`, `benchmark()`
- **def** `create_ieee_test_system()` (line 987)

### 📦 `fault_analysis/`

#### 📄 `fault_analysis/__init__.py` _1.6 KB_
> Fault Analysis - Short-circuit and arc-flash analysis engine.

Provides fault analysis capabilities including IEC 60909 short-circuit
calculations, IE


#### 📄 `fault_analysis/arc_flash_calc.py` _6.2 KB_
> IEEE 1584-2018 Arc Flash Calculation Utility
=============================================
Thin convenience wrapper around ``ArcFlashEngine`` from
``f

- **def** `calculate_arc_flash()` (line 36)

#### 📄 `fault_analysis/arc_flash_engine.py` _22.3 KB_
> Arc Flash Analysis Engine - IEEE 1584-2018 Implementation

This module implements arc flash calculations according to IEEE 1584-2018
"IEEE Guide for P

- **Class** `ElectrodeConfig` (line 24)
- **Class** `EnclosureType` (line 34)
- **Class** `ArcFlashResult` (line 42)
- **Class** `ArcFlashEngine` (line 121)
  - Methods: `calculate_arc_current()`, `calculate_incident_energy()`, `calculate_arc_flash_boundary()`, `determine_ppe_level()`, `calculate()`, `ralph_lee_method()`

#### 📄 `fault_analysis/fault.py` _8.3 KB_
- **Class** `FaultAnalyzer` (line 12)
  - Methods: `three_phase_fault()`, `line_to_ground_fault()`, `line_to_line_fault()`, `double_line_to_ground_fault()`

#### 📄 `fault_analysis/harmonic_analysis.py` _20.2 KB_
> Harmonic Analysis Engine
=========================
Implements harmonic power flow analysis per IEEE 519-2022.

Supports:
- Harmonic impedance calculat

- **Class** `HarmonicStandard` (line 28)
- **Class** `HarmonicSource` (line 37)
  - Methods: `frequency_hz()`
- **Class** `HarmonicResult` (line 55)
- **Class** `HarmonicAnalysisResult` (line 67)
- **Class** `HarmonicAnalysisEngine` (line 81)
  - Methods: `set_system_data()`, `add_harmonic_source()`, `calculate_harmonic_impedance()`, `solve_harmonic_power_flow()`, `calculate_thd()`, `calculate_tdd()`, `detect_resonance()`, `check_ieee_519_compliance()`

#### 📄 `fault_analysis/iec60909_engine.py` _17.4 KB_
> IEC 60909 Short Circuit Calculation Engine

Implements IEC 60909-0:2016 "Short-circuit currents in three-phase AC systems"
Supports:
- Three-phase sho

- **Class** `FaultType` (line 25)
- **Class** `VoltageFactorC` (line 32)
- **Class** `ShortCircuitResult` (line 44)
- **Class** `IEC60909Engine` (line 67)
  - Methods: `calculate_three_phase_fault()`, `calculate_line_to_ground_fault()`, `calculate_line_to_line_fault()`, `calculate_double_line_to_ground_fault()`, `calculate()`

#### 📄 `fault_analysis/ieee1584_database.py` _16.1 KB_
> IEEE 1584-2018 Complete Arc Flash Database and Calculation Engine

Contains full coefficient tables from IEEE 1584-2018 for:
- Arc current calculation

- **Class** `ElectrodeConfig` (line 21)
- **Class** `EnclosureType` (line 29)
- **Class** `IEEE1584Result` (line 174)
- **Class** `IEEE1584Database` (line 197)
  - Methods: `get_arc_current_coefficients()`, `get_incident_energy_coefficients()`, `get_boundary_coefficients()`, `calculate_enclosure_correction()`, `calculate_working_distance_correction()`, `calculate_arc_current()`, `calculate_reduced_arc_current()`, `calculate_incident_energy()`

### 📦 `load_flow/`

#### 📄 `load_flow/__init__.py` _0.6 KB_
> Load Flow - Power system load flow analysis.

Provides Newton-Raphson load flow solver, optimal power flow (OPF)
engine, and sparse-matrix solver inte


#### 📄 `load_flow/load_flow.py` _20.5 KB_
> Newton-Raphson Load Flow Solver

This is the canonical (consolidated) implementation. The previous
load_flow_solver_fixed.py has been merged into this

- **Class** `LoadFlowSolver` (line 15)
  - Methods: `solve()`

#### 📄 `load_flow/optimal_power_flow.py` _18.9 KB_
> Optimal Power Flow (OPF) Engine
=================================
Implements AC Optimal Power Flow using various optimization methods.

Supports:
- Ec

- **Class** `OPFObjective` (line 35)
- **Class** `GeneratorCost` (line 45)
  - Methods: `cost()`
- **Class** `OPFResult` (line 69)
- **Class** `OptimalPowerFlowEngine` (line 86)
  - Methods: `set_load_data()`, `set_generator_locations()`, `set_voltage_limits()`, `set_branch_limits()`, `solve_dc_opf()`, `solve_ac_opf_interior_point()`, `solve_opf()`, `generate_report()`

#### 📄 `load_flow/solver.py` _10.8 KB_
> Load Flow Solver Integration with Sparse Matrix Support.

This module provides the primary load-flow solver interface with both
dense (existing) and s

- **def** `solve_load_flow_sparse()` (line 173)

### 📦 `services/`

#### 📄 `services/cache_service.py` _6.8 KB_
> Cache Service module for the Engineering Service.

Provides a StudyCache with:
- Redis backend when available (optional)
- in-memory fallback when Red

- **Class** `StudyCache` (line 25)
  - Methods: `redis_client()`, `cache()`, `get()`, `set()`, `clear()`, `ping()`
- **async def** `get_study_cache()` (line 198)

#### 📄 `services/study_service.py` _22.1 KB_
> Study Service module for the Engineering Service.
Handles all study execution logic, system building, and ETAP integration.

- **Class** `BusSpec` (line 24)
  - Methods: `validate_bus_type()`
- **Class** `LineSpec` (line 69)
- **Class** `TransformerSpec` (line 86)
- **Class** `GeneratorSpec` (line 100)
- **Class** `LoadSpec` (line 132)
- **Class** `SystemSpec` (line 147)
- **Class** `StudyRequest` (line 162)
  - Methods: `validate_study_type()`
- **Class** `StudyResult` (line 212)
- **def** `execute_study_logic()` (line 453)

### 📦 `security/`

#### 📄 `security/__init__.py` _0.8 KB_

#### 📄 `security/abac.py` _25.2 KB_
> Attribute-Based Access Control (ABAC) for AhmedETAP Platform
============================================================
Extends the existing RBAC sy

- **Class** `RuleType` (line 64)
- **Class** `ABACRule` (line 75)
- **Class** `ABACPolicy` (line 101)
- **Class** `ABACPolicyEngine` (line 156)
  - Methods: `add_policy()`, `remove_policy()`, `list_policies()`, `evaluate()`
- **Class** `ABACMiddleware` (line 409)
  - Methods: `add_policy()`, `dispatch()`
- **Class** `ABACMiddleware` (line 532)
- **def** `ip_in_ranges()` (line 366)
- **def** `make_role_policy()` (line 544)
- **def** `make_business_hours_policy()` (line 590)
- **def** `make_ip_allowlist_policy()` (line 648)
- **def** `make_clearance_policy()` (line 685)
- **def** `create_default_etap_abac_engine()` (line 724)

#### 📄 `security/mfa.py` _27.0 KB_
> Multi-Factor Authentication (MFA) for AhmedETAP Platform
========================================================
Provides TOTP (Time-based One-Time P

- **Class** `TOTPSecret` (line 137)
- **Class** `TOTPProvider` (line 147)
  - Methods: `generate_secret()`, `generate_qr_code()`, `verify_code()`, `generate_backup_codes()`, `verify_backup_code()`, `enable_totp()`, `get_secret()`, `remove_secret()`
- **Class** `WebAuthnCredential` (line 365)
- **Class** `WebAuthnProvider` (line 376)
  - Methods: `generate_registration_options()`, `verify_registration()`, `generate_authentication_options()`, `verify_authentication()`, `get_credentials()`, `remove_credential()`, `has_credentials()`
- **Class** `MFAOrchestrator` (line 710)
  - Methods: `is_mfa_required()`, `verify_totp()`, `verify_backup_code()`, `verify_webauthn()`, `mark_session_verified()`, `is_session_verified()`, `revoke_session()`, `get_status()`

#### 📄 `security/rasp.py` _8.8 KB_
> Runtime Application Self-Protection (RASP) for AhmedETAP Platform
================================================================

Provides runtime a

- **Class** `RASPAction` (line 35)
- **Class** `RASPSeverity` (line 43)
- **Class** `RASPRule` (line 53)
- **Class** `RASPResult` (line 65)
- **Class** `RASPEngine` (line 162)
  - Methods: `enabled()`, `enabled()`, `inspect()`, `get_stats()`, `add_rule()`, `remove_rule()`
- **def** `create_default_rasp_engine()` (line 280)

#### 📄 `security/secrets_manager.py` _25.4 KB_
> Secrets Manager for AhmedETAP Engineering Platform
=================================================
Production-grade secrets management with HashiCor

- **Class** `VaultSecretsManager` (line 64)
  - Methods: `vault_token()`, `get_secret()`, `set_secret()`, `delete_secret()`, `list_secrets()`
- **Class** `LocalSecretsManager` (line 241)
  - Methods: `set_api_key()`, `get_api_key()`, `rotate_key()`, `delete_api_key()`, `list_services()`
- **Class** `KeyAccessAuditor` (line 366)
  - Methods: `log_access()`, `get_access_logs()`, `get_recent_access()`
- **Class** `EnvironmentValidator` (line 485)
  - Methods: `check_missing_secrets()`, `check_file_permissions()`, `check_for_hardcoded_secrets()`, `generate_env_template()`
- **def** `get_secrets_manager()` (line 638)

#### 📄 `security/secure_executor.py` _10.7 KB_
> Secure Python Executor
======================
P0 Security Control: Validates and executes Python code in a restricted environment.
Integrates with sec

- **def** `main()` (line 52)

#### 📄 `security/secure_powershell_executor.py` _4.0 KB_
> Secure PowerShell Executor
==========================
P0 Security Control: Validates and executes PowerShell commands in a restricted environment.
Int

- **def** `main()` (line 39)

#### 📄 `security/security_framework.py` _26.2 KB_
> Security Framework for AhmedETAP Platform
=========================================
Implements authentication, authorization, input validation, and se

- **Class** `UserRole` (line 43)
- **Class** `Permission` (line 53)
- **Class** `User` (line 136)
- **Class** `Session` (line 152)
- **Class** `AuthenticationManager` (line 163)
  - Methods: `create_user()`, `authenticate()`, `validate_token()`, `logout()`, `encrypt_secret()`, `decrypt_secret()`, `cleanup_expired_sessions()`
- **Class** `AuthorizationManager` (line 390)
  - Methods: `check_permission()`, `check_permissions()`, `get_user_permissions()`
- **Class** `InputValidator` (line 421)
  - Methods: `validate_python_code()`, `validate_powershell_command()`, `validate_file_path()`, `validate_numeric()`, `sanitize_string()`
- **Class** `RateLimiter` (line 643)
  - Methods: `is_allowed()`
- **Class** `AuditLogger` (line 700)
  - Methods: `log_event()`, `log_login()`, `log_action()`, `log_security_violation()`
- **def** `get_auth_manager()` (line 773)
- **def** `get_authz_manager()` (line 783)
- **def** `get_validator()` (line 792)
- **def** `get_rate_limiter()` (line 801)
- **def** `get_audit_logger()` (line 810)

#### 📄 `security/siem.py` _20.3 KB_
> SIEM Integration for AhmedETAP Platform
======================================
Forwards security events to external SIEM systems such as Grafana Loki


- **Class** `SecurityEvent` (line 64)
  - Methods: `to_dict()`, `to_json()`
- **Class** `SIEMForwarder` (line 111)
  - Methods: `forward_event()`, `forward_auth_event()`, `forward_access_event()`, `forward_anomaly_event()`, `forward_data_event()`, `flush()`, `get_stats()`, `health_check()`
- **def** `get_siem_forwarder()` (line 615)

### 📦 `ml/`

#### 📄 `ml/__init__.py` _0.5 KB_
> ML / Predictive Analytics Module
=================================

Provides machine-learning models for power systems prediction:

- :class:`LoadFore


#### 📄 `ml/predictive.py` _43.2 KB_
> Predictive Analytics Module for AhmedETAP Engineering Platform
============================================================

Provides ML-based predict

- **Class** `LoadForecaster` (line 133)
  - Methods: `train()`, `predict()`, `evaluate()`
- **Class** `FaultPredictor` (line 391)
  - Methods: `train()`, `predict()`, `explain()`, `feature_importance()`
- **Class** `AnomalyDetector` (line 685)
  - Methods: `train()`, `detect()`, `get_threshold()`
- **Class** `PowerGridGNN` (line 832)
  - Methods: `train_model()`, `predict()`
- **Class** `ModelRegistry` (line 1016)
  - Methods: `create_experiment()`, `start_run()`, `log_params()`, `log_metrics()`, `log_model()`, `end_run()`, `get_best_run()`
- **Class** `GCNModel` (line 875)
  - Methods: `forward()`
- **Class** `GATModel` (line 894)
  - Methods: `forward()`
- **def** `get_ml_capabilities()` (line 1165)

### 📦 `worker/`

#### 📄 `worker/celery_app.py` _0.8 KB_
> Celery application for handling heavy engineering tasks asynchronously.
Uses Redis as both broker and result backend.


#### 📄 `worker/tasks.py` _5.6 KB_
> Celery tasks for executing heavy engineering computations.
These tasks run asynchronously to prevent blocking the API.

- **def** `execute_engineering_study_task()` (line 21)
- **def** `execute_etap_integration_task()` (line 72)
- **def** `process_large_calculation_task()` (line 120)

### 📦 `reporting/`

#### 📄 `reporting/__init__.py` _0.7 KB_
> Reporting - Engineering report generation system.

Provides automated report generation for power system studies supporting
PDF, DOCX, and XLSX output


#### 📄 `reporting/advanced_reports.py` _30.6 KB_
> Advanced Report Generation System
===================================
Professional engineering report generation in multiple formats.

Supported Forma

- **Class** `ReportSection` (line 46)
- **Class** `ReportMetadata` (line 58)
- **Class** `ChartGenerator` (line 75)
  - Methods: `generate_voltage_profile_chart()`, `generate_fault_current_bar_chart()`, `generate_harmonic_spectrum_chart()`
- **Class** `TableGenerator` (line 206)
  - Methods: `generate_load_flow_table()`, `generate_fault_current_table()`, `generate_compliance_table()`
- **Class** `PDFReportGenerator` (line 302)
  - Methods: `generate_report()`
- **Class** `DOCXReportGenerator` (line 472)
  - Methods: `generate_report()`
- **Class** `XLSXReportGenerator` (line 532)
  - Methods: `generate_report()`
- **Class** `ReportGenerationAgent` (line 598)
  - Methods: `generate_complete_report()`
- **def** `get_report_agent()` (line 850)

### 📦 `digital_twin/`

#### 📄 `digital_twin/__init__.py` _2.1 KB_
> Digital Twin Package - ADMS + ETAP GIS + Power System Engineering
=================================================================
Unified synchroniz


#### 📄 `digital_twin/digital_twin_core.py` _52.4 KB_
> Digital Twin Core - Unified Synchronization Engine
====================================================
Merges GIS model, electrical model, and ADMS s

- **Class** `DigitalTwinState` (line 70)
  - Methods: `bind_gis()`, `bind_electrical()`, `bind_scada()`, `bind_adms()`, `gis()`, `system()`, `scada()`, `adms()`
- **Class** `SynchronizationEngine` (line 231)
  - Methods: `synchronize_gis_to_electrical()`, `synchronize_adms_to_electrical()`, `synchronize_gis_to_adms()`, `full_synchronization()`, `get_sync_log()`
- **Class** `ChangePropagationEngine` (line 379)
  - Methods: `bind_load_flow_solver()`, `bind_state_estimator()`, `propagate_switch_change()`, `propagate_load_change()`, `get_propagation_log()`
- **Class** `EventProcessor` (line 753)
  - Methods: `get_processed_events()`
- **Class** `TimeSteppedSimulator` (line 959)
  - Methods: `set_time_step()`, `set_scada_injector()`, `schedule_event()`, `step()`, `run()`, `stop()`, `get_step_log()`
- **Class** `LivePowerSystemEngine` (line 1128)
  - Methods: `run_load_flow()`, `run_fault_analysis()`, `run_protection_coordination()`, `open_switch()`, `close_switch()`, `change_load()`, `detect_fault()`, `inject_scada_update()`

#### 📄 `digital_twin/event_bus.py` _16.2 KB_
> Event Bus - Event-Driven Architecture for Digital Twin
======================================================
Implements publish/subscribe event syste

- **Class** `EventType` (line 30)
- **Class** `DomainEvent` (line 67)
  - Methods: `to_dict()`
- **Class** `SwitchOpened` (line 89)
- **Class** `SwitchClosed` (line 104)
- **Class** `FaultDetected` (line 119)
- **Class** `LoadChanged` (line 134)
- **Class** `PVChanged` (line 148)
- **Class** `BatteryDispatch` (line 163)
- **Class** `SCADAUpdateReceived` (line 178)
- **Class** `TopologyChanged` (line 191)
- **Class** `YbusRebuilt` (line 205)
- **Class** `LoadFlowCompleted` (line 218)
- **Class** `StateEstimationCompleted` (line 232)
- **Class** `FaultAnalysisCompleted` (line 246)
- **Class** `ArcFlashRefreshed` (line 260)
- **Class** `ProtectionRefreshed` (line 273)
- **Class** `DigitalTwinStateUpdated` (line 286)
- **Class** `ValidationErrorEvent` (line 300)
- **Class** `EventBus` (line 317)
  - Methods: `subscribe()`, `subscribe_all()`, `unsubscribe()`, `publish()`, `get_history()`, `get_handler_errors()`, `clear_history()`, `get_statistics()`

#### 📄 `digital_twin/gis_bridge.py` _26.3 KB_
> GIS ↔ Digital Twin Synchronization Bridge
===========================================
Bidirectional synchronization between GIS (PostGIS/QGIS) and the

- **Class** `SyncRecord` (line 74)
- **Class** `GISSyncBridge` (line 86)
  - Methods: `sync_gis_to_digital_twin()`, `sync_digital_twin_to_gis()`, `build_electrical_network_map()`, `get_sync_log()`, `get_sync_statistics()`, `run_full_sync()`

#### 📄 `digital_twin/handlers.py` _25.6 KB_
> Chain of Responsibility — Change Propagation Handlers
=====================================================

Decomposes the monolithic ``propagate_swi

- **Class** `PropagationContext` (line 44)
  - Methods: `record_step()`
- **Class** `PropagationHandler` (line 99)
  - Methods: `handle()`
- **Class** `TopologyUpdateHandler` (line 129)
  - Methods: `handle()`
- **Class** `YbusRebuildHandler` (line 166)
  - Methods: `handle()`
- **Class** `LoadFlowHandler` (line 197)
  - Methods: `handle()`
- **Class** `StateEstimationHandler` (line 250)
  - Methods: `handle()`
- **Class** `ShortCircuitRefreshHandler` (line 313)
  - Methods: `handle()`
- **Class** `ArcFlashRefreshHandler` (line 344)
  - Methods: `handle()`
- **Class** `ProtectionRefreshHandler` (line 491)
  - Methods: `handle()`
- **Class** `DigitalTwinUpdateHandler` (line 566)
  - Methods: `handle()`
- **Class** `PropagationChain` (line 619)
  - Methods: `execute()`

#### 📄 `digital_twin/state_store.py` _15.2 KB_
> State Store - Versioned State Management for Digital Twin
=========================================================
Implements immutable state snapsho

- **Class** `StateLayer` (line 27)
- **Class** `BusState` (line 37)
  - Methods: `voltage()`, `to_dict()`
- **Class** `SwitchState` (line 65)
  - Methods: `to_dict()`
- **Class** `TopologyState` (line 85)
  - Methods: `to_dict()`
- **Class** `GISAssetState` (line 103)
  - Methods: `to_dict()`
- **Class** `SimulationResults` (line 125)
  - Methods: `to_dict()`
- **Class** `StateSnapshot` (line 157)
  - Methods: `to_dict()`, `is_layer_synced()`, `to_json()`
- **Class** `StateStore` (line 231)
  - Methods: `commit()`, `get_current()`, `get_version()`, `get_current_version()`, `rollback()`, `diff()`, `get_history()`, `get_statistics()`

#### 📄 `digital_twin/validation_gateway.py` _24.3 KB_
> Validation Gateway - Three Truths Enforcement
==============================================
Enforces the hard constraints of the digital twin platfor

- **Class** `ValidationSeverity` (line 22)
- **Class** `ValidationRule` (line 31)
- **Class** `ValidationResult` (line 64)
  - Methods: `to_dict()`
- **Class** `DigitalTwinValidationError` (line 85)
  - Methods: `to_dict()`
- **Class** `ValidationGateway` (line 106)
  - Methods: `register_custom_rule()`, `validate_all()`, `validate_pre_mutation()`, `validate_post_mutation()`, `get_validation_history()`, `get_last_validation()`, `get_failed_rules()`, `get_statistics()`

### 📦 `network_solver/`

#### 📄 `network_solver/__init__.py` _0.6 KB_
> Network Solver - Power system network analysis utilities.

Provides per-unit conversion utilities and Z-bus matrix construction
for power system netwo


#### 📄 `network_solver/per_unit.py` _1.7 KB_
- **def** `to_per_unit()` (line 1)
- **def** `from_per_unit()` (line 15)
- **def** `power_to_per_unit()` (line 29)
- **def** `impedance_to_per_unit()` (line 43)
- **def** `admittance_to_per_unit()` (line 59)

#### 📄 `network_solver/zbus.py` _1.3 KB_
- **def** `zbus_from_ybus()` (line 4)
- **def** `zbus_full()` (line 27)

### 📦 `coordination/`

#### 📄 `coordination/__init__.py` _0.2 KB_
> Coordination - Protection coordination analysis engine.

Provides relay coordination analysis and time-current grading studies
for electrical power sy


#### 📄 `coordination/coordination.py` _6.2 KB_
- **Class** `CoordinationEngine` (line 4)
  - Methods: `check_coordination()`, `check_coordination_range()`, `suggest_tms_adjustment()`

### 📦 `relays/`

#### 📄 `relays/__init__.py` _0.4 KB_
> Relays - Protection relay models.

Provides implementations of various protection relay types including
overcurrent, distance, differential, and direc


#### 📄 `relays/relay.py` _7.9 KB_
- **Class** `Relay` (line 6)
  - Methods: `pickup_logic()`, `operate()`, `trip_time()`
- **Class** `OvercurrentRelay` (line 57)
  - Methods: `pickup_logic()`, `trip_time()`, `operate()`
- **Class** `DistanceRelay` (line 116)
  - Methods: `pickup_logic()`, `operate()`
- **Class** `DifferentialRelay` (line 152)
  - Methods: `pickup_logic()`, `operate()`
- **Class** `DirectionalRelay` (line 194)
  - Methods: `pickup_logic()`, `operate()`

### 📦 `adms_control/`

#### 📄 `adms_control/__init__.py` _0.6 KB_
> ADMS Control - Advanced Distribution Management System control engine.

Provides FLISR (Fault Location, Isolation, and Service Restoration)
and switch


#### 📄 `adms_control/adms_control.py` _22.4 KB_
> ADMS Control Engine - Real-Time Distribution Management
========================================================
Implements feeder switching, load tra

- **Class** `SwitchingActionType` (line 23)
- **Class** `FLISRStage` (line 30)
- **Class** `ControlCommandStatus` (line 38)
- **Class** `SwitchingAction` (line 46)
  - Methods: `to_dict()`
- **Class** `SwitchingSequence` (line 72)
  - Methods: `add_action()`, `to_dict()`
- **Class** `FLISRResult` (line 94)
  - Methods: `to_dict()`
- **Class** `TopologyProcessor` (line 125)
  - Methods: `add_connection()`, `remove_connection()`, `open_switch()`, `close_switch()`, `find_connected_components()`, `find_path()`, `get_switches_on_path()`, `identify_sections()`
- **Class** `ADMSControlEngine` (line 231)
  - Methods: `register_source_bus()`, `register_feeder()`, `set_section_load()`, `create_switching_sequence()`, `execute_switching_sequence()`, `plan_load_transfer()`, `detect_fault_section()`, `isolate_fault()`

### 📦 `utils/`

#### 📄 `utils/language_detection.py` _6.2 KB_
> Utility for detecting input language and converting keyboard layouts.
Supports Arabic-to-English keyboard layout conversion for non-English input.

- **def** `normalize_input()` (line 95)
- **def** `is_arabic_text()` (line 153)
- **def** `detect_language()` (line 179)
- **def** `convert_arabic_to_english()` (line 223)

### 📦 `guards/`

#### 📄 `guards/__init__.py` _1.8 KB_
> AhmedETAP Platform — Guard Skills Module
========================================
Surgical integration of guard-skills concepts (github.com/amElnagdy/


#### 📄 `guards/ai_failure_modes.py` _49.0 KB_
> AI Failure Mode Detector
=========================
Detects the 14 systematic LLM code-generation failure patterns identified
by the guard-skills proje

- **Class** `FailureMode` (line 40)
- **Class** `AIFailureModeDetector` (line 171)
  - Methods: `detect()`

#### 📄 `guards/base.py` _5.4 KB_
> Base Guard Framework
=====================
Shared abstractions for all guard validators.  The severity framework,
violation model, and guard-mode enum

- **Class** `GuardSeverity` (line 24)
- **Class** `GuardMode` (line 32)
- **Class** `GuardViolation` (line 47)
- **Class** `GuardResult` (line 78)
  - Methods: `passed()`, `must_fix_count()`, `should_fix_count()`, `worth_noting_count()`, `to_dict()`
- **Class** `BaseGuard` (line 142)
  - Methods: `scan()`

#### 📄 `guards/code_guard.py` _20.4 KB_
> Code Guard — Production Code Quality Gate
==========================================
Adapted from the clean-code-guard skill (github.com/amElnagdy/gua

- **Class** `CodeGuard` (line 30)
  - Methods: `scan()`

#### 📄 `guards/docs_guard.py` _20.9 KB_
> Docs Guard — Documentation Accuracy Gate
==========================================
Adapted from the docs-guard skill (github.com/amElnagdy/guard-skil

- **Class** `DocsGuard` (line 31)
  - Methods: `scan()`

#### 📄 `guards/test_guard.py` _26.7 KB_
> Test Guard — Test Code Quality Gate
=====================================
Adapted from the test-guard skill (github.com/amElnagdy/guard-skills).

Impl

- **Class** `TestGuard` (line 36)
  - Methods: `scan()`

### 📦 `copilot/`

#### 📄 `copilot/ai/__init__.py` _0.2 KB_
> AI Drawing Engine — Autonomous CAD generation from natural language.


#### 📄 `copilot/ai/drawing_engine.py` _37.1 KB_
> AI Drawing Engine
=================
Autonomous CAD generation engine that translates natural language
engineering intent into:
  1. Engineering Knowle

- **Class** `EngineeringIntentType` (line 54)
- **Class** `EngineeringIntent` (line 74)
- **Class** `EngineeringGraph` (line 86)
- **Class** `IntentParser` (line 100)
  - Methods: `parse()`
- **Class** `GraphBuilder` (line 399)
  - Methods: `build()`
- **Class** `ModelGenerator` (line 523)
  - Methods: `generate()`
- **Class** `AIDrawingEngine` (line 785)
  - Methods: `process()`, `get_history()`, `get_statistics()`

#### 📄 `copilot/api/__init__.py` _0.1 KB_
> FastAPI Backend — Engineering Copilot REST API.


#### 📄 `copilot/api/routes.py` _12.8 KB_
> Engineering Copilot — FastAPI Backend
=====================================
REST API for the Engineering Copilot that orchestrates ETAP, AutoCAD, Revi

- **Class** `ProcessRequest` (line 64)
- **Class** `TranslateRequest` (line 71)
- **Class** `ModelUpdateRequest` (line 77)
- **Class** `ToolCallRequest` (line 81)
- **Class** `SyncRequest` (line 85)
- **Class** `ValidateRequest` (line 91)
- **Class** `CopilotAPI` (line 101)
  - Methods: `get_router()`
- **def** `create_app()` (line 323)

#### 📄 `copilot/mcp/__init__.py` _0.1 KB_
> MCP Server — Engineering Copilot tool server.


#### 📄 `copilot/mcp/server.py` _25.2 KB_
> Engineering Copilot — MCP Server
=================================
Model Context Protocol server exposing all CAD, ETAP, and engineering tools
as MCP 

- **Class** `CopilotMCPServer` (line 294)
  - Methods: `list_tools()`, `call_tool()`, `health_check()`

#### 📄 `copilot/tests/test_copilot_unit.py` _19.2 KB_
> Engineering Copilot — Integration Tests
========================================
Tests for the unified model, translation engine, AI drawing engine,
M

- **Class** `TestUnifiedEngineeringModel` (line 43)
  - Methods: `test_create_bus()`, `test_create_transformer()`, `test_create_panel()`, `test_create_cable()`, `test_create_breaker()`, `test_create_load()`, `test_coordinates()`, `test_model_serialization_roundtrip()`
- **Class** `TestTranslationEngine` (line 166)
  - Methods: `setUp()`, `test_get_drawing_rule()`, `test_get_all_mapping_rules()`, `test_etap_to_unified_buses()`, `test_unified_to_etap()`, `test_unified_to_autocad_commands()`, `test_translate_dispatch()`
- **Class** `TestAIDrawingEngine` (line 261)
  - Methods: `setUp()`, `test_parse_panel_intent()`, `test_parse_sld_intent()`, `test_parse_validate_intent()`, `test_parse_add_feeder()`, `test_build_graph()`, `test_generate_model()`, `test_engine_process_basic()`
- **Class** `TestCopilotMCPServer` (line 332)
  - Methods: `setUp()`, `test_list_tools()`, `test_tool_has_schemas()`, `test_tool_create_panel()`, `test_tool_create_bus()`, `test_tool_create_transformer()`, `test_tool_create_cable()`, `test_tool_validate_design()`
- **Class** `TestDrawingRules` (line 461)
  - Methods: `test_entity_drawing_rules_completeness()`, `test_autocad_rules_have_required_fields()`, `test_revit_rules_have_family_info()`
- **Class** `TestETAPAdapter` (line 506)
  - Methods: `setUp()`, `test_bus_to_unified()`, `test_transformer_to_unified()`, `test_cable_to_unified()`

#### 📄 `copilot/translation/__init__.py` _0.1 KB_
> Translation Engine — Bidirectional engineering data translation.


#### 📄 `copilot/translation/engine.py` _23.3 KB_
> CAD Translation Engine
======================
Bidirectional translation between ETAP, AutoCAD, Revit, and the Unified Engineering Model.

Mapping Arch

- **Class** `MappingDirection` (line 37)
- **Class** `TranslationEngine` (line 259)
  - Methods: `get_drawing_rule()`, `get_all_mapping_rules()`, `etap_to_unified()`, `unified_to_etap()`, `unified_to_autocad_commands()`, `etap_to_autocad()`, `revit_to_unified()`, `unified_to_revit_commands()`

### 📦 `schemas/`

### 📦 `migrations/`

#### 📄 `migrations/__init__.py` _0.0 KB_

#### 📄 `migrations/env.py` _6.4 KB_
> migrations/env.py — Alembic environment configuration for async migrations.

This module configures Alembic to run migrations asynchronously using
``a

- **def** `run_migrations_online()` (line 84)
- **def** `run_migrations_offline()` (line 149)

#### 📄 `migrations/versions/001_initial_schema.py` _9.9 KB_
> Initial schema — core platform tables.

Revision ID: 001
Revises: —
Create Date: 2025-01-01 00:00:00.000000

This migration creates the foundational t

- **def** `upgrade()` (line 37)
- **def** `downgrade()` (line 392)

#### 📄 `migrations/versions/002_add_indexes_and_constraints.py` _3.6 KB_
> Add performance indexes and check constraints.

Revision ID: 002
Revises: 001
Create Date: 2025-01-02 00:00:00.000000

This migration adds:

* **Compo

- **def** `upgrade()` (line 38)
- **def** `downgrade()` (line 87)

#### 📄 `migrations/versions/003_add_mfa_credentials.py` _2.3 KB_
> Add MFA credentials table.

Revision ID: 003
Revises: 002
Create Date: 2025-01-03 00:00:00.000000

This migration creates the ``mfa_credentials`` tabl

- **def** `upgrade()` (line 37)
- **def** `downgrade()` (line 82)

#### 📄 `migrations/versions/004_add_study_results_composite_index.py` _1.6 KB_
> Add composite index (project_id, created_at DESC) on study_results.

Revision ID: 004
Revises: 003
Create Date: 2025-06-15 00:00:00.000000

This migra

- **def** `upgrade()` (line 33)
- **def** `downgrade()` (line 49)

#### 📄 `migrations/versions/__init__.py` _0.0 KB_

### 📦 `etap_integration/`

#### 📄 `etap_integration/__init__.py` _5.3 KB_
> ETAP Integration Package
========================
Provides ETAP COM automation, provider abstraction, worker service,
error recovery, compatibility ch


#### 📄 `etap_integration/etap_adapter.py` _5.6 KB_
> ETAP Adapter module for the Engineering Service.
Provides a common interface for ETAP integration with optional functionality.

- **Class** `ETAPStudyType` (line 16)
- **Class** `ETAPResult` (line 28)
- **Class** `ETAPAdapter` (line 46)
  - Methods: `is_available()`, `execute_study()`
- **Class** `ETAPProviderAdapter` (line 62)
  - Methods: `is_available()`, `execute_study()`
- **Class** `MockETAPAdapter` (line 121)
  - Methods: `is_available()`, `execute_study()`
- **def** `get_etap_adapter()` (line 165)
- **def** `get_etap_provider()` (line 177)

#### 📄 `etap_integration/etap_com.py` _57.0 KB_
> ETAP COM Automation Interface
==============================
Provides direct integration with ETAP Power System software via COM automation.

Requirem

- **Class** `ETAPStudyType` (line 90)
- **Class** `ETAPResult` (line 241)
- **Class** `ETAPProject` (line 252)
  - Methods: `run_study()`, `get_bus_data()`, `get_all_buses()`, `save()`, `close()`
- **Class** `ETAPAutomation` (line 923)
  - Methods: `add_allowed_project_directory()`, `launch()`, `open_project()`, `create_project()`, `get_active_project()`, `close_project()`, `close_all_projects()`, `shutdown()`
- **def** `run_etap_study()` (line 1480)

#### 📄 `etap_integration/etap_compatibility.py` _10.3 KB_
> ETAP Compatibility Checker
==========================
Verifies that the runtime environment meets ETAP software requirements,
including ETAP version, 

- **Class** `CheckResult` (line 66)
- **Class** `CompatibilityReport` (line 74)
- **Class** `ETAPCompatibilityChecker` (line 93)
  - Methods: `check_version()`, `is_version_supported()`, `get_supported_versions()`, `check_module_availability()`, `check_windows_version()`, `check_dependencies()`, `check_dotnet_version()`, `run_compatibility_tests()`

#### 📄 `etap_integration/etap_error_recovery.py` _14.1 KB_
> ETAP Error Recovery
===================
Provides ETAP-specific error classification and recovery strategies
for COM automation failures, study executi

- **Class** `ErrorCategory` (line 51)
- **Class** `ErrorDiagnosis` (line 62)
- **Class** `RecoveryAttempt` (line 71)
- **Class** `ETAPErrorRecovery` (line 78)
  - Methods: `recover_from_com_error()`, `recover_from_study_error()`, `recover_from_project_error()`, `auto_restart_etap()`, `is_etap_responsive()`, `get_error_diagnosis()`, `recovery_count()`, `successful_recoveries()`

#### 📄 `etap_integration/etap_provider.py` _17.4 KB_
> ETAP Provider Interface
=======================
Abstracts the ETAP execution layer to support both local COM (Windows)
and remote API-based (Linux) ex

- **Class** `ETAPStudyType` (line 21)
- **Class** `ETAPResult` (line 31)
- **Class** `IEtapProvider` (line 47)
  - Methods: `execute_study()`, `is_available()`
- **Class** `LocalEtapProvider` (line 70)
  - Methods: `is_available()`, `execute_study()`
- **Class** `RemoteEtapProvider` (line 133)
  - Methods: `is_available()`, `execute_study()`
- **Class** `MockEtapProvider` (line 272)
  - Methods: `is_available()`, `execute_study()`
- **Class** `NullEtapProvider` (line 451)
  - Methods: `is_available()`, `execute_study()`
- **def** `get_etap_provider()` (line 478)

#### 📄 `etap_integration/etap_worker_service.py` _5.9 KB_
> Windows ETAP Worker Service
===========================
A FastAPI service to be run on Windows hosts with ETAP installed.
Provides a REST API for the 

- **Class** `StudyRequest` (line 76)
- **Class** `StudyResponse` (line 83)
- **async def** `health_check()` (line 92)
- **async def** `execute_study()` (line 103)

#### 📄 `etap_integration/scada_client.py` _12.9 KB_
> AhmedETAP Platform — SCADA Client (IEC 61850)
=============================================

Provides real-time SCADA data ingestion via IEC 61850 pro

- **Class** `SCADAReading` (line 56)
- **Class** `SCADATelemetry` (line 67)
- **Class** `SimulatedSCADA` (line 113)
  - Methods: `generate_telemetry()`
- **Class** `SCADAClient` (line 194)
  - Methods: `get_live_data()`, `is_connected()`, `source()`, `last_telemetry()`
- **async def** `stream_scada_data()` (line 366)

#### 📄 `etap_integration/sync_engine.py` _20.3 KB_
> ETAP ↔ AhmedETAP Synchronization Engine
=========================================
Bidirectional synchronization between ETAP projects and the AhmedETA

- **Class** `SyncMapping` (line 40)
- **Class** `SyncOperation` (line 51)
- **Class** `ETAPSyncEngine` (line 64)
  - Methods: `import_from_etap()`, `export_to_etap()`, `run_full_sync()`, `get_sync_log()`, `get_statistics()`

### 📦 `core_model/`

#### 📄 `core_model/__init__.py` _0.3 KB_

#### 📄 `core_model/bus.py` _2.2 KB_
- **Class** `Bus` (line 4)
  - Methods: `voltage()`, `voltage()`

#### 📄 `core_model/generator.py` _2.9 KB_
- **Class** `Generator` (line 1)
  - Methods: `get_internal_voltage()`, `get_impedance()`

#### 📄 `core_model/line.py` _2.8 KB_
- **Class** `Line` (line 1)
  - Methods: `get_impedance()`, `get_shunt_admittance()`

#### 📄 `core_model/load.py` _2.3 KB_
- **Class** `Load` (line 1)
  - Methods: `get_impedance()`

#### 📄 `core_model/motor_model.py` _10.2 KB_
> Induction Motor Model for Power System Analysis

Supports:
- Motor starting current calculation
- Locked rotor current
- Acceleration time estimation


- **Class** `MotorParameters` (line 22)
- **Class** `MotorModel` (line 52)
  - Methods: `full_load_current()`, `starting_current()`, `starting_current_pu()`, `locked_rotor_current_pu()`, `running_current_pu()`, `acceleration_time()`, `voltage_dip_contribution()`, `short_circuit_contribution()`

#### 📄 `core_model/system.py` _7.1 KB_
- **Class** `System` (line 4)
  - Methods: `add_bus()`, `add_line()`, `add_transformer()`, `add_generator()`, `add_load()`, `build_ybus()`, `get_ybus()`, `build_sequence_networks()`

#### 📄 `core_model/transformer.py` _3.1 KB_
- **Class** `Transformer` (line 1)
  - Methods: `get_impedance()`, `get_shunt_admittance()`

#### 📄 `core_model/zip_load.py` _6.3 KB_
> ZIP Load Model for Power System Analysis

Implements the ZIP load model:
P = P0 * (aZ * V^2 + aI * V + aP)
Q = Q0 * (bZ * V^2 + bI * V + bP)

Where:
-

- **Class** `ZIPCoefficients` (line 27)
- **Class** `ZIPLoadModel` (line 63)
  - Methods: `calculate_power()`, `calculate_admittance()`, `get_impedance_component()`, `voltage_sensitivity()`, `to_dict()`, `from_dict()`

### 📦 `scada_model/`

#### 📄 `scada_model/__init__.py` _0.7 KB_
> SCADA Model - Supervisory Control and Data Acquisition data models.

Provides data structures for SCADA measurements, switch devices,
database managem


#### 📄 `scada_model/scada_model.py` _10.6 KB_
> SCADA Data Model - Real-Time Grid State
=========================================
Implements telemetry inputs, breaker status, real-time measurements,

- **Class** `MeasurementType` (line 24)
- **Class** `QualityFlag` (line 37)
- **Class** `Measurement` (line 45)
  - Methods: `is_valid()`, `age_seconds()`, `to_dict()`
- **Class** `SwitchStatus` (line 79)
- **Class** `SwitchDevice` (line 87)
  - Methods: `is_conducting()`, `operate()`, `to_dict()`
- **Class** `SCADADatabase` (line 133)
  - Methods: `add_measurement()`, `get_measurement()`, `get_measurements_for_element()`, `get_measurements_by_type()`, `get_latest_voltage()`, `get_latest_power()`, `get_expired_measurements()`, `clean_expired()`

#### 📄 `scada_model/state_estimation.py` _21.0 KB_
> State Estimation Engine - Weighted Least Squares (WLS) + GNN Enhancement
=======================================================================
Imple

- **Class** `StateEstimationStatus` (line 34)
- **Class** `StateEstimationResult` (line 42)
- **Class** `WLSEstimator` (line 56)
  - Methods: `estimate()`, `check_redundancy()`
- **Class** `GNNStateEstimator` (line 471)
  - Methods: `estimate_with_gnn()`

### 📦 `acp_runtime/`

#### 📄 `acp_runtime/acp/__init__.py` _3.3 KB_
> acp — Agent Communication Protocol (standalone, Python 3.12+).


#### 📄 `acp_runtime/acp/__main__.py` _0.1 KB_
> Allow running ACP as a module: ``python -m acp <command>``.


#### 📄 `acp_runtime/acp/cli.py` _14.4 KB_
> Unified CLI entrypoint for ACP.

Usage::

    python -m acp stdio --handlers myapp.handlers
    python -m acp uds --handlers myapp.handlers --path /tm

- **def** `main()` (line 412)

#### 📄 `acp_runtime/acp/config.py` _5.0 KB_
> ACP configuration file loader.

Supports both YAML and JSON.  Config keys are the same as the CLI flag
names (without leading dashes) so the mapping i

- **def** `env_int()` (line 23)
- **def** `env_bool()` (line 34)
- **def** `load_config()` (line 42)
- **def** `merge_config()` (line 87)

#### 📄 `acp_runtime/acp/errors.py` _2.0 KB_
> AcpError hierarchy.

Every ACP error carries a JSON-RPC 2.0 error code. The codes -32700 to
-32603 are reserved by the JSON-RPC 2.0 spec; ACP defines 

- **Class** `AcpError` (line 24)
  - Methods: `to_wire()`
- **Class** `DeadlineExceeded` (line 50)
- **Class** `CapabilityNotFound` (line 55)
- **Class** `ScopeNotPermitted` (line 60)
- **Class** `HandlerError` (line 65)
- **Class** `AuthenticationRequired` (line 70)
- **Class** `RateLimitExceeded` (line 75)
- **Class** `TransportClosed` (line 80)

#### 📄 `acp_runtime/acp/health.py` _5.6 KB_
> Built-in health & status handler for the ACP runtime.

This module provides a ``HealthHandler`` class that is automatically
registered by the CLI when

- **Class** `HealthHandler` (line 29)
  - Methods: `set_runtime()`, `health()`, `metrics()`, `prometheus()`, `openmetrics()`, `ready()`

#### 📄 `acp_runtime/acp/http_server.py` _5.7 KB_
> Lightweight async HTTP server for health/ready/metrics probes.

Intended for container and Kubernetes environments where a simple HTTP
endpoint is nee

- **async def** `start_http_server()` (line 151)

#### 📄 `acp_runtime/acp/observability/__init__.py` _1.9 KB_
> acp.observability — Tracing, metrics, and structured logging.

The observability layer provides three complementary signals:

    * **Tracing** — requ


#### 📄 `acp_runtime/acp/observability/metrics.py` _16.1 KB_
> Metrics — counters, histograms, gauges, and registry.

Design:
    * ``Counter`` — monotonically increasing value (inc / reset).
    * ``Histogram`` —

- **Class** `Counter` (line 76)
  - Methods: `inc()`, `reset()`, `value()`, `snapshot()`
- **Class** `Histogram` (line 128)
  - Methods: `observe()`, `reset()`, `buckets()`, `snapshot()`
- **Class** `Gauge` (line 218)
  - Methods: `set()`, `inc()`, `dec()`, `reset()`, `value()`, `snapshot()`
- **Class** `MetricsRegistry` (line 294)
  - Methods: `get_or_create_counter()`, `get_or_create_histogram()`, `get_or_create_gauge()`, `snapshot()`
- **Class** `InMemoryMetricsRegistry` (line 417)
  - Methods: `get_or_create_counter()`, `get_or_create_histogram()`, `get_or_create_gauge()`, `snapshot()`, `prometheus()`, `reset_all()`
- **def** `to_prometheus()` (line 385)
- **def** `to_openmetrics()` (line 397)

#### 📄 `acp_runtime/acp/observability/structured_logger.py` _6.5 KB_
> Structured logging — contextual JSON log entries.

Design:
    * ``LogEntry`` is an immutable record of a log event with timestamp,
      level, messa

- **Class** `LogLevel` (line 40)
- **Class** `LogEntry` (line 52)
  - Methods: `to_json()`
- **Class** `StructuredLogger` (line 90)
  - Methods: `with_context()`, `bind()`, `unbind()`, `debug()`, `info()`, `warning()`, `error()`, `critical()`
- **Class** `NullStructuredLogger` (line 155)
  - Methods: `write()`
- **Class** `InMemoryStructuredLogger` (line 165)
  - Methods: `write()`, `entries()`, `clear()`, `filter()`
- **Class** `ConsoleStructuredLogger` (line 199)
  - Methods: `write()`

#### 📄 `acp_runtime/acp/observability/tracer.py` _7.0 KB_
> Tracing — request-scoped spans with trace context propagation.

Design:
    * ``TraceContext`` carries trace_id, span_id, parent_span_id, and a sample

- **Class** `TraceContext` (line 38)
  - Methods: `with_span()`, `from_trace_id()`
- **Class** `Span` (line 72)
  - Methods: `duration_ms()`, `to_json()`
- **Class** `SpanStatus` (line 121)
- **Class** `Tracer` (line 130)
  - Methods: `start_span()`, `finish_span()`, `record_span()`
- **Class** `NullTracer` (line 186)
  - Methods: `record_span()`
- **Class** `InMemoryTracer` (line 196)
  - Methods: `record_span()`, `spans()`, `clear()`, `spans_for_trace()`
- **Class** `JsonTracer` (line 224)
  - Methods: `record_span()`

#### 📄 `acp_runtime/acp/router/__init__.py` _1.0 KB_
> acp.router — JSON-RPC 2.0 dispatch layer.

The router sits between the Transport layer (receives raw dicts) and
the Runtime layer (executes capabiliti


#### 📄 `acp_runtime/acp/router/router.py` _15.3 KB_
> Router — JSON-RPC 2.0 dispatch layer.

Accepts raw Python dicts (already parsed from JSON), validates them as
ACP envelopes, enforces scope-based auth

- **Class** `RouterConfig` (line 58)
- **Class** `Router` (line 102)
  - Methods: `handle()`

#### 📄 `acp_runtime/acp/router/scope.py` _2.0 KB_
> Scope validation — capability-based authorization.

A capability declares zero or more required scopes. A caller declares
the scopes they possess (typ

- **Class** `ScopeValidator` (line 20)
  - Methods: `is_permitted()`
- **def** `check_scope()` (line 48)

#### 📄 `acp_runtime/acp/runtime/__init__.py` _1.4 KB_
> acp.runtime — the async execution engine for ACP.

Public surface:
    AcpRuntime            — main engine
    capability            — decorator for m


#### 📄 `acp_runtime/acp/runtime/cancel.py` _1.7 KB_
> Cancellation helpers.

Thin wrappers over ``anyio.CancelScope``. Most uses are covered by
``enforce_deadline_ms`` (which uses ``move_on_after`` intern

- **async def** `cancellable()` (line 20)
- **def** `is_cancelled_exception()` (line 47)

#### 📄 `acp_runtime/acp/runtime/deadline.py` _2.3 KB_
> Deadline enforcement — wraps a coroutine with a hard timeout.

Built on ``anyio.move_on_after`` so it works on both asyncio and trio.
Cancellation is 

- **async def** `enforce_deadline_ms()` (line 22)
- **async def** `deadline_scope()` (line 62)

#### 📄 `acp_runtime/acp/runtime/engine.py` _9.5 KB_
> AcpRuntime — the main async execution engine.

Responsibilities:
    * Build a frozen capability registry from a list of handlers.
    * Dispatch an i

- **Class** `AcpRuntime` (line 47)
  - Methods: `capability_names()`, `get_meta()`, `execute()`, `handler_count()`, `stats()`

#### 📄 `acp_runtime/acp/runtime/handler.py` _3.6 KB_
> @capability decorator, AcpHandler Protocol, and capability discovery.

A *handler* is any object with one or more methods decorated with
``@capability

- **Class** `CapabilityMeta` (line 37)
- **Class** `AcpHandler` (line 46)
- **def** `capability()` (line 53)
- **def** `discover_capabilities()` (line 91)
- **def** `list_capabilities()` (line 114)

#### 📄 `acp_runtime/acp/runtime/progress.py` _3.6 KB_
> ProgressEmitter — fire-and-forget progress notifications.

Handlers that do long-running work can call ``emitter.emit(...)`` to
push a progress event 

- **Class** `ProgressEvent` (line 19)
  - Methods: `to_envelope()`, `from_envelope()`
- **Class** `ProgressEmitter` (line 56)
  - Methods: `trace_id()`, `events()`, `emit()`

#### 📄 `acp_runtime/acp/schema/__init__.py` _1.1 KB_
> acp.schema — pydantic v2 models for the ACP wire format.

Public surface:
    CapabilityDescriptor   — frozen, validated capability name + scopes
    


#### 📄 `acp_runtime/acp/schema/capability.py` _1.6 KB_
> CapabilityDescriptor — wire-safe representation of a callable capability.

Used for discovery, manifests, and registry introspection. The internal
``@

- **Class** `CapabilityDescriptor` (line 30)
- **def** `is_valid_capability_name()` (line 22)
- **def** `is_valid_scope()` (line 26)

#### 📄 `acp_runtime/acp/schema/envelope.py` _3.5 KB_
> JSON-RPC 2.0 envelope schemas — Request, Response, Notification, Error.

All models are frozen (immutable), extra=forbid, and validated at
constructio

- **Class** `JsonRpcError` (line 32)
- **Class** `JsonRpcRequest` (line 45)
- **Class** `JsonRpcResponse` (line 68)
- **Class** `JsonRpcNotification` (line 94)

#### 📄 `acp_runtime/acp/schema/ids.py` _0.9 KB_
> Typed identifier aliases.

These are validated identifiers used as ``id`` (request) and ``trace_id``
(progress / audit correlation). Using ``Annotated


#### 📄 `acp_runtime/acp/schema/params.py` _1.5 KB_
> ACP params / result base models.

These are the strongly-typed, domain-specific wrappers that sit inside
``JsonRpcRequest.params`` and ``JsonRpcRespon

- **Class** `AcpParams` (line 19)
- **Class** `AcpResult` (line 35)

#### 📄 `acp_runtime/acp/security/__init__.py` _1.3 KB_
> acp.security — Authentication, authorization, and audit logging.

The security layer sits between the Transport layer and the Router layer.
It provide


#### 📄 `acp_runtime/acp/security/audit.py` _6.4 KB_
> Audit logging — append-only, structured, and async-safe.

Every audit entry is a single line of JSON (NDJSON) written to a file.
The logger is designe

- **Class** `AuditEntry` (line 37)
  - Methods: `to_json()`
- **Class** `AuditLogger` (line 70)
  - Methods: `log()`, `write()`, `close()`
- **Class** `InMemoryAuditLogger` (line 114)
  - Methods: `write()`, `entries()`, `clear()`
- **Class** `NDJSONAuditLogger` (line 141)
  - Methods: `write()`, `close()`

#### 📄 `acp_runtime/acp/security/auth.py` _9.7 KB_
> Authentication — token validation and caller identity.

The ACP security layer is intentionally lightweight and pluggable. It
ships with a simple HMAC

- **Class** `CallerIdentity` (line 41)
- **Class** `AuthConfig` (line 71)
- **Class** `HmacTokenValidator` (line 112)
  - Methods: `validate()`, `issue()`
- **def** `validate_bearer_token()` (line 243)
- **def** `extract_token_from_header()` (line 279)

#### 📄 `acp_runtime/acp/transport/__init__.py` _1.1 KB_
> acp.transport — Transport layer adapters.

Provides three transport implementations:
    * StdioTransport      — line-delimited JSON over stdin/stdout


#### 📄 `acp_runtime/acp/transport/base.py` _1.3 KB_
> Transport abstract base class.

All ACP transports implement the same interface so the ``Server``
can drive them uniformly. The transport layer is res

- **Class** `Transport` (line 21)
  - Methods: `read_message()`, `write_message()`, `close()`

#### 📄 `acp_runtime/acp/transport/server.py` _4.0 KB_
> Server — drives a ``Transport`` + ``Router`` event loop.

The server is the glue between the transport layer (framing) and the
router layer (dispatch)

- **Class** `Server` (line 33)
  - Methods: `run()`

#### 📄 `acp_runtime/acp/transport/stdio.py` _2.1 KB_
> Stdio transport — line-delimited JSON over stdin / stdout.

The canonical transport for local editor integration (LSP-style).
Each JSON-RPC message is

- **Class** `StdioTransport` (line 24)
  - Methods: `read_message()`, `write_message()`, `close()`

#### 📄 `acp_runtime/acp/transport/uds.py` _3.7 KB_
> Unix Domain Socket (UDS) transport — line-delimited JSON over UDS.

UDS is the preferred IPC transport for low-latency, same-host agent
communication.

- **Class** `_LineBuffer` (line 29)
  - Methods: `read_line()`
- **Class** `UDSTransport` (line 53)
  - Methods: `read_message()`, `write_message()`, `close()`
- **Class** `UDSListener` (line 95)
  - Methods: `serve()`

#### 📄 `acp_runtime/acp/transport/websocket.py` _3.4 KB_
> WebSocket transport — JSON messages over WebSocket text frames.

The ``WebSocketTransport`` is transport-library-agnostic: it only
requires two async 

- **Class** `WebSocketTransport` (line 38)
  - Methods: `read_message()`, `write_message()`, `close()`
- **Class** `WebSocketListener` (line 75)
  - Methods: `serve()`

#### 📄 `acp_runtime/tests/__init__.py` _0.3 KB_
> Test suite for the ACP (Agent Communication Protocol) runtime engine.

Contains unit and integration tests for the ACP runtime, including
CLI, configu


#### 📄 `acp_runtime/tests/_cli_bad_handler.py` _0.3 KB_
> Helper module for CLI tests — contains a handler class requiring constructor args.

- **Class** `BadHandler` (line 6)
  - Methods: `run()`

#### 📄 `acp_runtime/tests/conftest.py` _0.2 KB_
> Shared pytest fixtures / configuration.

- **def** `anyio_backend()` (line 9)

#### 📄 `acp_runtime/tests/integration_handlers.py` _1.8 KB_
> Real handler module for integration / end-to-end tests.

Provides capabilities covering:
    * Simple arithmetic (math.sum, math.multiply, math.divide

- **Class** `IntegrationHandler` (line 17)
  - Methods: `sum()`, `multiply()`, `divide()`, `progress()`, `echo()`, `stats()`, `raise_error()`

#### 📄 `acp_runtime/tests/test_cancellation.py` _5.2 KB_
> Tests for cancellation propagation.

Covers:
    * Deadline-exceeded cancellation propagates to the handler.
    * External scope cancellation propaga

- **Class** `Slow` (line 163)
  - Methods: `forever()`
- **async def** `test_cancellation_propagates_into_handler()` (line 25)
- **async def** `test_cancellation_via_external_cancel_scope()` (line 44)
- **async def** `test_handler_that_ignores_cancellation_still_bails()` (line 72)
- **async def** `test_cancellable_with_deadline_fires()` (line 101)
- **async def** `test_cancellable_without_deadline_requires_external_cancel()` (line 116)
- **def** `test_is_cancelled_exception_recognises_asyncio()` (line 141)
- **def** `test_is_cancelled_exception_rejects_runtime_error()` (line 147)
- **async def** `test_engine_does_not_wrap_cancelled_error()` (line 155)

#### 📄 `acp_runtime/tests/test_cli.py` _16.9 KB_
> Tests for the unified CLI entrypoint.

Covers:
    * Argument parsing for stdio, uds, and websocket subcommands
    * Handler loading from a module pa

- **Class** `FakeHandler` (line 36)
  - Methods: `sum()`
- **Class** `TestSplitScopes` (line 45)
  - Methods: `test_empty()`, `test_single()`, `test_multiple()`, `test_whitespace()`
- **Class** `TestEnvInt` (line 61)
  - Methods: `test_default()`, `test_from_env()`, `test_bad_value()`
- **Class** `TestEnvBool` (line 76)
  - Methods: `test_default()`, `test_true_values()`, `test_false_values()`
- **Class** `TestParser` (line 96)
  - Methods: `test_stdio_subcommand()`, `test_uds_subcommand()`, `test_websocket_subcommand()`, `test_common_flags()`, `test_no_command_fails()`
- **Class** `TestLoadHandlers` (line 160)
  - Methods: `test_load_this_module()`, `test_bad_module()`, `test_handler_with_required_args()`, `test_no_capabilities()`
- **Class** `TestBuildRuntime` (line 185)
  - Methods: `test_build_runtime()`, `test_trace_file()`, `test_metrics()`
- **Class** `TestBuildRouter` (line 215)
  - Methods: `test_build_router_basic()`, `test_build_router_with_scopes()`, `test_build_router_with_auth()`, `test_build_router_with_audit()`
- **Class** `TestEnvVarFallback` (line 283)
  - Methods: `test_handlers_from_env()`
- **Class** `TestCliErrors` (line 306)
  - Methods: `test_missing_handlers()`, `test_main_bad_command()`, `test_version_flag()`
- **Class** `TestUdsArgs` (line 326)
  - Methods: `test_uds_args()`
- **Class** `TestWebSocketArgs` (line 336)
  - Methods: `test_websocket_args()`
- **Class** `TestHttpPortFlag` (line 347)
  - Methods: `test_http_port_parsed()`, `test_http_port_with_uds()`, `test_http_port_with_websocket()`
- **Class** `TestMetricsPathFlag` (line 366)
  - Methods: `test_default_metrics_path()`, `test_custom_metrics_path()`, `test_custom_metrics_path_with_uds()`, `test_custom_metrics_path_with_websocket()`
- **Class** `TestDefaultLabelsFlag` (line 394)
  - Methods: `test_default_labels_parsed()`, `test_default_labels_empty()`, `test_parse_labels_helper()`, `test_parse_labels_invalid()`
- **Class** `TestTransportErrorPaths` (line 431)
  - Methods: `test_uds_serve_oserror()`, `test_websocket_serve_import_error()`
- **async def** `test_stdio_transport_start()` (line 258)

#### 📄 `acp_runtime/tests/test_config.py` _10.8 KB_
> Tests for the configuration file loader.

Covers:
    * JSON config loading
    * YAML config loading
    * Missing file error
    * Unknown format er

- **Class** `DummyArgs` (line 23)
- **Class** `TestLoadConfig` (line 34)
  - Methods: `test_load_json()`, `test_load_yaml()`, `test_load_yml_suffix()`, `test_missing_file()`, `test_unknown_format()`, `test_invalid_json()`, `test_invalid_yaml()`, `test_yaml_not_installed()`
- **Class** `TestMergeConfig` (line 115)
  - Methods: `test_cli_takes_precedence()`, `test_config_fills_missing()`, `test_env_takes_precedence_over_config()`, `test_env_int_conversion()`, `test_env_bool_conversion()`, `test_env_int_bad_value()`, `test_config_none()`
- **Class** `TestConfigCliIntegration` (line 271)
  - Methods: `test_cli_with_json_config()`, `test_cli_flag_overrides_config()`, `test_main_with_config()`

#### 📄 `acp_runtime/tests/test_deadline.py` _2.5 KB_
> Tests for ``acp.runtime.deadline.enforce_deadline_ms``.

Covers:
    * completes within deadline → returns result
    * exceeds deadline → raises Dead

- **async def** `test_completes_within_deadline()` (line 21)
- **async def** `test_exceeds_deadline_raises()` (line 31)
- **async def** `test_deadline_data_carries_deadline_ms()` (line 48)
- **def** `test_zero_deadline_raises()` (line 57)
- **def** `test_negative_deadline_raises()` (line 65)
- **def** `test_excessive_deadline_raises()` (line 73)
- **async def** `test_deadline_scope_yields_cancellable_scope()` (line 82)

#### 📄 `acp_runtime/tests/test_engine.py` _6.8 KB_
> Tests for ``AcpRuntime`` — the composition root of the runtime layer.

Covers:
    * successful execution (sync + async handlers)
    * handler except

- **Class** `CalcHandler` (line 24)
  - Methods: `add()`, `div()`, `boom()`, `slow()`
- **Class** `H` (line 63)
  - Methods: `now()`
- **Class** `H1` (line 121)
  - Methods: `x()`
- **Class** `H2` (line 126)
  - Methods: `x()`
- **Class** `H` (line 138)
  - Methods: `z_last()`, `a_first()`
- **Class** `StringHandler` (line 202)
  - Methods: `echo()`
- **Class** `CustomError` (line 224)
- **Class** `H` (line 227)
  - Methods: `go()`
- **async def** `test_execute_async_handler()` (line 48)
- **async def** `test_execute_sync_handler()` (line 55)
- **async def** `test_execute_with_no_input()` (line 62)
- **async def** `test_unknown_capability_raises_capability_not_found()` (line 76)
- **async def** `test_handler_exception_wrapped_in_handler_error()` (line 87)
- **async def** `test_handler_deadline_enforced()` (line 100)
- **async def** `test_handler_does_not_observe_cancellation_on_success()` (line 110)
- **def** `test_duplicate_capability_raises_on_construct()` (line 120)
- **def** `test_capability_names_sorted()` (line 137)
- **def** `test_get_meta_returns_metadata()` (line 151)

#### 📄 `acp_runtime/tests/test_handler.py` _3.2 KB_
> Tests for the @capability decorator and discovery helpers.

- **Class** `MathHandler` (line 15)
  - Methods: `sum()`, `mul()`
- **Class** `MixedHandler` (line 25)
  - Methods: `upper()`, `helper()`
- **def** `test_decorator_attaches_metadata()` (line 35)
- **def** `test_decorator_preserves_functionality()` (line 44)
- **def** `test_discover_capabilities_returns_all_decorated()` (line 55)
- **def** `test_discover_ignores_undecorated_methods()` (line 62)
- **def** `test_list_capabilities_returns_descriptors()` (line 67)
- **def** `test_invalid_capability_name_rejected()` (line 79)
- **def** `test_invalid_scope_rejected()` (line 90)
- **def** `test_empty_scopes_is_allowed()` (line 98)
- **def** `test_capability_meta_is_frozen()` (line 107)
- **def** `test_scopes_can_be_list_or_tuple()` (line 113)

#### 📄 `acp_runtime/tests/test_health.py` _8.6 KB_
> Tests for the built-in health & status handler.

Covers:
    * HealthHandler returns correct shape for system.health
    * Metrics snapshot via system

- **Class** `TestHealthHandler` (line 22)
  - Methods: `test_health_shape()`, `test_health_with_runtime()`, `test_health_uptime_increases()`, `test_metrics_without_registry()`, `test_metrics_with_registry()`, `test_ready_without_runtime()`, `test_ready_with_runtime()`
- **Class** `TestHealthCliIntegration` (line 106)
  - Methods: `test_health_capability_auto_registered()`, `test_no_health_flag()`
- **Class** `DummyHandler` (line 88)
  - Methods: `test()`
- **async def** `test_stdio_health_request()` (line 133)
- **async def** `test_stdio_metrics_request()` (line 171)
- **async def** `test_stdio_ready_request()` (line 206)

#### 📄 `acp_runtime/tests/test_http_server.py` _11.6 KB_
> Tests for the lightweight HTTP health server.

Covers:
    * GET /health returns the system.health JSON
    * GET /ready returns the system.ready JSON

- **async def** `test_http_health_endpoint()` (line 71)
- **async def** `test_http_ready_endpoint()` (line 90)
- **async def** `test_http_ready_with_runtime()` (line 107)
- **async def** `test_http_metrics_endpoint_empty()` (line 131)
- **async def** `test_http_metrics_prometheus_format()` (line 147)
- **async def** `test_http_metrics_custom_path()` (line 189)
- **async def** `test_http_metrics_default_labels()` (line 216)
- **async def** `test_http_metrics_openmetrics_format()` (line 239)
- **async def** `test_http_404()` (line 275)
- **async def** `test_http_405()` (line 291)

#### 📄 `acp_runtime/tests/test_integration.py` _25.1 KB_
> Phase H — Comprehensive integration test suite.

Runs all transport adapters end-to-end with real handler modules:
    * StdioTransport  → StringIO-ba

- **Class** `TestStdioIntegration` (line 112)
  - Methods: `test_stdio_request_response()`, `test_stdio_multiple_requests()`, `test_stdio_notification_no_response()`, `test_stdio_parse_error()`, `test_stdio_invalid_jsonrpc_envelope()`, `test_stdio_scope_denied()`, `test_stdio_auth_valid_token()`, `test_stdio_auth_invalid_token()`
- **Class** `TestUdsIntegration` (line 379)
  - Methods: `test_uds_request_response()`, `test_uds_multiple_requests()`, `test_uds_auth()`
- **Class** `TestWebSocketIntegration` (line 511)
  - Methods: `ws_port()`, `test_websocket_request_response()`, `test_websocket_auth()`
- **Class** `TestCrossCutting` (line 605)
  - Methods: `test_metrics_counters_incremented()`, `test_audit_log_format()`, `test_division_by_zero_error()`, `test_public_capability_without_auth()`, `test_require_auth_blocks_public()`, `test_progress_capability_no_emitter()`, `test_cancellation()`
- **def** `uds_path()` (line 374)

#### 📄 `acp_runtime/tests/test_metrics_prometheus.py` _16.8 KB_
> Unit tests for the Prometheus text format rendering in metrics.py.

Covers:
    * Counter formatting (HELP, TYPE, value)
    * Gauge formatting
    * 

- **Class** `TestValidateLabelName` (line 26)
  - Methods: `test_valid_names()`, `test_empty_name()`, `test_starting_with_digit()`, `test_containing_dot()`, `test_containing_dash()`, `test_containing_space()`, `test_containing_special_char()`, `test_validate_labels_with_invalid_key()`
- **Class** `TestMetricLabelValidationIntegration` (line 73)
  - Methods: `test_counter_rejects_invalid_label()`, `test_gauge_rejects_invalid_label()`, `test_histogram_rejects_invalid_label()`, `test_registry_rejects_invalid_default_labels()`, `test_non_ascii_first_char_rejected()`
- **Class** `TestLabelsKey` (line 108)
  - Methods: `test_empty_labels()`, `test_consistency()`, `test_distinct_keys()`
- **Class** `TestFormatLabels` (line 122)
  - Methods: `test_empty()`, `test_single()`, `test_multiple_sorted()`, `test_escapes_quotes()`, `test_escapes_backslash()`
- **Class** `TestDefaultLabels` (line 139)
  - Methods: `test_registry_default_labels()`, `test_registry_default_labels_overridden()`, `test_registry_default_labels_prometheus()`, `test_registry_default_labels_histogram()`
- **Class** `TestSanitizeMetricName` (line 174)
  - Methods: `test_dot_to_underscore()`, `test_dash_to_underscore()`, `test_invalid_chars_removed()`, `test_leading_digit_underscore()`, `test_empty_name()`
- **Class** `TestToPrometheus` (line 191)
  - Methods: `test_counter()`, `test_gauge()`, `test_histogram()`, `test_multiple_metrics()`, `test_empty_snapshot()`, `test_no_description()`, `test_counter_with_labels()`, `test_histogram_with_labels()`
- **Class** `TestToOpenMetrics` (line 384)
  - Methods: `test_counter()`, `test_gauge()`, `test_histogram_cumulative()`, `test_empty_snapshot()`, `test_eof_is_last_line()`

#### 📄 `acp_runtime/tests/test_observability.py` _15.7 KB_
> Tests for the observability layer — tracing, metrics, and structured logging.

Covers:
    * TraceContext creation, parent-child, from_trace_id
    * 

- **Class** `MathHandler` (line 53)
  - Methods: `sum()`, `boom()`
- **Class** `TestTraceContext` (line 67)
  - Methods: `test_default()`, `test_from_trace_id()`, `test_with_span()`, `test_immutable()`
- **Class** `TestSpan` (line 96)
  - Methods: `test_duration_ms()`, `test_to_json()`
- **Class** `TestInMemoryTracer` (line 130)
  - Methods: `test_record_and_retrieve()`, `test_spans_for_trace()`, `test_clear()`
- **Class** `TestNullTracer` (line 155)
  - Methods: `test_no_op()`
- **Class** `TestCounter` (line 166)
  - Methods: `test_inc_and_value()`, `test_reset()`, `test_snapshot()`
- **Class** `TestHistogram` (line 188)
  - Methods: `test_observe()`, `test_default_buckets()`, `test_reset()`
- **Class** `TestGauge` (line 216)
  - Methods: `test_set_inc_dec()`, `test_reset()`
- **Class** `TestInMemoryMetricsRegistry` (line 231)
  - Methods: `test_get_or_create()`, `test_reset_all()`
- **Class** `TestLogEntry` (line 261)
  - Methods: `test_to_json()`
- **Class** `TestInMemoryStructuredLogger` (line 277)
  - Methods: `test_log_levels()`, `test_filter()`, `test_with_context()`, `test_clear()`
- **Class** `TestNullStructuredLogger` (line 313)
  - Methods: `test_no_op()`
- **Class** `TestConsoleStructuredLogger` (line 320)
  - Methods: `test_min_level()`
- **async def** `test_runtime_metrics_on_success()` (line 338)
- **async def** `test_runtime_metrics_on_error()` (line 348)
- **async def** `test_runtime_tracer_on_success()` (line 359)
- **async def** `test_runtime_tracer_on_error()` (line 369)
- **async def** `test_runtime_no_observability()` (line 379)
- **async def** `test_router_metrics_on_request()` (line 389)
- **async def** `test_router_metrics_on_error()` (line 415)
- **async def** `test_router_tracer_on_request()` (line 440)
- **async def** `test_router_invalid_envelope_metrics()` (line 466)
- **async def** `test_server_metrics()` (line 486)

#### 📄 `acp_runtime/tests/test_router.py` _11.9 KB_
> Tests for the router layer — JSON-RPC dispatch, scope validation, error mapping.

Covers:
    * Successful request dispatch (async + sync handlers)
  

- **Class** `MathHandler` (line 29)
  - Methods: `sum()`, `div()`, `identity()`, `slow()`, `boom()`
- **Class** `StringHandler` (line 53)
  - Methods: `echo()`
- **Class** `TestScopeValidator` (line 295)
  - Methods: `test_no_required_scopes_always_permitted()`, `test_exact_match()`, `test_partial_match()`, `test_no_match()`, `test_empty_caller_scopes()`, `test_invalid_scope_rejected()`, `test_check_scope_functional()`, `test_repr()`
- **Class** `TestResponseStructure` (line 335)
  - Methods: `test_success_response_has_all_fields()`, `test_error_response_has_all_fields()`
- **async def** `test_dispatch_async_handler()` (line 73)
- **async def** `test_dispatch_sync_handler()` (line 92)
- **async def** `test_dispatch_public_capability_no_scopes()` (line 110)
- **async def** `test_dispatch_with_trace_id_and_deadline()` (line 127)
- **async def** `test_unknown_capability()` (line 149)
- **async def** `test_scope_not_permitted()` (line 169)
- **async def** `test_handler_exception()` (line 188)
- **async def** `test_deadline_exceeded()` (line 208)
- **async def** `test_params_as_list_rejected()` (line 228)
- **async def** `test_invalid_envelope()` (line 247)

#### 📄 `acp_runtime/tests/test_schema.py` _12.0 KB_
> Phase A — JSON roundtrip tests for ACP schema layer.

Every model in ``acp.schema`` must survive:
    1. Construction from Python values
    2. ``mode

- **Class** `TestJsonRpcRequest` (line 55)
  - Methods: `test_minimal_request()`, `test_full_request_with_params()`, `test_request_with_int_id()`, `test_request_with_list_params()`, `test_invalid_jsonrpc_version()`, `test_extra_field_rejected()`, `test_missing_required_fields()`, `test_deadline_ms_bounds()`
- **Class** `TestJsonRpcResponse` (line 119)
  - Methods: `test_success_response()`, `test_error_response()`, `test_both_result_and_error_rejected()`, `test_neither_result_nor_error_rejected()`, `test_response_with_none_id()`, `test_response_with_int_id()`, `test_error_json_roundtrip()`
- **Class** `TestJsonRpcNotification` (line 166)
  - Methods: `test_minimal_notification()`, `test_full_notification()`, `test_notification_with_list_params()`, `test_extra_field_rejected()`, `test_notification_deadline_ms_bounds()`
- **Class** `TestAcpParams` (line 209)
  - Methods: `test_minimal_params()`, `test_full_params()`, `test_invalid_deadline()`, `test_extra_field_rejected()`
- **Class** `TestAcpResult` (line 232)
  - Methods: `test_minimal_result()`, `test_result_with_output()`, `test_extra_field_rejected()`
- **Class** `TestCapabilityDescriptor` (line 252)
  - Methods: `test_roundtrip()`, `test_invalid_name()`, `test_invalid_scope()`
- **Class** `TestProgressEvent` (line 273)
  - Methods: `test_envelope_roundtrip()`, `test_default_message()`, `test_json_string_roundtrip()`
- **Class** `TestRequestParamsIntegration` (line 303)
  - Methods: `test_request_params_nested_roundtrip()`, `test_response_result_nested_roundtrip()`
- **Class** `TestErrorFromException` (line 333)
  - Methods: `test_error_from_acp_exception()`

#### 📄 `acp_runtime/tests/test_security.py` _18.5 KB_
> Tests for the security layer — authentication, audit logging, and router integration.

Covers:
    * HMAC token issuance and validation (valid, expire

- **Class** `MathHandler` (line 42)
  - Methods: `sum()`, `identity()`
- **Class** `TestHmacTokenValidator` (line 56)
  - Methods: `test_issue_and_validate()`, `test_expired_token_rejected()`, `test_bad_signature_rejected()`, `test_malformed_token_rejected()`, `test_issuer_mismatch()`, `test_audience_mismatch()`, `test_custom_claims_preserved()`, `test_empty_scopes_allowed()`
- **Class** `TestCallerIdentity` (line 135)
  - Methods: `test_repr()`, `test_empty_defaults()`
- **Class** `TestHeaderHelpers` (line 152)
  - Methods: `test_extract_bearer_token()`, `test_validate_bearer_token_with_validator()`, `test_validate_bearer_token_no_validator()`, `test_validate_bearer_token_missing_header()`, `test_validate_bearer_token_bad_format()`
- **Class** `TestAuditEntry` (line 182)
  - Methods: `test_to_json()`
- **async def** `test_in_memory_audit_logger()` (line 208)
- **async def** `test_in_memory_audit_logger_clear()` (line 231)
- **async def** `test_in_memory_audit_logger_thread_safety()` (line 239)
- **async def** `test_ndjson_audit_logger()` (line 261)
- **async def** `test_router_with_valid_auth()` (line 284)
- **async def** `test_router_with_invalid_auth()` (line 314)
- **async def** `test_router_auth_missing_token()` (line 343)
- **async def** `test_router_no_auth_bypass()` (line 371)
- **async def** `test_router_require_auth_for_public()` (line 396)
- **async def** `test_router_auth_with_scope_merge()` (line 443)

#### 📄 `acp_runtime/tests/test_transport.py` _14.2 KB_
> Tests for the transport layer — stdio, UDS, WebSocket, and Server.

Covers:
    * StdioTransport read/write with memory streams
    * UDSTransport rea

- **Class** `MathHandler` (line 33)
  - Methods: `sum()`, `identity()`
- **Class** `FakeByteStream` (line 47)
  - Methods: `receive()`, `send()`, `aclose()`
- **Class** `TestStdioTransport` (line 77)
  - Methods: `test_read_message()`, `test_read_eof()`, `test_write_message()`, `test_read_strips_trailing_newline_only()`, `test_read_after_close()`, `test_write_after_close()`
- **Class** `TestLineBuffer` (line 132)
  - Methods: `test_read_line_single()`, `test_read_line_empty()`, `test_read_line_no_newline()`
- **Class** `TestUDSTransport` (line 150)
  - Methods: `test_read_message()`, `test_read_eof()`, `test_write_message()`, `test_read_after_close()`, `test_write_after_close()`
- **Class** `TestWebSocketTransport` (line 193)
  - Methods: `test_read_message()`, `test_read_eof()`, `test_write_message()`, `test_read_after_close()`, `test_write_after_close()`
- **Class** `TestServer` (line 270)
  - Methods: `test_server_request_response()`, `test_server_notification_no_response()`, `test_server_parse_error()`, `test_server_eof()`, `test_server_multiple_requests()`, `test_server_scope_denied()`, `test_server_invalid_jsonrpc_envelope()`, `test_server_concurrent_writes()`
- **async def** `test_end_to_end_stdio()` (line 462)

---

## 🌐 All API Endpoints

| Method | Path | File |
|:---|:---|:---|
| 🟢 `GET` | `/` | `api/health.py` |
| 🟢 `GET` | `/` | `api/refactored_service.py` |
| 🟢 `GET` | `/api/v1/agents/info` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/auth/abac/check` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/auth/mfa/totp/setup` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/auth/mfa/totp/verify` | `api/refactored_service.py` |
| 🟢 `GET` | `/api/v1/benchmark` | `api/refactored_service.py` |
| 🟢 `GET` | `/api/v1/digital-twin/status` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/predict/anomaly` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/predict/fault` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/predict/load` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/rag/query` | `api/refactored_service.py` |
| 🟢 `GET` | `/api/v1/scada/live` | `api/refactored_service.py` |
| 🟢 `GET` | `/api/v1/security/rasp/stats` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/security/siem/event` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/studies/run` | `api/refactored_service.py` |
| 🔵 `POST` | `/api/v1/studies/run` | `api/routes.py` |
| 🔵 `POST` | `/api/v1/system/validate` | `api/refactored_service.py` |
| 🔵 `POST` | `/etap-expert/chat` | `api/agents.py` |
| 🔵 `POST` | `/etap-gui/chat` | `api/agents.py` |
| 🔵 `POST` | `/gnn/predict` | `api/ai_ml.py` |
| 🟢 `GET` | `/health` | `api/health.py` |
| 🟢 `GET` | `/health` | `api/refactored_service.py` |
| 🟢 `GET` | `/health` | `api/routes.py` |
| 🟢 `GET` | `/healthz` | `api/health.py` |
| 🟢 `GET` | `/healthz` | `api/refactored_service.py` |
| 🟢 `GET` | `/info` | `api/agents.py` |
| 🟢 `GET` | `/live` | `api/scada.py` |
| 🟢 `GET` | `/me` | `api/dependencies.py` |
| 🟢 `GET` | `/metrics` | `api/health.py` |
| 🟢 `GET` | `/metrics` | `api/refactored_service.py` |
| 🟢 `GET` | `/metrics` | `api/routes.py` |
| 🟢 `GET` | `/ml/capabilities` | `api/ai_ml.py` |
| 🔵 `POST` | `/predict/anomaly` | `api/ai_ml.py` |
| 🔵 `POST` | `/predict/fault` | `api/ai_ml.py` |
| 🔵 `POST` | `/predict/fault/train` | `api/ai_ml.py` |
| 🔵 `POST` | `/predict/load` | `api/ai_ml.py` |
| 🟢 `GET` | `/prometheus/metrics` | `api/health.py` |
| 🟢 `GET` | `/prometheus/metrics` | `api/routes.py` |
| 🔵 `POST` | `/rag/query` | `api/ai_ml.py` |
| 🟢 `GET` | `/ready` | `api/health.py` |
| 🟢 `GET` | `/ready` | `api/refactored_service.py` |
| 🟢 `GET` | `/ready` | `api/routes.py` |
| 🟢 `GET` | `/readyz` | `api/health.py` |
| 🟢 `GET` | `/readyz` | `api/refactored_service.py` |
| 🔵 `POST` | `/run` | `api/studies.py` |
| 🟢 `GET` | `/status` | `api/digital_twin.py` |
| 🔵 `POST` | `/totp/setup` | `api/mfa.py` |
| 🔵 `POST` | `/totp/verify` | `api/mfa.py` |
| 🔴 `DELETE` | `/users/{user_id}` | `api/dependencies.py` |
| 🔵 `POST` | `/validate` | `api/validation.py` |

---

## ⚛️ UI Components & Pages

### 🖥️ `pages/`
- `AIAssistant.tsx` → Exports: `AIAssistant`
- `Administration.tsx` → Exports: `Administration`
- `AssetManagement.tsx` → Exports: `AssetManagement`
- `CodeGuard.tsx` → Exports: `CodeGuard`
- `Dashboard.tsx` → Exports: `Dashboard`
- `DataExport.tsx` → Exports: `DataExport`
- `DataImport.tsx` → Exports: `DataImport`
- `Diagnostics.tsx` → Exports: `Diagnostics`
- `DigitalTwin.tsx` → Exports: `DigitalTwin`
- `EtapIntegration.tsx` → Exports: `EtapIntegration`
- `GisIntegration.tsx` → Exports: `GisIntegration`
- `Logs.tsx` → Exports: `Logs`
- `Projects.tsx` → Exports: `Projects`
- `Reports.tsx` → Exports: `Reports`
- `Settings.tsx` → Exports: `Settings`
- `Studies.tsx` → Exports: `Studies`
- `StudyRun.tsx` → Exports: `StudyRun`
- `Dashboard.test.tsx` → Exports: _none_

### 🖥️ `components/`
- `Breadcrumbs.tsx` → Exports: `Breadcrumbs`
- `ErrorBoundary.tsx` → Exports: `ErrorBoundary`
- `Layout.tsx` → Exports: `Layout`
- `Navbar.tsx` → Exports: `Navbar`
- `Sidebar.tsx` → Exports: `Sidebar`
- `TitleBar.tsx` → Exports: `TitleBar`
- `CommandPalette.tsx` → Exports: `CommandPalette`
- `ContextPanel.tsx` → Exports: `ContextPanel`
- `ErrorRecovery.tsx` → Exports: `ErrorRecovery`, `useErrorRecovery`
- `ContextHelpButton.tsx` → Exports: `ContextHelpButton`
- `SmartHelpDrawer.tsx` → Exports: `SmartHelpDrawer`
- `AppShell.tsx` → Exports: `AppShell`
- `EngineeringWorkspace.tsx` → Exports: `EngineeringWorkspace`
- `Sidebar.tsx` → Exports: `Sidebar`
- `StatusBar.tsx` → Exports: `StatusBar`
- `TopBar.tsx` → Exports: `TopBar`
- `OnboardingTour.tsx` → Exports: `OnboardingTour`
- `Badge.tsx` → Exports: `Badge`
- `Button.tsx` → Exports: `Button`
- `Card.tsx` → Exports: `Card`, `CardHeader`, `CardSection`
- `EmptyState.tsx` → Exports: `EmptyState`
- `Modal.tsx` → Exports: `Modal`
- `Skeleton.tsx` → Exports: `Skeleton`, `SkeletonCard`, `SkeletonTable`
- `Tabs.tsx` → Exports: `Tabs`, `TabPanels`, `useTabState`
- `Toggle.tsx` → Exports: `Toggle`
- `Visual.tsx` → Exports: `GlassPanel`, `AnimatedBackground`, `StatusIndicator`, `PremiumEmptyState`, `PremiumLoading`, `GradientText`, `GlowCard`
- `index.ts` → Exports: _none_

### 🖥️ `hooks/`
- `useSmartHelp.ts` → Exports: `useSmartHelp`

### 🖥️ `store/`
- `index.ts` → Exports: `useAppStore`

### 🖥️ `context/`
- `NotificationContext.tsx` → Exports: `NotificationProvider`, `useNotify`
- `ThemeContext.tsx` → Exports: `ThemeProvider`, `useTheme`

### 🖥️ `utils/`
- `helpers.ts` → Exports: `cn`, `formatNumber`, `formatDate`, `formatDuration`, `generateId`

---

## 🧪 Test Suite

| Test File | Test Functions | Test Classes | Total |
|:---|---:|---:|---:|
| `test_app_startup.py` | 6 | 0 | **6** |
| `test_arc_flash_single_engine.py` | 0 | 3 | **8** |
| `test_auth_api.py` | 0 | 11 | **36** |
| `test_backend_request_context.py` | 0 | 1 | **6** |
| `test_backward_compatibility.py` | 7 | 0 | **7** |
| `test_cache_service.py` | 7 | 0 | **7** |
| `test_caching.py` | 0 | 2 | **21** |
| `test_coordination.py` | 0 | 1 | **18** |
| `test_core_database.py` | 0 | 11 | **30** |
| `test_core_models.py` | 0 | 6 | **24** |
| `test_digital_twin_sync.py` | 14 | 0 | **14** |
| `test_edge_cases.py` | 0 | 7 | **31** |
| `test_engineering_service.py` | 0 | 6 | **16** |
| `test_etap_expert_proof.py` | 33 | 0 | **33** |
| `test_etap_expert_skill.py` | 27 | 0 | **27** |
| `test_etap_gui_agent.py` | 36 | 0 | **36** |
| `test_gis_integration.py` | 17 | 0 | **17** |
| `test_gis_validation.py` | 0 | 6 | **30** |
| `test_guards.py` | 50 | 0 | **50** |
| `test_hf_space_production.py` | 12 | 0 | **12** |
| `test_hf_space_skill.py` | 14 | 0 | **14** |
| `test_integration_factories.py` | 0 | 4 | **10** |
| `test_integration_metrics.py` | 0 | 3 | **13** |
| `test_integration_tracing.py` | 0 | 3 | **8** |
| `test_knowledge.py` | 0 | 1 | **15** |
| `test_ml.py` | 0 | 3 | **22** |
| `test_network_solver.py` | 0 | 2 | **30** |
| `test_new_agents.py` | 0 | 6 | **26** |
| `test_projects_api.py` | 0 | 7 | **28** |
| `test_prompt_integration.py` | 0 | 3 | **20** |
| `test_rasp_security.py` | 0 | 4 | **20** |
| `test_relays.py` | 0 | 5 | **50** |
| `test_reporting.py` | 0 | 6 | **31** |
| `test_scada_state_estimation.py` | 0 | 4 | **44** |
| `test_security_e2e.py` | 0 | 10 | **39** |
| `test_security_hardening.py` | 0 | 3 | **25** |
| `test_sparse_solver.py` | 0 | 1 | **10** |
| `test_study_service.py` | 5 | 0 | **5** |
| `test_visualization.py` | 0 | 5 | **23** |
| `test_api_endpoints.py` | 12 | 0 | **12** |
| `test_retry_behavior.py` | 11 | 0 | **11** |
| `test_skill_loading.py` | 7 | 0 | **7** |
| `test_calculations_regression.py` | 6 | 0 | **6** |
| `test_arc_flash_scenario.py` | 0 | 1 | **6** |
| `test_battery_storage_scenario.py` | 0 | 1 | **6** |
| `test_cable_sizing_scenario.py` | 0 | 1 | **7** |
| `test_earth_grid_scenario.py` | 0 | 1 | **6** |
| `test_etap_execution_scenario.py` | 0 | 1 | **6** |
| `test_harmonic_scenario.py` | 0 | 1 | **6** |
| `test_load_flow_scenario.py` | 0 | 1 | **6** |
| `test_opf_scenario.py` | 0 | 1 | **6** |
| `test_protection_scenario.py` | 0 | 1 | **6** |
| `test_renewable_scenario.py` | 0 | 1 | **6** |
| `test_report_scenario.py` | 0 | 1 | **6** |
| `test_scada_scenario.py` | 0 | 1 | **6** |
| `test_short_circuit_scenario.py` | 0 | 1 | **6** |
| `test_stability_scenario.py` | 0 | 1 | **6** |
| `test_validation_scenario.py` | 0 | 1 | **6** |

---

## 🏗️ Infrastructure Files

| File | Size | Hash |
|:---|---:|:---|
| `Dockerfile` | 3.2 KB | `8287337831c5` |
| `Dockerfile.engineering-service` | 4.4 KB | `a85e704ca393` |
| `Dockerfile.hf` | 2.5 KB | `1c682fbfd145` |
| `docker-compose.yml` | 2.3 KB | `613be91434fb` |
| `docker-compose.monitoring.yml` | 8.7 KB | `d00866419cef` |
| `docker-compose.copilot.yml` | 7.4 KB | `042ce6111c73` |
| `pyproject.toml` | 4.2 KB | `720f061080e5` |
| `requirements.txt` | 3.0 KB | `ecaffb4332c7` |
| `requirements-prod.txt` | 1.4 KB | `85d327d39516` |
| `requirements-dev.txt` | 0.3 KB | `b01e6554da26` |
| `.github/workflows/ci-cd.yml` | 5.4 KB | `8861afd81014` |
| `.github/workflows/security.yml` | 5.4 KB | `51b189bbe9d1` |
| `.github/workflows/sync-hf-space.yml` | 2.7 KB | `5cca38fa234a` |
| `.github/workflows/release.yml` | 0.7 KB | `da0e2ecf1633` |
| `scripts/docker_deploy.sh` | 5.8 KB | `36699346dbc7` |
| `scripts/docker_build.sh` | 10.5 KB | `479b7a2517a0` |
| `scripts/deploy-engineering-service.sh` | 10.3 KB | `e491ad4f1c79` |
| `Makefile` | 6.1 KB | `95680cde28ea` |
| `alembic.ini` | 2.6 KB | `c6acd592ffa3` |
| `ruff.toml` | 2.6 KB | `aba9676f8b0b` |

---

> **How to update this index:** Run `python indexer.py` from the project root.
> The index captures content hashes for each file — only changed files need re-inspection.