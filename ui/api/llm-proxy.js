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

/**
 * Validate the request body and return a normalized request descriptor,
 * or send an error response and return null if the request is invalid.
 *
 * Extracted from `handler` to keep the main function's cognitive
 * complexity under 15 (SonarCloud S3776).
 */
function parseProxyRequest(req, res) {
  const { endpoint, apiKey, body, headers: customHeaders, stream } = req.body || {}

  if (!endpoint || !apiKey || !body) {
    res.status(400).json({
      error: 'Missing required fields: endpoint, apiKey, body',
    })
    return null
  }

  const headers = {
    'Content-Type': 'application/json',
    ...customHeaders,
  }

  if (!headers['Authorization'] && !headers['authorization']) {
    headers['Authorization'] = `Bearer ${apiKey}`
  }

  // Add stream: true to the body if streaming is requested
  const requestBody = typeof body === 'string'
    ? body
    : JSON.stringify({ ...body, stream: stream ? true : undefined })

  return { endpoint, apiKey, headers, requestBody, stream: !!stream }
}

/**
 * Streaming mode: pipe the upstream SSE response to the client.
 * Extracted from `handler` to reduce cognitive complexity (SonarCloud S3776).
 */
async function handleStreamingMode(res, endpoint, headers, requestBody) {
  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.setHeader('X-Accel-Buffering', 'no') // Disable Nginx buffering

  const response = await fetch(endpoint, {
    method: 'POST',
    headers,
    body: requestBody,
  })

  if (!response.ok) {
    const errorText = await response.text()
    res.write(`data: ${JSON.stringify({ error: true, status: response.status, message: errorText.slice(0, 500) })}\n\n`)
    res.end()
    return
  }

  // Pipe the stream through
  const reader = response.body.getReader()
  const decoder = new TextDecoder()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      const chunk = decoder.decode(value, { stream: true })
      // Forward each SSE chunk
      res.write(chunk)
    }
  } catch (_streamErr) {
    // Client disconnected or stream error — best-effort, nothing to do.
  }

  res.write('data: [DONE]\n\n')
  res.end()
}

/**
 * Non-streaming mode: forward the upstream JSON/text response to the client.
 * Extracted from `handler` to reduce cognitive complexity (SonarCloud S3776).
 */
async function handleNonStreamingMode(res, endpoint, headers, requestBody) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers,
    body: requestBody,
  })

  const responseText = await response.text()

  let responseData
  try {
    responseData = JSON.parse(responseText)
  } catch {
    responseData = { raw: responseText }
  }

  res.status(response.status).json(responseData)
}

export default async function handler(req, res) {
  // CORS preflight + method gate
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')

  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  try {
    const parsed = parseProxyRequest(req, res)
    if (!parsed) return // parseProxyRequest already sent the error response

    const { endpoint, headers, requestBody, stream } = parsed

    if (stream) {
      await handleStreamingMode(res, endpoint, headers, requestBody)
      return
    }

    await handleNonStreamingMode(res, endpoint, headers, requestBody)
  } catch (err) {
    console.error('LLM Proxy error:', err)
    return res.status(500).json({
      error: 'Proxy request failed',
      message: err.message,
    })
  }
}
