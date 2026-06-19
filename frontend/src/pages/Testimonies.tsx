import { useEffect, useState } from 'react'
import { Plus, ScrollText, Trash2, X } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Testimony {
  id: string
  title: string
  story: string
  themes: string[]
  created_at: string
  status: string
}

export default function Testimonies() {
  const [testimonies, setTestimonies] = useState<Testimony[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [story, setStory] = useState('')
  const [themesInput, setThemesInput] = useState('')
  const [suggestions, setSuggestions] = useState<Testimony[]>([])

  const load = () => {
    api.get('/testimonies', { params: { status: 'approved' } }).then((r) => setTestimonies(r.data)).finally(() => setLoading(false))
    api.get('/testimonies', { params: { status: 'suggested' } }).then((r) => setSuggestions(r.data))
  }

  const approveSuggestion = async (id: string) => {
    try {
      await api.post(`/testimonies/${id}/approve`)
      toast.success('Added to your vault')
      load()
    } catch {
      toast.error('Failed to approve')
    }
  }

  const dismissSuggestion = async (id: string) => {
    try {
      await api.delete(`/testimonies/${id}`)
      setSuggestions((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to dismiss')
    }
  }

  useEffect(load, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/testimonies', {
        title,
        story,
        themes: themesInput.split(',').map((t) => t.trim()).filter(Boolean),
      })
      toast.success('Testimony added to your vault')
      setTitle('')
      setStory('')
      setThemesInput('')
      setShowForm(false)
      load()
    } catch {
      toast.error('Failed to save testimony')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/testimonies/${id}`)
      setTestimonies((prev) => prev.filter((t) => t.id !== id))
      toast.success('Removed')
    } catch {
      toast.error('Failed to delete')
    }
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div className="flex items-center gap-3">
          <ScrollText size={24} className="text-seal" />
          <h1 className="font-display text-display-md font-semibold">Testimony Vault</h1>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary flex items-center gap-2">
          {showForm ? <X size={16} /> : <Plus size={16} />}
          {showForm ? 'Cancel' : 'Add Testimony'}
        </button>
      </div>

      <p className="text-study-300 mb-6">
        Personal stories that The Scribe can weave into your manuscripts — naturally, as revelation,
        retrieved exactly when relevant to a chapter's theme.
      </p>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-6 mb-6 space-y-4 animate-fade-in-up">
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Title</label>
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="input-field w-full"
              placeholder="The night God spoke through a dream"
            />
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Story</label>
            <textarea
              required
              value={story}
              onChange={(e) => setStory(e.target.value)}
              className="input-field w-full h-40 resize-none"
              placeholder="Tell the story in your own words..."
            />
          </div>
          <div>
            <label className="block text-sm text-study-400 mb-1.5">Themes (comma-separated)</label>
            <input
              value={themesInput}
              onChange={(e) => setThemesInput(e.target.value)}
              className="input-field w-full"
              placeholder="healing, faith, calling, perseverance"
            />
          </div>
          <button type="submit" className="btn-primary">Save to Vault</button>
        </form>
      )}

      {suggestions.length > 0 && (
        <div className="mb-8">
          <h2 className="font-display text-lg font-semibold mb-3">Suggested from your sermons</h2>
          <div className="space-y-3">
            {suggestions.map((t) => (
              <div key={t.id} className="card p-5 border-l-4 border-seal">
                <h3 className="font-display font-semibold mb-1">{t.title}</h3>
                <p className="text-study-400 text-sm leading-relaxed line-clamp-3 mb-3">{t.story}</p>
                <div className="flex gap-2">
                  <button onClick={() => approveSuggestion(t.id)} className="btn-primary text-sm px-3 py-1.5">Approve</button>
                  <button onClick={() => dismissSuggestion(t.id)} className="text-sm px-3 py-1.5 text-study-400 hover:text-red-400">Dismiss</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-study-300">Loading...</div>
      ) : testimonies.length === 0 ? (
        <div className="text-center py-16 text-study-300">
          Your vault is empty. Add your first testimony to start weaving your stories into your manuscripts.
        </div>
      ) : (
        <div className="space-y-4">
          {testimonies.map((t) => (
            <div key={t.id} className="card p-5">
              <div className="flex items-start justify-between mb-2">
                <h3 className="font-display text-lg font-semibold">{t.title}</h3>
                <button onClick={() => handleDelete(t.id)} className="text-ink0 hover:text-red-400">
                  <Trash2 size={16} />
                </button>
              </div>
              <p className="text-study-400 text-sm leading-relaxed line-clamp-3 mb-3">{t.story}</p>
              {t.themes && t.themes.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {t.themes.map((theme) => (
                    <span key={theme} className="text-xs bg-paper-200 text-study-400 rounded-full px-2.5 py-0.5">
                      {theme}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
