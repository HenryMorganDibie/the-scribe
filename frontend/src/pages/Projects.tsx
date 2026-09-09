import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Plus, BookOpen, X, Trash2, Pencil, Sparkles, Loader2 } from 'lucide-react'
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

interface Sermon {
  id: string
  title: string
  status: string
  word_count: number
}

const GENRES = ['teaching', 'devotional', 'prophetic', 'memoir']

export default function Projects() {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [editTheme, setEditTheme] = useState('')

  const handleDelete = async (e: React.MouseEvent, id: string, title: string) => {
    e.preventDefault()
    e.stopPropagation()
    if (!confirm(`Delete "${title}"? This will remove all chapters. This cannot be undone.`)) return
    setDeletingId(id)
    try {
      await api.delete(`/projects/${id}`)
      setProjects((prev) => prev.filter((p) => p.id !== id))
      toast.success('Manuscript deleted')
    } catch {
      toast.error('Failed to delete')
    } finally {
      setDeletingId(null)
    }
  }

  const startEdit = (e: React.MouseEvent, project: Project) => {
    e.preventDefault()
    e.stopPropagation()
    setEditingProject(project)
    setEditTitle(project.title)
    setEditTheme(project.theme || '')
  }

  const saveEdit = async () => {
    if (!editingProject || !editTitle.trim()) return
    try {
      await api.put(`/projects/${editingProject.id}`, { title: editTitle, theme: editTheme })
      setProjects((prev) => prev.map((p) => p.id === editingProject.id ? { ...p, title: editTitle, theme: editTheme } : p))
      setEditingProject(null)
      toast.success('Manuscript updated')
    } catch {
      toast.error('Failed to update')
    }
  }
  const [showForm, setShowForm] = useState(false)
  const [showBookBuilder, setShowBookBuilder] = useState(false)
  const [sermons, setSermons] = useState<Sermon[]>([])
  const [selectedSermonIds, setSelectedSermonIds] = useState<string[]>([])
  const [bookReader, setBookReader] = useState('')
  const [buildingBook, setBuildingBook] = useState(false)
  const [title, setTitle] = useState('')
  const [genre, setGenre] = useState('teaching')
  const [theme, setTheme] = useState('')
  const [targetChapters, setTargetChapters] = useState(10)
  const navigate = useNavigate()

  useEffect(() => {
    Promise.all([
      api.get('/projects').then((r) => setProjects(r.data)),
      api.get('/sermons').then((r) => setSermons(r.data.filter((sermon: Sermon) => sermon.status === 'complete'))),
    ]).catch(() => toast.error('Failed to load your writing library')).finally(() => setLoading(false))
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

  const handleBuildBook = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim() || selectedSermonIds.length === 0) return
    setBuildingBook(true)
    try {
      const res = await api.post('/projects/from-sermons', { title, target_reader: bookReader, sermon_ids: selectedSermonIds, target_chapters: targetChapters })
      toast.success(`Book blueprint created from ${selectedSermonIds.length} sermon${selectedSermonIds.length === 1 ? '' : 's'}`)
      navigate(`/projects/${res.data.id}`)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Unable to build the book blueprint')
    } finally {
      setBuildingBook(false)
    }
  }

  return (
    <div className="px-4 py-6 md:p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <BookOpen size={24} className="text-seal" />
          <h1 className="font-display text-display-md font-semibold">Manuscripts</h1>
        </div>
        <div className="flex gap-2">
          <button onClick={() => { setShowBookBuilder(!showBookBuilder); setShowForm(false) }} className="btn-primary flex items-center gap-2">
            {showBookBuilder ? <X size={16} /> : <Sparkles size={16} />}
            {showBookBuilder ? 'Cancel' : 'Build from Sermons'}
          </button>
          <button onClick={() => { setShowForm(!showForm); setShowBookBuilder(false) }} className="btn-secondary flex items-center gap-2">
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'New'}
          </button>
        </div>
      </div>

      {showBookBuilder && (
        <form onSubmit={handleBuildBook} className="card p-6 mb-6 space-y-5 animate-fade-in-up border-seal-200">
          <div>
            <div className="flex items-center gap-2 mb-1"><Sparkles size={18} className="text-seal" /><h2 className="font-display text-lg font-semibold">Build a book from your sermons</h2></div>
            <p className="text-sm text-study-300">Select completed sermons. The Scribe will create a chapter blueprint grounded in those messages and your voice profile.</p>
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Book title</label>
            <input required value={title} onChange={(e) => setTitle(e.target.value)} className="input-field w-full" placeholder="Called: Finding Your Voice in the Wilderness" />
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div><label className="block text-sm text-study-400 mb-1.5">Target reader</label><input value={bookReader} onChange={(e) => setBookReader(e.target.value)} className="input-field w-full" placeholder="Believers discerning their calling" /></div>
            <div><label className="block text-sm text-study-400 mb-1.5">Target chapters</label><input type="number" min={3} max={20} value={targetChapters} onChange={(e) => setTargetChapters(parseInt(e.target.value, 10) || 3)} className="input-field w-full" /></div>
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-2">Source sermons</label>
            {sermons.length === 0 ? <p className="text-sm text-study-300">Upload and process a sermon first, then return here to build your book.</p> : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto">
                {sermons.map((sermon) => {
                  const selected = selectedSermonIds.includes(sermon.id)
                  return <button type="button" key={sermon.id} onClick={() => setSelectedSermonIds((ids) => selected ? ids.filter((id) => id !== sermon.id) : [...ids, sermon.id])} className={`text-left rounded-lg border p-3 transition-colors ${selected ? 'border-seal bg-seal-50' : 'border-paper-300 hover:border-seal-300'}`}>
                    <p className="font-medium text-sm">{sermon.title}</p><p className="text-xs text-study-300 mt-1">{sermon.word_count || 0} words {selected ? '• selected' : ''}</p>
                  </button>
                })}
              </div>
            )}
          </div>
          <button type="submit" disabled={buildingBook || !title.trim() || selectedSermonIds.length === 0} className="btn-primary flex items-center gap-2 disabled:opacity-50">
            {buildingBook ? <><Loader2 size={16} className="animate-spin" /> Building your blueprint...</> : <><Sparkles size={16} /> Create book blueprint</>}
          </button>
        </form>
      )}

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
              <input type="number" min={1} max={50} value={targetChapters} onChange={(e) => setTargetChapters(parseInt(e.target.value, 10) || 1)} className="input-field w-full" />
            </div>
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Core Theme</label>
            <textarea value={theme} onChange={(e) => setTheme(e.target.value)} className="input-field w-full h-24 resize-none" placeholder="What is the central message of this book?" />
          </div>
          <button type="submit" className="btn-primary">Create Manuscript</button>
        </form>
      )}

      {/* Edit modal */}
      {editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40">
          <div className="bg-paper rounded-xl p-6 w-full max-w-md space-y-4 shadow-xl">
            <h2 className="font-display text-display-xs font-semibold">Edit Manuscript</h2>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Title</label>
              <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="input-field w-full" />
            </div>
            <div>
              <label className="block text-sm text-study-400 mb-1.5">Core Theme</label>
              <textarea value={editTheme} onChange={(e) => setEditTheme(e.target.value)} className="input-field w-full h-20 resize-none" />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditingProject(null)} className="btn-secondary">Cancel</button>
              <button onClick={saveEdit} disabled={!editTitle.trim()} className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed">Save changes</button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-study-300">Loading...</div>
      ) : projects.length === 0 ? (
        <div className="text-center py-16 text-study-300">No manuscripts yet. Create your first one above.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Link key={p.id} to={`/projects/${p.id}`} className="card p-5 hover:border-seal/50 relative group">
              <div className="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={(e) => startEdit(e, p)}
                  className="p-1.5 rounded hover:bg-paper-300 text-study-300 hover:text-study-700"
                  title="Edit"
                >
                  <Pencil size={14} />
                </button>
                <button
                  onClick={(e) => handleDelete(e, p.id, p.title)}
                  disabled={deletingId === p.id}
                  className="p-1.5 rounded hover:bg-red-50 text-study-300 hover:text-red-600"
                  title="Delete"
                >
                  <Trash2 size={14} />
                </button>
              </div>
              <h3 className="font-display text-lg font-semibold mb-1 pr-14">{p.title}</h3>
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
