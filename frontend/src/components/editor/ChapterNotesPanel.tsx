import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, NotebookPen, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { type BookEntry, type EntryKind, kindLabel } from '@/lib/bible'

interface Props {
  projectId: string
  chapterId: string
}

/** Notes and research attached to one chapter — the AI reads these first when drafting it. */
export default function ChapterNotesPanel({ projectId, chapterId }: Props) {
  const [entries, setEntries] = useState<BookEntry[] | null>(null)
  const [kind, setKind] = useState<EntryKind>('note')
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    api.get(`/projects/${projectId}/bible`, { params: { chapter_id: chapterId } })
      .then((r) => setEntries(r.data))
      .catch(() => setEntries([]))
  }, [projectId, chapterId])

  useEffect(load, [load])

  const add = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    setSaving(true)
    try {
      await api.post(`/projects/${projectId}/bible`, { kind, title, body, chapter_id: chapterId })
      setTitle('')
      setBody('')
      load()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not save the note')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    if (!window.confirm('Delete this note?')) return
    try {
      await api.delete(`/projects/${projectId}/bible/${id}`)
      setEntries((prev) => prev?.filter((e) => e.id !== id) ?? null)
    } catch {
      toast.error('Delete failed')
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      <p className="text-xs text-study-300 flex items-start gap-2">
        <NotebookPen size={14} className="mt-0.5 flex-shrink-0" />
        Notes for this chapter. The Scribe reads them — plus anything relevant in the{' '}
        <Link to={`/projects/${projectId}/bible`} className="text-seal underline">book bible</Link> — whenever it writes here.
      </p>

      <form onSubmit={add} className="card p-3 space-y-2">
        <div className="flex gap-2">
          <select value={kind} onChange={(e) => setKind(e.target.value as EntryKind)} className="input-field text-sm py-1.5">
            <option value="note">Note</option>
            <option value="research">Research</option>
          </select>
          <input value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} className="input-field flex-1 text-sm py-1.5" placeholder="Title" />
        </div>
        <textarea value={body} onChange={(e) => setBody(e.target.value)} maxLength={20000} className="input-field w-full h-20 resize-none text-sm" placeholder="What should The Scribe keep in mind?" />
        <button type="submit" disabled={saving || !title.trim()} className="btn-primary text-sm px-3 py-1.5 flex items-center gap-2 disabled:opacity-50">
          {saving && <Loader2 size={14} className="animate-spin" />} Add
        </button>
      </form>

      {entries === null ? (
        <p className="text-sm text-study-300">Loading…</p>
      ) : entries.length === 0 ? (
        <p className="text-sm text-study-400 italic">No notes on this chapter yet.</p>
      ) : (
        entries.map((e) => (
          <div key={e.id} className="card p-3 text-sm">
            <div className="flex items-start justify-between gap-2">
              <p className="font-medium"><span className="text-xs text-seal mr-1.5">{kindLabel(e.kind)}</span>{e.title}</p>
              <button onClick={() => remove(e.id)} className="text-study-300 hover:text-red-400 flex-shrink-0" aria-label="Delete note">
                <Trash2 size={14} />
              </button>
            </div>
            {e.body && <p className="text-xs text-study-400 mt-1 whitespace-pre-line">{e.body}</p>}
          </div>
        ))
      )}
    </div>
  )
}
