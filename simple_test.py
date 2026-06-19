#!/usr/bin/env python3
"""
Simple test script to verify matplotlib import works correctly.
"""

try:
    import matplotlib
    print("SUCCESS: matplotlib imported successfully!")
    print(f"Matplotlib version: {matplotlib.__version__}")
    
    import matplotlib.pyplot as plt
    print("SUCCESS: matplotlib.pyplot imported successfully!")
    
    # Check if we can create a basic figure object without displaying it
    fig = plt.figure()
    print("SUCCESS: matplotlib functionality works!")
    
    # Clean up
    plt.close(fig)
    
except ImportError as e:
    print(f"ERROR: Import failed - {e}")
except Exception as e:
    print(f"ERROR: Other error occurred - {e}")