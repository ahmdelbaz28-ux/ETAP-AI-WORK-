import numpy as np

class IEC60255Curves:
    """
    IEC 60255 inverse time curves for overcurrent relays.
    """
    @staticmethod
    def standard_inverse(TMS, I, Ip):
        """
        Standard inverse curve.
        t = TMS * (0.14 / ((I/Ip)^0.02 - 1))
        """
        if I <= Ip:
            return float('inf')
        return TMS * (0.14 / ((I/Ip)**0.02 - 1))

    @staticmethod
    def very_inverse(TMS, I, Ip):
        """
        Very inverse curve.
        t = TMS * (13.5 / ((I/Ip) - 1))
        """
        if I <= Ip:
            return float('inf')
        return TMS * (13.5 / ((I/Ip) - 1))

    @staticmethod
    def extremely_inverse(TMS, I, Ip):
        """
        Extremely inverse curve.
        t = TMS * (80 / ((I/Ip)^2 - 1))
        """
        if I <= Ip:
            return float('inf')
        return TMS * (80 / ((I/Ip)**2 - 1))

    @staticmethod
    def long_inverse(TMS, I, Ip):
        """
        Long inverse curve (UK).
        t = TMS * (120 / ((I/Ip) - 1))
        """
        if I <= Ip:
            return float('inf')
        return TMS * (120 / ((I/Ip) - 1))
