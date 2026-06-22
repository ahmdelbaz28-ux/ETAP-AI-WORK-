"""
Tests for visualization module — Visualizer class.
"""
import matplotlib

matplotlib.use('Agg')  # Must be set before importing pyplot

import numpy as np
import pytest

from relays.relay import OvercurrentRelay
from visualization.visualization import Visualizer


class TestVisualizerInit:
    def test_init(self):
        v = Visualizer()
        assert v._last_figure is None
        assert v._style_applied is False

    def test_ensure_mpl_applies_style_once(self):
        v = Visualizer()
        v._ensure_mpl()
        assert v._style_applied is True
        # Second call should not raise
        v._ensure_mpl()
        assert v._style_applied is True

    def test_plt_lazy_import(self):
        v = Visualizer()
        plt = v._plt()
        assert plt is not None
        assert hasattr(plt, "plot")


class TestVisualizerPlotTCC:
    def setup_method(self):
        self.v = Visualizer()
        self.relay = OvercurrentRelay(
            relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0
        )

    def test_plot_tcc_curve_returns_axes(self):
        ax = self.v.plot_tcc_curve(self.relay)
        assert ax is not None
        assert hasattr(ax, "get_xlabel")

    def test_plot_tcc_curve_with_custom_range(self):
        ax = self.v.plot_tcc_curve(self.relay, current_range=(1.0, 10), points=20)
        assert ax is not None

    def test_plot_tcc_curve_few_points(self):
        ax = self.v.plot_tcc_curve(self.relay, points=5)
        assert ax is not None

    def test_plot_tcc_curve_with_ax(self):
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots()
        result = self.v.plot_tcc_curve(self.relay, ax=ax)
        assert result is ax
        plt.close(fig)

    def test_plot_tcc_curve_very_inverse(self):
        r = OvercurrentRelay(
            relay_id=2, curve_type="very_inverse", TMS=0.5, Ip=1.0
        )
        ax = self.v.plot_tcc_curve(r)
        assert ax is not None

    def test_plot_tcc_curve_extremely_inverse(self):
        r = OvercurrentRelay(
            relay_id=3, curve_type="extremely_inverse", TMS=0.3, Ip=1.0
        )
        ax = self.v.plot_tcc_curve(r)
        assert ax is not None

    def test_plot_tcc_curve_long_inverse(self):
        r = OvercurrentRelay(
            relay_id=4, curve_type="long_inverse", TMS=0.2, Ip=1.0
        )
        ax = self.v.plot_tcc_curve(r)
        assert ax is not None

    def test_plot_tcc_curve_high_pickup(self):
        r = OvercurrentRelay(
            relay_id=5, curve_type="standard_inverse", TMS=1.0, Ip=5.0
        )
        ax = self.v.plot_tcc_curve(r)
        assert ax is not None


class TestVisualizerPlotMultiple:
    def test_plot_multiple_tcc(self):
        v = Visualizer()
        r1 = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=0.5, Ip=1.0)
        r2 = OvercurrentRelay(relay_id=2, curve_type="very_inverse", TMS=0.3, Ip=1.0)
        fig = v.plot_multiple_tcc([r1, r2])
        assert fig is not None

    def test_plot_multiple_tcc_single_relay(self):
        v = Visualizer()
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        fig = v.plot_multiple_tcc([r])
        assert fig is not None

    def test_plot_multiple_tcc_three_relays(self):
        v = Visualizer()
        relays = [
            OvercurrentRelay(relay_id=i, curve_type="standard_inverse", TMS=0.2 * i, Ip=1.0)
            for i in range(1, 4)
        ]
        fig = v.plot_multiple_tcc(relays)
        assert fig is not None

    def test_plot_multiple_tcc_custom_range(self):
        v = Visualizer()
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        fig = v.plot_multiple_tcc([r], current_range=(2.0, 15), points=30)
        assert fig is not None


class TestVisualizerCoordination:
    def test_plot_coordination_margin(self):
        v = Visualizer()
        up = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        fault_currents = np.linspace(1.5, 10, 5)
        fig = v.plot_coordination_margin(up, down, fault_currents)
        assert fig is not None

    def test_plot_coordination_margin_single_current(self):
        v = Visualizer()
        up = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        fig = v.plot_coordination_margin(up, down, [5.0])
        assert fig is not None

    def test_plot_coordination_margin_no_margin(self):
        v = Visualizer()
        up = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=0.1, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        fault_currents = np.linspace(1.5, 10, 5)
        fig = v.plot_coordination_margin(up, down, fault_currents)
        assert fig is not None

    def test_plot_coordination_margin_with_ax(self):
        from matplotlib import pyplot as plt

        v = Visualizer()
        up = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        down = OvercurrentRelay(relay_id=2, curve_type="standard_inverse", TMS=0.2, Ip=1.0)
        fig, ax = plt.subplots()
        result = v.plot_coordination_margin(up, down, [2.0, 5.0, 10.0], ax=ax)
        assert result is fig
        plt.close(fig)


class TestVisualizerFaultIntersection:
    def test_plot_fault_current_intersection(self):
        v = Visualizer()
        r1 = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=0.5, Ip=1.0)
        r2 = OvercurrentRelay(relay_id=2, curve_type="very_inverse", TMS=0.3, Ip=1.0)
        fault_currents = np.linspace(1.5, 10, 10)
        ax = v.plot_fault_current_intersection([r1, r2], fault_currents)
        assert ax is not None

    def test_plot_fault_current_intersection_single_relay(self):
        v = Visualizer()
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        ax = v.plot_fault_current_intersection([r], [2.0, 5.0, 10.0])
        assert ax is not None

    def test_plot_fault_current_intersection_three_relays(self):
        v = Visualizer()
        relays = [
            OvercurrentRelay(relay_id=i, curve_type="standard_inverse", TMS=0.3 * i, Ip=1.0)
            for i in range(1, 4)
        ]
        ax = v.plot_fault_current_intersection(relays, [2.0, 4.0, 8.0, 16.0])
        assert ax is not None

    def test_plot_fault_current_intersection_inf_time(self):
        v = Visualizer()
        r = OvercurrentRelay(relay_id=1, curve_type="standard_inverse", TMS=1.0, Ip=1.0)
        ax = v.plot_fault_current_intersection(
            [r], [0.5, 1.0, 5.0]
        )  # 0.5 is below pickup
        assert ax is not None
