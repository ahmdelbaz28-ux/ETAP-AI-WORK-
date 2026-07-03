import numpy as np


class CoordinationEngine:
    def __init__(
        self,
        default_margin_sec: float = 0.2,
        tms_search_min: float = 0.1,
        tms_search_max: float = 10.0,
        tms_search_steps: int = 100,
    ):
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
                "coordinated": coordinated,
                "upstream_time": t_up,
                "downstream_time": t_down,
                "margin": margin,
                "required_margin": 0.2,
                "fault_current": fault_current,
            }
        else:
            # Upstream trips first or same time: not coordinated
            return {
                "coordinated": False,
                "upstream_time": t_up,
                "downstream_time": t_down,
                "margin": t_up - t_down,
                "required_margin": 0.2,
                "fault_current": fault_current,
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
        for If in fault_currents:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            results.append(self.check_coordination(upstream_relay, downstream_relay, If))
        return results

    def suggest_tms_adjustment(  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
        self, upstream_relay, downstream_relay, fault_currents, target_margin=0.2,
    ):
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

        # Compute the upstream trip time for a given TMS WITHOUT mutating the relay.
        # This avoids the original bug where the relay's TMS was temporarily changed
        # during the search loop, which could affect concurrent reads of the relay.
        def _trip_time_for_tms(tms, relay, I):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            # Use the relay's curve type and Ip, but override TMS locally
            I_mag = abs(I)  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            if I_mag < relay.Ip:
                return float("inf")
            if relay.curve_type == "standard_inverse":
                return relay.curves.standard_inverse(tms, I_mag, relay.Ip)
            elif relay.curve_type == "very_inverse":
                return relay.curves.very_inverse(tms, I_mag, relay.Ip)
            elif relay.curve_type == "extremely_inverse":
                return relay.curves.extremely_inverse(tms, I_mag, relay.Ip)
            elif relay.curve_type == "long_inverse":
                return relay.curves.long_inverse(tms, I_mag, relay.Ip)
            else:
                raise ValueError(f"Unknown curve type: {relay.curve_type}")

        best_TMS = None  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        min_violation = float("inf")
        # When upstream trips before downstream the margin is negative (or zero).
        # We penalise those cases heavily so the search will never prefer a TMS
        # that lets the upstream device trip first.
        UNCOORDINATED_PENALTY = 100.0

        for TMS_candidate in np.linspace(  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
            self.tms_search_min, self.tms_search_max, self.tms_search_steps,
        ):
            violations = []
            for If in fault_currents:  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
                t_up = _trip_time_for_tms(TMS_candidate, upstream_relay, If)
                t_down = downstream_relay.trip_time(If)

                if t_down < t_up:
                    # Downstream trips first — proper coordination is possible.
                    margin = t_up - t_down
                    if margin < target_margin:
                        violations.append(target_margin - margin)
                else:
                    # Upstream trips first (or same time) — fundamentally
                    # uncoordinated.  Apply a heavy penalty so this TMS never
                    # beats a genuinely coordinated solution.
                    violations.append(UNCOORDINATED_PENALTY + (t_down - t_up))

            if not violations:
                best_TMS = TMS_candidate
                break

            avg_violation = float(np.mean(violations))
            if avg_violation < min_violation:
                min_violation = avg_violation
                best_TMS = TMS_candidate

        return best_TMS
