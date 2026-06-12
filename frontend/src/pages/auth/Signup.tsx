import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import QuillLogo from '@/components/ui/QuillLogo'
import { useAuthStore } from '@/stores/authStore'

export default function Signup() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { signup } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    try {
      await signup(email, password, fullName)
      navigate('/onboarding')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Signup failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-ink-950 flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <div className="flex justify-center mb-8">
          <Link to="/"><QuillLogo size="lg" animate={false} /></Link>
        </div>
        <div className="card p-8">
          <h1 className="font-display text-display-xs font-semibold mb-2 text-center">Begin your voice interview</h1>
          <p className="text-sm text-ink-400 text-center mb-6">It takes about 10 minutes — and The Scribe never forgets.</p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Full name</label>
              <input
                type="text"
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="input-field w-full"
                placeholder="Pastor Jane Doe"
              />
            </div>
            <div>
              <label className="block text-sm text-ink-300 mb-1.5">Email</label>
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
              <label className="block text-sm text-ink-300 mb-1.5">Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field w-full"
                placeholder="At least 8 characters"
              />
            </div>
            <button type="submit" disabled={loading} className="btn-gold w-full mt-2 disabled:opacity-50">
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>
          <p className="text-center text-sm text-ink-400 mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-gold-400 hover:underline">Log in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
