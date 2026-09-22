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
