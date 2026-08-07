import numpy as np


<<<<<<< HEAD
def zbus_from_ybus(
    ybus,
    reference_bus=0,
):  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
=======
def zbus_from_ybus(Ybus, reference_bus=0):
>>>>>>> origin/fix/scenario-tests-properly
    """
    Compute Zbus matrix from Ybus by inverting the reduced Ybus matrix.

    Parameters:
    Ybus (numpy.ndarray): Complex admittance matrix (n x n).
    reference_bus (int): Index of the reference bus to remove (default 0).

    Returns:
    numpy.ndarray: Complex impedance matrix (Zbus) of size (n-1 x n-1).
    """
    # Remove the reference bus row and column
<<<<<<< HEAD
    y_reduced = np.delete(
        np.delete(ybus, reference_bus, axis=0), reference_bus, axis=1
    )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    # Compute the inverse
    try:
        z_reduced = np.linalg.inv(
            y_reduced
        )  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
    except np.linalg.LinAlgError:
        # If singular, use pseudo-inverse
        z_reduced = np.linalg.pinv(y_reduced)
    # Expand back to full size if needed, but we return reduced for now
    return z_reduced


def zbus_full(
    ybus,
):  # NOSONAR physics/engineering notation (I=current, V=voltage, P/Q=power, Ybus/Zbus matrices); snake_case would harm domain readability
=======
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
>>>>>>> origin/fix/scenario-tests-properly
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
<<<<<<< HEAD
        return np.linalg.inv(ybus)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(ybus)
=======
        return np.linalg.inv(Ybus)
    except np.linalg.LinAlgError:
        return np.linalg.pinv(Ybus)
>>>>>>> origin/fix/scenario-tests-properly
