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
        if Ip >= I:
            return float("inf")
        return TMS * (0.14 / ((I / Ip) ** 0.02 - 1))

    @staticmethod
    def very_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Very inverse curve.
        t = TMS * (13.5 / ((I/Ip) - 1))
        """
        if Ip >= I:
            return float("inf")
        return TMS * (13.5 / ((I / Ip) - 1))

    @staticmethod
    def extremely_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Extremely inverse curve.
        t = TMS * (80 / ((I/Ip)^2 - 1))
        """
        if Ip >= I:
            return float("inf")
        return TMS * (80 / ((I / Ip) ** 2 - 1))

    @staticmethod
    def long_inverse(TMS, I, Ip):  # NOSONAR — S117: physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
        """
        Long inverse curve (UK).
        t = TMS * (120 / ((I/Ip) - 1))
        """
        if Ip >= I:
            return float("inf")
        return TMS * (120 / ((I / Ip) - 1))
