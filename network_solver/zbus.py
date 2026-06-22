import numpy as np


def zbus_from_ybus(Ybus, reference_bus=0):
    """
    Compute Zbus matrix from Ybus by inverting the reduced Ybus matrix.

    Parameters:
    Ybus (numpy.ndarray): Complex admittance matrix (n x n).
    reference_bus (int): Index of the reference bus to remove (default 0).

    Returns:
    numpy.ndarray: Complex impedance matrix (Zbus) of size (n-1 x n-1).
    """
    # Remove the reference bus row and column
    Y_reduced = np.delete(np.delete(Ybus, reference_bus, axis=0), reference_bus, axis=1)
    # Compute the inverse
    try:
        Z_reduced = np.linalg.inv(Y_reduced)
    except np.linalg.LinAlgError:
        # If singular, use pseudo-inverse
        Z_reduced = np.linalg.pinv(Y_reduced)
    # Expand back to full size if needed, but we return reduced for now
    return Z_reduced


def zbus_full(Ybus):
    """
    Compute Zbus by inverting the full Ybus matrix.
    Note: This may fail if Ybus is singular (which it is if there is no reference).
    Use with caution.

    Parameters:
    Ybus (numpy.ndarray): Complex admittance matrix (n x n).

    Returns:
    numpy.ndarray: Complex impedance matrix (Zbus) of size (n x n) or pseudo-inverse.
    """
    try:
        return np.linalg.inv(Ybus)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(Ybus)
