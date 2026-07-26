# SECURITY AUDIT 2026-07-25 — Fix S-22: Boundary consistency.
# Changed all curve guard conditions from `Ip >= I` to `Ip > I`.
# Previously, at exactly I == Ip, curves returned inf (never trips) but
# relay.pickup_logic returned True (picks up). This inconsistency meant
# a relay could pick up but never trip, causing an infinite wait state.
#
# SECURITY AUDIT 2026-07-26 — Fix S-CURVE-1: Mathematical singularity at I == Ip.
# At I == Ip, the ratio M = I/Ip = 1.0, making (M^k - 1) = 0.0 → division by
# zero → infinite trip time. Added epsilon nudge: when M == 1.0, use M = 1.0001
# to produce a very large but finite trip time (correct physical behavior).
_IEC_CURVE_EPSILON = 1.0001  # Slight nudge off the singularity at M=1.0

class IEC60255Curves:
    """
    IEC 60255 inverse time curves for overcurrent relays.
    """

    @staticmethod
    def standard_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Standard inverse curve.
        t = TMS * (0.14 / ((I/Ip)^0.02 - 1))
        """
        if Ip > I:
            return float("inf")
        M = I / Ip if Ip != I else _IEC_CURVE_EPSILON
        return TMS * (0.14 / (M ** 0.02 - 1))

    @staticmethod
    def very_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Very inverse curve.
        t = TMS * (13.5 / ((I/Ip) - 1))
        """
        if Ip > I:
            return float("inf")
        M = I / Ip if Ip != I else _IEC_CURVE_EPSILON
        return TMS * (13.5 / (M - 1))

    @staticmethod
    def extremely_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Extremely inverse curve.
        t = TMS * (80 / ((I/Ip)^2 - 1))
        """
        if Ip > I:
            return float("inf")
        M = I / Ip if Ip != I else _IEC_CURVE_EPSILON
        return TMS * (80 / (M ** 2 - 1))

    @staticmethod
    def long_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Long inverse curve (UK).
        t = TMS * (120 / ((I/Ip) - 1))
        """
        if Ip > I:
            return float("inf")
        M = I / Ip if Ip != I else _IEC_CURVE_EPSILON
        return TMS * (120 / (M - 1))
