import { createOpenAI } from '@ai-sdk/openai';

export default {
  dir: './src/mastra',
  providers: [
    {
      id: 'openai',
      name: 'OpenAI',
      client: createOpenAI({
        apiKey: process.env.OPENAI_API_KEY,
        baseURL: process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1',
      }),
      model: process.env.OPENAI_MODEL_ID || 'gpt-4o',
    },
  ],
};
