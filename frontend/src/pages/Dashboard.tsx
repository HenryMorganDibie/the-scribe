import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, BookOpen, Feather, ArrowRight, TrendingUp } from 'lucide-react'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

interface Project {
  id: string
  title: string
  genre: string
  status: string
  updated_at: string
}

interface VoiceProfileData {
  theological_lens?: string
  signature_phrases?: string[]
  anchor_scriptures?: { ref: string; themes?: string[] }[]
  cadence_score?: number
  style_tags?: string[]
  voice_summary?: string
}

function cadenceLabel(score?: number) {
  if (score === undefined) return 'Not yet calculated'
  if (score < 0.3) return 'Punchy & Declarative'
  if (score < 0.6) return 'Balanced'
  return 'Flowing & Expansive'
}

export default function Dashboard() {
  const { user } = useAuthStore()
  const [projects, setProjects] = useState<Project[]>([])
  const [profile, setProfile] = useState<VoiceProfileData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get('/projects').then((r) => setProjects(r.data)),
      api.get('/voice-profile').then((r) => setProfile(r.data)).catch(() => null),
    ]).finally(() => setLoading(false))
  }, [])

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="font-display text-display-md font-semibold mb-1">
          Welcome back, {user?.full_name?.split(' ')[0]}
        </h1>
        <p className="text-ink-400">Your voice is being honed. Here's where things stand.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Voice DNA Card */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Feather size={18} className="text-gold-400" />
              <h2 className="font-display text-display-xs font-semibold">Voice DNA</h2>
            </div>
            <Link to="/voice-profile" className="text-sm text-gold-400 hover:underline flex items-center gap-1">
              View full profile <ArrowRight size={14} />
            </Link>
          </div>

          {loading ? (
            <div className="text-ink-400 text-sm">Loading...</div>
          ) : !profile?.voice_summary ? (
            <div className="bg-gold-800/30 border border-gold-700/50 rounded-lg p-4 text-sm text-gold-200">
              Your Voice DNA is still being processed. This usually takes a minute or two after onboarding —
              check back shortly.
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <span className="text-xs text-ink-400 uppercase tracking-wide">Theological Lens</span>
                <p className="text-ink-100 font-medium">{profile.theological_lens}</p>
              </div>

              <div>
                <span className="text-xs text-ink-400 uppercase tracking-wide">Cadence</span>
                <p className="text-ink-100 font-medium">{cadenceLabel(profile.cadence_score)}</p>
              </div>

              {profile.signature_phrases && profile.signature_phrases.length > 0 && (
                <div>
                  <span className="text-xs text-ink-400 uppercase tracking-wide">Signature Phrases</span>
                  <div className="flex flex-wrap gap-2 mt-1.5">
                    {profile.signature_phrases.slice(0, 6).map((p) => (
                      <span key={p} className="text-xs bg-gold-800/40 border border-gold-700/50 text-gold-300 rounded-full px-3 py-1">
                        "{p}"
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {profile.anchor_scriptures && profile.anchor_scriptures.length > 0 && (
                <div>
                  <span className="text-xs text-ink-400 uppercase tracking-wide">Anchor Scriptures</span>
                  <div className="flex flex-wrap gap-2 mt-1.5">
                    {profile.anchor_scriptures.slice(0, 5).map((s) => (
                      <span key={s.ref} className="text-xs font-mono bg-ink-900 border border-ink-600 text-ink-200 rounded px-2 py-1">
                        {s.ref}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Quick actions */}
        <div className="card p-6 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={18} className="text-gold-400" />
            <h2 className="font-display text-display-xs font-semibold">Quick Actions</h2>
          </div>
          <div className="space-y-3 flex-1">
            <Link to="/projects" className="btn-gold w-full flex items-center justify-center gap-2">
              <Plus size={16} /> New Manuscript
            </Link>
            <Link to="/testimonies" className="btn-ghost w-full flex items-center justify-center gap-2">
              Add Testimony
            </Link>
            <Link to="/voice-profile" className="btn-ghost w-full flex items-center justify-center gap-2">
              Voice Evolution Timeline
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Projects */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-gold-400" />
            <h2 className="font-display text-display-xs font-semibold">Your Manuscripts</h2>
          </div>
          <Link to="/projects" className="text-sm text-gold-400 hover:underline">View all</Link>
        </div>

        {projects.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-ink-400 mb-4">You haven't started a manuscript yet.</p>
            <Link to="/projects" className="btn-gold inline-flex items-center gap-2">
              <Plus size={16} /> Start your first manuscript
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {projects.slice(0, 3).map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="card p-4 hover:border-gold-400/50">
                <h3 className="font-display font-semibold text-lg mb-1">{p.title}</h3>
                <span className="text-xs text-ink-400 capitalize">{p.genre}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
