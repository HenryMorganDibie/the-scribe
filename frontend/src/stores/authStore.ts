import { create } from 'zustand'
import { api } from '@/lib/api'

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
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,

  login: async (email, password) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const res = await api.post('/auth/login', form, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    localStorage.setItem('scribe_token', res.data.access_token)
    set({ user: res.data.user })
  },

  signup: async (email, password, fullName) => {
    const res = await api.post('/auth/signup', { email, password, full_name: fullName })
    localStorage.setItem('scribe_token', res.data.access_token)
    set({ user: res.data.user })
  },

  logout: () => {
    localStorage.removeItem('scribe_token')
    set({ user: null })
  },

  fetchMe: async () => {
    const token = localStorage.getItem('scribe_token')
    if (!token) {
      set({ loading: false })
      return
    }
    try {
      const res = await api.get('/auth/me')
      set({ user: res.data, loading: false })
    } catch {
      localStorage.removeItem('scribe_token')
      set({ user: null, loading: false })
    }
  },
}))
