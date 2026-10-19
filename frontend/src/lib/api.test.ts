import { afterEach, describe, expect, it, vi } from 'vitest'
import { detailMessage, shouldRedirectToLogin, streamSSE } from './api'

describe('shouldRedirectToLogin', () => {
  it('never redirects for the session probe, so logged-out visitors do not reload-loop', () => {
    expect(shouldRedirectToLogin('/auth/me', '/login')).toBe(false)
    expect(shouldRedirectToLogin('/auth/me', '/dashboard')).toBe(false)
  })

  it('does not redirect from public pages (e.g. a wrong password on /login)', () => {
    expect(shouldRedirectToLogin('/auth/login', '/login')).toBe(false)
    expect(shouldRedirectToLogin('/projects', '/')).toBe(false)
  })

  it('redirects when an authenticated page loses its session', () => {
    expect(shouldRedirectToLogin('/projects', '/dashboard')).toBe(true)
  })
})

describe('streamSSE', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('reports non-2xx JSON errors instead of finishing silently', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Daily usage limit reached. Please try again tomorrow.' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      })
    ))
    const onChunk = vi.fn()
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamSSE('/generate/chat', {}, onChunk, onDone, onError)

    expect(onError).toHaveBeenCalledWith('Daily usage limit reached. Please try again tomorrow.')
    expect(onDone).not.toHaveBeenCalled()
    expect(onChunk).not.toHaveBeenCalled()
  })

  it('falls back to a status message when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('Bad Gateway', { status: 502 })))
    const onError = vi.fn()

    await streamSSE('/generate/chat', {}, vi.fn(), vi.fn(), onError)

    expect(onError).toHaveBeenCalledWith('Request failed (502)')
  })

  it('still streams successful responses', async () => {
    const sse = 'data: {"text":"Grace "}\n\ndata: {"text":"abounds"}\n\ndata: [DONE]\n\n'
    vi.stubGlobal('fetch', vi.fn(async () => new Response(sse, { status: 200 })))
    const chunks: string[] = []
    const onDone = vi.fn()
    const onError = vi.fn()

    await streamSSE('/generate/chat', {}, (c) => chunks.push(c), onDone, onError)

    expect(chunks.join('')).toBe('Grace abounds')
    expect(onDone).toHaveBeenCalledOnce()
    expect(onError).not.toHaveBeenCalled()
  })
})

describe('detailMessage', () => {
  it('passes string details through', () => {
    expect(detailMessage('Email already registered', 'Signup failed')).toBe('Email already registered')
  })

  it('formats 422 validation arrays instead of rendering a blank toast', () => {
    const detail = [
      { loc: ['body', 'password'], msg: 'String should have at least 15 characters' },
      { loc: ['body', 'full_name'], msg: 'Value error, Name is required' },
    ]
    expect(detailMessage(detail, 'Signup failed')).toBe(
      'password: String should have at least 15 characters\nfull name: Name is required',
    )
  })

  it('falls back when there is nothing usable', () => {
    expect(detailMessage(undefined, 'Signup failed')).toBe('Signup failed')
    expect(detailMessage([], 'Signup failed')).toBe('Signup failed')
  })
})
