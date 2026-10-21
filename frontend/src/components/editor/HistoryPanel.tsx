import { useCallback, useEffect, useState } from 'react'
import { History, Loader2, RotateCcw } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { VERSION_REASONS, htmlToText } from '@/lib/bible'

interface VersionSummary {
  id: string
  reason: string
  word_count: number
  created_at: string
}

interface Props {
  projectId: string
  chapterId: string
  /** Bump to reload (e.g. after an AI draft or a save). */
  refreshKey: number
  onRestored: (content: string, wordCount: number) => void
}

function when(iso: string) {
  // API datetimes are naive UTC.
  const date = new Date(iso.endsWith('Z') ? iso : `${iso}Z`)
  return date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export default function HistoryPanel({ projectId, chapterId, refreshKey, onRestored }: Props) {
  const [versions, setVersions] = useState<VersionSummary[] | null>(null)
  const [openId, setOpenId] = useState<string | null>(null)
  const [preview, setPreview] = useState<string>('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const base = `/projects/${projectId}/chapters/${chapterId}/versions`

  const load = useCallback(() => {
    api.get(base).then((r) => setVersions(r.data)).catch(() => setVersions([]))
  }, [base])

  useEffect(load, [load, refreshKey])

  const togglePreview = async (id: string) => {
    if (openId === id) return setOpenId(null)
    setBusyId(id)
    try {
      const res = await api.get(`${base}/${id}`)
      setPreview(htmlToText(res.data.content))
      setOpenId(id)
    } catch {
      toast.error('Could not load that version')
    } finally {
      setBusyId(null)
    }
  }

  const restore = async (id: string) => {
    if (!window.confirm('Restore this version? Your current draft will be kept in History.')) return
    setBusyId(id)
    try {
      const res = await api.post(`${base}/${id}/restore`)
      onRestored(res.data.content, res.data.word_count)
      setOpenId(null)
      toast.success('Version restored')
      load()
    } catch {
      toast.error('Restore failed')
    } finally {
      setBusyId(null)
    }
  }

  if (versions === null) {
    return <div className="p-4 text-sm text-study-300">Loading history…</div>
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3">
      <p className="text-xs text-study-300 flex items-start gap-2">
        <History size={14} className="mt-0.5 flex-shrink-0" />
        Earlier drafts of this chapter, kept automatically while you write and before every AI draft.
      </p>
      {versions.length === 0 && (
        <p className="text-sm text-study-400 italic">No earlier versions yet — they appear as the chapter changes.</p>
      )}
      {versions.map((v) => (
        <div key={v.id} className="card p-3 text-sm">
          <div className="flex items-center justify-between gap-2">
            <div>
              <p className="font-medium">{VERSION_REASONS[v.reason] ?? v.reason}</p>
              <p className="text-xs text-study-300">{when(v.created_at)} · {v.word_count} words</p>
            </div>
            {busyId === v.id && <Loader2 size={14} className="animate-spin text-seal" />}
          </div>
          <div className="flex gap-3 mt-2 text-xs">
            <button onClick={() => togglePreview(v.id)} disabled={!!busyId} className="text-seal hover:underline disabled:opacity-50">
              {openId === v.id ? 'Hide' : 'Preview'}
            </button>
            <button onClick={() => restore(v.id)} disabled={!!busyId} className="text-seal hover:underline flex items-center gap-1 disabled:opacity-50">
              <RotateCcw size={12} /> Restore
            </button>
          </div>
          {openId === v.id && (
            <p className="mt-2 max-h-64 overflow-y-auto whitespace-pre-line text-xs text-study-400 bg-paper-100 border border-paper-300 rounded p-2">
              {preview || '(empty)'}
            </p>
          )}
        </div>
      ))}
    </div>
  )
}
