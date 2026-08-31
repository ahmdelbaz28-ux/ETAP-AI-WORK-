import { LangWatch } from 'langwatch';
import fs from 'node:fs';
import path from 'node:path';
import yaml from 'js-yaml';

const langwatch = new LangWatch({
  apiKey: process.env.LANGWATCH_API_KEY,
});

type PromptMessage = {
  role?: string;
  content?: unknown;
};

type LangWatchPrompt = {
  prompt?: string;
  messages?: PromptMessage[];
};

function stringifyContent(content: unknown): string {
  if (typeof content === 'string') {
    return content;
  }

  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === 'string') {
          return part;
        }
        if (part && typeof part === 'object' && 'text' in part) {
          return String((part as { text: unknown }).text);
        }
        return '';
      })
      .filter(Boolean)
      .join('\n');
  }

  return '';
}

/**
 * Parse YAML content using the standard js-yaml library.
 *
 * Replaces the previous hand-rolled YAML parser (parseSimpleYaml) that
 * diverged from Python's yaml.safe_load on edge cases. js-yaml is the
 * canonical Node.js YAML parser and matches PyYAML's behavior on
 * the prompt-file structures used by this project.
 */
function parseYaml(content: string): Record<string, unknown> {
  const result = yaml.load(content);
  if (result === null || typeof result !== 'object' || Array.isArray(result)) {
    return {};
  }
  return result as Record<string, unknown>;
}

/**
 * Load a value (messages or prompt string) from a parsed YAML prompt structure.
 */
function extractSystemMessage(parsed: Record<string, unknown>): string | null {
  const messages = parsed.messages;
  if (Array.isArray(messages)) {
    const msgList = messages as PromptMessage[];
    const systemMessage = msgList.find((m) => m.role === 'system');
    if (systemMessage?.content) {
      return stringifyContent(systemMessage.content).trim();
    }
  }

  const promptText = parsed.prompt;
  if (typeof promptText === 'string' && promptText.trim()) {
    return promptText.trim();
  }

  return null;
}

/**
 * Load prompt from local YAML file as fallback when LangWatch API is unavailable.
 */
function loadLocalPrompt(handle: string): string | null {
  try {
    const promptsDir = path.join(process.cwd(), 'prompts');

    // Manifest-first: prompts.json binds each handle to its canonical file
    // (e.g. etap_engineer_agent -> v2), so consult it BEFORE the filename-
    // pattern fallback, which can silently resolve to a stale same-named file.
    const manifestPath = path.join(process.cwd(), 'prompts.json');
    if (fs.existsSync(manifestPath)) {
      try {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8')) as {
          prompts?: Record<string, string>;
        };
        let mapped: string | undefined = manifest.prompts?.[handle];
        if (mapped && mapped.startsWith('file:')) {
          mapped = mapped.slice(5);
        }
        if (mapped) {
          const manifestFilePath = path.join(process.cwd(), mapped);
          if (fs.existsSync(manifestFilePath)) {
            const content = fs.readFileSync(manifestFilePath, 'utf-8');
            const parsed = parseYaml(content);
            const systemMsg = extractSystemMessage(parsed);
            if (systemMsg) {
              return systemMsg;
            }
          }
        }
      } catch {
        // Malformed manifest — fall through to filename patterns.
      }
    }

    const possibleFiles = [`${handle}.yaml`, `${handle}.prompt.yaml`];

    for (const filename of possibleFiles) {
      const filePath = path.join(promptsDir, filename);
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        const parsed = parseYaml(content);
        const systemMsg = extractSystemMessage(parsed);
        if (systemMsg) {
          return systemMsg;
        }
      }
    }

    const promptsJsonPath = path.join(process.cwd(), 'prompts.json');
    if (fs.existsSync(promptsJsonPath)) {
      const promptsJson = JSON.parse(fs.readFileSync(promptsJsonPath, 'utf-8'));
      const promptPath = promptsJson.prompts?.[handle];
      if (promptPath && typeof promptPath === 'string') {
        const actualPath = promptPath.startsWith('file:') ? promptPath.substring(5) : promptPath;
        const fullPath = path.join(process.cwd(), actualPath);
        if (fs.existsSync(fullPath)) {
          const content = fs.readFileSync(fullPath, 'utf-8');
          const parsed = parseYaml(content);
          const systemMsg = extractSystemMessage(parsed);
          if (systemMsg) {
            return systemMsg;
          }
        }
      }
    }

    return null;
  } catch (e) {
    console.warn(`[Prompts] Error loading local prompt "${handle}":`, e);
    return null;
  }
}

/**
 * Try to fetch the system prompt from LangWatch.
 * Returns the trimmed prompt string, or null if unavailable / empty.
 */
async function getLangWatchPrompt(handle: string): Promise<string | null> {
  if (process.env.DEPLOYMENT_VERIFICATION === 'true') {
    return null;
  }
  try {
    const prompt = (await langwatch.prompts.get(handle)) as LangWatchPrompt | null | undefined;
    if (!prompt) return null;

    if (prompt.prompt?.trim()) {
      return prompt.prompt.trim();
    }
    const systemMessage = prompt.messages?.find((message) => message.role === 'system');
    const systemContent = stringifyContent(systemMessage?.content).trim();
    return systemContent || null;
  } catch (e) {
    console.warn(`[Prompts] LangWatch API unavailable, using local fallback for "${handle}":`, e instanceof Error ? e.message : String(e));
    return null;
  }
}

export async function getSystemPrompt(handle: string): Promise<string> {
  const langwatchPrompt = await getLangWatchPrompt(handle);
  if (langwatchPrompt) {
    return langwatchPrompt;
  }

  const localPrompt = loadLocalPrompt(handle);
  if (localPrompt) {
    return localPrompt;
  }

  const fallbackPrompt = loadLocalPrompt('fallback_agent');
  if (fallbackPrompt) {
    return fallbackPrompt;
  }

  return `You are a safety-net fallback AI assistant for power systems engineering. Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations.`;
}
