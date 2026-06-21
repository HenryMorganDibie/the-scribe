import axios from 'axios'

// Resolution order: explicit VITE_API_URL (set in Vercel/Render) wins; otherwise
// production builds default to the deployed backend and dev builds use localhost.
const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? 'https://the-scribe.onrender.com/api' : 'http://localhost:8000/api')

export const api = axios.create({ baseURL: API_URL })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('scribe_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('scribe_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

/**
 * Stream an SSE endpoint, calling onChunk for each text delta.
 * Used for: chapter generation, continue, weave-story, chat, companion-chat.
 *
 * onEvent is called for any parsed JSON payload that has no `text` or
 * `error` key (e.g. companion-chat's final `{cited_chapter_ids: [...]}`
 * event) — onChunk only fires for text deltas, onEvent for everything else,
 * so existing callers that only pass onChunk are unaffected.
 */
export async function streamSSE(
  path: string,
  body: object,
  onChunk: (text: string) => void,
  onDone?: () => void,
  onError?: (err: string) => void,
  onEvent?: (payload: any) => void
) {
  const token = localStorage.getItem('scribe_token')
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: token ? `Bearer ${token}` : '',
    },
    body: JSON.stringify(body),
  })

  if (!res.body) return

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const data = line.slice(6)

      if (data === '[DONE]') {
        onDone?.()
        return
      }

      try {
        const parsed = JSON.parse(data)
        if (parsed.error) {
          onError?.(parsed.error)
        } else if (parsed.text) {
          onChunk(parsed.text)
        } else {
          onEvent?.(parsed)
        }
      } catch {
        // For onboarding preview, raw text chunks (not JSON)
        onChunk(data)
      }
    }
  }
  onDone?.()
}
