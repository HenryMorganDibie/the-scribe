import { useEffect, useRef, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Plus, GripVertical, FileText, ArrowLeft, X, MessageCircle, Trash2, Library, MoreVertical } from 'lucide-react'
import toast from 'react-hot-toast'
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors, DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext, verticalListSortingStrategy, useSortable, arrayMove,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { api } from '@/lib/api'
import BookStylePanel from '@/components/studio/BookStylePanel'
import BookSourcesPanel from '@/components/studio/BookSourcesPanel'
import ProgressPanel from '@/components/studio/ProgressPanel'
import RepetitionPanel from '@/components/studio/RepetitionPanel'
import ExportMenu from '@/components/ui/ExportMenu'
import { STAGES, stageOf, type Stage } from '@/lib/stages'

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
  target_audience?: string | null
  style_rules: string[]
  style_notes?: string | null
}

/** "⋮" menu on a chapter row, so delete isn't one stray click away. */
function RowMenu({ title, onDelete }: { title: string; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => { e.preventDefault(); setOpen((o) => !o) }}
        className="icon-btn"
        aria-label={`More actions for ${title}`}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <MoreVertical size={16} />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full mt-1 z-20 w-44 card py-1 shadow-paper-lift">
          <button
            role="menuitem"
            onClick={() => { setOpen(false); onDelete() }}
            className="menu-item flex items-center gap-2 text-red-700 hover:bg-red-50"
          >
            <Trash2 size={14} /> Delete chapter
          </button>
        </div>
      )}
    </div>
  )
}

function SortableChapter({ chapter, projectId, onDelete, onStageChange }: {
  chapter: Chapter
  projectId: string
  onDelete: (id: string) => void
  onStageChange: (id: string, stage: Stage) => void
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: chapter.id })
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 }

  return (
    <div ref={setNodeRef} style={style} className="card px-3 py-3 md:px-4 flex items-center gap-3 hover:border-seal/50">
      <button {...attributes} {...listeners} className="text-study-200 hover:text-seal cursor-grab active:cursor-grabbing" aria-label={`Reorder ${chapter.title}`}>
        <GripVertical size={18} />
      </button>
      <span className="text-xs text-study-400 font-mono w-10 flex-shrink-0">Ch. {chapter.chapter_number}</span>
      <Link to={`/projects/${projectId}/chapters/${chapter.id}`} className="flex-1 min-w-0">
        <h3 className="font-display font-semibold text-[17px] text-ink truncate">{chapter.title}</h3>
        <p className="text-xs text-study-400 mt-0.5">
          {(chapter.word_count || 0).toLocaleString()} words
          {chapter.voice_match_score ? ` · voice match ${Math.round(chapter.voice_match_score * 100)}%` : ''}
        </p>
      </Link>
      <select
        value={stageOf(chapter.status).id}
        onChange={(e) => onStageChange(chapter.id, e.target.value as Stage)}
        className={`status-tag cursor-pointer ${stageOf(chapter.status).className}`}
        aria-label={`Stage of ${chapter.title}`}
      >
        {STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
      </select>
      <RowMenu title={chapter.title} onDelete={() => onDelete(chapter.id)} />
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
  const [view, setView] = useState<'chapters' | 'settings'>('chapters')
  const handleDeleteChapter = async (chapterId: string) => {
    if (!project) return
    const ch = project.chapters.find((c) => c.id === chapterId)
    if (!confirm(`Delete "${ch?.title || 'this chapter'}"? This cannot be undone.`)) return
    try {
      await api.delete(`/projects/${id}/chapters/${chapterId}`)
      setProject((prev) => prev ? { ...prev, chapters: prev.chapters.filter((c) => c.id !== chapterId) } : prev)
      setProgressKey((k) => k + 1)
      toast.success('Chapter deleted')
    } catch {
      toast.error('Failed to delete chapter')
    }
  }

  const handleStageChange = async (chapterId: string, status: Stage) => {
    setProject((prev) => prev ? { ...prev, chapters: prev.chapters.map((c) => c.id === chapterId ? { ...c, status } : c) } : prev)
    try {
      await api.put(`/projects/${id}/chapters/${chapterId}`, { status })
      setProgressKey((k) => k + 1)
    } catch {
      toast.error('Failed to update stage')
      load()
    }
  }

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 5 } }))
  const [progressKey, setProgressKey] = useState(0)

  const load = () => {
    api.get(`/projects/${id}`)
      .then((r) => setProject(r.data))
      .catch(() => toast.error('Failed to load manuscript'))
      .finally(() => setLoading(false))
    setProgressKey((k) => k + 1)
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

  return (
    <div className="px-4 py-6 md:p-8 max-w-4xl mx-auto">
      <Link to="/projects" className="text-sm text-study-400 hover:text-seal flex items-center gap-1 mb-4">
        <ArrowLeft size={14} /> All manuscripts
      </Link>

      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="font-display text-display-md font-semibold">{project.title}</h1>
          <p className="text-study-400">
            <span className="text-seal capitalize">{project.genre}</span>
            {project.theme && <> · {project.theme}</>}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/projects/${project.id}/bible`} className="btn-secondary flex items-center gap-2 text-sm">
            <Library size={16} /> Book Bible
          </Link>
          <Link to={`/projects/${project.id}/companion-chat`} className="btn-secondary flex items-center gap-2 text-sm">
            <MessageCircle size={16} /> Ask your book
          </Link>
          <ExportMenu onExport={handleExport} busy={!!exporting} />
          <button
            onClick={() => { setView('chapters'); setShowForm(!showForm) }}
            className="btn-primary flex items-center gap-2 text-sm"
          >
            {showForm ? <X size={16} /> : <Plus size={16} />}
            {showForm ? 'Cancel' : 'Add chapter'}
          </button>
        </div>
      </div>

      <ProgressPanel projectId={project.id} refreshKey={progressKey} />

      <div className="flex gap-6 border-b border-paper-300 mb-5" role="tablist">
        {([
          ['chapters', `Chapters · ${project.chapters.length}`],
          ['settings', 'Book settings'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={view === id}
            onClick={() => setView(id)}
            className={`py-3 -mb-px text-[15px] font-medium border-b-2 transition-colors ${view === id ? 'text-seal border-seal' : 'text-study-400 border-transparent hover:text-study-700'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {view === 'settings' ? (
        <div className="space-y-4 animate-fade-in-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <BookStylePanel
              projectId={project.id}
              targetAudience={project.target_audience}
              styleRules={project.style_rules}
              styleNotes={project.style_notes}
              onSaved={load}
            />
            <BookSourcesPanel projectId={project.id} linked={project.source_sermons} onSaved={load} />
          </div>
          {project.chapters.length > 1 && <RepetitionPanel projectId={project.id} />}
        </div>
      ) : (
        <>
          {showForm && (
            <form onSubmit={handleAddChapter} className="card p-6 mb-6 space-y-4 animate-fade-in-up">
              <div>
                <label htmlFor="chapter-title" className="block text-sm text-study-400 mb-1.5">Chapter Title</label>
                <input id="chapter-title" required value={chTitle} onChange={(e) => setChTitle(e.target.value)} className="input-field w-full" placeholder="The Wilderness Season" />
              </div>
              <div>
                <label htmlFor="chapter-intent" className="block text-sm text-study-400 mb-1.5">Intent</label>
                <textarea id="chapter-intent" value={chIntent} onChange={(e) => setChIntent(e.target.value)} className="input-field w-full h-24 resize-none" placeholder="What should this chapter accomplish for the reader?" />
              </div>
              <button type="submit" className="btn-primary">Add Chapter</button>
            </form>
          )}

          {project.chapters.length === 0 ? (
            <div className="text-center py-16">
              <FileText size={32} className="mx-auto text-study-200 mb-3" />
              <p className="text-study-400 mb-4">No chapters yet. Add your first chapter to begin.</p>
            </div>
          ) : (
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={project.chapters.map((c) => c.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-2">
                  {project.chapters.map((ch) => (
                    <SortableChapter key={ch.id} chapter={ch} projectId={project.id} onDelete={handleDeleteChapter} onStageChange={handleStageChange} />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}
        </>
      )}
    </div>
  )
}
