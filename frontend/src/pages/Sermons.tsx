import { useEffect, useRef, useState } from 'react'
import { Upload, FileText, Loader2 , Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Sermon {
  id: string
  title: string
  source_type: string
  status: string
  phrases_added: number
  testimonies_suggested: number
  error_message?: string | null
}

const ACTIVE = ['pending', 'extracting', 'analyzing']

export default function Sermons() {
  const [sermons, setSermons] = useState<Sermon[]>([])
  const [title, setTitle] = useState('')
  const [text, setText] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const handleDelete = async (id: string, title: string) => {
    if (!confirm(`Delete "${title}"?`)) return
    setDeletingId(id)
    try {
      await api.delete(`/sermons/${id}`)
      setSermons((prev) => prev.filter((s) => s.id !== id))
      toast.success('Sermon deleted')
    } catch {
      toast.error('Failed to delete')
    } finally {
      setDeletingId(null)
    }
  }
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => api.get('/sermons').then((r) => setSermons(r.data))

  useEffect(() => { load() }, [])

  // Poll while any sermon is still processing
  useEffect(() => {
    if (!sermons.some((s) => ACTIVE.includes(s.status))) return
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [sermons])

  const MAX_FILE_BYTES = 25 * 1024 * 1024 // matches the backend's Groq Whisper cap

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!title.trim()) return toast.error('Give the sermon a title')
    if (!file && !text.trim()) return toast.error('Upload a file or paste text')
    if (file && file.size > MAX_FILE_BYTES) {
      return toast.error(`That file is ${Math.round(file.size / 1024 / 1024)}MB — the limit is 25MB.`)
    }

    setSubmitting(true)
    setUploadProgress(file ? 0 : null)
    try {
      const form = new FormData()
      form.append('title', title)
      if (file) form.append('file', file)
      else form.append('text', text)

      await api.post('/sermons', form, {
        onUploadProgress: (evt) => {
          if (file && evt.total) setUploadProgress(Math.round((evt.loaded / evt.total) * 100))
        },
      })

      toast.success('Sermon uploaded — processing in the background')
      setTitle(''); setText('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Upload failed')
    } finally {
      setSubmitting(false)
      setUploadProgress(null)
    }
  }

  return (
    <div className="px-4 py-6 md:p-8 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-8">
        <Upload size={24} className="text-seal" />
        <h1 className="font-display text-display-md font-semibold">Sermons</h1>
      </div>
      <p className="text-study-300 mb-6">
        Upload sermons (PDF, DOCX, audio) or paste a transcript. The Scribe transcribes, learns your voice,
        and mines personal stories into suggested testimonies.
      </p>

      <form onSubmit={submit} className="card p-6 mb-8 space-y-4">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="input-field w-full"
          placeholder="Sermon title"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          className="input-field w-full h-32 resize-none"
          placeholder="Paste a transcript here, or choose a file below..."
        />
        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.mp3,.m4a,.wav,.mpga"
            className="block text-sm text-study-400"
          />
          <p className="text-xs text-study-300 mt-1">
            PDF, DOCX, or audio (.mp3/.m4a/.wav, up to 25MB). Video files aren't supported yet —
            extract the audio first if you have a recording.
          </p>
        </div>
        <button type="submit" disabled={submitting} className="btn-primary flex items-center gap-2">
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          {submitting && uploadProgress !== null ? `Uploading… ${uploadProgress}%` : 'Upload sermon'}
        </button>
      </form>

      <div className="space-y-3">
        {sermons.map((s) => (
          <div key={s.id} className="card p-5 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileText size={18} className="text-study-300" />
              <div>
                <h3 className="font-display font-semibold">{s.title}</h3>
                <p className="text-xs text-study-300 uppercase">{s.source_type}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
            <div className="text-right text-sm">
              {ACTIVE.includes(s.status) ? (
                <span className="flex items-center gap-1.5 text-study-300">
                  <Loader2 size={14} className="animate-spin" /> {s.status}…
                </span>
              ) : s.status === 'failed' ? (
                <span className="text-red-400" title={s.error_message || ''}>Failed</span>
              ) : (
                <span className="text-green-600">
                  +{s.phrases_added} phrases · {s.testimonies_suggested} stories
                </span>
              )}
            </div>
            <button
              onClick={() => handleDelete(s.id, s.title)}
              disabled={deletingId === s.id}
              className="p-1.5 text-study-300 hover:text-red-600 hover:bg-red-50 rounded flex-shrink-0"
              title="Delete"
            >
              <Trash2 size={16} />
            </button>
            </div>
          </div>
        ))}
        {sermons.length === 0 && <p className="text-study-300 text-center py-12">No sermons yet.</p>}
      </div>
    </div>
  )
}
