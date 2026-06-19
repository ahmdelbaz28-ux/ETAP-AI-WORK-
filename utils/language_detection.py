# =============================================================================
# Language Detection & Auto-Correction Utility
# =============================================================================
"""
Utility for detecting input language and converting keyboard layouts.
Supports Arabic-to-English keyboard layout conversion for non-English input.
"""

import os
import re
from typing import Optional, Dict, Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AUTO_CORRECT_LANGUAGE = os.getenv("AUTO_CORRECT_LANGUAGE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Arabic to English Keyboard Layout Mapping
# ---------------------------------------------------------------------------
# This mapping converts Arabic keyboard layout characters to their
# corresponding English QWERTY equivalents
ARABIC_TO_ENGLISH_KEYBOARD_MAP: Dict[str, str] = {
    # Arabic letters that map to English letters when typed on Arabic keyboard
    "ض": "q",
    "ص": "w",
    "ث": "e",
    "ق": "r",
    "ف": "t",
    "غ": "y",
    "ع": "u",
    "ه": "i",
    "خ": "o",
    "ح": "p",
    "ج": "[",
    "د": "]",
    "ش": "a",
    "س": "s",
    "ي": "d",
    "ب": "f",
    "ل": "g",
    "ا": "h",
    "ت": "j",
    "ن": "k",
    "م": "l",
    "ك": ";",
    "ط": "'",
    "ئ": "z",
    "ء": "x",
    "ظ": "c",
    "و": "v",
    "ر": "b",
    "ى": "n",
    "ة": "m",
    "،": ",",
    ".