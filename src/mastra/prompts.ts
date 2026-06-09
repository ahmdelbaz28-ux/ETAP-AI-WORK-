import { LangWatch } from 'langwatch';

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

export async function getSystemPrompt(handle: string): Promise<string> {
  const prompt = (await langwatch.prompts.get(handle)) as LangWatchPrompt | null | undefined;

  if (!prompt) {
    throw new Error(`Prompt "${handle}" was not found. Run "langwatch prompt sync" and verify prompts.json.`);
  }

  if (prompt.prompt?.trim()) {
    return prompt.prompt.trim();
  }

  const systemMessage = prompt.messages?.find((message) => message.role === 'system');
  const systemContent = stringifyContent(systemMessage?.content).trim();
  if (systemContent) {
    return systemContent;
  }

  throw new Error(`Prompt "${handle}" does not contain usable system instructions.`);
}
