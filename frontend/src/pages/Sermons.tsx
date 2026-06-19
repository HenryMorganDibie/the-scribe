import { useEffect, useRef, useState } from 'react'
import { Upload, FileText, Loader2 } from 'lucide-react'
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
  const fileRef = useRef<HTMLInputElement>(null)

  const load = () => api.get('/sermons').then((r) => setSermons(r.data))

  useEffect(() => { load() }, [])

  // Poll while any sermon is still processing
  useEffect(() => {
    if (!sermons.some((s) => ACTIVE.includes(s.status))) return
    const t = setInterval(load, 2500)
    return () => clearInterval(t)
  }, [sermons])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!title.trim()) return toast.error('Give the sermon a title')
    if (!file && !text.trim()) return toast.error('Upload a file or paste text')
    setSubmitting(true)
    try {
      const form = new FormData()
      form.append('title', title)
      if (file) form.append('file', file)
      else form.append('text', text)
      await api.post('/sermons', form)
      toast.success('Sermon uploaded — processing in the background')
      setTitle(''); setText('')
      if (fileRef.current) fileRef.current.value = ''
      load()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || 'Upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
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
        <input ref={fileRef} type="file" accept=".pdf,.docx,.mp3,.m4a,.wav,.webm,.mp4" className="block text-sm text-study-400" />
        <button type="submit" disabled={submitting} className="btn-primary flex items-center gap-2">
          {submitting ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
          Upload sermon
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
          </div>
        ))}
        {sermons.length === 0 && <p className="text-study-300 text-center py-12">No sermons yet.</p>}
      </div>
    </div>
  )
}
