from relays.relay import OvercurrentRelay  # noqa: F401 - used by plot methods


class Visualizer:
    """
    Plotting helper for TCC curves and coordination margins.

    All matplotlib imports happen lazily inside the method that needs them,
    so importing ``Visualizer`` or constructing a ``PowerSystemEngine`` does
    not trigger the ~50 MB matplotlib dependency chain.
    """

    def __init__(self):
        """Initialize the visualizer — no matplotlib imports here."""
        self._last_figure = None
        self._style_applied = False

    def _ensure_mpl(self):
        """Lazy-load matplotlib and apply default styles once."""
        if self._style_applied:
            return
        from matplotlib import pyplot as plt

        try:
            plt.style.use("seaborn-v0_8-whitegrid")
        except (OSError, ValueError):
            plt.rcParams["axes.grid"] = True
        plt.rcParams["axes.titlesize"] = 12
        plt.rcParams["axes.labelsize"] = 10
        plt.rcParams["legend.fontsize"] = 9
        plt.rcParams["figure.dpi"] = 100
        self._style_applied = True

    def _plt(self):
        """Return the matplotlib pyplot module (lazy import)."""
        self._ensure_mpl()
        from matplotlib import pyplot as plt

        return plt

    def plot_tcc_curve(self, relay, current_range=(0.5, 20), points=100, ax=None):
        """
        Plot the time-current curve for a given overcurrent relay.

        Parameters:
        relay (OvercurrentRelay): The relay to plot.
        current_range (tuple): Min and max current in multiples of pickup (Ip).
        points (int): Number of points to plot.
        ax (matplotlib.axes.Axes): Axes to plot on. If None, create new figure.

        Returns:
        matplotlib.axes.Axes: The axes with the plot.
        """
        import numpy as np

        plt = self._plt()
        if ax is None:
            fig, ax = plt.subplots()
        Ip = relay.Ip
        I_multiples = np.linspace(current_range[0], current_range[1], points)
        currents = I_multiples * Ip
        times = []
        for I in currents:
            t = relay.trip_time(I)
            times.append(t)
        times = np.array(times)
        ax.loglog(currents, times, label=relay.name)
        ax.set_xlabel("Current (A)")
        ax.set_ylabel("Time (s)")
        ax.set_title("Time-Current Curves")
        ax.grid(True, which="both", ls="-")
        ax.legend()
        return ax

    def plot_multiple_tcc(self, relays, current_range=(0.5, 20), points=100, ax=None):
        """
        Plot multiple TCC curves on the same axes.

        Parameters:
        relays (list): List of OvercurrentRelay objects.
        current_range (tuple): Min and max current in multiples of pickup.
        points (int): Number of points to plot.
        ax (matplotlib.axes.Axes): Axes to plot on. If None, create new figure.

        Returns:
        matplotlib.figure.Figure: The figure object.
        """
        plt = self._plt()
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()
        for relay in relays:
            self.plot_tcc_curve(relay, current_range=current_range, points=points, ax=ax)
        ax.set_xlabel("Current (per unit)")
        ax.set_ylabel("Time (s)")
        ax.set_title("Multiple Time-Current Curves")
        ax.grid(True, which="both", ls="-")
        return fig

    def plot_coordination_margin(self, upstream_relay, downstream_relay, fault_currents, ax=None):
        """
        Plot the coordination margin between two relays over a range of fault currents.

        Parameters:
        upstream_relay (OvercurrentRelay): The upstream relay.
        downstream_relay (OvercurrentRelay): The downstream relay.
        fault_currents (list or array): Fault currents in per-unit.
        ax (matplotlib.axes.Axes): Axes to plot on. If None, create new figure.

        Returns:
        matplotlib.axes.Axes: The axes with the plot.
        """
        import numpy as np

        plt = self._plt()
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.get_figure()
        margins = []
        for If in fault_currents:
            t_up = upstream_relay.trip_time(If)
            t_down = downstream_relay.trip_time(If)
            margin = t_up - t_down
            margins.append(margin)
        margins = np.array(margins)
        ax.plot(fault_currents, margins, label="Margin (Up - Down)")
        ax.axhline(y=0.2, color="r", linestyle="--", label="Required Margin (0.2 s)")
        ax.axhline(y=0, color="k", linestyle="-", label="Zero Margin")
        ax.set_xlabel("Fault Current (per unit)")
        ax.set_ylabel("Margin (s)")
        ax.set_title("Coordination Margin")
        ax.grid(True)
        ax.legend()
        return fig

    def plot_fault_current_intersection(self, relays, fault_currents, ax=None):
        """
        Plot the trip times of multiple relays vs fault current to show intersection points.

        Parameters:
        relays (list): List of OvercurrentRelay objects.
        fault_currents (list or array): Fault currents in per-unit.
        ax (matplotlib.axes.Axes): Axes to plot on. If None, create new figure.

        Returns:
        matplotlib.axes.Axes: The axes with the plot.
        """
        plt = self._plt()
        if ax is None:
            fig, ax = plt.subplots()
        for relay in relays:
            times = [relay.trip_time(If) for If in fault_currents]
            ax.semilogx(fault_currents, times, label=relay.name)
        ax.set_xlabel("Fault Current (per unit)")
        ax.set_ylabel("Trip Time (s)")
        ax.set_title("Relay Trip Times vs Fault Current")
        ax.grid(True, which="both", ls="-")
        ax.legend()
        return ax
