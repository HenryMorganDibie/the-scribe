import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, ChevronDown, ChevronUp, Flame, Loader2, Pencil } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { STAGES } from '@/lib/stages'

interface Progress {
  total_words: number
  target_word_count: number | null
  percent_complete: number | null
  deadline: string | null
  days_left: number | null
  words_left: number | null
  needed_per_day: number | null
  daily_word_goal: number | null
  today_words: number
  current_streak: number
  longest_streak: number
  chapters_total: number
  target_chapters: number
  stage_counts: Record<string, number>
  history: { day: string; words_added: number }[]
  next_steps: { kind: string; message: string; chapter_id?: string }[]
}

interface Props {
  projectId: string
  /** Bump to reload after chapters change. */
  refreshKey: number
}

const fmt = (n: number) => n.toLocaleString()

export default function ProgressPanel({ projectId, refreshKey }: Props) {
  const [p, setP] = useState<Progress | null>(null)
  const [editing, setEditing] = useState(false)
  const [target, setTarget] = useState('')
  const [daily, setDaily] = useState('')
  const [deadline, setDeadline] = useState('')
  const [saving, setSaving] = useState(false)
  const [showDetails, setShowDetails] = useState(false)

  const load = useCallback(() => {
    api.get(`/projects/${projectId}/progress`).then((r) => setP(r.data)).catch(() => toast.error('Failed to load progress'))
  }, [projectId])

  useEffect(load, [load, refreshKey])

  const startEdit = () => {
    setTarget(p?.target_word_count ? String(p.target_word_count) : '')
    setDaily(p?.daily_word_goal ? String(p.daily_word_goal) : '')
    setDeadline(p?.deadline ?? '')
    setEditing(true)
  }

  const saveGoals = async () => {
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}`, {
        target_word_count: Number(target) || 0,
        daily_word_goal: Number(daily) || 0,
        ...(deadline ? { deadline } : { clear_deadline: true }),
      })
      setEditing(false)
      load()
      toast.success('Goals saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  if (!p) return <div className="card p-4 mb-6 text-sm text-study-400">Loading progress…</div>

  const peak = Math.max(...p.history.map((h) => h.words_added), p.daily_word_goal ?? 0, 1)
  const [nextStep, ...laterSteps] = p.next_steps
  const deadlineText = p.deadline
    ? p.days_left! < 0
      ? `Deadline passed ${-p.days_left!} day${p.days_left === -1 ? '' : 's'} ago`
      : `${p.days_left} day${p.days_left === 1 ? '' : 's'} to deadline${p.needed_per_day ? ` · ~${fmt(p.needed_per_day)}/day` : ''}`
    : null

  return (
    <section className="card p-4 md:p-5 mb-6" aria-label="Progress">
      {editing ? (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <label className="text-xs text-study-400">Target words
              <input type="number" min={0} value={target} onChange={(e) => setTarget(e.target.value)} className="input-field w-full text-sm mt-1" placeholder="e.g. 60000" />
            </label>
            <label className="text-xs text-study-400">Daily goal
              <input type="number" min={0} value={daily} onChange={(e) => setDaily(e.target.value)} className="input-field w-full text-sm mt-1" placeholder="e.g. 500" />
            </label>
            <label className="text-xs text-study-400">Deadline
              <input type="date" value={deadline} onChange={(e) => setDeadline(e.target.value)} className="input-field w-full text-sm mt-1" />
            </label>
          </div>
          <p className="text-xs text-study-400">Leave a field empty to remove that goal.</p>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditing(false)} className="btn-secondary text-sm">Cancel</button>
            <button onClick={saveGoals} disabled={saving} className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
              {saving && <Loader2 size={14} className="animate-spin" />} Save goals
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-x-7 gap-y-3">
          <div className="flex-1 min-w-[240px]">
            <div className="flex items-baseline justify-between text-sm mb-1.5">
              <span><span className="font-semibold">{fmt(p.total_words)}</span> words{p.target_word_count ? ` of ${fmt(p.target_word_count)}` : ''}</span>
              {p.percent_complete !== null && <span className="text-seal font-medium">{p.percent_complete}%</span>}
            </div>
            {p.target_word_count ? (
              <div className="h-1.5 bg-paper-200 rounded-full overflow-hidden">
                <div className="h-full bg-seal transition-all" style={{ width: `${p.percent_complete ?? 0}%` }} />
              </div>
            ) : (
              <button onClick={startEdit} className="text-xs text-seal hover:underline">Set a word target to track progress</button>
            )}
          </div>
          <span className="text-sm text-study-400">
            <span className="font-semibold text-ink">{fmt(p.today_words)}</span>{p.daily_word_goal ? ` / ${fmt(p.daily_word_goal)}` : ''} today
          </span>
          <span className="text-sm text-study-400 flex items-center gap-1.5">
            <Flame size={15} className={p.current_streak ? 'text-seal' : 'text-study-300'} aria-hidden="true" />
            <span className="font-semibold text-ink">{p.current_streak}-day</span> streak
          </span>
          {deadlineText && <span className="text-sm text-study-400">{deadlineText}</span>}
          <div className="flex items-center gap-1 ml-auto">
            <button onClick={() => setShowDetails((d) => !d)} aria-expanded={showDetails} className="toolbar-btn text-xs">
              {showDetails ? <ChevronUp size={14} /> : <ChevronDown size={14} />} Details
            </button>
            <button onClick={startEdit} className="toolbar-btn text-xs"><Pencil size={13} /> Goals</button>
          </div>
        </div>
      )}

      {showDetails && !editing && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-5 pt-5 border-t border-paper-200 animate-fade-in-up">
          <div className="md:col-span-2">
            <p className="folio mb-2">Last 14 days</p>
            <div className="flex items-end gap-1 h-16" aria-label="Words written over the last 14 days">
              {p.history.map((h) => (
                <div key={h.day} className="flex-1 flex flex-col justify-end h-full" title={`${h.day}: ${fmt(h.words_added)} words`}>
                  <div
                    className={`rounded-sm ${h.words_added ? 'bg-seal' : 'bg-paper-300'}`}
                    style={{ height: `${Math.max(h.words_added ? 8 : 4, (h.words_added / peak) * 100)}%` }}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[11px] text-study-400 mt-1"><span>14 days ago</span><span>Today</span></div>
          </div>
          <div className="space-y-3">
            <div>
              <p className="folio mb-1.5">Chapters</p>
              <div className="flex flex-wrap gap-1.5">
                {STAGES.map((s) => (
                  <span key={s.id} className={`status-tag ${s.className}`}>{s.label} {p.stage_counts[s.id] ?? 0}</span>
                ))}
              </div>
            </div>
            <p className="text-sm text-study-400">Best streak: {p.longest_streak} day{p.longest_streak === 1 ? '' : 's'}</p>
          </div>
          {laterSteps.length > 0 && (
            <div className="md:col-span-3">
              <p className="folio mb-1.5">After that</p>
              <ol className="space-y-1.5">
                {laterSteps.map((step, i) => (
                  <li key={i} className="text-sm">
                    {step.chapter_id ? (
                      <Link to={`/projects/${projectId}/chapters/${step.chapter_id}`} className="hover:text-seal inline-flex items-center gap-1">
                        {step.message} <ArrowRight size={13} />
                      </Link>
                    ) : step.message}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}

      {nextStep && (
        <div className="flex flex-wrap items-center justify-between gap-3 mt-4 pt-4 border-t border-paper-200">
          <div>
            <p className="folio">Next up</p>
            <p className="text-sm mt-0.5">{nextStep.message}</p>
          </div>
          {nextStep.chapter_id && (
            <Link to={`/projects/${projectId}/chapters/${nextStep.chapter_id}`} className="btn-primary text-sm flex items-center gap-2">
              Continue writing <ArrowRight size={15} />
            </Link>
          )}
        </div>
      )}
    </section>
  )
}
