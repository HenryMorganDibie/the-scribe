import { useCallback, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore } from '@/stores/authStore'
import GoogleSignInButton from '@/components/auth/GoogleSignInButton'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, googleLogin } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await login(email, password)
      navigate('/dashboard')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleCredential = useCallback(async (credential: string) => {
    setLoading(true)
    try {
      await googleLogin(credential)
      navigate('/dashboard')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Google sign-in failed')
    } finally {
      setLoading(false)
    }
  }, [googleLogin, navigate])

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="mb-8">
          <Link to="/"><QuillLogo size="lg" /></Link>
        </div>
        <div className="card p-8">
          <h1 className="font-display text-display-xs font-semibold mb-6">Log in</h1>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="input-field w-full"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Password</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field w-full"
                placeholder="••••••••"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-primary w-full mt-2">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
          <div className="flex items-center gap-3 my-6 text-xs text-study-300">
            <div className="h-px bg-rule flex-1" />
            <span>or</span>
            <div className="h-px bg-rule flex-1" />
          </div>
          <GoogleSignInButton onCredential={handleGoogleCredential} onError={toast.error} />
          <p className="text-sm text-study-300 mt-6">
            New here?{' '}
            <Link to="/signup" className="text-seal hover:underline">Create an account</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
