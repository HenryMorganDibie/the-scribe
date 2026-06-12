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
        <p className="text-study-300">Your voice is being honed. Here's where things stand.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Voice DNA Card */}
        <div className="lg:col-span-2 card p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Feather size={18} className="text-seal" />
              <h2 className="font-display text-display-xs font-semibold">Voice DNA</h2>
            </div>
            <Link to="/voice-profile" className="text-sm text-seal hover:underline flex items-center gap-1">
              View full profile <ArrowRight size={14} />
            </Link>
          </div>

          {loading ? (
            <div className="text-study-300 text-sm">Loading...</div>
          ) : !profile?.voice_summary ? (
            <div className="bg-seal-50 border border-seal-200 rounded-lg p-4 text-sm text-seal-500">
              Your Voice DNA is still being processed. This usually takes a minute or two after onboarding —
              check back shortly.
            </div>
          ) : (
            <div className="space-y-4">
              <div>
                <span className="text-xs text-study-300 uppercase tracking-wide">Theological Lens</span>
                <p className="text-ink font-medium">{profile.theological_lens}</p>
              </div>

              <div>
                <span className="text-xs text-study-300 uppercase tracking-wide">Cadence</span>
                <p className="text-ink font-medium">{cadenceLabel(profile.cadence_score)}</p>
              </div>

              {profile.signature_phrases && profile.signature_phrases.length > 0 && (
                <div>
                  <span className="text-xs text-study-300 uppercase tracking-wide">Signature Phrases</span>
                  <div className="flex flex-wrap gap-2 mt-1.5">
                    {profile.signature_phrases.slice(0, 6).map((p) => (
                      <span key={p} className="text-xs bg-seal-50 border border-seal-200 text-seal-400 rounded-full px-3 py-1">
                        "{p}"
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {profile.anchor_scriptures && profile.anchor_scriptures.length > 0 && (
                <div>
                  <span className="text-xs text-study-300 uppercase tracking-wide">Anchor Scriptures</span>
                  <div className="flex flex-wrap gap-2 mt-1.5">
                    {profile.anchor_scriptures.slice(0, 5).map((s) => (
                      <span key={s.ref} className="text-xs font-mono bg-paper-100 border border-paper-300 text-study-400 rounded px-2 py-1">
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
            <TrendingUp size={18} className="text-seal" />
            <h2 className="font-display text-display-xs font-semibold">Quick Actions</h2>
          </div>
          <div className="space-y-3 flex-1">
            <Link to="/projects" className="btn-primary w-full flex items-center justify-center gap-2">
              <Plus size={16} /> New Manuscript
            </Link>
            <Link to="/testimonies" className="btn-secondary w-full flex items-center justify-center gap-2">
              Add Testimony
            </Link>
            <Link to="/voice-profile" className="btn-secondary w-full flex items-center justify-center gap-2">
              Voice Evolution Timeline
            </Link>
          </div>
        </div>
      </div>

      {/* Recent Projects */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BookOpen size={18} className="text-seal" />
            <h2 className="font-display text-display-xs font-semibold">Your Manuscripts</h2>
          </div>
          <Link to="/projects" className="text-sm text-seal hover:underline">View all</Link>
        </div>

        {projects.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-study-300 mb-4">You haven't started a manuscript yet.</p>
            <Link to="/projects" className="btn-primary inline-flex items-center gap-2">
              <Plus size={16} /> Start your first manuscript
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {projects.slice(0, 3).map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="card p-4 hover:border-seal/50">
                <h3 className="font-display font-semibold text-lg mb-1">{p.title}</h3>
                <span className="text-xs text-study-300 capitalize">{p.genre}</span>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
