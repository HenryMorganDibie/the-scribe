import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Library, Loader2, Pencil, Plus, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { ENTRY_KINDS, type BookEntry, type EntryKind, kindLabel } from '@/lib/bible'

interface ChapterRef {
  id: string
  title: string
  chapter_number: number
}

interface Draft {
  id?: string
  kind: EntryKind
  title: string
  body: string
  chapter_id: string
  when_label: string
  timeline_order: string
}

const emptyDraft = (kind: EntryKind): Draft => ({ kind, title: '', body: '', chapter_id: '', when_label: '', timeline_order: '' })

export default function BookBible() {
  const { id: projectId } = useParams<{ id: string }>()
  const [title, setTitle] = useState('')
  const [chapters, setChapters] = useState<ChapterRef[]>([])
  const [entries, setEntries] = useState<BookEntry[] | null>(null)
  const [filter, setFilter] = useState<EntryKind | 'all'>('all')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    api.get(`/projects/${projectId}/bible`).then((r) => setEntries(r.data)).catch(() => setEntries([]))
  }, [projectId])

  useEffect(() => {
    api.get(`/projects/${projectId}`).then((r) => {
      setTitle(r.data.title)
      setChapters(r.data.chapters)
    }).catch(() => toast.error('Failed to load manuscript'))
    load()
  }, [projectId, load])

  const counts = useMemo(() => {
    const c: Record<string, number> = {}
    for (const e of entries ?? []) c[e.kind] = (c[e.kind] ?? 0) + 1
    return c
  }, [entries])

  const visible = (entries ?? []).filter((e) => filter === 'all' || e.kind === filter)
  const chapterName = (id: string | null) => {
    const ch = chapters.find((c) => c.id === id)
    return ch ? `Ch. ${ch.chapter_number}: ${ch.title}` : null
  }

  const save = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!draft || !draft.title.trim()) return
    setSaving(true)
    const isEvent = draft.kind === 'event'
    const order = draft.timeline_order.trim() === '' ? null : Number(draft.timeline_order)
    const payload = {
      kind: draft.kind, title: draft.title, body: draft.body,
      when_label: isEvent ? draft.when_label : '',
    }
    try {
      if (draft.id) {
        await api.put(`/projects/${projectId}/bible/${draft.id}`, {
          ...payload,
          ...(draft.chapter_id ? { chapter_id: draft.chapter_id } : { detach_chapter: true }),
          ...(isEvent && order !== null ? { timeline_order: order } : { clear_timeline_order: true }),
        })
      } else {
        await api.post(`/projects/${projectId}/bible`, {
          ...payload, chapter_id: draft.chapter_id || null, timeline_order: isEvent ? order : null,
        })
      }
      setDraft(null)
      load()
      toast.success('Saved to the book bible')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (entry: BookEntry) => {
    if (!window.confirm(`Delete "${entry.title}"?`)) return
    try {
      await api.delete(`/projects/${projectId}/bible/${entry.id}`)
      setEntries((prev) => prev?.filter((e) => e.id !== entry.id) ?? null)
    } catch {
      toast.error('Delete failed')
    }
  }

  const activeKind = filter === 'all' ? null : ENTRY_KINDS.find((k) => k.kind === filter)

  return (
    <div className="px-4 py-6 md:p-8 max-w-4xl mx-auto">
      <Link to={`/projects/${projectId}`} className="text-sm text-study-300 hover:text-seal flex items-center gap-1 mb-4">
        <ArrowLeft size={14} /> {title || 'Manuscript'}
      </Link>

      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-3">
          <Library size={24} className="text-seal" />
          <h1 className="font-display text-display-md font-semibold">Book Bible</h1>
        </div>
        <button
          onClick={() => setDraft(draft ? null : emptyDraft(filter === 'all' ? 'character' : filter))}
          className="btn-primary flex items-center gap-2"
        >
          {draft ? <X size={16} /> : <Plus size={16} />} {draft ? 'Cancel' : 'Add entry'}
        </button>
      </div>
      <p className="text-study-300 mb-6">
        Everything this book needs to stay consistent. The Scribe looks up the relevant entries every time it
        drafts, continues or answers questions about this manuscript.
      </p>

      {draft && (
        <form onSubmit={save} className="card p-5 mb-6 space-y-3 animate-fade-in-up">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <select value={draft.kind} onChange={(e) => setDraft({ ...draft, kind: e.target.value as EntryKind })} className="input-field">
              {ENTRY_KINDS.map((k) => <option key={k.kind} value={k.kind}>{k.label}</option>)}
            </select>
            <input
              value={draft.title}
              onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              maxLength={200}
              required
              className="input-field sm:col-span-2"
              placeholder="Name or title"
            />
          </div>
          {draft.kind === 'event' && (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <input
                value={draft.when_label}
                onChange={(e) => setDraft({ ...draft, when_label: e.target.value })}
                maxLength={120}
                className="input-field sm:col-span-2"
                placeholder="When — e.g. Spring 1998, Day 3, Before the war"
              />
              <input
                type="number"
                value={draft.timeline_order}
                onChange={(e) => setDraft({ ...draft, timeline_order: e.target.value })}
                className="input-field"
                placeholder="Order (1, 2, 3…)"
                aria-label="Position in the timeline"
              />
            </div>
          )}
          <textarea
            value={draft.body}
            onChange={(e) => setDraft({ ...draft, body: e.target.value })}
            maxLength={20000}
            className="input-field w-full h-36 resize-y"
            placeholder={ENTRY_KINDS.find((k) => k.kind === draft.kind)?.hint}
          />
          <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
            <select value={draft.chapter_id} onChange={(e) => setDraft({ ...draft, chapter_id: e.target.value })} className="input-field text-sm">
              <option value="">Whole book</option>
              {chapters.map((c) => <option key={c.id} value={c.id}>Only chapter {c.chapter_number}: {c.title}</option>)}
            </select>
            <button type="submit" disabled={saving || !draft.title.trim()} className="btn-primary flex items-center gap-2 disabled:opacity-50">
              {saving && <Loader2 size={16} className="animate-spin" />} {draft.id ? 'Save changes' : 'Add to bible'}
            </button>
          </div>
        </form>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        <button onClick={() => setFilter('all')} className={`text-sm rounded-full px-3 py-1 border ${filter === 'all' ? 'border-seal bg-seal-50 text-seal-400' : 'border-paper-300 text-study-400'}`}>
          All {entries ? `(${entries.length})` : ''}
        </button>
        {ENTRY_KINDS.map((k) => (
          <button key={k.kind} onClick={() => setFilter(k.kind)} className={`text-sm rounded-full px-3 py-1 border ${filter === k.kind ? 'border-seal bg-seal-50 text-seal-400' : 'border-paper-300 text-study-400'}`}>
            {k.plural} {counts[k.kind] ? `(${counts[k.kind]})` : ''}
          </button>
        ))}
      </div>
      {activeKind && <p className="text-sm text-study-300 mb-4">{activeKind.hint}</p>}

      {entries === null ? (
        <p className="text-study-300">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="text-center py-16 text-study-300">
          {entries.length === 0
            ? 'Nothing here yet. Add the characters, places, terms and sources this book depends on.'
            : `No ${activeKind?.plural.toLowerCase() ?? 'entries'} yet.`}
        </div>
      ) : (
        <div className="space-y-3">
          {visible.map((e) => (
            <div key={e.id} className="card p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-xs text-seal uppercase tracking-wide">
                    {kindLabel(e.kind)}{chapterName(e.chapter_id) ? ` · ${chapterName(e.chapter_id)}` : ''}
                  </p>
                  <h3 className="font-display font-semibold">
                    {e.kind === 'event' && e.timeline_order !== null && <span className="text-study-300 font-mono text-sm mr-2">#{e.timeline_order}</span>}
                    {e.title}
                    {e.when_label && <span className="text-study-300 font-normal text-sm"> · {e.when_label}</span>}
                  </h3>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    onClick={() => setDraft({
                      id: e.id, kind: e.kind, title: e.title, body: e.body, chapter_id: e.chapter_id ?? '',
                      when_label: e.when_label ?? '', timeline_order: e.timeline_order === null ? '' : String(e.timeline_order),
                    })}
                    className="text-study-300 hover:text-seal" aria-label={`Edit ${e.title}`}
                  >
                    <Pencil size={15} />
                  </button>
                  <button onClick={() => remove(e)} className="text-study-300 hover:text-red-400" aria-label={`Delete ${e.title}`}>
                    <Trash2 size={15} />
                  </button>
                </div>
              </div>
              {e.body && <p className="text-sm text-study-400 mt-2 whitespace-pre-line">{e.body}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
