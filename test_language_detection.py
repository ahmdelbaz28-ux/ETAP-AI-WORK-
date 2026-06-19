#!/usr/bin/env python3
"""
Test script to verify language detection and normalization functionality.
"""

try:
    from utils.language_detection import normalize_input, detect_language, is_arabic_text
    print("SUCCESS: Language detection utilities imported successfully!")
    
    # Test cases
    test_cases = [
        {
            "input": "ضصث قم بتشغيل التحليل",
            "description": "Arabic text typed on Arabic keyboard (should be converted)"
        },
        {
            "input": "Run load flow analysis",
            "description": "English text (should remain unchanged)"
        },
        {
            "input": "شغّل_fault_analysis",
            "description": "Mixed content with Arabic keyboard layout"
        },
        {
            "input": "Execute short circuit",
            "description": "Pure English text"
        }
    ]
    
    print("\nTesting language detection and normalization:")
    print("="*60)
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {case['description']}")
        print(f"Input:  '{case['input']}'")
        
        # Detect language
        detected_lang = detect_language(case['input'])
        print(f"Detected language: {detected_lang}")
        
        # Check if Arabic
        is_arabic = is_arabic_text(case['input'])
        print(f"Is Arabic text: {is_arabic}")
        
        # Normalize input
        normalized = normalize_input(case['input'])
        print(f"Output: '{normalized}'")
        
        if case['input'] != normalized:
            print("✓ Input was normalized!")
        else:
            print("- Input remained unchanged")
    
    print("\n" + "="*60)
    print("Language detection functionality test completed!")

except ImportError as e:
    print(f"ERROR: Import failed - {e}")
except Exception as e:
    print(f"ERROR: Other error occurred - {e}")