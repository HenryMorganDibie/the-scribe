import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
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
  const [exporting, setExporting] = useState(false)
  const navigate = useNavigate()

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
    api.get(`/projects/${id}`).then((r) => setProject(r.data)).finally(() => setLoading(false))
  }

  useEffect(load, [id])

  const handleAddChapter = async (e: React.FormEvent) => {
    e.preventDefault()
    const nextNumber = (project?.chapters.length || 0) + 1
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

  const handleExport = async () => {
    setExporting(true)
    try {
      const res = await api.post(`/export/project/${id}`, {}, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project?.title.toLowerCase().replace(/\s+/g, '-')}-manuscript.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success('Manuscript exported')
    } catch {
      toast.error('Export failed')
    } finally {
      setExporting(false)
    }
  }

  if (loading) return <div className="p-8 text-study-300">Loading manuscript...</div>
  if (!project) return <div className="p-8 text-study-300">Manuscript not found.</div>

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
          <button onClick={handleExport} disabled={exporting} className="btn-secondary flex items-center gap-2 text-sm">
            <Download size={16} /> {exporting ? 'Exporting...' : 'Export .docx'}
          </button>
          <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2 text-sm">
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'Add Chapter'}
          </button>
        </div>
      </div>

      {project.theme && <p className="text-study-300 mb-6">{project.theme}</p>}

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
