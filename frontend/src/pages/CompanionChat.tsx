import { useEffect, useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Send, Loader2, MessageCircle, BookOpen } from 'lucide-react'
import toast from 'react-hot-toast'
import { api, streamSSE } from '@/lib/api'

interface ChatMessage {
  id?: string
  role: 'user' | 'assistant'
  content: string
  referenced_chapter_ids?: string[]
}

interface ChapterRef {
  id: string
  chapter_number: number
  title: string
}

interface ProjectSummary {
  id: string
  title: string
  chapters: { id: string; chapter_number: number; title: string }[]
}

const SUGGESTED_PROMPTS = [
  'Have I already covered this idea anywhere?',
  'Which chapter discusses calling and purpose?',
  'Am I repeating myself across chapters?',
  'Where have I used Isaiah 61 before?',
]

export default function CompanionChat() {
  const { id: projectId } = useParams<{ id: string }>()
  const [project, setProject] = useState<ProjectSummary | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loading, setLoading] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!projectId) return
    Promise.all([
      api.get(`/projects/${projectId}`),
      api.get(`/projects/${projectId}/companion-chat/history`),
    ])
      .then(([projRes, historyRes]) => {
        setProject(projRes.data)
        setMessages(
          historyRes.data.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            referenced_chapter_ids: m.referenced_chapter_ids,
          }))
        )
      })
      .catch(() => toast.error('Failed to load manuscript'))
      .finally(() => setLoading(false))
  }, [projectId])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const chapterById = (id: string): ChapterRef | undefined =>
    project?.chapters.find((c) => c.id === id)

  const handleSend = async (overrideText?: string) => {
    const text = (overrideText ?? input).trim()
    if (!text || streaming || !projectId) return

    setMessages((prev) => [...prev, { role: 'user', content: text }, { role: 'assistant', content: '' }])
    setInput('')
    setStreaming(true)

    let buffer = ''
    let citedIds: string[] = []

    try {
      await streamSSE(
        `/projects/${projectId}/companion-chat`,
        { message: text },
        (chunk) => {
          buffer += chunk
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = { role: 'assistant', content: buffer, referenced_chapter_ids: citedIds }
            return updated
          })
        },
        () => setStreaming(false),
        () => {
          setStreaming(false)
          toast.error('Companion Chat had trouble responding')
        },
        (event) => {
          if (event.cited_chapter_ids) {
            citedIds = event.cited_chapter_ids
            setMessages((prev) => {
              const updated = [...prev]
              updated[updated.length - 1] = { ...updated[updated.length - 1], referenced_chapter_ids: citedIds }
              return updated
            })
          }
        }
      )
    } catch {
      setStreaming(false)
    }
  }

  if (loading) return <div className="p-8 text-study-300">Loading your manuscript...</div>
  if (!project) return <div className="p-8 text-study-300">Manuscript not found.</div>

  return (
    <div className="flex flex-col h-screen">
      <div className="px-4 py-4 md:px-8 md:py-5 border-b border-paper-300 flex-shrink-0">
        <Link to={`/projects/${projectId}`} className="text-sm text-study-300 hover:text-seal flex items-center gap-1 mb-2">
          <ArrowLeft size={14} /> Back to manuscript
        </Link>
        <div className="flex items-center gap-2">
          <MessageCircle size={20} className="text-seal" />
          <h1 className="font-display text-display-sm font-semibold">Manuscript Companion</h1>
        </div>
        <p className="text-sm text-study-300 mt-1">
          Knows all {project.chapters.length} chapter{project.chapters.length === 1 ? '' : 's'} of "{project.title}" — ask about structure, repetition, or scripture usage across the whole book.
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 md:px-8 md:py-6 max-w-3xl mx-auto w-full">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-study-300 italic mb-4">
              Try asking one of these, or write your own question:
            </p>
            {SUGGESTED_PROMPTS.map((prompt) => (
              <button
                key={prompt}
                onClick={() => handleSend(prompt)}
                className="block w-full text-left card p-3 text-sm hover:border-seal/50 transition-colors"
              >
                {prompt}
              </button>
            ))}
          </div>
        )}

        <div className="space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'user' ? 'ml-8' : 'mr-8'}>
              <div
                className={`rounded-lg p-4 text-sm leading-relaxed ${
                  m.role === 'user' ? 'bg-paper-200' : 'bg-seal-50 border border-seal-100'
                }`}
              >
                {m.content || (streaming && i === messages.length - 1 && (
                  <Loader2 size={14} className="animate-spin text-seal" />
                ))}
              </div>
              {m.role === 'assistant' && m.referenced_chapter_ids && m.referenced_chapter_ids.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {m.referenced_chapter_ids.map((cid) => {
                    const ch = chapterById(cid)
                    if (!ch) return null
                    return (
                      <Link
                        key={cid}
                        to={`/projects/${projectId}/chapters/${cid}`}
                        className="inline-flex items-center gap-1 text-xs text-seal bg-seal-50 border border-seal-100 rounded-full px-2.5 py-1 hover:bg-seal-100 transition-colors"
                      >
                        <BookOpen size={11} />
                        Ch. {ch.chapter_number}: {ch.title}
                      </Link>
                    )
                  })}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="border-t border-paper-300 px-4 py-3 md:px-8 md:py-4 flex-shrink-0">
        <div className="max-w-3xl mx-auto flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !streaming && handleSend()}
            className="input-field flex-1"
            placeholder="Ask about your manuscript..."
            disabled={streaming}
            autoFocus
          />
          <button
            onClick={() => handleSend()}
            disabled={streaming || !input.trim()}
            className="btn-primary px-4 disabled:opacity-50"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
