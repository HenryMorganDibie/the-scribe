import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Feather, GitCommit, TrendingUp, TrendingDown, Minus, BookOpen, Activity, Pencil } from 'lucide-react'
import { api } from '@/lib/api'
import toast from 'react-hot-toast'

interface VoiceProfileData {
  theological_lens?: string
  signature_phrases?: string[]
  anchor_scriptures?: { ref: string; themes?: string[] }[]
  cadence_score?: number
  style_tags?: string[]
  voice_summary?: string
  tone_preferences?: string[]
  preferred_translation?: string
}

interface VoiceVersion {
  id: string
  version_number: number
  trigger: string
  change_summary?: string
  cadence_score?: number
  phrase_count?: number
  scripture_count?: number
  created_at: string
}

const triggerLabels: Record<string, string> = {
  onboarding_complete: 'Voice Interview Completed',
  edit_accepted: 'Learned from Edit',
  manual_update: 'Manual Update',
}

function cadenceLabel(score?: number) {
  if (score === undefined || score === null) return '—'
  if (score < 0.3) return 'Punchy & Declarative'
  if (score < 0.6) return 'Balanced'
  return 'Flowing & Expansive'
}

export default function VoiceProfile() {
  const [profile, setProfile] = useState<VoiceProfileData | null>(null)
  const [timeline, setTimeline] = useState<VoiceVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [editSummary, setEditSummary] = useState('')
  const [editTranslation, setEditTranslation] = useState('')
  const [editPhrases, setEditPhrases] = useState('')

  const startEdit = () => {
    setEditSummary(profile?.voice_summary || '')
    setEditTranslation(profile?.preferred_translation || 'NKJV')
    setEditPhrases((profile?.signature_phrases || []).join('\n'))
    setEditing(true)
  }

  const saveEdit = async () => {
    try {
      const phrases = editPhrases.split('\n').map((p) => p.trim()).filter(Boolean)
      await api.put('/voice-profile', {
        voice_summary: editSummary,
        preferred_translation: editTranslation,
        signature_phrases: phrases,
      })
      setProfile((prev) => prev ? { ...prev, voice_summary: editSummary, preferred_translation: editTranslation, signature_phrases: phrases } : prev)
      setEditing(false)
      toast.success('Voice profile updated')
    } catch {
      toast.error('Failed to save')
    }
  }

  useEffect(() => {
    Promise.all([
      api.get('/voice-profile').then((r) => setProfile(r.data)).catch(() => null),
      api.get('/voice-profile/timeline').then((r) => setTimeline(r.data)).catch(() => []),
    ]).finally(() => setLoading(false))
  }, [])

  if (loading) {
    return <div className="p-8 text-study-300">Loading your Voice DNA...</div>
  }

  return (
    <div className="px-4 py-6 md:p-8 max-w-5xl mx-auto">
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Feather size={24} className="text-seal" />
          <h1 className="font-display text-display-md font-semibold">Voice DNA</h1>
        </div>
        <div className="flex gap-2">
          {profile?.voice_summary && (
            <button onClick={startEdit} className="btn-secondary flex items-center gap-2 text-sm">
              <Pencil size={14} /> Edit Voice
            </button>
          )}
          <Link to="/voice-profile/drift-analytics" className="btn-secondary flex items-center gap-2 text-sm">
            <Activity size={16} /> Drift Analytics
          </Link>
        </div>
      </div>

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-paper rounded-xl p-6 w-full max-w-lg space-y-4 shadow-xl max-h-[90vh] overflow-y-auto">
            <h2 className="font-display text-display-xs font-semibold">Edit Voice Profile</h2>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Ghost Brief (voice summary)</label>
              <textarea
                value={editSummary}
                onChange={(e) => setEditSummary(e.target.value)}
                className="input-field w-full h-32 resize-none text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Preferred Bible Translation</label>
              <select value={editTranslation} onChange={(e) => setEditTranslation(e.target.value)} className="input-field w-full">
                {['NKJV', 'KJV', 'NIV', 'ESV', 'NLT', 'NASB', 'AMP'].map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Signature Phrases (one per line)</label>
              <textarea
                value={editPhrases}
                onChange={(e) => setEditPhrases(e.target.value)}
                className="input-field w-full h-32 resize-none text-sm font-mono"
                placeholder={"What if\nLet that sink in\nThere are seasons in life"}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(false)} className="btn-secondary">Cancel</button>
              <button onClick={saveEdit} className="btn-primary">Save changes</button>
            </div>
          </div>
        </div>
      )}

      {!profile?.voice_summary ? (
        <div className="bg-seal-50 border border-seal-200 rounded-lg p-6 text-seal-500">
          Your Voice DNA is still being processed in the background. This typically takes 1-2 minutes
          after completing onboarding. Refresh this page shortly.
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-10">
          {/* Voice summary */}
          <div className="lg:col-span-2 card p-6">
            <h2 className="font-display text-display-xs font-semibold mb-3">Your Ghost Brief</h2>
            <p className="text-study-400 leading-relaxed whitespace-pre-line">{profile.voice_summary}</p>
          </div>

          {/* Stats */}
          <div className="card p-6 space-y-4">
            <div>
              <span className="text-xs text-study-300 uppercase tracking-wide">Theological Lens</span>
              <p className="text-ink font-medium">{profile.theological_lens || '—'}</p>
            </div>
            <div>
              <span className="text-xs text-study-300 uppercase tracking-wide">Cadence</span>
              <p className="text-ink font-medium">{cadenceLabel(profile.cadence_score)}</p>
              {profile.cadence_score !== undefined && (
                <div className="mt-2 h-1.5 bg-paper-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-seal transition-all"
                    style={{ width: `${(profile.cadence_score || 0) * 100}%` }}
                  />
                </div>
              )}
            </div>
            <div>
              <span className="text-xs text-study-300 uppercase tracking-wide">Translation</span>
              <p className="text-ink font-medium">{profile.preferred_translation || 'NKJV'}</p>
            </div>
          </div>

          {/* Signature phrases */}
          {profile.signature_phrases && profile.signature_phrases.length > 0 && (
            <div className="lg:col-span-3 card p-6">
              <h2 className="font-display text-display-xs font-semibold mb-3">Signature Phrases</h2>
              <div className="flex flex-wrap gap-2">
                {profile.signature_phrases.map((p) => (
                  <span key={p} className="text-sm bg-seal-50 border border-seal-200 text-seal-400 rounded-full px-3 py-1.5">
                    "{p}"
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Anchor scriptures */}
          {profile.anchor_scriptures && profile.anchor_scriptures.length > 0 && (
            <div className="lg:col-span-3 card p-6">
              <h2 className="font-display text-display-xs font-semibold mb-3 flex items-center gap-2">
                <BookOpen size={16} className="text-seal" /> Anchor Scriptures
              </h2>
              <div className="flex flex-wrap gap-3">
                {profile.anchor_scriptures.map((s) => (
                  <div key={s.ref} className="scripture-block py-2 px-3">
                    <span className="font-mono text-sm not-italic text-seal-400">{s.ref}</span>
                    {s.themes && s.themes.length > 0 && (
                      <div className="text-xs text-study-300 mt-1 not-italic">{s.themes.join(', ')}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Style tags */}
          {profile.style_tags && profile.style_tags.length > 0 && (
            <div className="lg:col-span-3 card p-6">
              <h2 className="font-display text-display-xs font-semibold mb-3">Style Characteristics</h2>
              <div className="flex flex-wrap gap-2">
                {profile.style_tags.map((t) => (
                  <span key={t} className="text-xs bg-paper-200 border border-paper-300 text-study-400 rounded px-2.5 py-1 capitalize">
                    {t.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Voice Evolution Timeline */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <GitCommit size={20} className="text-seal" />
          <h2 className="font-display text-display-sm font-semibold">Voice Evolution Timeline</h2>
        </div>
        <p className="text-study-300 text-sm mb-6">
          Your voice profile evolves like a commit history — every refinement is tracked, like a
          ghostwriter who learns more about you with every chapter.
        </p>

        {timeline.length === 0 ? (
          <div className="text-ink0 text-sm italic">No voice versions yet.</div>
        ) : (
          <div className="relative pl-8 space-y-6">
            <div className="absolute left-3 top-2 bottom-2 w-px bg-paper-200" />
            {timeline.map((v, idx) => {
              const prev = timeline[idx + 1]
              const cadenceDelta = prev ? (v.cadence_score || 0) - (prev.cadence_score || 0) : 0
              const phraseDelta = prev ? (v.phrase_count || 0) - (prev.phrase_count || 0) : 0

              return (
                <div key={v.id} className="relative">
                  <div className="absolute -left-8 top-1.5 w-6 h-6 rounded-full bg-wax-gradient flex items-center justify-center text-paper-50 text-xs font-bold">
                    v{v.version_number}
                  </div>
                  <div className="card p-4">
                    <div className="flex items-center justify-between mb-1">
                      <h3 className="font-medium text-ink">{triggerLabels[v.trigger] || v.trigger}</h3>
                      <span className="text-xs text-study-300">
                        {new Date(v.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                      </span>
                    </div>
                    {v.change_summary && <p className="text-sm text-study-400 mb-2">{v.change_summary}</p>}

                    <div className="flex flex-wrap gap-3 text-xs text-study-300 mt-2">
                      <span className="flex items-center gap-1">
                        {v.phrase_count ?? 0} signature phrases
                        {idx < timeline.length - 1 && phraseDelta !== 0 && (
                          <span className={phraseDelta > 0 ? 'text-green-400' : 'text-red-400'}>
                            ({phraseDelta > 0 ? '+' : ''}{phraseDelta})
                          </span>
                        )}
                      </span>
                      <span>•</span>
                      <span>{v.scripture_count ?? 0} anchor scriptures</span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        Cadence: {cadenceLabel(v.cadence_score)}
                        {idx < timeline.length - 1 && (
                          cadenceDelta > 0.02 ? <TrendingUp size={12} className="text-green-400" /> :
                          cadenceDelta < -0.02 ? <TrendingDown size={12} className="text-blue-400" /> :
                          <Minus size={12} className="text-ink0" />
                        )}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
