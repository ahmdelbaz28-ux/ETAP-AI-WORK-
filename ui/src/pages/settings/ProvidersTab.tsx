/**
 * ProvidersTab — temporary placeholder created for the P4b web key freeze.
 *
 * Web mode  : API keys are NEVER entered in the browser anymore. Chat runs
 *             through the server-side path (`/api/v1/chat/stream`, P4b) with
 *             keys configured by the administrator on the server environment
 *             (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY).
 * Electron  : legacy per-machine provider management still lives in the
 *             classic Settings page until the P7a-d tab split lands. This
 *             component accepts optional `children` so the existing fields
 *             can be slotted into desktop builds without editing this file.
 */

import type { ReactNode } from "react";

import { isElectronRuntime } from "../../lib/llm-chat";

interface ProvidersTabProps {
  /** Legacy provider-management controls rendered in Electron mode only. */
  children?: ReactNode;
}

export default function ProvidersTab({ children }: Readonly<ProvidersTabProps>) {
  if (isElectronRuntime()) {
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-900 p-5">
        <h2 className="mb-2 text-lg font-semibold text-slate-100">AI Providers</h2>
        <p className="text-sm text-slate-400">
          {`Desktop mode: provider keys stay local to this machine. Management is
available in the classic settings page and will move here when the
settings split ships.`}
        </p>
        {children}
      </section>
    );
  }

  return (
    <section dir="rtl" className="rounded-lg border border-slate-700 bg-slate-900 p-5 text-right">
      <h2 className="mb-2 text-lg font-semibold text-slate-100">إدارة المفاتيح عبر الخادم</h2>
      <p className="text-sm leading-relaxed text-slate-400">
        {`في وضع الويب لا تُدخل مفاتيح LLM في المتصفح إطلاقًا. يضبط مسؤول النظام
المفاتيح على الخادم عبر متغيرات البيئة (OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY)،
وتُبثّ الردود عبر المسار الخادمي الآمن. للتفعيل أو تغيير المفاتيح يرجى التواصل مع مسؤول المنصة.`}
      </p>
      <div className="mt-3 rounded-md border border-slate-700/60 bg-slate-800/50 px-3 py-2 text-xs text-slate-500">
        Server-side chat: <code className="text-slate-300">POST /api/v1/chat/stream</code> (OpenAI, Anthropic, Gemini) — P4b
      </div>
    </section>
  );
}
