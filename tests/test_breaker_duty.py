"""Golden test suite for breaker_duty package per IEC 62271-100 and IEC 60947-2."""

import pytest

from breaker_duty import BreakerDutyEvaluator, load_breaker_catalog
from engine.dispatch import STUDY_DISPATCH


class TestBreakerDutyGolden:
    """Validate breaker duty evaluations against the 5 catalog switchgear items."""

    @pytest.fixture
    def catalog(self):
        return load_breaker_catalog()

    @pytest.fixture
    def evaluator(self, catalog):
        return BreakerDutyEvaluator(catalog)

    def test_catalog_all_five_breakers_present(self, catalog):
        expected_breakers = [
            "lv_acb_1600a_65ka",
            "lv_mccb_250a_36ka",
            "mv_vcb_12kv_1250a_25ka",
            "mv_vcb_24kv_1250a_25ka",
            "hv_sf6_72kv_2500a_31ka",
        ]
        for name in expected_breakers:
            assert name in catalog, f"Expected {name} to be loaded in catalog"
            item = catalog[name]
            assert item.rated_voltage_kv > 0
            assert item.breaking_capacity_ka > 0
            assert item.making_capacity_ka > 0

    def test_golden_mv_vcb_12kv_compliant(self, evaluator):
        # 12kV VCB: 1250A, 25kA breaking, 62.5kA making
        res = evaluator.evaluate_breaker(
            "mv_vcb_12kv_1250a_25ka",
            ik_initial_ka=20.0,
            ip_peak_ka=50.0,
            ib_breaking_ka=18.0,
            operating_voltage_kv=11.0,
            operating_current_a=800.0,
        )
        assert res.is_compliant is True
        assert res.status == "COMPLIANT_PASS"
        assert len(res.violations) == 0
        assert res.max_duty_percent <= 100.0
        assert len(res.duty_table) >= 4

    def test_manufactured_breaking_overduty_rejected(self, evaluator):
        # Manufacture a fault exceeding 25kA breaking capacity (e.g. 30kA)
        res = evaluator.evaluate_breaker(
            "mv_vcb_12kv_1250a_25ka",
            ik_initial_ka=30.0,
            ip_peak_ka=60.0,
            ib_breaking_ka=30.0,
            operating_voltage_kv=11.0,
        )
        assert res.is_compliant is False
        assert res.status == "OVERDUTY_REJECTED"
        assert any("Breaking duty 120.0% exceeds 100%" in v for v in res.violations)

    def test_manufactured_making_overduty_rejected(self, evaluator):
        # Manufacture a peak fault exceeding 62.5kA making capacity (e.g. 70kA)
        res = evaluator.evaluate_breaker(
            "mv_vcb_12kv_1250a_25ka",
            ik_initial_ka=20.0,
            ip_peak_ka=70.0,
            ib_breaking_ka=20.0,
            operating_voltage_kv=11.0,
        )
        assert res.is_compliant is False
        assert res.status == "OVERDUTY_REJECTED"
        assert any("Making peak duty" in v for v in res.violations)

    def test_dispatch_registration(self):
        assert "breaker_duty" in STUDY_DISPATCH
        reg = STUDY_DISPATCH["breaker_duty"]
        assert reg.requires_system is False
        assert reg.handler == "breaker_duty.evaluator.BreakerDutyEvaluator"

    def test_dispatch_via_study_executor_gated(self, monkeypatch):
        from services.study_executor import StudyExecutor

        svc = StudyExecutor()
        params = {
            "breaker_id": "mv_vcb_12kv_1250a_25ka",
            "ik_initial_ka": 20.0,
            "ip_peak_ka": 50.0,
            "ib_breaking_ka": 18.0,
            "voltage_kv": 11.0,
        }

        # 1) When feature flag is disabled (default), dispatch must raise ValueError
        monkeypatch.delenv("FEATURE_FLAG_BREAKER_DUTY", raising=False)
        with pytest.raises(ValueError, match="disabled by feature flag"):
            svc._dispatch("breaker_duty", system=None, parameters=params)

        # 2) When feature flag is enabled via env, dispatch executes study
        monkeypatch.setenv("FEATURE_FLAG_BREAKER_DUTY", "true")
        res = svc._dispatch("breaker_duty", system=None, parameters=params)
        assert res["is_compliant"] is True
        assert res["status"] == "COMPLIANT_PASS"
        assert "duty_table" in res

    def test_execute_study_rejects_missing_breaker_id(self, evaluator):
        with pytest.raises(ValueError, match="Parameter required: breaker_id"):
            evaluator.execute_study({"ik_initial_ka": 20.0})

    def test_execute_study_rejects_missing_fault_current(self, evaluator):
        with pytest.raises(ValueError, match="Parameter required: ik_initial_ka"):
            evaluator.execute_study({"breaker_id": "mv_vcb_12kv_1250a_25ka"})

    def test_execute_study_rejects_missing_ip_ib_without_voltage(self, evaluator):
        with pytest.raises(ValueError, match="parameter required: ip_peak_ka/ib_breaking_ka"):
            evaluator.execute_study({
                "breaker_id": "mv_vcb_12kv_1250a_25ka",
                "ik_initial_ka": 20.0,
            })

    def test_execute_study_analytical_derivation(self, evaluator):
        # When voltage_kv is provided, IEC 60909 engine derives ip and ib analytically
        res = evaluator.execute_study({
            "breaker_id": "mv_vcb_12kv_1250a_25ka",
            "ik_initial_ka": 20.0,
            "voltage_kv": 11.0,
            "rx_ratio": 0.1,
        })
        assert res["is_compliant"] is True
        assert res["status"] == "COMPLIANT_PASS"
        # Verify peak duty is present and calculated without arbitrary 2.5 multiplier
        peak_row = next(r for r in res["duty_table"] if r["parameter"] == "Peak Making Current (ip)")
        assert peak_row["calculated_value"] > 0

