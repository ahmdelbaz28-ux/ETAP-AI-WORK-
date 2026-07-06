# =============================================================================
# Language Detection & Auto-Correction Utility
# =============================================================================
"""
Utility for detecting input language and converting keyboard layouts.
Supports Arabic-to-English keyboard layout conversion for non-English input.
"""

import contextlib
import os
from typing import TYPE_CHECKING

# Try to import langdetect for better language detection
try:
    from langdetect import detect

    HAS_LANGDETECT = True
except ImportError:
    HAS_LANGDETECT = False
    detect = None  # type: ignore
    print(
        "Warning: langdetect not installed. Install with 'pip install langdetect' for better language detection.",
    )

if TYPE_CHECKING or HAS_LANGDETECT and detect is not None:
    from langdetect import detect

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AUTO_CORRECT_LANGUAGE = os.getenv("AUTO_CORRECT_LANGUAGE", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Arabic to English Keyboard Layout Mapping
# ---------------------------------------------------------------------------
# This mapping converts Arabic keyboard layout characters to their
# corresponding English QWERTY equivalents
ARABIC_TO_ENGLISH_KEYBOARD_MAP: dict[str, str] = {
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
    ".": ".",
    "إ": "i",
    "أ": "a",
    "آ": "a",
    " ": " ",
    "1": "1",
    "2": "2",
    "3": "3",
    "4": "4",
    "5": "5",
    "6": "6",
    "7": "7",
    "8": "8",
    "9": "9",
    "0": "0",
    "-": "-",
    "=": "=",
    "\\": "\\",
    "/": "/",
    "*": "*",
    ")": ")",
    "(": "(",
}


def normalize_input(text: str) -> str:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """
    Normalize input text by converting Arabic keyboard layout to English.
    This is especially useful when users accidentally type in Arabic layout
    but mean to type in English.

    Args:
        text: Input text that may be in Arabic keyboard layout

    Returns:
        Normalized text with Arabic keyboard layout converted to English
    """
    if not AUTO_CORRECT_LANGUAGE:
        return text

    # First, check if the text has a high ratio of Arabic keyboard characters
    arabic_kb_chars = 0
    total_chars = len(text)

    for char in text:
        if char in ARABIC_TO_ENGLISH_KEYBOARD_MAP:
            arabic_kb_chars += 1

    # If more than 30% of characters are Arabic keyboard layout chars, convert them
    if total_chars > 0 and arabic_kb_chars / total_chars > 0.3:
        result = ""
        for char in text:
            if char in ARABIC_TO_ENGLISH_KEYBOARD_MAP:
                result += ARABIC_TO_ENGLISH_KEYBOARD_MAP[char]
            else:
                # If character is not in the mapping, keep it as is
                result += char
        return result

    # If not primarily Arabic keyboard layout, try language detection
    detected_lang = None
    if HAS_LANGDETECT:
        try:
            detected_lang = detect(text)
        except Exception:
            # If langdetect fails, fall back to manual detection
            detected_lang = None

    # If langdetect detected Arabic, convert keyboard layout
    if detected_lang == "ar":
        result = ""
        for char in text:
            if char in ARABIC_TO_ENGLISH_KEYBOARD_MAP:
                result += ARABIC_TO_ENGLISH_KEYBOARD_MAP[char]
            else:
                # If character is not in the mapping, keep it as is
                result += char
        return result

    # Otherwise, return the text as-is
    return text


def is_arabic_text(text: str) -> bool:
    """
    Simple heuristic to check if text is likely Arabic.

    Args:
        text: Input text to analyze

    Returns:
        True if text appears to be Arabic, False otherwise
    """
    arabic_chars = 0
    total_alpha = 0

    for char in text:
        if char.isalpha():
            total_alpha += 1
            if "\u0600" <= char <= "\u06ff":  # Arabic Unicode block
                arabic_chars += 1

    if total_alpha == 0:
        return False

    # If more than 30% of alphabetic characters are Arabic, consider it Arabic
    return arabic_chars / total_alpha > 0.3


def detect_language(text: str) -> str:  # NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
    """
    Detect the likely language of input text based on character sets.

    Args:
        text: Input text to analyze

    Returns:
        Detected language ('arabic', 'english', or 'mixed')
    """
    if HAS_LANGDETECT:
        # Fall back to simple character-based detection on any failure
        with contextlib.suppress(Exception):
            lang = detect(text)
            if lang == "ar":
                return "arabic"
            elif lang == "en":
                return "english"
            else:
                return lang

    arabic_chars = 0
    english_chars = 0

    for char in text:
        if "\u0600" <= char <= "\u06ff":  # Arabic Unicode block
            arabic_chars += 1
        elif char.isalpha() and char <= "\u017f":  # Basic Latin characters
            english_chars += 1

    total_alpha = arabic_chars + english_chars

    if total_alpha == 0:
        return "unknown"
    elif arabic_chars / total_alpha > 0.5:
        return "arabic"
    elif english_chars / total_alpha > 0.5:
        return "english"
    else:
        return "mixed"


def convert_arabic_to_english(text: str) -> str:
    """
    Convert Arabic keyboard layout input to English equivalent.

    Args:
        text: Text typed using Arabic keyboard layout

    Returns:
        Converted text as it would appear if typed using English layout
    """
    result = ""
    for char in text:
        result += ARABIC_TO_ENGLISH_KEYBOARD_MAP.get(char, char)
    return result
