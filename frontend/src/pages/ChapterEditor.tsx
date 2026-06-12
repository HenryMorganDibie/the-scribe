import { useEffect, useState, useCallback, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import CharacterCount from '@tiptap/extension-character-count'
import {
  ArrowLeft, Sparkles, Wand2, BookOpen, ScrollText, CheckCircle2,
  Send, Loader2, Download, Save,
} from 'lucide-react'
import toast from 'react-hot-toast'
import { api, streamSSE } from '@/lib/api'

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
}

interface Testimony {
  id: string
  title: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

type SidebarTab = 'actions' | 'chat'

export default function ChapterEditor() {
  const { id: projectId, chapterId } = useParams<{ id: string; chapterId: string }>()
  const [chapter, setChapter] = useState<Chapter | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [testimonies, setTestimonies] = useState<Testimony[]>([])
  const [voiceCheck, setVoiceCheck] = useState<{ score: number; grade: string; feedback: string } | null>(null)
  const [scriptureSuggestions, setScriptureSuggestions] = useState<any[]>([])
  const [tab, setTab] = useState<SidebarTab>('actions')
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [chatInput, setChatInput] = useState('')
  const [chatStreaming, setChatStreaming] = useState(false)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout>>()

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Begin writing — or let The Scribe generate a first draft in your voice...' }),
      CharacterCount,
    ],
    content: '',
    editorProps: {
      attributes: {
        class: 'prose prose-invert prose-lg max-w-none focus:outline-none font-display leading-relaxed min-h-[60vh]',
      },
    },
    onUpdate: ({ editor }) => {
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, chapterId, editor])

  useEffect(() => {
    if (editor) load()
  }, [editor, load])

  const autoSave = async (content: string, wordCount: number) => {
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, { content, word_count: wordCount })
    } catch {
      // silent
    } finally {
      setSaving(false)
    }
  }

  const manualSave = async () => {
    if (!editor) return
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, {
        content: editor.getHTML(),
        word_count: editor.storage.characterCount.words(),
      })
      toast.success('Saved')
    } catch {
      toast.error('Save failed')
    } finally {
      setSaving(false)
    }
  }

  // ── Generate full chapter ──────────────────
  const handleGenerateChapter = async () => {
    if (!editor) return
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
          autoSave(editor.getHTML(), editor.storage.characterCount.words())
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

    let buffer = ''
    const startPos = editor.state.doc.content.size
    editor.commands.focus('end')

    try {
      await streamSSE(
        '/generate/continue',
        { chapter_id: chapterId, cursor_text: cursorText },
        (chunk) => {
          buffer += chunk
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
      setVoiceCheck(res.data)
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
        () => setChatStreaming(false)
      )
    } catch {
      setChatStreaming(false)
    }
  }

  const handleExportChapter = async () => {
    try {
      const res = await api.post(`/export/chapter/${chapterId}`, {}, { responseType: 'blob' })
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `chapter-${chapter?.chapter_number}-${chapter?.title.toLowerCase().replace(/\s+/g, '-')}.docx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch {
      toast.error('Export failed')
    }
  }

  if (loading || !chapter) return <div className="p-8 text-ink-400">Loading chapter...</div>

  const wordCount = editor?.storage.characterCount.words() || 0

  return (
    <div className="flex h-screen">
      {/* Editor */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-8">
          <Link to={`/projects/${projectId}`} className="text-sm text-ink-400 hover:text-gold-400 flex items-center gap-1 mb-4">
            <ArrowLeft size={14} /> Back to manuscript
          </Link>

          <div className="flex items-start justify-between mb-6">
            <div>
              <span className="text-xs text-ink-500 font-mono">Chapter {chapter.chapter_number}</span>
              <h1 className="font-display text-display-md font-semibold">{chapter.title}</h1>
              {chapter.intent && <p className="text-ink-400 mt-1 text-sm">{chapter.intent}</p>}
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <button onClick={handleExportChapter} className="btn-ghost text-sm flex items-center gap-1.5">
                <Download size={14} /> Export
              </button>
              <button onClick={manualSave} disabled={saving} className="btn-ghost text-sm flex items-center gap-1.5">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                {saving ? 'Saving' : 'Save'}
              </button>
            </div>
          </div>

          {(!chapter.content || chapter.content.length < 20) && !generating && (
            <button onClick={handleGenerateChapter} className="btn-gold w-full flex items-center justify-center gap-2 mb-6 py-3">
              <Sparkles size={18} /> Generate Chapter Draft in My Voice
            </button>
          )}

          {generating && (
            <div className="flex items-center gap-2 text-gold-400 text-sm mb-4 animate-pulse-gold">
              <Sparkles size={16} /> The Scribe is writing in your voice...
            </div>
          )}

          <div className="border-t border-ink-700 pt-6">
            <EditorContent editor={editor} />
          </div>

          <div className="mt-6 text-xs text-ink-500 flex items-center gap-4">
            <span>{wordCount} words</span>
            {voiceCheck && (
              <span className="flex items-center gap-1">
                <CheckCircle2 size={12} className="text-gold-400" />
                Voice match: {Math.round(voiceCheck.score * 100)}% ({voiceCheck.grade})
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Scribe AI Sidebar */}
      <div className="w-96 border-l border-ink-700 bg-ink-900/60 flex flex-col">
        <div className="p-4 border-b border-ink-700 flex items-center gap-2">
          <Sparkles size={18} className="text-gold-400" />
          <h2 className="font-display text-display-xs font-semibold">The Scribe</h2>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-ink-700">
          <button
            onClick={() => setTab('actions')}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === 'actions' ? 'text-gold-400 border-b-2 border-gold-400' : 'text-ink-400 hover:text-ink-200'}`}
          >
            Quick Actions
          </button>
          <button
            onClick={() => setTab('chat')}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${tab === 'chat' ? 'text-gold-400 border-b-2 border-gold-400' : 'text-ink-400 hover:text-ink-200'}`}
          >
            Chat
          </button>
        </div>

        {tab === 'actions' ? (
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Continue writing */}
            <button
              onClick={handleContinue}
              disabled={!!actionLoading || generating}
              className="w-full card p-3 text-left hover:border-gold-400/50 flex items-start gap-3 disabled:opacity-50"
            >
              <Wand2 size={18} className="text-gold-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-medium text-sm">Continue Writing</h3>
                <p className="text-xs text-ink-400">Pick up from where you left off, in your voice.</p>
              </div>
              {actionLoading === 'continue' && <Loader2 size={14} className="animate-spin text-gold-400 ml-auto" />}
            </button>

            {/* Voice check */}
            <button
              onClick={handleVoiceCheck}
              disabled={!!actionLoading}
              className="w-full card p-3 text-left hover:border-gold-400/50 flex items-start gap-3 disabled:opacity-50"
            >
              <CheckCircle2 size={18} className="text-gold-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-medium text-sm">Check My Voice</h3>
                <p className="text-xs text-ink-400">Score this chapter against your voice profile.</p>
              </div>
              {actionLoading === 'voice-check' && <Loader2 size={14} className="animate-spin text-gold-400 ml-auto" />}
            </button>

            {voiceCheck?.feedback && (
              <div className="bg-gold-800/20 border border-gold-700/40 rounded-lg p-3 text-sm">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-gold-300">Voice Match: {Math.round(voiceCheck.score * 100)}%</span>
                  <span className="text-xs text-ink-400">{voiceCheck.grade}</span>
                </div>
                <p className="text-ink-300 text-xs">{voiceCheck.feedback}</p>
              </div>
            )}

            {/* Weave story */}
            <div className="card p-3">
              <div className="flex items-start gap-3 mb-2">
                <ScrollText size={18} className="text-gold-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-medium text-sm">Weave In My Story</h3>
                  <p className="text-xs text-ink-400">Pull from your testimony vault.</p>
                </div>
              </div>
              {testimonies.length === 0 ? (
                <p className="text-xs text-ink-500 ml-8">
                  No testimonies yet — <Link to="/testimonies" className="text-gold-400 underline">add one</Link>
                </p>
              ) : (
                <div className="ml-8 space-y-1.5">
                  {testimonies.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => handleWeaveStory(t.id)}
                      disabled={!!actionLoading}
                      className="w-full text-left text-xs px-2.5 py-1.5 bg-ink-800 hover:bg-gold-800/30 hover:text-gold-300 rounded border border-ink-600 transition-colors disabled:opacity-50"
                    >
                      {t.title}
                    </button>
                  ))}
                </div>
              )}
              {actionLoading === 'weave' && <Loader2 size={14} className="animate-spin text-gold-400 ml-8 mt-2" />}
            </div>

            {/* Scripture suggestions */}
            <button
              onClick={handleScriptureSuggest}
              disabled={!!actionLoading}
              className="w-full card p-3 text-left hover:border-gold-400/50 flex items-start gap-3 disabled:opacity-50"
            >
              <BookOpen size={18} className="text-gold-400 flex-shrink-0 mt-0.5" />
              <div>
                <h3 className="font-medium text-sm">Suggest Scripture Anchor</h3>
                <p className="text-xs text-ink-400">Get verified scriptures fitting this passage.</p>
              </div>
              {actionLoading === 'scripture' && <Loader2 size={14} className="animate-spin text-gold-400 ml-auto" />}
            </button>

            {scriptureSuggestions.length > 0 && (
              <div className="space-y-2">
                {scriptureSuggestions.map((s, i) => (
                  <div key={i} className="scripture-block py-2 px-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-mono text-xs not-italic text-gold-300">{s.ref}</span>
                      <button onClick={() => insertScripture(s)} className="text-xs text-gold-400 hover:underline not-italic">
                        Insert
                      </button>
                    </div>
                    <p className="text-sm">{s.text}</p>
                    {s.reason && <p className="text-xs text-ink-400 not-italic mt-1">{s.reason}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {chatMessages.length === 0 && (
                <p className="text-sm text-ink-500 italic">
                  Ask The Scribe anything — "Make this more prophetic", "What's missing from this chapter?",
                  "Suggest a stronger opening hook"...
                </p>
              )}
              {chatMessages.map((m, i) => (
                <div key={i} className={`text-sm rounded-lg p-3 ${m.role === 'user' ? 'bg-ink-800 ml-6' : 'bg-gold-800/20 border border-gold-700/30 mr-6'}`}>
                  {m.content || (chatStreaming && i === chatMessages.length - 1 && <Loader2 size={14} className="animate-spin text-gold-400" />)}
                </div>
              ))}
            </div>
            <div className="p-4 border-t border-ink-700 flex gap-2">
              <input
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !chatStreaming && handleChatSend()}
                className="input-field flex-1 text-sm"
                placeholder="Ask The Scribe..."
                disabled={chatStreaming}
              />
              <button onClick={handleChatSend} disabled={chatStreaming || !chatInput.trim()} className="btn-gold px-3 disabled:opacity-50">
                <Send size={16} />
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
