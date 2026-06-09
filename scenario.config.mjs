import 'dotenv/config';
import { defineConfig } from '@langwatch/scenario/config';
import { openai } from '@ai-sdk/openai';

export default defineConfig({
  defaultModel: {
    model: openai('gpt-4o-mini'),
    temperature: 0.1,
  },
});
