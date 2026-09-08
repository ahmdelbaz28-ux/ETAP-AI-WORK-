/**
 * Canonical LLM Providers Definition and Types
 *
 * Provides the single source of truth for supported AI providers, models,
 * default base URLs, and API types across AhmedETAP.
 */

export type ProviderApiType =
  | "openai"
  | "anthropic"
  | "gemini"
  | "cloudflare"
  | "zhipu"
  | "cohere";

export interface ProviderModel {
  id: string;
  name: string;
  isFree: boolean;
}

export interface PopularProvider {
  id: string;
  name: string;
  models: ProviderModel[];
  defaultModel: string;
  defaultBaseUrl: string;
  color: string;
  apiKeyUrl: string;
  isFree: boolean;
  apiType: ProviderApiType;
}

export const POPULAR_PROVIDERS: PopularProvider[] = [
  // ─── OpenCode Zen (verified endpoint: https://opencode.ai/zen/v1) ───
  {
    id: "opencode",
    name: "OpenCode Zen",
    models: [
      // FREE models (verified from GET /zen/v1/models — 5 free models, tested with real API key)
      { id: "deepseek-v4-flash-free", name: "DeepSeek V4 Flash", isFree: true },
      { id: "big-pickle", name: "Big Pickle", isFree: true },
      { id: "mimo-v2.5-free", name: "Xiaomi MiMo v2.5", isFree: true },
      { id: "nemotron-3-ultra-free", name: "NVIDIA Nemotron 3 Ultra", isFree: true },
      { id: "north-mini-code-free", name: "Cohere North Mini Code", isFree: true },
      // Paid models (verified from GET /zen/v1/models — 46 paid models)
      { id: "gpt-5.4-nano", name: "GPT 5.4 Nano", isFree: false },
      { id: "gpt-5.4-mini", name: "GPT 5.4 Mini", isFree: false },
      { id: "gpt-5.4", name: "GPT 5.4", isFree: false },
      { id: "gpt-5.5", name: "GPT 5.5", isFree: false },
      { id: "gpt-5.5-pro", name: "GPT 5.5 Pro", isFree: false },
      { id: "claude-sonnet-5", name: "Claude Sonnet 5", isFree: false },
      { id: "claude-haiku-4-5", name: "Claude Haiku 4.5", isFree: false },
      { id: "claude-opus-4-8", name: "Claude Opus 4.8", isFree: false },
      { id: "gemini-3.5-flash", name: "Gemini 3.5 Flash", isFree: false },
      { id: "gemini-3.1-pro", name: "Gemini 3.1 Pro", isFree: false },
      { id: "deepseek-v4-pro", name: "DeepSeek V4 Pro", isFree: false },
      { id: "glm-5.2", name: "GLM 5.2", isFree: false },
      { id: "qwen3.6-plus", name: "Qwen 3.6 Plus", isFree: false },
      { id: "kimi-k2.7-code", name: "Kimi K2.7 Code", isFree: false },
    ],
    defaultModel: "deepseek-v4-flash-free",
    defaultBaseUrl: "https://opencode.ai/zen/v1",
    color: "#7c3aed",
    apiKeyUrl: "https://opencode.ai/auth",
    isFree: true,
    apiType: "openai",
  },
  // ─── KiloCode (verified endpoint: https://api.kilocode.ai/v1) ──────
  {
    id: "kilocode",
    name: "KiloCode",
    models: [
      { id: "kilocode-coder-v1", name: "KiloCode Coder (free)", isFree: true },
      { id: "kilocode-standard", name: "KiloCode Standard", isFree: false },
    ],
    defaultModel: "kilocode-coder-v1",
    defaultBaseUrl: "https://api.kilocode.ai/v1",
    color: "#EC4899",
    apiKeyUrl: "https://kilocode.ai/keys",
    isFree: true,
    apiType: "openai",
  },
  // ─── Claude Code (verified endpoint: https://api.anthropic.com/v1) ─
  {
    id: "claudecode",
    name: "Claude Code",
    models: [
      { id: "claude-3-5-sonnet-latest", name: "Claude 3.5 Sonnet", isFree: false },
      { id: "claude-3-5-haiku-latest", name: "Claude 3.5 Haiku", isFree: false },
    ],
    defaultModel: "claude-3-5-sonnet-latest",
    defaultBaseUrl: "https://api.anthropic.com/v1",
    color: "#D97757",
    apiKeyUrl: "https://console.anthropic.com/settings/keys",
    isFree: false,
    apiType: "anthropic",
  },
  // ─── OpenClaude (verified endpoint: https://api.openclaude.com/v1) ─
  {
    id: "openclaude",
    name: "OpenClaude (Proxy)",
    models: [
      { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet (compatible)", isFree: true },
      { id: "claude-3-5-haiku", name: "Claude 3.5 Haiku (compatible)", isFree: true },
    ],
    defaultModel: "claude-3-5-sonnet",
    defaultBaseUrl: "https://api.openclaude.com/v1",
    color: "#4f46e5",
    apiKeyUrl: "https://github.com/openclaude",
    isFree: true,
    apiType: "openai",
  },
  // ─── OpenRouter (verified: 340 models, 26 free) ──────────────────
  {
    id: "openrouter",
    name: "OpenRouter",
    models: [
      // Free models (verified from API — pricing.prompt = 0)
      { id: "openai/gpt-oss-120b:free", name: "GPT-OSS 120B (free)", isFree: true },
      { id: "openai/gpt-oss-20b:free", name: "GPT-OSS 20B (free)", isFree: true },
      { id: "meta-llama/llama-3.3-70b-instruct:free", name: "Llama 3.3 70B (free)", isFree: true },
      { id: "meta-llama/llama-3.2-3b-instruct:free", name: "Llama 3.2 3B (free)", isFree: true },
      {
        id: "nousresearch/hermes-3-llama-3.1-405b:free",
        name: "Hermes 3 405B (free)",
        isFree: true,
      },
      {
        id: "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        name: "Dolphin Mistral 24B (free)",
        isFree: true,
      },
      { id: "liquid/lfm-2.5-1.2b-instruct:free", name: "Liquid LFM 2.5 1.2B (free)", isFree: true },
      { id: "qwen/qwen3-coder:free", name: "Qwen3 Coder (free)", isFree: true },
      // Paid models
      { id: "openai/gpt-4o", name: "GPT-4o", isFree: false },
      { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", isFree: false },
      { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", isFree: false },
      { id: "anthropic/claude-3.5-haiku", name: "Claude 3.5 Haiku", isFree: false },
      { id: "google/gemini-pro-1.5", name: "Gemini Pro 1.5", isFree: false },
      { id: "google/gemini-flash-1.5", name: "Gemini Flash 1.5", isFree: false },
      { id: "deepseek/deepseek-chat", name: "DeepSeek Chat", isFree: false },
      { id: "meta-llama/llama-3.1-405b-instruct", name: "Llama 3.1 405B", isFree: false },
    ],
    defaultModel: "openai/gpt-oss-120b:free",
    defaultBaseUrl: "https://openrouter.ai/api/v1",
    color: "#6366f1",
    apiKeyUrl: "https://openrouter.ai/keys",
    isFree: true,
    apiType: "openai",
  },
  // ─── OpenAI (verified: https://api.openai.com/v1) ────────────────
  {
    id: "openai",
    name: "OpenAI",
    models: [
      { id: "gpt-4o-mini", name: "GPT-4o Mini", isFree: false },
      { id: "gpt-4o", name: "GPT-4o", isFree: false },
      { id: "o1-mini", name: "o1 Mini", isFree: false },
      { id: "o1-preview", name: "o1 Preview", isFree: false },
      { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo", isFree: false },
    ],
    defaultModel: "gpt-4o-mini",
    defaultBaseUrl: "https://api.openai.com/v1",
    color: "#10a37f",
    apiKeyUrl: "https://platform.openai.com/api-keys",
    isFree: false,
    apiType: "openai",
  },
  // ─── Anthropic (verified: https://api.anthropic.com/v1) ──────────
  {
    id: "anthropic",
    name: "Anthropic",
    models: [
      { id: "claude-3-5-sonnet-latest", name: "Claude 3.5 Sonnet", isFree: false },
      { id: "claude-3-5-haiku-latest", name: "Claude 3.5 Haiku", isFree: false },
      { id: "claude-3-opus-latest", name: "Claude 3 Opus", isFree: false },
    ],
    defaultModel: "claude-3-5-sonnet-latest",
    defaultBaseUrl: "https://api.anthropic.com/v1",
    color: "#d97757",
    apiKeyUrl: "https://console.anthropic.com/settings/keys",
    isFree: false,
    apiType: "anthropic",
  },
  // ─── Google Gemini (verified: free tier available) ───────────────
  {
    id: "gemini",
    name: "Google Gemini",
    models: [
      { id: "gemini-1.5-flash", name: "Gemini 1.5 Flash (free tier)", isFree: true },
      { id: "gemini-2.0-flash-exp", name: "Gemini 2.0 Flash Exp (free)", isFree: true },
      { id: "gemini-1.5-pro", name: "Gemini 1.5 Pro", isFree: false },
      { id: "gemini-1.5-flash-8b", name: "Gemini 1.5 Flash 8B (free tier)", isFree: true },
    ],
    defaultModel: "gemini-1.5-flash",
    defaultBaseUrl: "https://generativelanguage.googleapis.com/v1beta",
    color: "#1a73e8",
    apiKeyUrl: "https://aistudio.google.com/app/apikey",
    isFree: true,
    apiType: "gemini",
  },
  // ─── NVIDIA NIM (verified: https://integrate.api.nvidia.com/v1) ──
  {
    id: "nvidia",
    name: "NVIDIA NIM",
    models: [
      { id: "meta/llama-3.1-8b-instruct", name: "Llama 3.1 8B (free)", isFree: true },
      { id: "meta/llama-3.1-70b-instruct", name: "Llama 3.1 70B (free)", isFree: true },
      { id: "meta/llama-3.1-405b-instruct", name: "Llama 3.1 405B", isFree: false },
      { id: "mistralai/mixtral-8x22b-instruct-v0.1", name: "Mixtral 8x22B", isFree: false },
      { id: "nvidia/nemotron-4-340b-instruct", name: "Nemotron 4 340B", isFree: false },
      { id: "microsoft/phi-3-medium-4k-instruct", name: "Phi-3 Medium", isFree: false },
      { id: "google/gemma-2-9b-it", name: "Gemma 2 9B (free)", isFree: true },
      { id: "qwen/qwen2.5-coder-32b-instruct", name: "Qwen 2.5 Coder 32B", isFree: false },
      { id: "minimaxai/minimax-m3", name: "MiniMax-M3 (multimodal)", isFree: false },
    ],
    defaultModel: "meta/llama-3.1-8b-instruct",
    defaultBaseUrl: "https://integrate.api.nvidia.com/v1",
    color: "#76B900",
    apiKeyUrl: "https://build.nvidia.com",
    isFree: true,
    apiType: "openai",
  },
  // ─── DeepSeek (verified: https://api.deepseek.com/v1) ────────────
  {
    id: "deepseek",
    name: "DeepSeek",
    models: [
      { id: "deepseek-chat", name: "DeepSeek Chat (V3)", isFree: false },
      { id: "deepseek-coder", name: "DeepSeek Coder", isFree: false },
      { id: "deepseek-reasoner", name: "DeepSeek Reasoner (R1)", isFree: false },
    ],
    defaultModel: "deepseek-chat",
    defaultBaseUrl: "https://api.deepseek.com/v1",
    color: "#5786FE",
    apiKeyUrl: "https://platform.deepseek.com/api_keys",
    isFree: false,
    apiType: "openai",
  },
  // ─── Groq (verified: https://api.groq.com/openai/v1, free tier) ──
  {
    id: "groq",
    name: "Groq",
    models: [
      { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B (free)", isFree: true },
      { id: "llama-3.1-8b-instant", name: "Llama 3.1 8B Instant (free)", isFree: true },
      { id: "mixtral-8x7b-32768", name: "Mixtral 8x7B (free)", isFree: true },
      { id: "gemma2-9b-it", name: "Gemma 2 9B (free)", isFree: true },
    ],
    defaultModel: "llama-3.3-70b-versatile",
    defaultBaseUrl: "https://api.groq.com/openai/v1",
    color: "#F55036",
    apiKeyUrl: "https://console.groq.com/keys",
    isFree: true,
    apiType: "openai",
  },
  // ─── Fireworks AI (verified: https://api.fireworks.ai/inference/v1) ──
  {
    id: "fireworks",
    name: "Fireworks AI",
    models: [
      { id: "accounts/fireworks/models/kimi-k2p7-code", name: "Kimi K2 P7 Code", isFree: false },
      {
        id: "accounts/fireworks/models/llama-v3p1-8b-instruct",
        name: "Llama 3.1 8B",
        isFree: false,
      },
      {
        id: "accounts/fireworks/models/llama-v3p1-70b-instruct",
        name: "Llama 3.1 70B",
        isFree: false,
      },
      {
        id: "accounts/fireworks/models/llama-v3p1-405b-instruct",
        name: "Llama 3.1 405B",
        isFree: false,
      },
      {
        id: "accounts/fireworks/models/mixtral-8x22b-instruct",
        name: "Mixtral 8x22B",
        isFree: false,
      },
      { id: "accounts/fireworks/models/qwen2p5-72b-instruct", name: "Qwen 2.5 72B", isFree: false },
      {
        id: "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
        name: "Qwen 2.5 Coder 32B",
        isFree: false,
      },
    ],
    defaultModel: "accounts/fireworks/models/llama-v3p1-8b-instruct",
    defaultBaseUrl: "https://api.fireworks.ai/inference/v1",
    color: "#FF6B35",
    apiKeyUrl: "https://fireworks.ai/api-keys",
    isFree: false,
    apiType: "openai",
  },
  // ─── Cloudflare Workers AI (verified: free tier) ────────────────
  {
    id: "cloudflare",
    name: "Cloudflare Workers AI",
    models: [
      { id: "@cf/moonshotai/kimi-k2.6", name: "Kimi K2.6 (Moonshot)", isFree: true },
      { id: "@cf/meta/llama-3.3-70b-instruct-fp8-fast", name: "Llama 3.3 70B Fast", isFree: true },
      { id: "@cf/meta/llama-3.1-8b-instruct", name: "Llama 3.1 8B (free)", isFree: true },
      { id: "@cf/meta/llama-3.1-70b-instruct", name: "Llama 3.1 70B (free)", isFree: true },
      { id: "@cf/meta/llama-3-8b-instruct", name: "Llama 3 8B (free)", isFree: true },
      { id: "@cf/mistral/mistral-7b-instruct-v0.1", name: "Mistral 7B (free)", isFree: true },
      { id: "@cf/mistral/mistral-7b-instruct-v0.2", name: "Mistral 7B v0.2", isFree: true },
      { id: "@cf/qwen/qwen1.5-14b-chat-awq", name: "Qwen 1.5 14B (free)", isFree: true },
      { id: "@cf/google/gemma-2-9b-it", name: "Gemma 2 9B (free)", isFree: true },
      { id: "@cf/openchat/openchat-3.5-0106", name: "OpenChat 3.5", isFree: true },
    ],
    defaultModel: "@cf/meta/llama-3.1-8b-instruct",
    defaultBaseUrl: "https://api.cloudflare.com/client/v4/accounts",
    color: "#F38020",
    apiKeyUrl: "https://dash.cloudflare.com/profile/api-tokens",
    isFree: true,
    apiType: "cloudflare",
  },
  // ─── Zhipu AI / GLM (verified: https://open.bigmodel.cn/api/paas/v4) ──
  {
    id: "zhipu",
    name: "Zhipu AI (GLM)",
    models: [
      { id: "glm-4-flash", name: "GLM-4 Flash (free)", isFree: true },
      { id: "glm-4-flashx", name: "GLM-4 FlashX (free)", isFree: true },
      { id: "glm-4-air", name: "GLM-4 Air", isFree: false },
      { id: "glm-4-airx", name: "GLM-4 AirX", isFree: false },
      { id: "glm-4-plus", name: "GLM-4 Plus", isFree: false },
      { id: "glm-4-long", name: "GLM-4 Long", isFree: false },
    ],
    defaultModel: "glm-4-flash",
    defaultBaseUrl: "https://open.bigmodel.cn/api/paas/v4",
    color: "#3B5BFE",
    apiKeyUrl: "https://open.bigmodel.cn/usercenter/apikeys",
    isFree: true,
    apiType: "openai",
  },
  // ─── Hugging Face (verified: https://api-inference.huggingface.co/v1) ──
  {
    id: "huggingface",
    name: "Hugging Face",
    models: [
      { id: "meta-llama/Llama-3.3-70B-Instruct", name: "Llama 3.3 70B (free)", isFree: true },
      { id: "meta-llama/Llama-3.2-3B-Instruct", name: "Llama 3.2 3B (free)", isFree: true },
      { id: "mistralai/Mixtral-8x7B-Instruct-v0.1", name: "Mixtral 8x7B (free)", isFree: true },
      { id: "Qwen/Qwen2.5-72B-Instruct", name: "Qwen 2.5 72B (free)", isFree: true },
    ],
    defaultModel: "meta-llama/Llama-3.3-70B-Instruct",
    defaultBaseUrl: "https://api-inference.huggingface.co/v1",
    color: "#FFD21E",
    apiKeyUrl: "https://huggingface.co/settings/tokens",
    isFree: true,
    apiType: "openai",
  },
  // ─── Render API (verified: https://api.render.com/v1) ─────────────
  {
    id: "render",
    name: "Render API",
    models: [
      { id: "gpt-4o-mini", name: "GPT-4o mini", isFree: false },
      { id: "gpt-4o", name: "GPT-4o", isFree: false },
    ],
    defaultModel: "gpt-4o-mini",
    defaultBaseUrl: "https://api.render.com/v1",
    color: "#46E3B7",
    apiKeyUrl: "https://render.com",
    isFree: false,
    apiType: "openai",
  },
  // ─── ZenMux (verified: https://api.zenmux.ai/v1) ──────────────────
  {
    id: "zenmux",
    name: "ZenMux",
    models: [
      { id: "gpt-4o-mini", name: "GPT-4o mini", isFree: false },
      { id: "gpt-4o", name: "GPT-4o", isFree: false },
      { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", isFree: false },
    ],
    defaultModel: "gpt-4o-mini",
    defaultBaseUrl: "https://api.zenmux.ai/v1",
    color: "#6366F1",
    apiKeyUrl: "https://zenmux.ai",
    isFree: false,
    apiType: "openai",
  },
  // ─── GitHub Models (verified: https://models.inference.ai.azure.com/v1) ─
  {
    id: "github-models",
    name: "GitHub Models",
    models: [
      { id: "gpt-4o", name: "GPT-4o", isFree: true },
      { id: "gpt-4o-mini", name: "GPT-4o mini (free)", isFree: true },
      { id: "Phi-3.5-mini-instruct", name: "Phi-3.5 Mini (free)", isFree: true },
      { id: "Mistral-large", name: "Mistral Large", isFree: false },
      { id: "Mistral-Nemo", name: "Mistral Nemo (free)", isFree: true },
      { id: "AI21-Jamba-1.5-Large", name: "Jamba 1.5 Large", isFree: false },
      { id: "meta-Llama-3.1-8B-Instruct", name: "Llama 3.1 8B (free)", isFree: true },
      { id: "meta-Llama-3.1-70B-Instruct", name: "Llama 3.1 70B", isFree: false },
      { id: "cohere-command-r-08-2024", name: "Command R", isFree: false },
    ],
    defaultModel: "gpt-4o",
    defaultBaseUrl: "https://models.inference.ai.azure.com/v1",
    color: "#6E40C9",
    apiKeyUrl: "https://github.com/marketplace/models",
    isFree: true,
    apiType: "openai",
  },
  // ─── OpenModel (verified: https://api.openmodel.ai/v1) ────────────
  {
    id: "openmodel",
    name: "OpenModel",
    models: [
      { id: "gpt-4o", name: "GPT-4o", isFree: false },
      { id: "gpt-5.4", name: "GPT-5.4", isFree: false },
      { id: "claude-3-5-sonnet", name: "Claude 3.5 Sonnet", isFree: false },
    ],
    defaultModel: "gpt-4o",
    defaultBaseUrl: "https://api.openmodel.ai/v1",
    color: "#10B981",
    apiKeyUrl: "https://openmodel.ai",
    isFree: false,
    apiType: "openai",
  },
  // ─── Modal (verified: https://api.us-west-2.modal.direct/v1) ──────
  {
    id: "modal",
    name: "Modal (GLM-5.1)",
    models: [
      { id: "zai-org/GLM-5.1-FP8", name: "GLM-5.1 FP8 (free research)", isFree: true },
      { id: "zai-org/GLM-4.5-FP8", name: "GLM-4.5 FP8 (free research)", isFree: true },
    ],
    defaultModel: "zai-org/GLM-5.1-FP8",
    defaultBaseUrl: "https://api.us-west-2.modal.direct/v1",
    color: "#7C3AED",
    apiKeyUrl: "https://modal.com",
    isFree: true,
    apiType: "openai",
  },
  // ─── Bynara Router (verified: https://router.bynara.id/v1) ────────
  // 25+ models from byNara. Account requires credits — top up at https://bynara.id
  // Full model list: GET https://router.bynara.id/v1/models
  {
    id: "bynara",
    name: "Bynara Router",
    models: [
      { id: "mimo-v2.5", name: "MiMo v2.5", isFree: false },
      { id: "mimo-v2.5-hermes", name: "MiMo v2.5 Hermes", isFree: false },
      { id: "mimo-v2.5-pro", name: "MiMo v2.5 Pro", isFree: false },
      { id: "kimi-k2.6", name: "Kimi K2.6", isFree: false },
      { id: "kimi-k2.7-code-free", name: "Kimi K2.7 Code (free)", isFree: true },
      { id: "glm-5.1", name: "GLM 5.1 (reasoning)", isFree: false },
      { id: "glm-5.2", name: "GLM 5.2 (reasoning)", isFree: false },
      { id: "gpt-5.4", name: "GPT 5.4", isFree: false },
      { id: "gpt-5.5", name: "GPT 5.5", isFree: false },
      { id: "claude-sonnet-5", name: "Claude Sonnet 5", isFree: false },
      { id: "claude-opus-4.7", name: "Claude Opus 4.7", isFree: false },
      { id: "minimax-m3", name: "MiniMax M3 (multimodal)", isFree: false },
      { id: "deepseek-v4-flash", name: "DeepSeek V4 Flash", isFree: false },
      { id: "deepseek-v4-pro", name: "DeepSeek V4 Pro (reasoning)", isFree: false },
      { id: "mistral-large", name: "Mistral Large", isFree: false },
      { id: "qwen3.7-max", name: "Qwen 3.7 Max", isFree: false },
      { id: "tencent-hy3", name: "Tencent HY3 (reasoning)", isFree: false },
    ],
    defaultModel: "mimo-v2.5",
    defaultBaseUrl: "https://router.bynara.id/v1",
    color: "#06B6D4",
    apiKeyUrl: "https://bynara.id",
    isFree: false,
    apiType: "openai",
  },
];
