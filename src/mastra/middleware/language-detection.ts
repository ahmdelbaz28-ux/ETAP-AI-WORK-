/**
 * Language Detection & Auto-Correction Middleware
<<<<<<< HEAD
 *
=======
 * 
>>>>>>> origin/fix/scenario-tests-properly
 * Middleware for detecting input language and converting keyboard layouts
 * in the Mastra TypeScript runtime.
 */

// Type aliases for Mastra middleware compatibility across versions.
// In @mastra/core 0.x these were exported as `AgentContext` and `NextFunction`.
// In 1.x the middleware signature uses generic `Record<string, unknown>` contexts.
// We define permissive local types so the middleware compiles on both lines.
type AgentContext = {
  input?: unknown;
  messages?: unknown;
  [key: string]: unknown;
};
<<<<<<< HEAD
type NextFunction = () => Promise<unknown>;
=======
type NextFunction = () => Promise<unknown> | unknown;
>>>>>>> origin/fix/scenario-tests-properly

// ===========================================================================
// Configuration
// ===========================================================================

interface LanguageDetectionConfig {
  enabled: boolean;
  confidenceThreshold: number;
  autoCorrect: boolean;
}

const DEFAULT_CONFIG: LanguageDetectionConfig = {
  enabled: true,
  confidenceThreshold: 0.5,
  autoCorrect: true,
};

let config: LanguageDetectionConfig = { ...DEFAULT_CONFIG };

// ===========================================================================
// Arabic to English Keyboard Layout Mapping
// ===========================================================================

const ARABIC_TO_ENGLISH_KEYBOARD_MAP: Record<string, string> = {
  // Arabic letters that map to English letters when typed on Arabic keyboard
<<<<<<< HEAD
  ض: 'q',
  ص: 'w',
  ث: 'e',
  ق: 'r',
  ف: 't',
  غ: 'y',
  ع: 'u',
  ه: 'i',
  خ: 'o',
  ح: 'p',
  ج: '[',
  د: ']',
  ش: 'a',
  س: 's',
  ي: 'd',
  ب: 'f',
  ل: 'g',
  ا: 'h',
  ت: 'j',
  ن: 'k',
  م: 'l',
  ك: ';',
  ط: "'",
  ئ: 'z',
  ء: 'x',
  ظ: 'c',
  و: 'v',
  ر: 'b',
  ى: 'n',
  ة: 'm',
=======
  'ض': 'q',
  'ص': 'w',
  'ث': 'e',
  'ق': 'r',
  'ف': 't',
  'غ': 'y',
  'ع': 'u',
  'ه': 'i',
  'خ': 'o',
  'ح': 'p',
  'ج': '[',
  'د': ']',
  'ش': 'a',
  'س': 's',
  'ي': 'd',
  'ب': 'f',
  'ل': 'g',
  'ا': 'h',
  'ت': 'j',
  'ن': 'k',
  'م': 'l',
  'ك': ';',
  'ط': "'",
  'ئ': 'z',
  'ء': 'x',
  'ظ': 'c',
  'و': 'v',
  'ر': 'b',
  'ى': 'n',
  'ة': 'm',
>>>>>>> origin/fix/scenario-tests-properly
  '،': ',',
  '.': '.',
  // Numbers (Arabic numerals to English)
  '٠': '0',
  '١': '1',
  '٢': '2',
  '٣': '3',
  '٤': '4',
  '٥': '5',
  '٦': '6',
  '٧': '7',
  '٨': '8',
  '٩': '9',
  // Common punctuation
  '؟': '?',
  '!': '!',
  '-': '-',
<<<<<<< HEAD
  _: '_',
=======
  '_': '_',
>>>>>>> origin/fix/scenario-tests-properly
  ' ': ' ',
  '\t': '\t',
  '\n': '\n',
};

const ENGLISH_TO_ARABIC_KEYBOARD_MAP: Record<string, string> = Object.fromEntries(
<<<<<<< HEAD
  Object.entries(ARABIC_TO_ENGLISH_KEYBOARD_MAP).map(([k, v]) => [v, k]),
=======
  Object.entries(ARABIC_TO_ENGLISH_KEYBOARD_MAP).map(([k, v]) => [v, k])
>>>>>>> origin/fix/scenario-tests-properly
);

// ===========================================================================
// Language Detection
// ===========================================================================

/**
 * Common Arabic characters for fallback detection
 */
const ARABIC_CHARACTERS = new Set(Object.keys(ARABIC_TO_ENGLISH_KEYBOARD_MAP));

/**
 * Common Arabic words for fallback detection
 */
const ARABIC_WORDS = new Set([
<<<<<<< HEAD
  'ال',
  'و',
  'في',
  'من',
  'إلى',
  'على',
  'أن',
  'لا',
  'ما',
  'هذا',
  'ب',
  'ك',
  'ل',
  'م',
  'ه',
  'س',
  'ف',
  'ي',
  'ت',
  'ن',
=======
  'ال', 'و', 'في', 'من', 'إلى', 'على', 'أن', 'لا', 'ما', 'هذا',
  'ب', 'ك', 'ل', 'م', 'ه', 'س', 'ف', 'ي', 'ت', 'ن'
>>>>>>> origin/fix/scenario-tests-properly
]);

/**
 * Check if text contains Arabic characters
 */
<<<<<<< HEAD
function _hasArabicCharacters(text: string): boolean {
  return Array.from(text).some((char) => ARABIC_CHARACTERS.has(char));
=======
function hasArabicCharacters(text: string): boolean {
  return Array.from(text).some(char => ARABIC_CHARACTERS.has(char));
>>>>>>> origin/fix/scenario-tests-properly
}

/**
 * Check if text contains common Arabic words
 */
function hasArabicWords(text: string): boolean {
  const textLower = text.toLowerCase();
<<<<<<< HEAD
  return Array.from(ARABIC_WORDS).some((word) => textLower.includes(word));
=======
  return Array.from(ARABIC_WORDS).some(word => textLower.includes(word));
>>>>>>> origin/fix/scenario-tests-properly
}

/**
 * Estimate confidence that text is Arabic (0.0 to 1.0)
 */
function estimateArabicConfidence(text: string): number {
  if (!text || text.trim().length === 0) {
<<<<<<< HEAD
    return 0.0; // NOSONAR — S7748: number literal trailing zero; cosmetic
  }

  const arabicChars = Array.from(text).filter((char) => ARABIC_CHARACTERS.has(char)).length;
  const totalChars = text.length;

  if (totalChars === 0) {
    return 0.0; // NOSONAR — S7748: number literal trailing zero; cosmetic
=======
    return 0.0;
  }

  const arabicChars = Array.from(text).filter(char => ARABIC_CHARACTERS.has(char)).length;
  const totalChars = text.length;

  if (totalChars === 0) {
    return 0.0;
>>>>>>> origin/fix/scenario-tests-properly
  }

  const arabicRatio = arabicChars / totalChars;

  // If more than 30% of characters are Arabic, high confidence
  if (arabicRatio > 0.3) {
<<<<<<< HEAD
    return Math.min(1.0, arabicRatio * 1.5); // NOSONAR — S7748: number literal trailing zero; cosmetic
=======
    return Math.min(1.0, arabicRatio * 1.5);
>>>>>>> origin/fix/scenario-tests-properly
  }

  // Check for Arabic words
  if (hasArabicWords(text)) {
    return 0.7;
  }

  return arabicRatio;
}

/**
 * Try to import franc for better language detection
 * Note: This is a placeholder - in practice, you'd need to dynamically import
 */
<<<<<<< HEAD
const franc: ((text: string) => string | undefined) | null = null;
=======
let franc: ((text: string) => string | undefined) | null = null;
>>>>>>> origin/fix/scenario-tests-properly

try {
  // Dynamic import would be used in actual implementation
  // import('franc').then(mod => franc = mod.default);
  // For now, we'll use our fallback
} catch {
  // franc not available, use fallback
}

/**
 * Detect the language of the input text
 */
export function detectLanguage(text: string): string | null {
<<<<<<< HEAD
  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
=======
>>>>>>> origin/fix/scenario-tests-properly
  if (!text || text.trim().length === 0) {
    return null;
  }

  // Try franc first if available
  if (franc) {
    try {
      const lang = franc(text);
      if (lang) {
        // franc returns ISO 639-3 codes, 'ara' for Arabic, 'eng' for English
        if (lang.startsWith('ara')) return 'ar';
        if (lang.startsWith('eng')) return 'en';
        // Map other common codes
        if (lang === 'ara') return 'ar';
        if (lang === 'eng') return 'en';
      }
    } catch {
      // Fall through to fallback
    }
  }

  // Fallback: use our simple detection
  const confidence = estimateArabicConfidence(text);
  if (confidence >= config.confidenceThreshold) {
    return 'ar';
  }

  // Default to English if we can't detect Arabic
  return 'en';
}

/**
 * Check if text is likely Arabic
 */
<<<<<<< HEAD
export function isArabicText(
  text: string,
  confidenceThreshold: number = config.confidenceThreshold,
): boolean {
=======
export function isArabicText(text: string, confidenceThreshold: number = config.confidenceThreshold): boolean {
>>>>>>> origin/fix/scenario-tests-properly
  const lang = detectLanguage(text);
  if (lang === 'ar') {
    return true;
  }

  // Fallback check
  return estimateArabicConfidence(text) >= confidenceThreshold;
}

// ===========================================================================
// Keyboard Layout Conversion
// ===========================================================================

/**
 * Convert text from one keyboard layout to another
 */
export function convertKeyboardLayout(
  text: string,
  fromLayout: string = 'arabic',
<<<<<<< HEAD
  toLayout: string = 'english',
=======
  toLayout: string = 'english'
>>>>>>> origin/fix/scenario-tests-properly
): string {
  if (!text) {
    return text;
  }

  // Normalize layout names
  fromLayout = fromLayout.toLowerCase().trim();
  toLayout = toLayout.toLowerCase().trim();

  // If same layout, return as-is
  if (fromLayout === toLayout) {
    return text;
  }

  // Arabic to English
  if (fromLayout === 'arabic' && toLayout === 'english') {
    return Array.from(text)
<<<<<<< HEAD
      .map((char) => ARABIC_TO_ENGLISH_KEYBOARD_MAP[char] || char)
=======
      .map(char => ARABIC_TO_ENGLISH_KEYBOARD_MAP[char] || char)
>>>>>>> origin/fix/scenario-tests-properly
      .join('');
  }

  // English to Arabic
  if (fromLayout === 'english' && toLayout === 'arabic') {
    return Array.from(text)
<<<<<<< HEAD
      .map((char) => ENGLISH_TO_ARABIC_KEYBOARD_MAP[char] || char)
=======
      .map(char => ENGLISH_TO_ARABIC_KEYBOARD_MAP[char] || char)
>>>>>>> origin/fix/scenario-tests-properly
      .join('');
  }

  // Unsupported conversion
  return text;
}

// ===========================================================================
// Input Normalization
// ===========================================================================

/**
 * Normalize input text by detecting language and converting keyboard layout
 */
<<<<<<< HEAD
export function normalizeInput(text: string, autoCorrect: boolean = config.autoCorrect): string {
=======
export function normalizeInput(
  text: string,
  autoCorrect: boolean = config.autoCorrect
): string {
>>>>>>> origin/fix/scenario-tests-properly
  if (!text) {
    return text;
  }

  // Check if auto-correction is enabled
  if (!autoCorrect || !config.enabled) {
    return text;
  }

  // Check if text is Arabic
  if (isArabicText(text)) {
    // Convert from Arabic keyboard layout to English
    return convertKeyboardLayout(text, 'arabic', 'english');
  }

  // Return as-is if not Arabic
  return text;
}

/**
 * Normalize input for API usage (handles objects and arrays)
 */
export function normalizeInputForAPI(
  input: unknown,
<<<<<<< HEAD
  autoCorrect: boolean = config.autoCorrect,
=======
  autoCorrect: boolean = config.autoCorrect
>>>>>>> origin/fix/scenario-tests-properly
): unknown {
  if (input === null || input === undefined) {
    return input;
  }

  if (typeof input === 'string') {
    return normalizeInput(input, autoCorrect);
  }

  if (typeof input === 'object') {
    if (Array.isArray(input)) {
<<<<<<< HEAD
      return input.map((item) => normalizeInputForAPI(item, autoCorrect));
    }

=======
      return input.map(item => normalizeInputForAPI(item, autoCorrect));
    }
    
>>>>>>> origin/fix/scenario-tests-properly
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(input)) {
      result[key] = normalizeInputForAPI(value, autoCorrect);
    }
    return result;
  }

  return input;
}

// ===========================================================================
// Middleware
// ===========================================================================

/**
 * Language detection middleware for Mastra agents
 * This middleware normalizes the user's input before it reaches the agent
 */
<<<<<<< HEAD
export async function languageDetectionMiddleware(context: AgentContext, next: NextFunction) {
=======
export async function languageDetectionMiddleware(
  context: AgentContext,
  next: NextFunction
) {
>>>>>>> origin/fix/scenario-tests-properly
  // Normalize the user's input
  if (context.input && typeof context.input === 'string') {
    context.input = normalizeInput(context.input);
  } else if (context.input && typeof context.input === 'object') {
    context.input = normalizeInputForAPI(context.input) as any;
  }

  // Continue to the next middleware/agent
  return next();
}

// ===========================================================================
// Configuration
// ===========================================================================

/**
 * Configure the language detection middleware
 */
<<<<<<< HEAD
export function configureLanguageDetection(options: Partial<LanguageDetectionConfig> = {}): void {
=======
export function configureLanguageDetection(
  options: Partial<LanguageDetectionConfig> = {}
): void {
>>>>>>> origin/fix/scenario-tests-properly
  config = {
    ...config,
    ...options,
  };
}

/**
 * Get current configuration
 */
export function getLanguageDetectionConfig(): LanguageDetectionConfig {
  return { ...config };
}

/**
 * Enable or disable language detection
 */
export function setLanguageDetectionEnabled(enabled: boolean): void {
  config.enabled = enabled;
}

/**
 * Check if language detection is enabled
 */
export function isLanguageDetectionEnabled(): boolean {
  return config.enabled;
}

// ===========================================================================
// Test Helpers
// ===========================================================================

/**
 * Run basic tests for language detection
 */
export function testLanguageDetection(): {
  testsPassed: number;
  testsFailed: number;
  details: Array<{
    test: string;
    status: 'passed' | 'failed';
    expected?: string;
    got?: string;
    result?: string;
  }>;
} {
  const results = {
    testsPassed: 0,
    testsFailed: 0,
    details: [] as Array<{
      test: string;
      status: 'passed' | 'failed';
      expected?: string;
      got?: string;
      result?: string;
    }>,
  };

  // Test Arabic detection
  const arabicText = 'قم بتنفيذ هذه المهمة';
  const detectedArabic = detectLanguage(arabicText);
  if (detectedArabic === 'ar') {
    results.testsPassed++;
    results.details.push({ test: 'Arabic detection', status: 'passed' });
  } else {
    results.testsFailed++;
    results.details.push({
      test: 'Arabic detection',
      status: 'failed',
      expected: 'ar',
      got: detectedArabic || 'null',
    });
  }

  // Test English detection
  const englishText = 'Execute this task';
  const detectedEnglish = detectLanguage(englishText);
  if (detectedEnglish === 'en') {
    results.testsPassed++;
    results.details.push({ test: 'English detection', status: 'passed' });
  } else {
    results.testsFailed++;
    results.details.push({
      test: 'English detection',
      status: 'failed',
      expected: 'en',
      got: detectedEnglish || 'null',
    });
  }

  // Test conversion
  const converted = convertKeyboardLayout(arabicText, 'arabic', 'english');
  if (converted && converted !== arabicText) {
    results.testsPassed++;
    results.details.push({
      test: 'Arabic to English conversion',
      status: 'passed',
      result: converted,
    });
  } else {
    results.testsFailed++;
    results.details.push({
      test: 'Arabic to English conversion',
      status: 'failed',
    });
  }

  // Test normalization
  const normalized = normalizeInput(arabicText);
  if (normalized && normalized !== arabicText) {
    results.testsPassed++;
    results.details.push({
      test: 'Input normalization',
      status: 'passed',
      result: normalized,
    });
  } else {
    results.testsFailed++;
    results.details.push({
      test: 'Input normalization',
      status: 'failed',
    });
  }

  return results;
}

// ===========================================================================
// Default Export
// ===========================================================================

export default {
  detectLanguage,
  isArabicText,
  convertKeyboardLayout,
  normalizeInput,
  normalizeInputForAPI,
  languageDetectionMiddleware,
  configureLanguageDetection,
  getLanguageDetectionConfig,
  setLanguageDetectionEnabled,
  isLanguageDetectionEnabled,
  testLanguageDetection,
};
