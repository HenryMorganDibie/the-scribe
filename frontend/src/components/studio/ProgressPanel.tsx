import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Flame, Loader2, Pencil, Target } from 'lucide-react'
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

  if (!p) return <div className="card p-4 mb-6 text-sm text-study-300">Loading progress…</div>

  const peak = Math.max(...p.history.map((h) => h.words_added), p.daily_word_goal ?? 0, 1)
  const todayGoalPct = p.daily_word_goal ? Math.min(100, Math.round((p.today_words / p.daily_word_goal) * 100)) : null

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      {/* Goals & pace */}
      <div className="card p-4 md:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs uppercase tracking-wide text-study-300 flex items-center gap-1.5"><Target size={13} /> Progress</p>
          {!editing && <button onClick={startEdit} className="text-xs text-seal hover:underline flex items-center gap-1"><Pencil size={12} /> Goals</button>}
        </div>

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
            <p className="text-xs text-study-300">Leave a field empty to remove that goal.</p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditing(false)} className="btn-secondary text-sm">Cancel</button>
              <button onClick={saveGoals} disabled={saving} className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
                {saving && <Loader2 size={14} className="animate-spin" />} Save goals
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-baseline justify-between text-sm mb-2">
              <span className="font-medium">{fmt(p.total_words)} words{p.target_word_count ? ` of ${fmt(p.target_word_count)}` : ''}</span>
              {p.percent_complete !== null && <span className="text-seal">{p.percent_complete}%</span>}
            </div>
            {p.target_word_count && (
              <div className="h-2 bg-paper-200 rounded-full overflow-hidden mb-2">
                <div className="h-full bg-seal transition-all" style={{ width: `${p.percent_complete ?? 0}%` }} />
              </div>
            )}
            <p className="text-xs text-study-300">
              {p.deadline
                ? p.days_left! < 0
                  ? `Deadline passed ${-p.days_left!} day${p.days_left === -1 ? '' : 's'} ago.`
                  : `${p.days_left} day${p.days_left === 1 ? '' : 's'} to your deadline${p.needed_per_day ? ` · about ${fmt(p.needed_per_day)} words a day to finish` : ''}.`
                : p.target_word_count ? 'Add a deadline to see the pace you need.' : 'Set a word target and deadline to track your pace.'}
            </p>

            {/* Last 14 days */}
            <div className="flex items-end gap-1 h-16 mt-4" aria-label="Words written over the last 14 days">
              {p.history.map((h) => (
                <div key={h.day} className="flex-1 flex flex-col justify-end h-full" title={`${h.day}: ${fmt(h.words_added)} words`}>
                  <div
                    className={`rounded-sm ${h.words_added ? 'bg-seal' : 'bg-paper-300'}`}
                    style={{ height: `${Math.max(h.words_added ? 8 : 4, (h.words_added / peak) * 100)}%` }}
                  />
                </div>
              ))}
            </div>
            <div className="flex justify-between text-[11px] text-study-300 mt-1"><span>14 days ago</span><span>Today</span></div>
          </>
        )}
      </div>

      {/* Today & streak */}
      <div className="card p-4 space-y-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-study-300 mb-1">Today</p>
          <p className="text-sm"><span className="font-medium">{fmt(p.today_words)}</span> words{p.daily_word_goal ? ` of ${fmt(p.daily_word_goal)}` : ''}</p>
          {todayGoalPct !== null && (
            <div className="h-1.5 bg-paper-200 rounded-full overflow-hidden mt-1.5"><div className="h-full bg-seal" style={{ width: `${todayGoalPct}%` }} /></div>
          )}
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-study-300 mb-1">Streak</p>
          <p className="text-sm flex items-center gap-1.5">
            <Flame size={15} className={p.current_streak ? 'text-seal' : 'text-study-300'} />
            <span className="font-medium">{p.current_streak} day{p.current_streak === 1 ? '' : 's'}</span>
            <span className="text-study-300">· best {p.longest_streak}</span>
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-study-300 mb-1">Chapters</p>
          <div className="flex flex-wrap gap-1.5">
            {STAGES.map((s) => (
              <span key={s.id} className={`status-tag ${s.className}`}>{s.label} {p.stage_counts[s.id] ?? 0}</span>
            ))}
          </div>
        </div>
      </div>

      {/* What's next */}
      {p.next_steps.length > 0 && (
        <div className="card p-4 md:col-span-3">
          <p className="text-xs uppercase tracking-wide text-study-300 mb-2">What's next</p>
          <ol className="space-y-1.5">
            {p.next_steps.map((step, i) => (
              <li key={i} className="text-sm flex items-start gap-2">
                <span className="text-seal font-mono text-xs mt-0.5">{i + 1}.</span>
                {step.chapter_id ? (
                  <Link to={`/projects/${projectId}/chapters/${step.chapter_id}`} className="hover:text-seal flex items-center gap-1">
                    {step.message} <ArrowRight size={13} />
                  </Link>
                ) : (
                  <span>{step.message}</span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
