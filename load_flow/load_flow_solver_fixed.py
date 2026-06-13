import numpy as np
import logging

logger = logging.getLogger(__name__)


class LoadFlowSolver:
    """
    Newton-Raphson Load Flow Solver with:
    - PV Bus Reactive Power Limits (Qmin/Qmax) and PV -> PQ switching
    - Step Size Limiting
    - Damping Factor
    - Divergence Detection
    - Adaptive Tolerance
    """

    def __init__(self, system):
        self.system = system
        self.Ybus = self.system.get_ybus(seq='1')
        self.n_buses = self.Ybus.shape[0]

        self.bus_ids = sorted(self.system.buses.keys())
        self.bus_index = {bid: i for i, bid in enumerate(self.bus_ids)}
        self.V = np.array(
            [self.system.buses[bid].voltage for bid in self.bus_ids],
            dtype=complex
        )

        # PV Q limits: {bus_index: (Qmin, Qmax)}
        self.q_limits = {}
        for bid in self.bus_ids:
            bus = self.system.buses[bid]
            if bus.bus_type == 'pv':
                qmin = getattr(bus, 'q_min', -999.0)
                qmax = getattr(bus, 'q_max', 999.0)
                self.q_limits[self.bus_index[bid]] = (qmin, qmax)

        # Original PV indices (indices in bus_ids order)
        self.original_pv_indices = [
            i for i, bid in enumerate(self.bus_ids)
            if self.system.buses[bid].bus_type == 'pv'
        ]

        self._rebuild_bus_type_indices()

        # Solver parameters
        self.damping_factor = 1.0
        self.max_step_angle = 0.2       # radians
        self.max_step_voltage = 0.1    # pu
        self.oscillation_window = 5
        self.oscillation_threshold = 0.7

        # Logs
        self.switching_log = []
        self.iteration_log = []

    def _rebuild_bus_type_indices(self):
        self.bus_types = [self.system.buses[bid].bus_type for bid in self.bus_ids]
        self.slack_indices = [i for i, bt in enumerate(self.bus_types) if bt == 'slack']
        self.pv_indices = [i for i, bt in enumerate(self.bus_types) if bt == 'pv']
        self.pq_indices = [i for i, bt in enumerate(self.bus_types) if bt == 'pq']
        self.n_unknowns = len(self.pv_indices) + 2 * len(self.pq_indices)

    def _calculate_power(self, V):
        I = np.dot(self.Ybus, V)
        S = V * np.conj(I)
        return np.real(S), np.imag(S)

    def _scheduled_power(self):
        P_sch = np.zeros(self.n_buses)
        Q_sch = np.zeros(self.n_buses)
        for i, bid in enumerate(self.bus_ids):
            bus = self.system.buses[bid]
            P_sch[i] = bus.generation_power.real - bus.load_power.real
            Q_sch[i] = bus.generation_power.imag - bus.load_power.imag
        return P_sch, Q_sch

    def _power_mismatch(self, V, P_sch, Q_sch):
        P, Q = self._calculate_power(V)
        return P_sch - P, Q_sch - Q

    def _build_jacobian(self, V, P_sch=None, Q_sch=None):
        """
        Robust reduced Jacobian via finite differences.

        This replaces the analytical Jacobian to ensure consistency with:
          mismatch ordering = [dP_pv, dP_pq, dQ_pq]
          unknown ordering  = [dtheta_pv, dtheta_pq, d|V|_pq]
        """
        if P_sch is None or Q_sch is None:
            P_sch, Q_sch = self._scheduled_power()

        eps_theta = 1e-6
        eps_v = 1e-6

        base_deltaP, base_deltaQ = self._power_mismatch(V, P_sch, Q_sch)
        base_mismatch = self._build_mismatch_vector(base_deltaP, base_deltaQ)

        J = np.zeros((self.n_unknowns, self.n_unknowns), dtype=float)

        pv = self.pv_indices
        pq = self.pq_indices
        n_pv = len(pv)
        n_pq = len(pq)

        # Helper to set unknown perturbation and compute mismatch
        def compute_mismatch(V_trial):
            dP_trial, dQ_trial = self._power_mismatch(V_trial, P_sch, Q_sch)
            return self._build_mismatch_vector(dP_trial, dQ_trial)

        # theta unknowns: pv then pq
        for col in range(n_pv + n_pq):
            V_trial = V.copy()
            if col < n_pv:
                bus_i = pv[col]
                theta_i = np.angle(V_trial[bus_i])
                V_trial[bus_i] = np.abs(V_trial[bus_i]) * np.exp(1j * (theta_i + eps_theta))
            else:
                bus_i = pq[col - n_pv]
                theta_i = np.angle(V_trial[bus_i])
                V_trial[bus_i] = np.abs(V_trial[bus_i]) * np.exp(1j * (theta_i + eps_theta))

            m = compute_mismatch(V_trial)
            J[:, col] = (m - base_mismatch).real / eps_theta

        # |V| unknowns: pq only
        for k in range(n_pq):
            col = n_pv + n_pq + k
            V_trial = V.copy()
            bus_i = pq[k]
            Vmag = np.abs(V_trial[bus_i])
            V_trial[bus_i] = (Vmag + eps_v) * np.exp(1j * np.angle(V_trial[bus_i]))

            m = compute_mismatch(V_trial)
            J[:, col] = (m - base_mismatch).real / eps_v

        return J

    def _build_mismatch_vector(self, deltaP, deltaQ):
        pv = self.pv_indices
        pq = self.pq_indices
        n_pv = len(pv)
        n_pq = len(pq)

        mismatch = np.zeros(self.n_unknowns)
        mismatch[:n_pv] = deltaP[pv]
        mismatch[n_pv:n_pv + n_pq] = deltaP[pq]
        mismatch[n_pv + n_pq:] = deltaQ[pq]
        return mismatch

    def _apply_step_limiting(self, correction):
        """Apply step limits using uniform scaling to preserve Newton direction.

        Individual clipping distorts the correction direction, causing oscillation
        on radial networks. Uniform scaling keeps the direction intact.
        """
        pv = self.pv_indices
        pq = self.pq_indices
        n_pv = len(pv)
        n_pq = len(pq)

        max_angle_ratio = 1.0
        max_voltage_ratio = 1.0

        # Angle corrections: PV buses then PQ buses (both use max_step_angle)
        for idx in range(n_pv + n_pq):
            val = abs(correction[idx])
            if val > self.max_step_angle:
                max_angle_ratio = min(max_angle_ratio, self.max_step_angle / val)

        # Voltage magnitude corrections (PQ buses only)
        for idx in range(n_pq):
            mag_idx = n_pv + n_pq + idx
            val = abs(correction[mag_idx])
            if val > self.max_step_voltage:
                max_voltage_ratio = min(max_voltage_ratio, self.max_step_voltage / val)

        # Apply uniform scaling to preserve direction
        scale = min(max_angle_ratio, max_voltage_ratio)
        if scale < 1.0:
            return correction * scale
        return correction

    def _update_voltages(self, correction):
        pv = self.pv_indices
        pq = self.pq_indices
        n_pv = len(pv)
        n_pq = len(pq)

        alpha = self.damping_factor

        # Update angles
        for idx, bus_i in enumerate(pv):
            theta_i = np.angle(self.V[bus_i])
            theta_i += alpha * correction[idx]
            Vmag_i = np.abs(self.V[bus_i])
            self.V[bus_i] = Vmag_i * np.exp(1j * theta_i)

        for idx, bus_i in enumerate(pq):
            theta_i = np.angle(self.V[bus_i])
            theta_i += alpha * correction[n_pv + idx]
            Vmag_i = np.abs(self.V[bus_i])
            self.V[bus_i] = Vmag_i * np.exp(1j * theta_i)

        # Update magnitudes (PQ only)
        for idx, bus_i in enumerate(pq):
            Vmag_i = np.abs(self.V[bus_i])
            Vmag_i += alpha * correction[n_pv + n_pq + idx]
            theta_i = np.angle(self.V[bus_i])
            self.V[bus_i] = Vmag_i * np.exp(1j * theta_i)

    def _check_q_limits(self, V):
        P, Q = self._calculate_power(V)
        switched = False

        for bus_i in self.original_pv_indices:
            bid = self.bus_ids[bus_i]
            bus = self.system.buses[bid]

            if bus_i not in self.q_limits:
                continue

            qmin, qmax = self.q_limits[bus_i]
            Q_gen = Q[bus_i] + bus.load_power.imag

            if bus.bus_type == 'pv' and Q_gen > qmax:
                bus.bus_type = 'pq'
                bus.generation_power = complex(bus.generation_power.real, qmax + bus.load_power.imag)
                event = f"PV->PQ (Q>Qmax): Bus {bid} Q={Q_gen:.4f} > Qmax={qmax:.4f}"
                self.switching_log.append(event)
                logger.info(event)
                switched = True

            elif bus.bus_type == 'pv' and Q_gen < qmin:
                bus.bus_type = 'pq'
                bus.generation_power = complex(bus.generation_power.real, qmin + bus.load_power.imag)
                event = f"PV->PQ (Q<Qmin): Bus {bid} Q={Q_gen:.4f} < Qmin={qmin:.4f}"
                self.switching_log.append(event)
                logger.info(event)
                switched = True

        if switched:
            self._rebuild_bus_type_indices()
        return switched

    def _detect_oscillation(self, mismatch_history):
        if len(mismatch_history) < 2 * self.oscillation_window:
            return False
        recent = mismatch_history[-self.oscillation_window:]
        prev = mismatch_history[-2 * self.oscillation_window:-self.oscillation_window]
        if np.mean(recent) > self.oscillation_threshold * np.mean(prev):
            return True
        return False

    def solve(self, max_iter=100, tol=1e-6, mode='engineering'):
        if mode == 'high_accuracy':
            tol = min(tol, 1e-8)

        P_sch, Q_sch = self._scheduled_power()
        mismatch_history = []
        self.iteration_log = []
        self.switching_log = []

        for iteration in range(max_iter):
            deltaP, deltaQ = self._power_mismatch(self.V, P_sch, Q_sch)
            mismatch = self._build_mismatch_vector(deltaP, deltaQ)

            max_mismatch = np.max(np.abs(mismatch))
            mismatch_history.append(max_mismatch)

            # Lightweight debug: first few iterations and when oscillation triggers later.
            if iteration < 5:
                logger.info(
                    f"[LoadFlow] iter={iteration} max_mismatch={max_mismatch:.6e} "
                    f"n_pv={len(self.pv_indices)} n_pq={len(self.pq_indices)} "
                    f"damping={self.damping_factor:.3f}"
                )
                try:
                    J_dbg = self._build_jacobian(self.V)
                    nan_count = int(np.isnan(J_dbg).sum())
                    inf_count = int(np.isinf(J_dbg).sum())
                    finite_all = bool(np.isfinite(J_dbg).all())
                    logger.info(
                        f"[LoadFlow] iter={iteration} Jacobian finite_all={finite_all} "
                        f"nan_count={nan_count} inf_count={inf_count} shape={J_dbg.shape}"
                    )
                except Exception as e:
                    logger.exception(f"[LoadFlow] iter={iteration} Jacobian build debug failed: {e}")

            self.iteration_log.append({
                'iteration': iteration,
                'max_mismatch': max_mismatch,
                'n_pv': len(self.pv_indices),
                'n_pq': len(self.pq_indices),
            })

            if max_mismatch < tol:
                self._check_q_limits(self.V)
                # Write back results to system buses
                P, Q = self._calculate_power(self.V)
                for i, bid in enumerate(self.bus_ids):
                    bus = self.system.buses[bid]
                    bus.voltage = self.V[i]
                    # generation_power = injected power + load (since P_inj = P_gen - P_load)
                    bus.generation_power = complex(
                        P[i] + bus.load_power.real,
                        Q[i] + bus.load_power.imag
                    )
                return True

            J = self._build_jacobian(self.V)

            try:
                correction = np.linalg.solve(J, -mismatch)
            except np.linalg.LinAlgError:
                correction = np.linalg.lstsq(J, -mismatch, rcond=None)[0]

            correction = self._apply_step_limiting(correction)

            # Line-search style damping: reduce applied correction if mismatch increases.
            # This prevents oscillation loops when Newton step overshoots.
            V_prev = self.V.copy()
            mismatch_prev = max_mismatch

            alphas = [self.damping_factor, 0.7 * self.damping_factor, 0.3 * self.damping_factor]
            chosen = False
            for alpha in alphas:
                if alpha < 1e-3:
                    break

                self.V = V_prev.copy()
                alpha_backup = self.damping_factor
                self.damping_factor = alpha
                self._update_voltages(correction)
                # evaluate mismatch at trial point
                dP_trial, dQ_trial = self._power_mismatch(self.V, P_sch, Q_sch)
                mismatch_trial = self._build_mismatch_vector(dP_trial, dQ_trial)
                max_trial = float(np.max(np.abs(mismatch_trial)))

                self.damping_factor = alpha_backup

                if max_trial < mismatch_prev:
                    chosen = True
                    break

            if not chosen:
                # Line search exhausted — try Levenberg-Marquardt regularization
                # to escape oscillation limit cycles common in radial networks
                lm_escaped = False
                if self._detect_oscillation(mismatch_history):
                    saved_damping = self.damping_factor
                    for lm_lambda in [0.01, 0.1, 1.0, 10.0]:
                        J_lm = J + lm_lambda * np.eye(J.shape[0])
                        try:
                            corr_lm = np.linalg.solve(J_lm, -mismatch)
                        except np.linalg.LinAlgError:
                            corr_lm = np.linalg.lstsq(J_lm, -mismatch, rcond=None)[0]
                        corr_lm = self._apply_step_limiting(corr_lm)
                        for alpha in [1.0, 0.5, 0.25, 0.1]:
                            self.V = V_prev.copy()
                            self.damping_factor = alpha
                            self._update_voltages(corr_lm)
                            dP_trial, dQ_trial = self._power_mismatch(self.V, P_sch, Q_sch)
                            mismatch_trial = self._build_mismatch_vector(dP_trial, dQ_trial)
                            max_trial = float(np.max(np.abs(mismatch_trial)))
                            if max_trial < mismatch_prev:
                                self.damping_factor = max(alpha, 0.3)
                                lm_escaped = True
                                # Feed the improved mismatch to history so the
                                # oscillation detector sees the escape, preventing
                                # unnecessary damping reduction next iteration.
                                mismatch_history.append(max_trial)
                                logger.info(
                                    "LM escape at iter=%d lambda=%.2f alpha=%.2f "
                                    "mismatch %.4e -> %.4e",
                                    iteration, lm_lambda, alpha, mismatch_prev, max_trial
                                )
                                break
                        if lm_escaped:
                            break
                    if not lm_escaped:
                        self.damping_factor = saved_damping
                if not lm_escaped:
                    # Last resort: reduced damping in original direction
                    self.V = V_prev.copy()
                    self.damping_factor = max(0.1, 0.3 * self.damping_factor)
                    self._update_voltages(correction)

            if self._check_q_limits(self.V):
                P_sch, Q_sch = self._scheduled_power()

            if self._detect_oscillation(mismatch_history):
                self.damping_factor = max(0.3, self.damping_factor * 0.7)
                logger.warning(
                    f"Oscillation detected at iteration {iteration}, reducing damping to {self.damping_factor:.3f}"
                )

            if max_mismatch > 1e4:
                logger.error(f"Divergence detected at iteration {iteration} (mismatch={max_mismatch:.2e})")
                break

        # Best-effort writeback even on non-convergence
        P, Q = self._calculate_power(self.V)
        for i, bid in enumerate(self.bus_ids):
            bus = self.system.buses[bid]
            bus.voltage = self.V[i]
            bus.generation_power = complex(
                P[i] + bus.load_power.real,
                Q[i] + bus.load_power.imag
            )
        return False
