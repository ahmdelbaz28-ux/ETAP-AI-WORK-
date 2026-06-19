#!/usr/bin/env python3
"""
Simple test script to verify matplotlib import works correctly.
"""

try:
    import matplotlib.pyplot as plt
    import numpy as np
    print("SUCCESS: matplotlib.pyplot imported successfully!")
    print(f"Matplotlib version: {plt.matplotlib.__version__}")
    
    # Test basic functionality
    x = np.linspace(0, 10, 100)
    y = np.sin(x)
    print("SUCCESS: Basic numpy/matplotlib functionality works!")
    
except ImportError as e:
    print(f"ERROR: Import failed - {e}")
except Exception as e:
    print(f"ERROR: Other error occurred - {e}")