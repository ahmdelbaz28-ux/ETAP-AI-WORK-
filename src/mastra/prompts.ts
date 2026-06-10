import { LangWatch } from 'langwatch';
import fs from 'fs';
import path from 'path';

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
 * Simple YAML parser for basic prompt structures (avoids import issues in ESM)
 */
function parseSimpleYaml(content: string): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const lines = content.split('\n');
  let currentKey = '';
  let currentMessages: PromptMessage[] = [];
  let inMessages = false;
  let currentMessageRole = '';
  let currentMessageContent = '';
  
  for (const line of lines) {
    if (line.startsWith('messages:')) {
      inMessages = true;
      continue;
    }
    if (inMessages && line.match(/^\s+- role:/)) {
      if (currentMessageRole && currentMessageContent) {
        currentMessages.push({ role: currentMessageRole, content: currentMessageContent.trim() });
      }
      currentMessageRole = line.split(':')[1]?.trim().replace(/"/g, '') || '';
      currentMessageContent = '';
    } else if (inMessages && line.match(/^\s+content:/)) {
      currentMessageContent = line.substring(line.indexOf(':') + 1).trim().replace(/^|\n/g, '').replace(/\|$/,'');
    } else if (inMessages && line.match(/^\s{4}/) && currentMessageRole) {
      currentMessageContent += '\n' + line.trim();
    } else if (line.match(/^\S+:/) && !line.startsWith('messages')) {
      inMessages = false;
      if (currentKey === 'prompt' && currentMessageContent) {
        result[currentKey] = currentMessageContent;
      }
      const [key, value] = line.split(':');
      currentKey = key.trim();
      const val = value?.trim().replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1');
      if (currentKey && val) {
        result[currentKey] = val;
      }
    }
  }
  
  if (inMessages && currentMessageRole && currentMessageContent) {
    currentMessages.push({ role: currentMessageRole, content: currentMessageContent.trim() });
  }
  
  if (currentMessages.length > 0) {
    result.messages = currentMessages;
  }
  
  return result;
}

/**
 * Load prompt from local YAML file as fallback when LangWatch API is unavailable.
 */
function loadLocalPrompt(handle: string): string | null {
  try {
    const promptsDir = path.join(process.cwd(), 'prompts');
    // Try different filename patterns
    const possibleFiles = [
      `${handle}.yaml`,
      `${handle}.prompt.yaml`,
      `${handle.replace(/_/g, '_')}_agent.prompt.yaml`,
    ];
    
    for (const filename of possibleFiles) {
      const filePath = path.join(promptsDir, filename);
      if (fs.existsSync(filePath)) {
        const content = fs.readFileSync(filePath, 'utf-8');
        const parsed = parseSimpleYaml(content);
        
        // Look for system message in messages array
        if (Array.isArray(parsed?.messages)) {
          const messages = parsed.messages as PromptMessage[];
          const systemMessage = messages.find((m) => m.role === 'system');
          if (systemMessage?.content) {
            return stringifyContent(systemMessage.content);
          }
        }
        
        // Or use prompt field directly
        if (typeof parsed?.prompt === 'string' && parsed.prompt.trim()) {
          return parsed.prompt.trim();
        }
      }
    }
    
    // Try reading prompts.json to find exact mapping
    const promptsJsonPath = path.join(process.cwd(), 'prompts.json');
    if (fs.existsSync(promptsJsonPath)) {
      const promptsJson = JSON.parse(fs.readFileSync(promptsJsonPath, 'utf-8'));
      const promptPath = promptsJson.prompts?.[handle];
      if (promptPath && typeof promptPath === 'string') {
        const actualPath = promptPath.startsWith('file:') ? promptPath.substring(5) : promptPath;
        const fullPath = path.join(process.cwd(), actualPath);
        if (fs.existsSync(fullPath)) {
          const content = fs.readFileSync(fullPath, 'utf-8');
          const parsed = parseSimpleYaml(content);
          if (Array.isArray(parsed?.messages)) {
            const messages = parsed.messages as PromptMessage[];
            const systemMessage = messages.find((m) => m.role === 'system');
            if (systemMessage?.content) {
              return stringifyContent(systemMessage.content);
            }
          }
          if (typeof parsed?.prompt === 'string' && parsed.prompt.trim()) {
            return parsed.prompt.trim();
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

export async function getSystemPrompt(handle: string): Promise<string> {
  // Try LangWatch first (unless we're in deployment verification mode)
  if (process.env.DEPLOYMENT_VERIFICATION !== 'true') {
    try {
      const prompt = (await langwatch.prompts.get(handle)) as LangWatchPrompt | null | undefined;
      if (prompt) {
        if (prompt.prompt?.trim()) {
          return prompt.prompt.trim();
        }
        const systemMessage = prompt.messages?.find((message) => message.role === 'system');
        const systemContent = stringifyContent(systemMessage?.content).trim();
        if (systemContent) {
          return systemContent;
        }
      }
    } catch (e) {
      // LangWatch API unavailable, fall back to local prompt
      console.warn(`[Prompts] LangWatch API unavailable, using local fallback for "${handle}"`);
    }
  }
  
  // Fall back to local YAML file
  const localPrompt = loadLocalPrompt(handle);
  if (localPrompt) {
    return localPrompt;
  }

  // Return a default engineering-focused prompt as ultimate fallback
  return `You are an AI assistant for power systems engineering. Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations.`;
}
