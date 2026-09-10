import { create } from 'zustand'
import { api, setCsrfToken } from '@/lib/api'

interface User {
  id: string
  email: string
  full_name: string
  onboarded: boolean
  avatar_url?: string
}

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string, fullName: string) => Promise<void>
  googleLogin: (credential: string) => Promise<void>
  logout: () => Promise<void>
  fetchMe: () => Promise<void>
}

function acceptLogin(res: { data: { csrf_token: string; user: User } }, set: (state: Partial<AuthState>) => void) {
  localStorage.removeItem('scribe_token') // remove legacy browser-persisted JWTs
  setCsrfToken(res.data.csrf_token)
  set({ user: res.data.user, loading: false })
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,

  login: async (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const res = await api.post('/auth/login', form, { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } })
    acceptLogin(res, set)
  },

  signup: async (email, password, fullName) => {
    const res = await api.post('/auth/signup', { email, password, full_name: fullName })
    acceptLogin(res, set)
  },

  googleLogin: async (credential) => {
    const res = await api.post('/auth/google', { credential })
    acceptLogin(res, set)
  },

  logout: async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // The local browser should still be logged out if the session expired.
    }
    setCsrfToken(null)
    localStorage.removeItem('scribe_token')
    set({ user: null, loading: false })
  },

  fetchMe: async () => {
    try {
      const res = await api.get('/auth/me')
      setCsrfToken(res.data.csrf_token || null)
      set({ user: res.data, loading: false })
    } catch {
      setCsrfToken(null)
      localStorage.removeItem('scribe_token')
      set({ user: null, loading: false })
    }
  },
}))
