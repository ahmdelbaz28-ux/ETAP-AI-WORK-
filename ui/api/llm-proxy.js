/**
 * Vercel Serverless Function — LLM API Proxy (with streaming support)
 *
 * Two modes:
 *   1. Non-streaming: POST /api/llm-proxy → JSON response
 *   2. Streaming: POST /api/llm-proxy?stream=true → SSE stream
 *
 * Solves CORS: browsers can't directly call LLM APIs because they don't
 * send CORS headers. This proxy forwards server-to-server.
 */

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  // CORS headers for our own domain
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const { endpoint, apiKey, body, headers: customHeaders, stream } = req.body;

    if (!endpoint || !apiKey || !body) {
      return res.status(400).json({
        error: 'Missing required fields: endpoint, apiKey, body',
      });
    }

    const headers = {
      'Content-Type': 'application/json',
      ...customHeaders,
    };

    if (!headers.Authorization && !headers.authorization) {
      headers.Authorization = `Bearer ${apiKey}`;
    }

    // Add stream: true to the body if streaming is requested
    const requestBody =
      typeof body === 'string'
        ? body
        : JSON.stringify({
            ...body,
            stream: stream ? true : undefined,
          });

    // ─── Streaming mode ──────────────────────────────────────────
    if (stream) {
      res.setHeader('Content-Type', 'text/event-stream');
      res.setHeader('Cache-Control', 'no-cache');
      res.setHeader('Connection', 'keep-alive');
      res.setHeader('X-Accel-Buffering', 'no'); // Disable Nginx buffering

      const response = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: requestBody,
      });

      if (!response.ok) {
        const errorText = await response.text();
        res.write(
          `data: ${JSON.stringify({ error: true, status: response.status, message: errorText.slice(0, 500) })}\n\n`,
        );
        return res.end();
      }

      // Pipe the stream through
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          // Forward each SSE chunk
          res.write(chunk);
        }
      } catch (_streamErr) {
        // Client disconnected or stream error
      }

      res.write('data: [DONE]\n\n');
      return res.end();
    }

    // ─── Non-streaming mode ─────────────────────────────────────
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: requestBody,
    });

    const responseText = await response.text();

    let responseData;
    try {
      responseData = JSON.parse(responseText);
    } catch {
      responseData = { raw: responseText };
    }

    return res.status(response.status).json(responseData);
  } catch (err) {
    console.error('LLM Proxy error:', err);
    return res.status(500).json({
      error: 'Proxy request failed',
      message: err.message,
    });
  }
}
