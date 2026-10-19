import { useState } from 'react'
import { ArrowDown, ArrowUp, ListOrdered, Loader2, Plus, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'
import { cap } from '@/lib/packs'
import { usePack } from '@/stores/authStore'

export interface Scene {
  title: string
  summary: string
  pov: string
  setting: string
}

interface Props {
  projectId: string
  chapterId: string
  intent?: string | null
  keyPoints?: string[] | null
  scenes?: Scene[] | null
  onSaved: (update: { intent: string; key_points: string[]; scenes: Scene[] }) => void
}

const blankScene = (): Scene => ({ title: '', summary: '', pov: '', setting: '' })

/** The chapter brief (intent, key points) and its ordered scene/section plan. */
export default function PlanPanel({ projectId, chapterId, intent, keyPoints, scenes, onSaved }: Props) {
  const pack = usePack()
  const noun = pack.section
  const [draftIntent, setDraftIntent] = useState(intent ?? '')
  const [draftPoints, setDraftPoints] = useState((keyPoints ?? []).join('\n'))
  const [draftScenes, setDraftScenes] = useState<Scene[]>(scenes?.length ? scenes.map((s) => ({ ...blankScene(), ...s })) : [])
  const [saving, setSaving] = useState(false)

  const updateScene = (i: number, patch: Partial<Scene>) =>
    setDraftScenes((list) => list.map((s, j) => (j === i ? { ...s, ...patch } : s)))

  const move = (i: number, by: number) =>
    setDraftScenes((list) => {
      const next = [...list]
      const [item] = next.splice(i, 1)
      next.splice(Math.min(Math.max(i + by, 0), next.length), 0, item)
      return next
    })

  const save = async () => {
    const cleanScenes = draftScenes.filter((s) => s.title.trim()).map((s) => ({
      title: s.title.trim(), summary: s.summary.trim(), pov: s.pov.trim(), setting: s.setting.trim(),
    }))
    const update = {
      intent: draftIntent.trim(),
      key_points: draftPoints.split('\n').map((p) => p.trim()).filter(Boolean),
      scenes: cleanScenes,
    }
    setSaving(true)
    try {
      await api.put(`/projects/${projectId}/chapters/${chapterId}`, update)
      setDraftScenes(cleanScenes)
      onSaved(update)
      toast.success('Plan saved')
    } catch (err: any) {
      const detail = err.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : 'Save failed — check the plan for very long fields')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      <p className="text-xs text-study-300 flex items-start gap-2">
        <ListOrdered size={14} className="mt-0.5 flex-shrink-0" />
        The plan The Scribe follows when it drafts this chapter.
      </p>

      <div>
        <label className="block text-xs text-study-400 mb-1">Intent — what this chapter must accomplish</label>
        <textarea value={draftIntent} onChange={(e) => setDraftIntent(e.target.value)} maxLength={4000} className="input-field w-full h-20 resize-none text-sm" />
      </div>
      <div>
        <label className="block text-xs text-study-400 mb-1">Key points (one per line)</label>
        <textarea value={draftPoints} onChange={(e) => setDraftPoints(e.target.value)} className="input-field w-full h-20 resize-none text-sm" />
      </div>

      <div className="space-y-2">
        <p className="text-xs text-study-400">{cap(noun.plural)}, in order</p>
        {draftScenes.length === 0 && (
          <p className="text-xs text-ink0 italic">
            No {noun.plural} planned. Add them to have the draft follow your structure{pack.isFiction ? ', with a point of view and setting for each' : ''}.
          </p>
        )}
        {draftScenes.map((scene, i) => (
          <div key={i} className="card p-2.5 space-y-1.5">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-mono text-study-300 w-5">{i + 1}.</span>
              <input value={scene.title} onChange={(e) => updateScene(i, { title: e.target.value })} maxLength={200} className="input-field flex-1 text-sm py-1" placeholder={`${cap(noun.singular)} title`} />
              <button onClick={() => move(i, -1)} disabled={i === 0} className="text-study-300 hover:text-seal disabled:opacity-30" aria-label="Move up"><ArrowUp size={14} /></button>
              <button onClick={() => move(i, 1)} disabled={i === draftScenes.length - 1} className="text-study-300 hover:text-seal disabled:opacity-30" aria-label="Move down"><ArrowDown size={14} /></button>
              <button onClick={() => setDraftScenes((list) => list.filter((_, j) => j !== i))} className="text-study-300 hover:text-red-400" aria-label={`Remove ${noun.singular}`}><Trash2 size={14} /></button>
            </div>
            <textarea value={scene.summary} onChange={(e) => updateScene(i, { summary: e.target.value })} maxLength={2000} className="input-field w-full h-14 resize-none text-xs" placeholder={pack.isFiction ? 'What happens, and what changes' : 'What this section covers'} />
            {pack.isFiction && (
              <div className="grid grid-cols-2 gap-1.5">
                <input value={scene.pov} onChange={(e) => updateScene(i, { pov: e.target.value })} maxLength={120} className="input-field text-xs py-1" placeholder="POV character" />
                <input value={scene.setting} onChange={(e) => updateScene(i, { setting: e.target.value })} maxLength={200} className="input-field text-xs py-1" placeholder="Setting" />
              </div>
            )}
          </div>
        ))}
        <button onClick={() => setDraftScenes((list) => [...list, blankScene()])} disabled={draftScenes.length >= 40} className="btn-ghost text-sm flex items-center gap-1 disabled:opacity-50">
          <Plus size={14} /> Add {noun.singular}
        </button>
      </div>

      <button onClick={save} disabled={saving} className="btn-primary text-sm w-full flex items-center justify-center gap-2 disabled:opacity-50">
        {saving && <Loader2 size={14} className="animate-spin" />} Save plan
      </button>
    </div>
  )
}
