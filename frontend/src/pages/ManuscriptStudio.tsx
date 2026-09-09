import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Plus, GripVertical, FileText, Download, ArrowLeft, X, MessageCircle, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { api } from '@/lib/api'

interface Chapter {
  id: string
  title: string
  chapter_number: number
  status: string
  word_count: number
  position: number
  voice_match_score?: number
}

interface ProjectDetail {
  id: string
  title: string
  genre: string
  theme?: string
  target_chapters: number
  chapters: Chapter[]
  source_sermons: { id: string; title: string }[]
}

const statusColors: Record<string, string> = {
  draft: 'status-draft',
  in_progress: 'status-in_progress',
  complete: 'status-complete',
}

function SortableChapter({ chapter, projectId, onDelete }: { chapter: Chapter; projectId: string; onDelete: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: chapter.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <div ref={setNodeRef} style={style} className="card p-4 flex items-center gap-3">
      <button {...attributes} {...listeners} className="text-ink0 hover:text-seal cursor-grab active:cursor-grabbing">
        <GripVertical size={18} />
      </button>
      <Link to={`/projects/${projectId}/chapters/${chapter.id}`} className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink0 font-mono">Ch. {chapter.chapter_number}</span>
          <h3 className="font-medium text-ink truncate">{chapter.title}</h3>
        </div>
        <div className="flex items-center gap-3 mt-1 text-xs text-study-300">
          <span>{chapter.word_count || 0} words</span>
          {chapter.voice_match_score && <span>Voice match: {Math.round(chapter.voice_match_score * 100)}%</span>}
        </div>
      </Link>
      <span className={`status-tag ${statusColors[chapter.status] || statusColors.draft}`}>
        {chapter.status.replace('_', ' ')}
      </span>
      <button
        onClick={(e) => { e.preventDefault(); onDelete(chapter.id) }}
        className="p-1.5 text-study-300 hover:text-red-600 hover:bg-red-50 rounded"
        title="Delete chapter"
      >
        <Trash2 size={14} />
      </button>
    </div>
  )
}

export default function ManuscriptStudio() {
  const { id } = useParams<{ id: string }>()
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [chTitle, setChTitle] = useState('')
  const [chIntent, setChIntent] = useState('')
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null)
  const handleDeleteChapter = async (chapterId: string) => {
    if (!project) return
    const ch = project.chapters.find((c) => c.id === chapterId)
    if (!confirm(`Delete "${ch?.title || 'this chapter'}"? This cannot be undone.`)) return
    try {
      await api.delete(`/projects/${id}/chapters/${chapterId}`)
      setProject((prev) => prev ? { ...prev, chapters: prev.chapters.filter((c) => c.id !== chapterId) } : prev)
      toast.success('Chapter deleted')
    } catch {
      toast.error('Failed to delete chapter')
    }
  }

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))

  const load = () => {
    api.get(`/projects/${id}`)
      .then((r) => setProject(r.data))
      .catch(() => toast.error('Failed to load manuscript'))
      .finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleAddChapter = async (e: React.FormEvent) => {
    e.preventDefault()
    const nextNumber = project?.chapters.length
      ? Math.max(...project.chapters.map((c) => c.chapter_number)) + 1
      : 1
    try {
      await api.post(`/projects/${id}/chapters`, {
        title: chTitle,
        chapter_number: nextNumber,
        intent: chIntent,
        key_points: [],
        anchor_scriptures: [],
        testimony_ids: [],
      })
      toast.success('Chapter added')
      setChTitle('')
      setChIntent('')
      setShowForm(false)
      load()
    } catch {
      toast.error('Failed to add chapter')
    }
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    if (!over || active.id === over.id || !project) return

    const oldIndex = project.chapters.findIndex((c) => c.id === active.id)
    const newIndex = project.chapters.findIndex((c) => c.id === over.id)
    const reordered = arrayMove(project.chapters, oldIndex, newIndex)
    setProject({ ...project, chapters: reordered })

    try {
      await api.put(`/projects/${id}/chapters/reorder`, { order: reordered.map((c) => c.id) })
    } catch {
      toast.error('Failed to save order')
      load()
    }
  }

  const handleExport = async (format: 'docx' | 'pdf') => {
    setExporting(format)
    try {
      const res = await api.post(`/export/project/${id}?format=${format}`, {}, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project?.title.toLowerCase().replace(/\s+/g, '-')}-manuscript.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Manuscript exported')
    } catch {
      toast.error('Export failed')
    } finally {
      setExporting(null)
    }
  }

  if (loading) return <div className="p-8 text-study-300">Loading manuscript...</div>
  if (!project) return <div className="p-8 text-study-300">Manuscript not found.</div>

  const completedChapters = project.chapters.filter((chapter) => chapter.status === 'complete').length
  const totalWords = project.chapters.reduce((sum, chapter) => sum + (chapter.word_count || 0), 0)
  const chapterProgress = Math.min(100, Math.round((completedChapters / Math.max(project.target_chapters, 1)) * 100))
  const nextChapter = project.chapters.find((chapter) => chapter.status === 'draft') || project.chapters.find((chapter) => chapter.status !== 'complete')

  return (
    <div className="px-4 py-6 md:p-8 max-w-4xl mx-auto">
      <Link to="/projects" className="text-sm text-study-300 hover:text-seal flex items-center gap-1 mb-4">
        <ArrowLeft size={14} /> All manuscripts
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 mb-2">
        <div>
          <h1 className="font-display text-display-md font-semibold">{project.title}</h1>
          <span className="text-sm text-seal capitalize">{project.genre}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/projects/${project.id}/companion-chat`} className="btn-secondary flex items-center gap-2 text-sm">
            <MessageCircle size={16} /> Companion Chat
          </Link>
          <button onClick={() => handleExport('docx')} disabled={!!exporting} className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={16} /> {exporting === 'docx' ? 'Exporting...' : 'Export .docx'}
          </button>
          <button onClick={() => handleExport('pdf')} disabled={!!exporting} className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={16} /> {exporting === 'pdf' ? 'Exporting...' : 'Export .pdf'}
          </button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2 text-sm">
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'Add Chapter'}
          </button>
        </div>
      </div>

      {project.theme && <p className="text-study-300 mb-6">{project.theme}</p>}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="card p-4 md:col-span-2">
          <div className="flex items-center justify-between text-sm mb-2"><span className="font-medium">Manuscript progress</span><span className="text-seal">{completedChapters}/{project.target_chapters} chapters complete</span></div>
          <div className="h-2 bg-paper-200 rounded-full overflow-hidden"><div className="h-full bg-seal transition-all" style={{ width: `${chapterProgress}%` }} /></div>
          <p className="text-xs text-study-300 mt-2">{totalWords.toLocaleString()} words drafted · {nextChapter ? `Next: ${nextChapter.title}` : 'Your manuscript is ready to review and export.'}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs uppercase tracking-wide text-study-300 mb-2">Next best step</p>
          {nextChapter ? <Link to={`/projects/${project.id}/chapters/${nextChapter.id}`} className="text-sm text-seal hover:underline">{nextChapter.status === 'draft' ? `Draft “${nextChapter.title}”` : `Finish “${nextChapter.title}”`}</Link> : <span className="text-sm text-seal">Export your manuscript</span>}
        </div>
      </div>

      {project.source_sermons.length > 0 && (
        <div className="card p-4 mb-6">
          <p className="text-xs uppercase tracking-wide text-study-300 mb-2">Book sources</p>
          <p className="text-sm text-study-400 mb-2">This blueprint was grounded in these sermons. Generation still uses your voice profile and verified scripture references.</p>
          <div className="flex flex-wrap gap-2">{project.source_sermons.map((sermon) => <span key={sermon.id} className="text-xs bg-seal-50 border border-seal-200 text-seal-400 rounded-full px-3 py-1">{sermon.title}</span>)}</div>
        </div>
      )}

      {showForm && (
        <form onSubmit={handleAddChapter} className="card p-6 mb-6 space-y-4 animate-fade-in-up">
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Chapter Title</label>
            <input required value={chTitle} onChange={(e) => setChTitle(e.target.value)} className="input-field w-full" placeholder="The Wilderness Season" />
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Intent</label>
            <textarea value={chIntent} onChange={(e) => setChIntent(e.target.value)} className="input-field w-full h-24 resize-none" placeholder="What should this chapter accomplish for the reader?" />
          </div>
          <button type="submit" className="btn-primary">Add Chapter</button>
        </form>
      )}

      {project.chapters.length === 0 ? (
        <div className="text-center py-16">
          <FileText size={32} className="mx-auto text-ink0 mb-3" />
          <p className="text-study-300 mb-4">No chapters yet. Add your first chapter to begin.</p>
        </div>
      ) : (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
          <SortableContext items={project.chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
            <div className="space-y-2">
              {project.chapters.map((ch) => (
                <SortableChapter key={ch.id} chapter={ch} projectId={project.id} onDelete={handleDeleteChapter} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      )}
    </div>
  )
}
