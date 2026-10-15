import { useState } from 'react'
import { Loader2, Palette, Pencil } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Props {
  projectId: string
  targetAudience?: string | null
  styleRules: string[]
  styleNotes?: string | null
  onSaved: () => void
}

/** Per-book overrides of the author's voice profile. Empty fields inherit. */
export default function BookStylePanel({ projectId, targetAudience, styleRules, styleNotes, onSaved }: Props) {
  const [editing, setEditing] = useState(false)
  const [audience, setAudience] = useState('')
  const [rules, setRules] = useState('')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const start = () => {
    setAudience(targetAudience ?? '')
    setRules(styleRules.join('\n'))
    setNotes(styleNotes ?? '')
    setEditing(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}`, {
        target_audience: audience,
        style_rules: rules.split('\n').map((r) => r.trim()).filter(Boolean),
        style_notes: notes,
      })
      setEditing(false)
      onSaved()
      toast.success('Book style saved')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const hasOverrides = !!(targetAudience || styleRules.length || styleNotes)

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs uppercase tracking-wide text-study-300 flex items-center gap-1.5"><Palette size={13} /> Book style</p>
        {!editing && (
          <button onClick={start} className="text-xs text-seal hover:underline flex items-center gap-1"><Pencil size={12} /> Edit</button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-study-400 mb-1">Reader for this book</label>
            <input value={audience} onChange={(e) => setAudience(e.target.value)} maxLength={2000} className="input-field w-full text-sm" placeholder="Leave blank to use your usual audience" />
          </div>
          <div>
            <label className="block text-xs text-study-400 mb-1">Extra style rules (one per line)</label>
            <textarea value={rules} onChange={(e) => setRules(e.target.value)} className="input-field w-full h-20 resize-none text-sm" placeholder={'Present tense\nNo chapter longer than 3,000 words'} />
          </div>
          <div>
            <label className="block text-xs text-study-400 mb-1">Style notes</label>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={5000} className="input-field w-full h-24 resize-none text-sm" placeholder="How this book should feel, compared with your usual writing." />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditing(false)} className="btn-secondary text-sm">Cancel</button>
            <button onClick={save} disabled={saving} className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
              {saving && <Loader2 size={14} className="animate-spin" />} Save
            </button>
          </div>
        </div>
      ) : hasOverrides ? (
        <div className="space-y-1.5 text-sm text-study-400">
          {targetAudience && <p><span className="text-study-300">Reader:</span> {targetAudience}</p>}
          {styleRules.length > 0 && <p><span className="text-study-300">Rules:</span> {styleRules.join(' · ')}</p>}
          {styleNotes && <p className="whitespace-pre-line line-clamp-3"><span className="text-study-300">Notes:</span> {styleNotes}</p>}
        </div>
      ) : (
        <p className="text-sm text-study-300">Using your voice profile as-is. Set a different reader, rules or tone for this book only.</p>
      )}
    </div>
  )
}
