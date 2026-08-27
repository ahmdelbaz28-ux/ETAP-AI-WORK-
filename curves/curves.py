# SECURITY AUDIT 2026-07-25 — Fix S-22: Boundary consistency.
# Changed all curve guard conditions from `Ip >= I` to `Ip > I`.
# Previously, at exactly I == Ip, curves returned inf (never trips) but
# relay.pickup_logic returned True (picks up). This inconsistency meant
# a relay could pick up but never trip, causing an infinite wait state.
#
# SECURITY AUDIT 2026-07-26 — Fix S-CURVE-1: Mathematical singularity at I == Ip.
# At I == Ip, the ratio M = I/Ip = 1.0, making (M^k - 1) = 0.0 -> division by
# zero -> infinite trip time. Added epsilon nudge: when M == 1.0, use M = 1.0001
# to produce a very large but finite trip time (correct physical behavior).
#
# V-TCC-01 — Replace unbounded TCC formula with IEC 60255 + safety guards
# ---------------------------------------------------------------------------
# Root cause: the original IEC60255Curves class had no bounds on the formula.
# When I/Ip >> 1 (high fault current), the trip time could approach zero,
# which is physically impossible — every relay has a minimum operating time.
# When I/Ip was extremely large (> 40), the formula was being applied far
# outside the IEC 60255-1 valid range, producing unreliable results.
# Additionally, there was no instantaneous overcurrent element (element 50)
# which is a standard feature in real numerical relays.
#
# Fix: Introduce calculate_iec_operating_time() as the single safe entry
# point for all IEC 60255 curve calculations. It enforces:
#   1. Input validation (positive currents, valid TMS, known curve type)
#   2. Maximum multiplier cap (I/Ip <= 40x) — IEC 60255-1 valid range
#   3. Minimum operating time floor (0.02 s) — physical relay limit
#   4. Instantaneous overcurrent element (element 50) — immediate trip
#   5. IEEE C37.112 curves with the same safety guards
#
# The IEC60255Curves class is retained for backward compatibility but now
# delegates to calculate_iec_operating_time() internally.
# ---------------------------------------------------------------------------

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# IEC 60255 curve constants (k, alpha) per IEC 60255-151:2019 Table 1
# Formula: t = TMS * k / (M^alpha - 1),  where M = I_fault / I_pickup
# ---------------------------------------------------------------------------
_IEC_CURVE_PARAMS: dict[str, tuple[float, float]] = {
    "standard_inverse": (0.14, 0.02),
    "very_inverse": (13.5, 1.0),
    "extremely_inverse": (80.0, 2.0),
    "long_inverse": (120.0, 1.0),
}

# ---------------------------------------------------------------------------
# IEEE C37.112 curve constants (A, B, p) per IEEE C37.112-2018
# Formula: t = TDS * (A + B / (M^p - 1)),  where M = I_fault / I_pickup
# ---------------------------------------------------------------------------
_IEEE_CURVE_PARAMS: dict[str, tuple[float, float, float]] = {
    "ieee_moderately_inverse": (0.0515, 0.1140, 0.02),
    "ieee_very_inverse": (19.61, 0.491, 2.0),
    "ieee_extremely_inverse": (28.2, 0.1217, 2.0),
}

# Unified lookup that maps curve names to their type family and parameters
_CURVE_REGISTRY: dict[str, dict] = {}

for _name, (_k, _alpha) in _IEC_CURVE_PARAMS.items():
    _CURVE_REGISTRY[_name] = {"family": "iec", "k": _k, "alpha": _alpha}

for _name, (_a, _b, _p) in _IEEE_CURVE_PARAMS.items():
    _CURVE_REGISTRY[_name] = {"family": "ieee", "A": _a, "B": _b, "p": _p}

# ---------------------------------------------------------------------------
# Safety-guard constants
# ---------------------------------------------------------------------------
MIN_OPERATING_TIME_S: float = 0.02  # IEC 60255-1 §6.1.2.3 — minimum trip time
MAX_MULTIPLIER_OF_PICKUP: float = 40.0  # IEC 60255-1 valid range upper bound

# Epsilon nudge for the M=1.0 singularity — avoids division by zero while
# producing a very large but finite trip time (correct physical behavior).
_IEC_CURVE_EPSILON: float = 1.0001


def calculate_iec_operating_time(
    i_fault: float,
    i_setting: float,
    tms: float,
    curve_type: str = "very_inverse",
    *,
    instantaneous_override_a: float | None = None,
    instantaneous_time_s: float = 0.02,
    min_operating_time_s: float = MIN_OPERATING_TIME_S,
    max_multiplier: float = MAX_MULTIPLIER_OF_PICKUP,
) -> dict:
    """Calculate relay operating time with IEC 60255 / IEEE C37.112 safety guards.

    This is the single safe entry point for all TCC curve calculations.
    It enforces physical bounds and input validation that the raw IEC/IEEE
    formulas do not provide.

    Parameters
    ----------
    i_fault : float
        Fault current (A). Must be positive.
    i_setting : float
        Pickup / plug setting current (A). Must be positive.
    tms : float
        Time Multiplier Setting (IEC) or Time Dial Setting (IEEE). Must be > 0.
    curve_type : str
        One of the IEC 60255 or IEEE C37.112 curve names.
    instantaneous_override_a : float or None
        If provided, when I_fault >= this value the relay trips instantly
        (element 50 / instantaneous overcurrent). None = no instantaneous element.
    instantaneous_time_s : float
        Operating time for the instantaneous element (default 0.02 s).
    min_operating_time_s : float
        Floor for trip time — no relay can operate faster than this.
    max_multiplier : float
        Maximum M = I_fault / I_setting beyond which the formula is unreliable.

    Returns
    -------
    dict with keys:
        operating_time_s : float   — the computed trip time
        curve_type : str            — the curve used
        i_fault : float             — echo of fault current
        i_setting : float           — echo of pickup setting
        multiples_of_pickup : float — M = I_fault / I_setting
        tms : float                 — echo of TMS
        status : str                — "ok" | "no_trip" | "instantaneous" | "capped"
        warnings : list[str]        — any warnings about the calculation
    """

    warnings: list[str] = []

    # --- Input validation ---
    if i_fault <= 0:
        raise ValueError(f"i_fault must be positive, got {i_fault}")
    if i_setting <= 0:
        raise ValueError(f"i_setting must be positive, got {i_setting}")
    if tms <= 0:
        raise ValueError(f"tms must be positive, got {tms}")

    curve_type_lower = curve_type.lower().strip()
    if curve_type_lower not in _CURVE_REGISTRY:
        valid = sorted(_CURVE_REGISTRY.keys())
        raise ValueError(f"Unknown curve type '{curve_type}'. Valid: {valid}")

    # --- Compute M = I_fault / I_setting ---
    M = i_fault / i_setting

    # --- No-trip: fault current strictly below pickup (I < I_setting) ---
    if i_fault < i_setting and not math.isclose(M, 1.0):
        return {
            "operating_time_s": float("inf"),
            "curve_type": curve_type_lower,
            "i_fault": i_fault,
            "i_setting": i_setting,
            "multiples_of_pickup": M,
            "tms": tms,
            "status": "no_trip",
            "warnings": warnings,
        }

    # --- Instantaneous override (element 50) ---
    if instantaneous_override_a is not None and i_fault >= instantaneous_override_a:
        return {
            "operating_time_s": instantaneous_time_s,
            "curve_type": curve_type_lower,
            "i_fault": i_fault,
            "i_setting": i_setting,
            "multiples_of_pickup": M,
            "tms": tms,
            "status": "instantaneous",
            "warnings": warnings,
        }

    # --- Cap M at maximum valid range ---
    if max_multiplier < M:
        warnings.append(
            f"M={M:.1f} exceeds max_multiplier={max_multiplier}; "
            f"capped to {max_multiplier}. Results may be unreliable."
        )
        M = max_multiplier

    # --- Apply epsilon nudge at singularity ---
    M_effective = M if not math.isclose(M, 1.0) else _IEC_CURVE_EPSILON
    M_effective = M if not math.isclose(M, 1.0) else _IEC_CURVE_EPSILON  # noqa: S117 — domain notation

    # --- Compute raw trip time ---
    curve_info = _CURVE_REGISTRY[curve_type_lower]

    if curve_info["family"] == "iec":
        k = curve_info["k"]
        alpha = curve_info["alpha"]
        t_raw = tms * k / (M_effective**alpha - 1)
    else:  # ieee
        A = curve_info["A"]
        B = curve_info["B"]
        p = curve_info["p"]
        t_raw = tms * (A + B / (M_effective**p - 1))

    # --- Enforce minimum operating time floor ---
    status = "ok"
    if t_raw < min_operating_time_s:
        warnings.append(
            f"Raw trip time {t_raw:.6f}s clamped to min_operating_time_s={min_operating_time_s}s"
        )
        t_raw = min_operating_time_s
        status = "capped"

    return {
        "operating_time_s": t_raw,
        "curve_type": curve_type_lower,
        "i_fault": i_fault,
        "i_setting": i_setting,
        "multiples_of_pickup": M,
        "tms": tms,
        "status": status,
        "warnings": warnings,
    }


class IEC60255Curves:
    """
    IEC 60255 inverse time curves for overcurrent relays.

    .. deprecated::
        Use :func:`calculate_iec_operating_time` for new code — it provides
        safety guards (min operating time, max multiplier, instantaneous
        override) that this class does not enforce on its own.  This class
        is retained for backward compatibility and now delegates to the safe
        function internally.
    """

    @staticmethod
    def standard_inverse(
        tms,
        i,
        ip,
    ):  # NOSONAR physics/engineering notation
        """Standard inverse curve."""
        Ip, I = ip, i
        if Ip > I:
            return float("inf")
        M = I / Ip if I != Ip else _IEC_CURVE_EPSILON
        result = calculate_iec_operating_time(
            i_fault=i,
            i_setting=ip,
            tms=tms,
            curve_type="standard_inverse",
        )
        return result["operating_time_s"]

    @staticmethod
    def very_inverse(tms, i, ip):  # NOSONAR physics/engineering notation
        """Very inverse curve."""
        Ip, I = ip, i
        if Ip > I:
            return float("inf")
        M = I / Ip if I != Ip else _IEC_CURVE_EPSILON
        result = calculate_iec_operating_time(
            i_fault=i,
            i_setting=ip,
            tms=tms,
            curve_type="very_inverse",
        )
        return result["operating_time_s"]

    @staticmethod
    def extremely_inverse(tms, i, ip):  # NOSONAR physics/engineering notation
        """Extremely inverse curve."""
        Ip, I = ip, i
        if Ip > I:
            return float("inf")
        M = I / Ip if I != Ip else _IEC_CURVE_EPSILON
        result = calculate_iec_operating_time(
            i_fault=i,
            i_setting=ip,
            tms=tms,
            curve_type="extremely_inverse",
        )
        return result["operating_time_s"]

    @staticmethod
    def long_inverse(tms, i, ip):  # NOSONAR physics/engineering notation
        """Long inverse curve (UK)."""
        Ip, I = ip, i
        if Ip > I:
            return float("inf")
        M = I / Ip if I != Ip else _IEC_CURVE_EPSILON
        result = calculate_iec_operating_time(
            i_fault=i,
            i_setting=ip,
            tms=tms,
            curve_type="long_inverse",
        )
        return result["operating_time_s"]
