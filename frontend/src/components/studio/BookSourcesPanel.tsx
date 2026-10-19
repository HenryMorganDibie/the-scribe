import { useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Loader2, Pencil } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { cap } from '@/lib/packs'
import { usePack } from '@/stores/authStore'

interface SourceRef {
  id: string
  title: string
}

interface Props {
  projectId: string
  linked: SourceRef[]
  onSaved: () => void
}

/** The sources (talks, sermons, transcripts…) this book draws on during generation. */
export default function BookSourcesPanel({ projectId, linked, onSaved }: Props) {
  const pack = usePack()
  const [editing, setEditing] = useState(false)
  const [library, setLibrary] = useState<(SourceRef & { status: string; word_count: number })[] | null>(null)
  const [selected, setSelected] = useState<string[]>([])
  const [saving, setSaving] = useState(false)

  const start = async () => {
    setSelected(linked.map((s) => s.id))
    setEditing(true)
    try {
      const res = await api.get('/sermons')
      setLibrary(res.data.filter((s: { status: string }) => s.status === 'complete'))
    } catch {
      setLibrary([])
    }
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}`, { source_sermon_ids: selected })
      setEditing(false)
      onSaved()
      toast.success(`${cap(pack.source.plural)} updated`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const toggle = (id: string) =>
    setSelected((ids) => (ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id]))

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs uppercase tracking-wide text-study-300 flex items-center gap-1.5"><FileText size={13} /> Book {pack.source.plural}</p>
        {!editing && (
          <button onClick={start} className="text-xs text-seal hover:underline flex items-center gap-1"><Pencil size={12} /> Manage</button>
        )}
      </div>

      {editing ? (
        <div className="space-y-3">
          {library === null ? (
            <p className="text-sm text-study-300">Loading your library…</p>
          ) : library.length === 0 ? (
            <p className="text-sm text-study-300">
              No processed {pack.source.plural} yet. <Link to="/sermons" className="text-seal underline">Upload one</Link> first.
            </p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto">
              {library.map((s) => {
                const on = selected.includes(s.id)
                return (
                  <button type="button" key={s.id} onClick={() => toggle(s.id)} className={`text-left rounded-lg border p-2.5 text-sm transition-colors ${on ? 'border-seal bg-seal-50' : 'border-paper-300 hover:border-seal-300'}`}>
                    <p className="font-medium">{s.title}</p>
                    <p className="text-xs text-study-300">{s.word_count || 0} words{on ? ' · linked' : ''}</p>
                  </button>
                )
              })}
            </div>
          )}
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditing(false)} className="btn-secondary text-sm">Cancel</button>
            <button onClick={save} disabled={saving || library === null} className="btn-primary text-sm flex items-center gap-2 disabled:opacity-50">
              {saving && <Loader2 size={14} className="animate-spin" />} Save
            </button>
          </div>
        </div>
      ) : linked.length > 0 ? (
        <>
          <p className="text-sm text-study-400 mb-2">The Scribe draws on these when it drafts this book.</p>
          <div className="flex flex-wrap gap-2">
            {linked.map((s) => <span key={s.id} className="text-xs bg-seal-50 border border-seal-200 text-seal-400 rounded-full px-3 py-1">{s.title}</span>)}
          </div>
        </>
      ) : (
        <p className="text-sm text-study-300">Link {pack.source.plural} from your library so drafts can draw on your own material.</p>
      )}
    </div>
  )
}
