import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useEditor, EditorContent, BubbleMenu } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import CharacterCount from '@tiptap/extension-character-count'
import {
  ChevronLeft, Sparkles, Wand2, BookOpen, ScrollText, CheckCircle2,
  Send, Loader2, X, Check, AlertCircle, Maximize2, Minimize2,
  Bold, Italic, Heading2, Quote,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { api, getCsrfToken, streamSSE } from '@/lib/api'
import { usePack } from '@/stores/authStore'
import HistoryPanel from '@/components/editor/HistoryPanel'
import ChapterNotesPanel from '@/components/editor/ChapterNotesPanel'
import ConsistencyCheck from '@/components/editor/ConsistencyCheck'
import PlanPanel, { type Scene } from '@/components/editor/PlanPanel'
import QuoteCheck from '@/components/editor/QuoteCheck'
import ExportMenu from '@/components/ui/ExportMenu'
import { STAGES, stageOf, type Stage } from '@/lib/stages'

interface Chapter {
  id: string
  title: string
  chapter_number: number
  intent?: string
  key_points?: string[]
  anchor_scriptures?: string[]
  testimony_ids?: string[]
  content?: string
  status: string
  voice_match_score?: number
  scenes?: Scene[] | null
}

interface Testimony {
  id: string
  title: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface VoiceCheck {
  score: number
  grade: string
  feedback: string
  cadence_score?: number
  cadence_delta?: number
  phrase_matches?: string[]
  phrase_usage_rate?: number
  scripture_matches?: string[]
  fiction_signals?: { pov: string; tense: string; dialogue_ratio: number } | null
}

type SidebarTab = 'assist' | 'plan' | 'notes' | 'history'

const SIDEBAR_TABS: { id: SidebarTab; label: string }[] = [
  { id: 'assist', label: 'Assist' },
  { id: 'plan', label: 'Plan' },
  { id: 'notes', label: 'Notes' },
  { id: 'history', label: 'History' },
]

type SaveState = 'saved' | 'unsaved' | 'saving' | 'error'

const SAVE_LABELS: Record<SaveState, string> = {
  saved: 'Saved',
  unsaved: 'Unsaved changes',
  saving: 'Saving…',
  error: 'Not saved, retry',
}

export default function ChapterEditor() {
  const pack = usePack()
  const { id: projectId, chapterId } = useParams<{ id: string; chapterId: string }>()
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [loading, setLoading] = useState(true)
  const [saveState, setSaveState] = useState<SaveState>('saved')
  const [focused, setFocused] = useState(false)
  const [panelOpen, setPanelOpen] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [testimonies, setTestimonies] = useState<Testimony[]>([])
  const [voiceCheck, setVoiceCheck] = useState<VoiceCheck | null>(null)
  const [mobileAiOpen, setMobileAiOpen] = useState(false)
  const [scriptureSuggestions, setScriptureSuggestions] = useState<any[]>([])
  const [tab, setTab] = useState<SidebarTab>('assist')
  const [historyKey, setHistoryKey] = useState(0)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatStreaming, setChatStreaming] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout>>()
  const lastIndexedHtmlRef = useRef<string>('')

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Begin writing — or let The Scribe generate a first draft in your voice...' }),
      CharacterCount,
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'manuscript-canvas max-w-none focus:outline-none min-h-[60vh]',
      },
    },
    onUpdate: ({ editor }) => {
      setSaveState('unsaved')
      // Debounced autosave
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
      saveTimeoutRef.current = setTimeout(() => {
        autoSave(editor.getHTML(), editor.storage.characterCount.words())
      }, 2000)
    },
  })

  const load = useCallback(async () => {
    try {
      const [chRes, testRes] = await Promise.all([
        api.get(`/projects/${projectId}/chapters/${chapterId}`),
        api.get('/testimonies'),
      ])
      setChapter(chRes.data)
      setTestimonies(testRes.data)
      if (editor && chRes.data.content) {
        editor.commands.setContent(chRes.data.content)
        lastIndexedHtmlRef.current = chRes.data.content
      } else if (editor) {
        lastIndexedHtmlRef.current = ''
      }
      if (chRes.data.voice_match_score) {
        setVoiceCheck({
          score: chRes.data.voice_match_score,
          grade: chRes.data.voice_match_score >= 0.9 ? 'Excellent' : chRes.data.voice_match_score >= 0.8 ? 'Strong' : chRes.data.voice_match_score >= 0.7 ? 'Good' : 'Needs work',
          feedback: '',
        })
      }
    } catch {
      toast.error('Failed to load chapter')
    } finally {
      setLoading(false)
    }
  }, [projectId, chapterId, editor])

  useEffect(() => {
    if (editor) load()
  }, [editor, load])

  useEffect(() => {
    return () => {
      if (editor) {
        const content = editor.getHTML()
        if (content !== lastIndexedHtmlRef.current) {
          const wordCount = editor.storage.characterCount.words()
          const url = api.defaults.baseURL + `/projects/${projectId}/chapters/${chapterId}`
          const csrf = getCsrfToken()
          // keepalive lets this finish after the page goes away. Auth is the
          // session cookie + CSRF header, same as every other write.
          fetch(url, {
            method: 'PUT',
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
              ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
            },
            body: JSON.stringify({
              content,
              word_count: wordCount,
              trigger_indexing: true,
            }),
            keepalive: true,
          }).catch(() => {})
        }
      }
    }
  }, [projectId, chapterId, editor])

  const autoSave = async (content: string, wordCount: number) => {
    setSaveState('saving')
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, {
        content,
        word_count: wordCount,
        trigger_indexing: false,
      })
      setSaveState('saved')
    } catch {
      setSaveState('error')
    }
  }

  const handleStageChange = async (status: Stage) => {
    if (!chapter) return
    const previous = chapter.status
    setChapter({ ...chapter, status })
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, { status })
      toast.success(`Marked ${stageOf(status).label}`)
    } catch {
      setChapter((c) => (c ? { ...c, status: previous } : c))
      toast.error('Failed to update stage')
    }
  }

  const manualSave = async () => {
    if (!editor) return
    if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current)
    setSaveState('saving')
    const content = editor.getHTML()
    const wordCount = editor.storage.characterCount.words()
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, {
        content,
        word_count: wordCount,
        trigger_indexing: true,
      })
      lastIndexedHtmlRef.current = content
      setHistoryKey((k) => k + 1)
      setSaveState('saved')
    } catch {
      setSaveState('error')
      toast.error('Save failed')
    }
  }

  // ── Generate full chapter ──────────────────
  const handleGenerateChapter = async () => {
    if (!editor) return
    if (!editor.isEmpty && !window.confirm('Replace this draft with a new AI draft? Your current draft is kept in History.')) return
    setGenerating(true)
    editor.commands.clearContent()

    let buffer = ''
    try {
      await streamSSE(
        '/generate/chapter',
        { chapter_id: chapterId },
        (chunk) => {
          buffer += chunk
          editor.commands.setContent(buffer.replace(/\n/g, '<br>'))
        },
        () => {
          setGenerating(false)
          const content = editor.getHTML()
          const wordCount = editor.storage.characterCount.words()
          api.put(`/projects/${projectId}/chapters/${chapterId}`, {
            content,
            word_count: wordCount,
            trigger_indexing: true,
          }).catch(() => {})
          lastIndexedHtmlRef.current = content
          setHistoryKey((k) => k + 1)
          toast.success('Chapter draft generated')
        },
        (err) => {
          setGenerating(false)
          toast.error(err)
        }
      )
    } catch {
      setGenerating(false)
      toast.error('Generation failed')
    }
  }

  // ── Continue writing ───────────────────────
  const handleContinue = async () => {
    if (!editor) return
    setActionLoading('continue')
    const cursorText = editor.getText()

    editor.commands.focus('end')

    try {
      await streamSSE(
        '/generate/continue',
        { chapter_id: chapterId, cursor_text: cursorText },
        (chunk) => {
          editor.chain().focus('end').insertContent(chunk).run()
        },
        () => {
          setActionLoading(null)
          autoSave(editor.getHTML(), editor.storage.characterCount.words())
        },
        (err) => {
          setActionLoading(null)
          toast.error(err)
        }
      )
    } catch {
      setActionLoading(null)
    }
  }

  // ── Weave story ─────────────────────────────
  const handleWeaveStory = async (testimonyId: string) => {
    if (!editor) return
    setActionLoading('weave')
    const cursorText = editor.getText()
    editor.commands.focus('end')
    editor.chain().focus('end').insertContent('<p></p>').run()

    try {
      await streamSSE(
        '/generate/weave-story',
        { chapter_id: chapterId, testimony_id: testimonyId, cursor_text: cursorText },
        (chunk) => {
          editor.chain().focus('end').insertContent(chunk).run()
        },
        () => {
          setActionLoading(null)
          autoSave(editor.getHTML(), editor.storage.characterCount.words())
          toast.success('Testimony woven in')
        },
        (err) => {
          setActionLoading(null)
          toast.error(err)
        }
      )
    } catch {
      setActionLoading(null)
    }
  }

  // ── Voice check ──────────────────────────────
  const handleVoiceCheck = async () => {
    if (!editor) return
    setActionLoading('voice-check')
    try {
      const res = await api.post('/generate/voice-check', {
        chapter_id: chapterId,
        text: editor.getText(),
      })
      // The API calls the headline number voice_match_score; the panel reads `score`.
      setVoiceCheck({ ...res.data, score: res.data.voice_match_score })
      toast.success(`Voice match: ${Math.round(res.data.voice_match_score * 100)}%`)
    } catch {
      toast.error('Voice check failed')
    } finally {
      setActionLoading(null)
    }
  }

  // ── Scripture suggestions ────────────────────
  const handleScriptureSuggest = async () => {
    setActionLoading('scripture')
    try {
      const context = editor?.getText().slice(-800) || chapter?.intent || ''
      const res = await api.post('/generate/scripture-suggest', { chapter_id: chapterId, context })
      setScriptureSuggestions(res.data.suggestions || [])
    } catch {
      toast.error('Scripture suggestion failed')
    } finally {
      setActionLoading(null)
    }
  }

  const insertScripture = (s: any) => {
    if (!editor) return
    editor.chain().focus('end').insertContent(
      `<blockquote>${s.text} — <em>${s.ref}</em></blockquote>`
    ).run()
  }

  // ── Chat ──────────────────────────────────────
  const handleChatSend = async () => {
    if (!chatInput.trim()) return
    const userMsg: ChatMessage = { role: 'user', content: chatInput }
    setChatMessages((prev) => [...prev, userMsg, { role: 'assistant', content: '' }])
    setChatInput('')
    setChatStreaming(true)

    let buffer = ''
    try {
      await streamSSE(
        '/generate/chat',
        {
          chapter_id: chapterId,
          message: userMsg.content,
          history: chatMessages.map((m) => ({ role: m.role, content: m.content })),
        },
        (chunk) => {
          buffer += chunk
          setChatMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = { role: 'assistant', content: buffer }
            return updated
          })
        },
        () => setChatStreaming(false),
        (err) => {
          setChatStreaming(false)
          toast.error(err)
        }
      )
    } catch {
      setChatStreaming(false)
    }
  }

  const handleExportChapter = async (format: 'docx' | 'pdf') => {
    try {
      const res = await api.post(`/export/chapter/${chapterId}?format=${format}`, {}, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `chapter-${chapter?.chapter_number}-${chapter?.title.toLowerCase().replace(/\s+/g, '-')}.${format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch {
      toast.error('Export failed')
    }
  }

  if (loading || !chapter) return <div className="p-8 text-study-300">Loading chapter...</div>

  const wordCount = editor?.storage.characterCount.words() || 0
  const showPanel = panelOpen && !focused
  const saveBefore = async () => {
    if (editor) await autoSave(editor.getHTML(), editor.storage.characterCount.words())
  }

  return (
    <div className={focused ? 'fixed inset-0 z-40 bg-paper flex' : 'flex h-screen'}>
      {/* Writing column */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-4 md:px-5 py-2 border-b border-paper-300 bg-paper">
          {!focused && (
            <>
              <Link to={`/projects/${projectId}`} className="text-sm text-study-400 hover:text-seal flex items-center gap-1">
                <ChevronLeft size={16} /> Manuscript
              </Link>
              <span className="text-study-200" aria-hidden="true">/</span>
            </>
          )}
          <span className="folio">Chapter {chapter.chapter_number}</span>
          <select
            value={stageOf(chapter.status).id}
            onChange={(e) => handleStageChange(e.target.value as Stage)}
            className={`status-tag cursor-pointer ${stageOf(chapter.status).className}`}
            aria-label="Chapter stage"
          >
            {STAGES.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
          <span className="flex-1" />
          <button
            onClick={manualSave}
            disabled={saveState === 'saving'}
            title="Save now and add a version to History"
            className={`flex items-center gap-1.5 text-sm px-2 py-1 rounded hover:bg-paper-200 ${saveState === 'error' ? 'text-seal' : 'text-study-400'}`}
          >
            {saveState === 'saving' ? <Loader2 size={14} className="animate-spin" />
              : saveState === 'error' ? <AlertCircle size={14} />
              : saveState === 'saved' ? <Check size={14} />
              : <span className="w-1.5 h-1.5 rounded-full bg-seal-300" aria-hidden="true" />}
            {SAVE_LABELS[saveState]}
          </button>
          {!focused && <ExportMenu iconOnly onExport={handleExportChapter} />}
          <button
            onClick={() => setFocused((f) => !f)}
            className={`toolbar-btn ${focused ? 'toolbar-btn-on' : ''}`}
            title={focused ? 'Exit focus mode' : 'Hide everything except your writing'}
          >
            {focused ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
            {focused ? 'Exit focus' : 'Focus'}
          </button>
          {!focused && (
            <button
              onClick={() => setPanelOpen((o) => !o)}
              aria-pressed={panelOpen}
              className={`toolbar-btn hidden md:inline-flex ${panelOpen ? 'toolbar-btn-on' : ''}`}
            >
              <Sparkles size={16} /> The Scribe
            </button>
          )}
        </div>

        {/* Manuscript */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-[680px] mx-auto px-5 md:px-8 py-10">
            <h1 className="font-display text-display-md font-semibold">{chapter.title}</h1>
            {chapter.intent && <p className="text-study-400 mt-1 mb-8">{chapter.intent}</p>}

            {(!chapter.content || chapter.content.length < 20) && !generating && (
              <button onClick={handleGenerateChapter} className="btn-primary w-full flex items-center justify-center gap-2 mb-6 py-3">
                <Sparkles size={18} /> Generate Chapter Draft in My Voice
              </button>
            )}

            {generating && (
              <div className="flex items-center gap-2 text-seal text-sm mb-4 animate-pulse">
                <Sparkles size={16} /> The Scribe is writing in your voice...
              </div>
            )}

            {editor && (
              <BubbleMenu editor={editor} tippyOptions={{ duration: 120 }} className="flex items-center gap-0.5 p-1 bg-study-700 rounded-md shadow-paper-lift">
                <button onClick={() => editor.chain().focus().toggleBold().run()} aria-label="Bold" aria-pressed={editor.isActive('bold')} className={`bubble-btn ${editor.isActive('bold') ? 'bubble-btn-on' : ''}`}><Bold size={15} /></button>
                <button onClick={() => editor.chain().focus().toggleItalic().run()} aria-label="Italic" aria-pressed={editor.isActive('italic')} className={`bubble-btn ${editor.isActive('italic') ? 'bubble-btn-on' : ''}`}><Italic size={15} /></button>
                <button onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()} aria-label="Heading" aria-pressed={editor.isActive('heading', { level: 2 })} className={`bubble-btn ${editor.isActive('heading', { level: 2 }) ? 'bubble-btn-on' : ''}`}><Heading2 size={15} /></button>
                <button onClick={() => editor.chain().focus().toggleBlockquote().run()} aria-label="Quote" aria-pressed={editor.isActive('blockquote')} className={`bubble-btn ${editor.isActive('blockquote') ? 'bubble-btn-on' : ''}`}><Quote size={15} /></button>
              </BubbleMenu>
            )}

            <EditorContent editor={editor} />

            <div className="mt-8 pt-4 border-t border-paper-300 text-xs text-study-400 flex flex-wrap items-center gap-4">
              <span>{wordCount.toLocaleString()} words</span>
              {voiceCheck && (
                <span className="flex items-center gap-1">
                  <CheckCircle2 size={12} className="text-seal" />
                  Voice match: {Math.round(voiceCheck.score * 100)}% ({voiceCheck.grade})
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile AI toggle button — floating, bottom-right */}
      {!focused && (
        <button
          onClick={() => setMobileAiOpen(true)}
          className="fixed bottom-5 right-5 z-30 md:hidden btn-primary rounded-full p-3 shadow-lg flex items-center gap-2"
        >
          <Sparkles size={18} />
          <span className="text-sm font-medium">The Scribe</span>
        </button>
      )}

      {/* The Scribe panel — desktop: collapsible right column; mobile: slide-over */}
      {mobileAiOpen && (
        <div className="fixed inset-0 z-40 bg-black/50 md:hidden" onClick={() => setMobileAiOpen(false)} />
      )}
      <aside
        aria-label="The Scribe"
        className={`
          bg-paper-200 flex-col border-paper-300 border-l
          fixed inset-y-0 right-0 z-50 w-full max-w-sm flex
          transition-transform duration-200
          ${mobileAiOpen ? 'translate-x-0' : 'translate-x-full'}
          ${showPanel ? 'md:static md:z-auto md:w-96 md:max-w-none md:translate-x-0' : 'md:hidden'}
        `}
      >
        <div className="p-4 border-b border-paper-300 flex items-center gap-2">
          <Sparkles size={18} className="text-seal" />
          <h2 className="font-display text-display-xs font-semibold flex-1">The Scribe</h2>
          <button
            onClick={() => { setMobileAiOpen(false); setPanelOpen(false) }}
            className="icon-btn"
            aria-label="Close panel"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex border-b border-paper-300" role="tablist">
          {SIDEBAR_TABS.map(({ id, label }) => (
            <button
              key={id}
              role="tab"
              aria-selected={tab === id}
              onClick={() => setTab(id)}
              className={`flex-1 py-3 text-sm font-medium transition-colors border-b-2 ${tab === id ? 'text-seal border-seal' : 'text-study-400 border-transparent hover:text-study-700'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === 'history' ? (
          <HistoryPanel
            projectId={projectId!}
            chapterId={chapterId!}
            refreshKey={historyKey}
            onRestored={(content) => {
              editor?.commands.setContent(content)
              lastIndexedHtmlRef.current = content
            }}
          />
        ) : tab === 'plan' ? (
          <PlanPanel
            key={chapter?.id}
            projectId={projectId!}
            chapterId={chapterId!}
            intent={chapter?.intent}
            keyPoints={chapter?.key_points}
            scenes={chapter?.scenes}
            onSaved={(update) => setChapter((c) => (c ? { ...c, ...update } : c))}
          />
        ) : tab === 'notes' ? (
          <ChapterNotesPanel projectId={projectId!} chapterId={chapterId!} />
        ) : (
          <>
            {chatMessages.length > 0 ? (
              /* A conversation replaces the action list until it's cleared */
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <button
                  onClick={() => setChatMessages([])}
                  disabled={chatStreaming}
                  className="text-xs text-study-400 hover:text-seal flex items-center gap-1 disabled:opacity-50"
                >
                  <ChevronLeft size={14} /> Back to actions
                </button>
                {chatMessages.map((m, i) => (
                  <div key={i} className={`text-sm rounded-lg p-3 whitespace-pre-wrap ${m.role === 'user' ? 'bg-paper-100 ml-6' : 'bg-seal-50 border border-seal-100 mr-6'}`}>
                    {m.content || (chatStreaming && i === chatMessages.length - 1 && <Loader2 size={14} className="animate-spin text-seal" />)}
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                <p className="folio">Write</p>

                <button
                  onClick={handleContinue}
                  disabled={!!actionLoading || generating}
                  className="w-full card p-3 text-left hover:border-seal/50 flex items-start gap-3 disabled:opacity-50"
                >
                  <Wand2 size={18} className="text-seal flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-sm">Continue Writing</h3>
                    <p className="text-xs text-study-400">Pick up from where you left off, in your voice.</p>
                  </div>
                  {actionLoading === 'continue' && <Loader2 size={14} className="animate-spin text-seal ml-auto" />}
                </button>

                <div className="card p-3">
                  <div className="flex items-start gap-3 mb-2">
                    <ScrollText size={18} className="text-seal flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="font-medium text-sm">Weave In My Story</h3>
                      <p className="text-xs text-study-400">Pull from your {pack.story.vault}.</p>
                    </div>
                  </div>
                  {testimonies.length === 0 ? (
                    <p className="text-xs text-study-400 ml-8">
                      No {pack.story.plural} yet — <Link to="/testimonies" className="text-seal underline">add one</Link>
                    </p>
                  ) : (
                    <div className="ml-8 space-y-1.5">
                      {testimonies.map((t) => (
                        <button
                          key={t.id}
                          onClick={() => handleWeaveStory(t.id)}
                          disabled={!!actionLoading}
                          className="w-full text-left text-xs px-2.5 py-1.5 bg-paper-200 hover:bg-seal-50 hover:text-seal-400 rounded border border-paper-300 transition-colors disabled:opacity-50"
                        >
                          {t.title}
                        </button>
                      ))}
                    </div>
                  )}
                  {actionLoading === 'weave' && <Loader2 size={14} className="animate-spin text-seal ml-8 mt-2" />}
                </div>

                <p className="folio pt-2">Check</p>

                <button
                  onClick={handleVoiceCheck}
                  disabled={!!actionLoading}
                  className="w-full card p-3 text-left hover:border-seal/50 flex items-start gap-3 disabled:opacity-50"
                >
                  <CheckCircle2 size={18} className="text-seal flex-shrink-0 mt-0.5" />
                  <div>
                    <h3 className="font-medium text-sm">Check My Voice</h3>
                    <p className="text-xs text-study-400">
                      {voiceCheck ? `Last check: ${Math.round(voiceCheck.score * 100)}%, ${voiceCheck.grade.toLowerCase()}.` : 'Score this chapter against your voice profile.'}
                    </p>
                  </div>
                  {actionLoading === 'voice-check' && <Loader2 size={14} className="animate-spin text-seal ml-auto" />}
                </button>

                {voiceCheck?.feedback && (
                  <div className="bg-seal-50 border border-seal-100 rounded-lg p-3 text-sm">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-medium text-seal-400">Voice Match: {Math.round(voiceCheck.score * 100)}%</span>
                      <span className="text-xs text-study-400">{voiceCheck.grade}</span>
                    </div>
                    <p className="text-study-400 text-xs">{voiceCheck.feedback}</p>
                    <div className="mt-3 pt-3 border-t border-seal-100 space-y-2 text-xs text-study-400">
                      <p><span className="font-medium text-seal-400">Cadence:</span> {voiceCheck.cadence_delta === undefined ? 'Run a fresh check to compare cadence.' : `${voiceCheck.cadence_delta >= 0 ? 'Slightly more flowing' : 'Slightly more punchy'} than your baseline`}</p>
                      {voiceCheck.phrase_matches && voiceCheck.phrase_matches.length > 0 && <p><span className="font-medium text-seal-400">Voice signals found:</span> {voiceCheck.phrase_matches.join(' · ')}</p>}
                      {voiceCheck.scripture_matches && voiceCheck.scripture_matches.length > 0 && <p><span className="font-medium text-seal-400">Anchor scriptures used:</span> {voiceCheck.scripture_matches.join(' · ')}</p>}
                      {voiceCheck.fiction_signals && (
                        <p title="Approximate — based on word counts in the narration">
                          <span className="font-medium text-seal-400">Narration (approx.):</span>{' '}
                          {voiceCheck.fiction_signals.pov} · {voiceCheck.fiction_signals.tense} tense · {Math.round(voiceCheck.fiction_signals.dialogue_ratio * 100)}% dialogue
                        </p>
                      )}
                      {(!voiceCheck.phrase_matches || voiceCheck.phrase_matches.length === 0) && (!voiceCheck.scripture_matches || voiceCheck.scripture_matches.length === 0) && <p>Check the chapter after adding more of your own language{pack.usesScripture ? ' or scripture anchors' : ''} to see evidence here.</p>}
                    </div>
                  </div>
                )}

                <ConsistencyCheck projectId={projectId!} chapterId={chapterId!} disabled={!!actionLoading} beforeCheck={saveBefore} />

                {pack.verifiesQuotes && (
                  <QuoteCheck projectId={projectId!} chapterId={chapterId!} disabled={!!actionLoading} beforeCheck={saveBefore} />
                )}

                {/* Scripture suggestions — only for packs with a verified scripture index */}
                {pack.usesScripture && (<>
                  <p className="folio pt-2">Find</p>

                  <button
                    onClick={handleScriptureSuggest}
                    disabled={!!actionLoading}
                    className="w-full card p-3 text-left hover:border-seal/50 flex items-start gap-3 disabled:opacity-50"
                  >
                    <BookOpen size={18} className="text-seal flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="font-medium text-sm">Suggest Scripture Anchor</h3>
                      <p className="text-xs text-study-400">Get verified scriptures fitting this passage.</p>
                    </div>
                    {actionLoading === 'scripture' && <Loader2 size={14} className="animate-spin text-seal ml-auto" />}
                  </button>

                  {scriptureSuggestions.length > 0 && (
                    <div className="space-y-2">
                      {scriptureSuggestions.map((s, i) => (
                        <div key={i} className="scripture-block py-2 px-3">
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-mono text-xs not-italic text-seal-400">{s.ref}</span>
                            <button onClick={() => insertScripture(s)} className="text-xs text-seal hover:underline not-italic">
                              Insert
                            </button>
                          </div>
                          <p className="text-sm">{s.text}</p>
                          {s.reason && <p className="text-xs text-study-400 not-italic mt-1">{s.reason}</p>}
                        </div>
                      ))}
                    </div>
                  )}
                </>)}
              </div>
            )}

            {/* Chat lives here as an always-available ask box */}
            <div className="p-4 border-t border-paper-300">
              <label htmlFor="scribe-ask" className="block text-xs text-study-400 mb-1.5">Ask about this chapter</label>
              <div className="flex gap-2">
                <input
                  id="scribe-ask"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !chatStreaming && handleChatSend()}
                  className="input-field flex-1 min-w-0 text-sm"
                  placeholder="What's missing from this chapter?"
                  disabled={chatStreaming}
                />
                <button onClick={handleChatSend} disabled={chatStreaming || !chatInput.trim()} className="btn-primary px-3 disabled:opacity-50" aria-label="Send">
                  <Send size={16} />
                </button>
              </div>
            </div>
          </>
        )}
      </aside>
    </div>
  )
}
