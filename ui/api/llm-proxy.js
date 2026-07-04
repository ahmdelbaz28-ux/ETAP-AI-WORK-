/**
 * Vercel Serverless Function — LLM API Proxy
 * ============================================
 * 
 * Solves CORS issue: browsers can't directly call OpenCode Zen, OpenAI, etc.
 * because those APIs don't send CORS headers. This proxy forwards requests
 * server-to-server (no CORS restriction) and returns the response with
 * proper CORS headers.
 * 
 * Usage:
 *   POST /api/llm-proxy
 *   Body: { endpoint, apiKey, body }
 *   Response: The provider's response JSON
 */

export default async function handler(req, res) {
  // Only allow POST
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' })
  }

  // Set CORS headers for our own domain
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')

  // Handle preflight
  if (req.method === 'OPTIONS') {
    return res.status(200).end()
  }

  try {
    const { endpoint, apiKey, body, headers: customHeaders } = req.body

    if (!endpoint || !apiKey || !body) {
      return res.status(400).json({ 
        error: 'Missing required fields: endpoint, apiKey, body' 
      })
    }

    // Build headers
    const headers = {
      'Content-Type': 'application/json',
      ...customHeaders,
    }

    // If customHeaders doesn't have Authorization, add it from apiKey
    if (!headers['Authorization'] && !headers['authorization']) {
      headers['Authorization'] = `Bearer ${apiKey}`
    }

    // Forward the request to the provider
    const response = await fetch(endpoint, {
      method: 'POST',
      headers,
      body: typeof body === 'string' ? body : JSON.stringify(body),
    })

    // Get the response
    const responseText = await response.text()
    
    // Try to parse as JSON, fall back to text
    let responseData
    try {
      responseData = JSON.parse(responseText)
    } catch {
      responseData = { raw: responseText }
    }

    // Return with the same status code
    return res.status(response.status).json(responseData)
  } catch (err) {
    console.error('LLM Proxy error:', err)
    return res.status(500).json({ 
      error: 'Proxy request failed',
      message: err.message 
    })
  }
}
