"""
tests/test_chain_coordinator.py — Test Suite for Protection Coordination Chain Grading.
"""

from __future__ import annotations

import pytest

from coordination.chain_coordinator import ChainCoordinator, RelayNode
from relays.relay import OvercurrentRelay


class TestChainCoordinator:
    """Test suite for automated multi-relay coordination grading."""

    def test_three_relay_chain_grading(self):
        """Grade a 3-relay radial feeder: Incomer -> Feeder -> Recloser."""
        # 1. Downstream Recloser near industrial load
        r3 = OvercurrentRelay("R3", name="Branch Recloser", curve_type="standard_inverse", tms=0.1, ip=1.0)
        node3 = RelayNode(
            relay_id="R3",
            name="Branch Recloser",
            location="Bus 3 (Branch)",
            relay=r3,
            ct_ratio=20.0,  # 100/5
            load_current_a=60.0,
            max_fault_current_a=2000.0,
            min_fault_current_a=800.0,
        )

        # 2. Feeder Breaker
        r2 = OvercurrentRelay("R2", name="Feeder Breaker", curve_type="standard_inverse", tms=0.2, ip=1.0)
        node2 = RelayNode(
            relay_id="R2",
            name="Feeder Breaker",
            location="Bus 2 (Feeder)",
            relay=r2,
            ct_ratio=40.0,  # 200/5
            load_current_a=150.0,
            max_fault_current_a=5000.0,
            min_fault_current_a=1500.0,
        )

        # 3. Substation Main Incomer
        r1 = OvercurrentRelay("R1", name="Main Incomer", curve_type="standard_inverse", tms=0.3, ip=1.0)
        node1 = RelayNode(
            relay_id="R1",
            name="Main Incomer",
            location="Bus 1 (Substation)",
            relay=r1,
            ct_ratio=100.0,  # 500/5
            load_current_a=350.0,
            max_fault_current_a=12000.0,
            min_fault_current_a=3000.0,
        )

        chain = [node1, node2, node3]
        coordinator = ChainCoordinator(default_cti_s=0.30, min_cti_s=0.20)

        result = coordinator.grade_chain(chain, cti_target_s=0.30)

        assert result.success is True
        assert len(result.violations) == 0
        assert len(result.pair_evaluations) == 2

        # Check pair 1: Main (R1) vs Feeder (R2)
        pair_12 = result.pair_evaluations[0]
        assert pair_12["upstream_id"] == "R1"
        assert pair_12["downstream_id"] == "R2"
        assert pair_12["margin_at_max_fault_s"] >= 0.29
        assert pair_12["is_coordinated"] is True

        # Check pair 2: Feeder (R2) vs Recloser (R3)
        pair_23 = result.pair_evaluations[1]
        assert pair_23["upstream_id"] == "R2"
        assert pair_23["downstream_id"] == "R3"
        assert pair_23["margin_at_max_fault_s"] >= 0.29
        assert pair_23["is_coordinated"] is True

        # TMS must be graded progressively: TMS_1 > TMS_2 > TMS_3
        assert r1.TMS > r2.TMS > r3.TMS

        # Operating times at fault must be progressive: T1 > T2 > T3
        assert pair_12["t_upstream_s"] > pair_23["t_upstream_s"] > pair_23["t_downstream_s"]

        report = coordinator.generate_report(result)
        assert "FULLY COORDINATED" in report
        assert "Main Incomer" in report
        assert "Branch Recloser" in report

    def test_detection_of_uncoordinated_chain(self):
        """Engine flags margin violations when relays are poorly coordinated."""
        # Intentionally give upstream relay a lower TMS than downstream
        r2 = OvercurrentRelay("R2", curve_type="standard_inverse", tms=0.4, ip=1.0)
        node2 = RelayNode(relay_id="R2", name="R2", location="Bus 2", relay=r2, ct_ratio=20.0, max_fault_current_a=3000.0)

        r1 = OvercurrentRelay("R1", curve_type="standard_inverse", tms=0.1, ip=1.0)  # Too fast!
        node1 = RelayNode(relay_id="R1", name="R1", location="Bus 1", relay=r1, ct_ratio=40.0, max_fault_current_a=5000.0)

        coordinator = ChainCoordinator(min_cti_s=0.20)
        verify_res = coordinator.verify_coordination([node1, node2])

        assert verify_res.success is False
        assert len(verify_res.violations) > 0
