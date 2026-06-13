import numpy as np

class CoordinationEngine:
    def __init__(self, default_margin_sec: float = 0.2,
                 tms_search_min: float = 0.1, tms_search_max: float = 10.0,
                 tms_search_steps: int = 100):
        """
        Initialize the coordination engine with grading-margin defaults.

        Parameters
        ----------
        default_margin_sec : float
            Default coordination time interval (CTI) between upstream and
            downstream devices. 0.2 s is the IEC 60255-151 typical value.
        tms_search_min : float
            Lower bound when sweeping TMS to satisfy a margin target.
        tms_search_max : float
            Upper bound for the TMS search sweep.
        tms_search_steps : int
            Number of candidate TMS values to try in the sweep.
        """
        self.default_margin_sec = default_margin_sec
        self.tms_search_min = tms_search_min
        self.tms_search_max = tms_search_max
        self.tms_search_steps = tms_search_steps

    def check_coordination(self, upstream_relay, downstream_relay, fault_current):
        """
        Check coordination between upstream and downstream relays for a given fault current.

        Parameters:
        upstream_relay (OvercurrentRelay): The upstream relay.
        downstream_relay (OvercurrentRelay): The downstream relay.
        fault_current (float): Fault current in per-unit.

        Returns:
        dict: Coordination status and times.
        """
        # Get trip times for both relays
        t_up = upstream_relay.trip_time(fault_current)
        t_down = downstream_relay.trip_time(fault_current)

        # Check if downstream relay trips first
        if t_down < t_up:
            margin = t_up - t_down
            coordinated = margin >= 0.2  # typical grading margin of 0.2 seconds
            return {
                'coordinated': coordinated,
                'upstream_time': t_up,
                'downstream_time': t_down,
                'margin': margin,
                'required_margin': 0.2,
                'fault_current': fault_current
            }
        else:
            # Upstream trips first or same time: not coordinated
            return {
                'coordinated': False,
                'upstream_time': t_up,
                'downstream_time': t_down,
                'margin': t_up - t_down,
                'required_margin': 0.2,
                'fault_current': fault_current
            }

    def check_coordination_range(self, upstream_relay, downstream_relay, fault_currents):
        """
        Check coordination over a range of fault currents.

        Parameters:
        upstream_relay (OvercurrentRelay): The upstream relay.
        downstream_relay (OvercurrentRelay): The downstream relay.
        fault_currents (list): List of fault currents in per-unit.

        Returns:
        list: List of coordination results for each fault current.
        """
        results = []
        for If in fault_currents:
            results.append(self.check_coordination(upstream_relay, downstream_relay, If))
        return results

    def suggest_tms_adjustment(self, upstream_relay, downstream_relay, fault_currents, target_margin=0.2):
        """
        Suggest TMS adjustment for upstream relay to achieve coordination.

        Parameters:
        upstream_relay (OvercurrentRelay): The upstream relay (to be adjusted).
        downstream_relay (OvercurrentRelay): The downstream relay (fixed).
        fault_currents (list): List of fault currents in per-unit.
        target_margin (float): Desired margin in seconds.

        Returns:
        float: Suggested TMS for upstream relay, or None if not possible.
        """
        # We will try to find a TMS such that for all fault currents,
        # t_up - t_down >= target_margin
        # We'll do a simple search over TMS values.
        best_TMS = None
        min_violation = float('inf')
        for TMS_candidate in np.linspace(0.1, 10.0, 100):
            # Temporarily set TMS
            original_TMS = upstream_relay.TMS
            upstream_relay.TMS = TMS_candidate
            violations = []
            for If in fault_currents:
                result = self.check_coordination(upstream_relay, downstream_relay, If)
                if not result['coordinated']:
                    # How much we are missing the margin
                    violation = target_margin - result['margin']
                    if violation > 0:
                        violations.append(violation)
            # If no violations, this TMS works
            if not violations:
                best_TMS = TMS_candidate
                # Restore original TMS before returning
                upstream_relay.TMS = original_TMS
                break
            else:
                # Average violation
                avg_violation = np.mean(violations)
                if avg_violation < min_violation:
                    min_violation = avg_violation
                    best_TMS = TMS_candidate
                # Restore original TMS
                upstream_relay.TMS = original_TMS
        return best_TMS
