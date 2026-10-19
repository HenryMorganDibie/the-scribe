import axios from 'axios'

// Resolution order: explicit VITE_API_URL (set in Vercel/Render) wins; otherwise
// production builds default to the deployed backend and dev builds use localhost.
const API_URL =
  import.meta.env.VITE_API_URL ||
  (import.meta.env.PROD ? '/api' : 'http://localhost:8000/api')

// The browser never stores the login cookie or bearer token. This value is a
// short-lived CSRF secret kept in memory and sent only with state changes.
let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

export function getCsrfToken() {
  return csrfToken
}

const PUBLIC_PATHS = ['/', '/login', '/signup']

/**
 * Whether a 401 should bounce the browser to /login. The session probe
 * (/auth/me) is expected to 401 for logged-out visitors — the auth store
 * handles that — and redirecting from a public page reloads it, which runs
 * the probe again and loops forever.
 */
export function shouldRedirectToLogin(requestUrl: string | undefined, pathname: string) {
  if (requestUrl?.replace(/^\//, '').startsWith('auth/me')) return false
  return !PUBLIC_PATHS.includes(pathname)
}

/** Pull a readable message out of a non-2xx response body. */
export async function errorMessageFrom(res: Response) {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
    if (typeof body?.error === 'string') return body.error
  } catch {
    // Non-JSON body — fall through to the generic message.
  }
  if (res.status === 429) return 'Daily usage limit reached. Please try again tomorrow.'
  return `Request failed (${res.status})`
}

export const api = axios.create({ baseURL: API_URL, withCredentials: true })

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase()
  if (csrfToken && method && !['get', 'head', 'options'].includes(method)) {
    config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      setCsrfToken(null)
      localStorage.removeItem('scribe_token') // clears sessions from the pre-cookie release
      if (shouldRedirectToLogin(err.config?.url, window.location.pathname)) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

/** Stream an SSE endpoint while authenticating with the secure session cookie. */
export async function streamSSE(
  path: string,
  body: object,
  onChunk: (text: string) => void,
  onDone?: () => void,
  onError?: (err: string) => void,
  onEvent?: (payload: any) => void
) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
    },
    body: JSON.stringify(body),
  })

  // Quota (429), CSRF (403) and ownership (404) failures arrive as JSON,
  // not SSE — surface them instead of silently reporting an empty stream.
  if (!res.ok) {
    onError?.(await errorMessageFrom(res))
    return
  }
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
        if (parsed.error) onError?.(parsed.error)
        else if (parsed.text) onChunk(parsed.text)
        else onEvent?.(parsed)
      } catch {
        onChunk(data)
      }
    }
  }
  onDone?.()
}
