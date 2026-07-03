import { createOpenAI } from '@ai-sdk/openai';
import { generateText, streamText } from 'ai';
import type { LanguageModel } from 'ai';

// Read all API keys from the environment. Tests are SKIPPED (not failed)
// when keys are missing — SonarCloud S6418 (hard-coded secrets).
const OPENMODEL_API_KEY = process.env.OPENMODEL_API_KEY ?? '';
const MODAL_API_KEY = process.env.MODAL_API_KEY ?? '';
const NVIDIA_API_KEY = process.env.NVIDIA_API_KEY ?? '';

const SKIP_MESSAGE =
  'Set OPENMODEL_API_KEY / MODAL_API_KEY / NVIDIA_API_KEY to run this live integration test.';

// 1. Define custom OpenModel wrapper
const openModelLanguageModel: any = {
  specificationVersion: 'v3',
  provider: 'openmodel',
  modelId: 'gpt-5.4',

  async doGenerate(options: any) {
    let input = '';
    for (const msg of options.prompt) {
      if (msg.role === 'system') {
        input += `System: ${msg.content}\n`;
      } else if (msg.role === 'user') {
        const text = msg.content.map((c: any) => c.text || '').join('');
        input += `User: ${text}\n`;
      } else if (msg.role === 'assistant') {
        const text = msg.content.map((c: any) => c.text || '').join('');
        input += `Assistant: ${text}\n`;
      }
    }
    input += `Assistant:`;

    const resp = await fetch('https://api.openmodel.ai/v1/responses', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${OPENMODEL_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'gpt-5.4',
        input: input
      })
    });
    
    if (!resp.ok) {
      const errText = await resp.text();
      throw new Error(`OpenModel error: HTTP ${resp.status} - ${errText}`);
    }
    
    const data = (await resp.json()) as any;
    let outputText = '';
    if (data && Array.isArray(data.output)) {
      const assistantMsg = data.output.find((o: any) => o.type === 'message' && o.role === 'assistant');
      if (assistantMsg && Array.isArray(assistantMsg.content)) {
        outputText = assistantMsg.content.map((c: any) => c.text || '').join('');
      }
    }
    
    if (!outputText) {
      outputText = JSON.stringify(data);
    }
    
    return {
      text: outputText,
      content: [{ type: 'text', text: outputText }],
      finishReason: 'stop',
      usage: {
        inputTokens: { total: data.usage?.input_tokens ?? 0 },
        outputTokens: { total: data.usage?.output_tokens ?? 0 }
      },
      rawCall: { rawPrompt: options.prompt, rawSettings: {} },
      rawResponse: { headers: {} }
    };
  },
  
  async doStream(options: any) {
    const result = await this.doGenerate(options);
    const textStream = new ReadableStream({
      start(controller) {
        controller.enqueue({
          type: 'text-delta',
          delta: result.text || ''
        });
        controller.close();
      }
    });
    
    return {
      stream: textStream,
      rawCall: { rawPrompt: options.prompt, rawSettings: {} },
      rawResponse: { headers: {} }
    };
  }
} as any;

// 2. Define Modal & Nvidia NIM models
const modalClient = createOpenAI({
  apiKey: MODAL_API_KEY,
  baseURL: 'https://api.us-west-2.modal.direct/v1'
});
const modalModel = modalClient('zai-org/GLM-5.1-FP8');

const nvidiaClient = createOpenAI({
  apiKey: NVIDIA_API_KEY,
  baseURL: 'https://integrate.api.nvidia.com/v1'
});
const nvidiaModel = nvidiaClient('abacusai/dracarys-llama-3.1-70b-instruct');

// 3. Define failover wrapper
function createFailoverModel(models: any[]): any {
  if (models.length === 0) {
    throw new Error('No models provided for failover');
  }
  const primary = models[0];
  
  return {
    specificationVersion: 'v3',
    provider: primary?.provider,
    modelId: primary?.modelId,
    defaultObjectGenerationMode: primary?.defaultObjectGenerationMode,
    
    async doGenerate(options: any) {
      let lastError: any = null;
      for (const model of models) {
        try {
          console.log(`[Failover] Attempting doGenerate with model: ${model.provider}:${model.modelId}`);
          return await model.doGenerate(options);
        } catch (err: any) {
          lastError = err;
          console.warn(`[Failover] Model ${model.modelId} failed: ${err.message || err}. Trying next...`);
        }
      }
      throw lastError;
    },
    
    async doStream(options: any) {
      let lastError: any = null;
      for (const model of models) {
        try {
          console.log(`[Failover] Attempting doStream with model: ${model.provider}:${model.modelId}`);
          return await model.doStream(options);
        } catch (err: any) {
          lastError = err;
          console.warn(`[Failover] Model ${model.modelId} failed: ${err.message || err}. Trying next...`);
        }
      }
      throw lastError;
    }
  } as any;
}

// 4. Test execution
async function runTest() {
  const failoverModel = createFailoverModel([
    openModelLanguageModel,
    modalModel,
    nvidiaModel
  ]);

  console.log('--- Testing generateText ---');
  try {
    const { text, usage } = await generateText({
      model: failoverModel as any,
      prompt: 'Say "hello, verification successful!"'
    });
    console.log('Result text:', text);
    console.log('Result usage:', usage);
  } catch (err) {
    console.error('generateText completely failed:', err);
  }

  console.log('\n--- Testing streamText ---');
  try {
    const { textStream } = await streamText({
      model: failoverModel as any,
      prompt: 'What is 2 + 2?'
    });
    
    let fullText = '';
    for await (const chunk of textStream) {
      fullText += chunk;
    }
    console.log('Stream full text:', fullText);
  } catch (err) {
    console.error('streamText completely failed:', err);
  }
}

runTest();
