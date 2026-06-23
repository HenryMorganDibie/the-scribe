import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, BookOpen, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Project {
  id: string
  title: string
  genre: string
  theme?: string
  status: string
  target_chapters: number
}

const GENRES = ['teaching', 'devotional', 'prophetic', 'memoir']

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [genre, setGenre] = useState('teaching')
  const [theme, setTheme] = useState('')
  const [targetChapters, setTargetChapters] = useState(10)
  const navigate = useNavigate()

  useEffect(() => {
    api.get('/projects').then((r) => setProjects(r.data)).finally(() => setLoading(false))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const res = await api.post('/projects', { title, genre, theme, target_chapters: targetChapters })
      toast.success('Manuscript created')
      navigate(`/projects/${res.data.id}`)
    } catch {
      toast.error('Failed to create manuscript')
    }
  }

  return (
    <div className="px-4 py-6 md:p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <BookOpen size={24} className="text-seal" />
          <h1 className="font-display text-display-md font-semibold">Manuscripts</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2">
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? 'Cancel' : 'New Manuscript'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-6 mb-6 space-y-4 animate-fade-in-up">
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Title</label>
            <input required value={title} onChange={(e) => setTitle(e.target.value)} className="input-field w-full" placeholder="Called: Finding Your Voice in the Wilderness" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Genre</label>
              <select value={genre} onChange={(e) => setGenre(e.target.value)} className="input-field w-full capitalize">
                {GENRES.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Target Chapters</label>
              <input type="number" min={1} max={50} value={targetChapters} onChange={(e) => setTargetChapters(parseInt(e.target.value))} className="input-field w-full" />
            </div>
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Core Theme</label>
            <textarea value={theme} onChange={(e) => setTheme(e.target.value)} className="input-field w-full h-24 resize-none" placeholder="What is the central message of this book?" />
          </div>
          <button type="submit" className="btn-primary">Create Manuscript</button>
        </form>
      )}

      {loading ? (
        <div className="text-study-300">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 text-study-300">No manuscripts yet. Create your first one above.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="card p-5 hover:border-seal/50">
              <h3 className="font-display text-lg font-semibold mb-1">{p.title}</h3>
              <span className="text-xs text-seal capitalize">{p.genre}</span>
              {p.theme && <p className="text-sm text-study-300 mt-2 line-clamp-2">{p.theme}</p>}
              <div className="mt-3 text-xs text-ink0">{p.target_chapters} chapters target</div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
