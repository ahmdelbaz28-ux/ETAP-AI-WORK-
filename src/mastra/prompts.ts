import { LangWatch } from 'langwatch';
import fs from 'node:fs';
import path from 'node:path';

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
 * Improved YAML parser that handles basic structures, multiline strings, and pipe operators
 */
function parseSimpleYaml(content: string): Record<string, unknown> {  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  const result: Record<string, unknown> = {};
  const lines = content.split('\n');
  let currentKey = '';
  let currentMessages: PromptMessage[] = [];
  let inMessages = false;
  let currentMessageRole = '';
  let currentMessageContent = '';
  let inMultilineContent = false;
  let multilineIndent = 0;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    // Handle multiline content started with |
    if (inMultilineContent) {
      const trimmedLine = line.trim();
      if (line.startsWith(' '.repeat(multilineIndent)) || trimmedLine === '') {
        // This line is part of the multiline content
        currentMessageContent += '\n' + line.substring(multilineIndent);
      } else {
        // End of multiline content
        inMultilineContent = false;
        if (currentMessageRole && currentMessageContent.trim()) {
          currentMessages.push({ role: currentMessageRole, content: currentMessageContent.trim() });
          currentMessageRole = '';
          currentMessageContent = '';
        }
      }
      continue;
    }
    
    if (line.startsWith('messages:')) {
      inMessages = true;
      continue;
    }
    
    if (inMessages && line.match(/^\s*- role:/)) {  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      // Save previous message if exists
      if (currentMessageRole && currentMessageContent) {
        currentMessages.push({ role: currentMessageRole, content: currentMessageContent.trim() });
      }
      
      currentMessageRole = line.split(':')[1]?.trim().replaceAll('"', '').replaceAll("'", '') || '';
      currentMessageContent = '';
    } else if (inMessages && line.match(/^\s+content:\s*\|/)) {  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      // Handle multiline content with pipe operator
      currentMessageContent = '';
      inMultilineContent = true;
      multilineIndent = line.search(/\S/); // Find the position of first non-space character
      
      // Extract content after the pipe if there's anything
      const pipeMatch = line.match(/^\s+content:\s*\|\s*(.*)/);  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      if (pipeMatch?.[1]) {
        currentMessageContent = pipeMatch[1];
      }
      
      // Next line should be indented content
      multilineIndent += 2; // Content after pipe should be indented more
      continue;
    } else if (inMessages && line.match(/^\s+content:/)) {  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      // Handle single-line content
      const contentMatch = line.match(/^\s+content:(.*)/);  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      if (contentMatch) {
        currentMessageContent = contentMatch[1].trim().replace(/^"|"$/g, '').replace(/^'|'$/g, '');
      }
    } else if (inMessages && line.match(/^\s{4,}/) && currentMessageRole && !inMultilineContent) {  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      // Handle content continuation lines (indented)
      const contentIndent = line.search(/\S/);
      if (contentIndent > multilineIndent && currentMessageContent) {
        currentMessageContent += '\n' + line.trim();
      }
    } else if (line.match(/^\S+:/) && !line.startsWith('messages')) {  // NOSONAR — S6594: RegExp.exec vs match; performance neutral
      // Handle regular key-value pairs
      inMessages = false;
      inMultilineContent = false;
      
      // Save previous message if exists
      if (currentKey === 'prompt' && currentMessageContent) {
        result[currentKey] = currentMessageContent;
        currentMessageContent = '';
      }
      
      if (currentMessageRole && currentMessageContent) {
        currentMessages.push({ role: currentMessageRole, content: currentMessageContent.trim() });
        currentMessageRole = '';
        currentMessageContent = '';
      }
      
      const colonIndex = line.indexOf(':');
      if (colonIndex > 0) {
        currentKey = line.substring(0, colonIndex).trim();
        let value = line.substring(colonIndex + 1).trim();
        
        // Handle values that start with | (multiline)
        if (value.startsWith('|')) {
          value = value.substring(1).trim();
          inMultilineContent = true;
          multilineIndent = line.search(/\S/) + 2; // Indent for content should be more than the key
          
          // Store the initial value if any
          if (value) {
            if (inMessages && currentMessageRole) {
              currentMessageContent = value;
            } else {
              result[currentKey] = value;
            }
          }
        } else if (value.startsWith('"') || value.startsWith("'")) {
          // Handle quoted values
          value = value.replace(/^"(.*)"$/, '$1').replace(/^'(.*)'$/, '$1');
          result[currentKey] = value;
        } else if (value.toLowerCase() === 'true' || value.toLowerCase() === 'false') {
          // Handle boolean values
          result[currentKey] = value.toLowerCase() === 'true';
        } else if (!Number.isNaN(Number(value))) {
          // Handle numeric values
          result[currentKey] = Number(value);
        } else if (value !== '') {
          // Regular string value
          result[currentKey] = value;
        }
      }
    }
  }
  
  // Handle remaining content after loop ends. Both the multiline and
  // single-line cases push the same shape, so the inMultilineContent
  // branch is not needed (SonarCloud S1871).
  if (currentMessageRole && currentMessageContent) {
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
function loadLocalPrompt(handle: string): string | null {  // NOSONAR — S3776: cognitive complexity; scheduled for refactoring sprint (extract helpers / early returns)
  try {
    const promptsDir = path.join(process.cwd(), 'prompts');
    // Try different filename patterns
    const possibleFiles = [
      `${handle}.yaml`,
      `${handle}.prompt.yaml`,
      `${handle}_agent.prompt.yaml`,
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
      console.warn(`[Prompts] LangWatch API unavailable, using local fallback for "${handle}":`, e instanceof Error ? e.message : String(e));
    }
  }
  
  // Fall back to local YAML file
  const localPrompt = loadLocalPrompt(handle);
  if (localPrompt) {
    return localPrompt;
  }

  // Try loading the fallback YAML prompt
  const fallbackPrompt = loadLocalPrompt('fallback_agent');
  if (fallbackPrompt) {
    return fallbackPrompt;
  }

  // Return a hardcoded default as ultimate safety-net
  return `You are a safety-net fallback AI assistant for power systems engineering. Provide accurate, standards-compliant (IEEE/IEC) analysis and recommendations.`;
}