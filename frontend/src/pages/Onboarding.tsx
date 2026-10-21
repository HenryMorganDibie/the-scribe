import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronLeft, Sparkles, Loader2, BookOpen, PenLine, Feather } from 'lucide-react'
import toast from 'react-hot-toast'
import QuillLogo from '@/components/ui/QuillLogo'
import { api, streamSSE } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { PACKS, PACK_CHOICES, type PackId } from '@/lib/packs'

export default function Onboarding() {
  const [packId, setPackId] = useState<PackId | null>(null)
  const [chosenPath, setChosenPath] = useState(false)
  const [stepIndex, setStepIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, any>>({
    tone_preferences: [],
    signature_phrases: [],
    anchor_scriptures: [],
    style_rules: [],
    writing_samples: [],
  })
  const [tagInput, setTagInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [preview, setPreview] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const navigate = useNavigate()
  const { fetchMe } = useAuthStore()

  const pack = PACKS[packId ?? 'general']
  const STEPS = pack.steps
  const step = STEPS[stepIndex]
  const progress = ((stepIndex + 1) / STEPS.length) * 100
  const previewAbortRef = useRef<boolean>(false)

  const currentValue = answers[step.key]

  const choosePack = async (id: PackId) => {
    setPackId(id)
    try {
      await api.put('/onboarding/step', { step: 0, field: 'pack', value: id })
    } catch {
      // non-blocking — the pack is sent again when onboarding completes
    }
  }

  const startWithSources = async () => {
    setSubmitting(true)
    try {
      await api.post('/onboarding/complete', {
        data: {
          pack: pack.id,
          theological_lens: pack.usesScripture ? 'To be learned from my sermons' : undefined,
          preferred_translation: pack.usesScripture ? 'NKJV' : undefined,
          tone_preferences: [],
          writing_samples: [],
          signature_phrases: [],
          anchor_scriptures: [],
        },
      })
      await fetchMe()
      toast.success(`Upload your ${pack.source.plural} and The Scribe will begin learning your voice.`)
      navigate('/sermons')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || `Unable to start ${pack.source.singular}-first setup`)
      setSubmitting(false)
    }
  }

  const isStepValid = () => {
    if (step.key === 'style_rules') return true // optional
    if (step.type === 'multiselect' || step.type === 'tags' || step.type === 'samples') {
      return Array.isArray(currentValue) && currentValue.length > 0
    }
    return currentValue && String(currentValue).trim().length > 0
  }

  const saveStep = async (field: string, value: any) => {
    try {
      await api.put('/onboarding/step', { step: stepIndex, field, value })
    } catch {
      // non-blocking
    }
  }

  const refreshPreview = async () => {
    previewAbortRef.current = false
    setPreviewLoading(true)
    setPreview('')
    try {
      await streamSSE(
        '/onboarding/preview',
        {},
        (chunk) => {
          if (!previewAbortRef.current) setPreview((prev) => prev + chunk)
        },
        () => setPreviewLoading(false),
        () => setPreviewLoading(false)
      )
    } catch {
      setPreviewLoading(false)
    }
  }

  const handleNext = async () => {
    await saveStep(step.key, currentValue)

    if (step.previewTrigger) {
      refreshPreview()
    }

    if (stepIndex < STEPS.length - 1) {
      setStepIndex(stepIndex + 1)
      setTagInput('')
    } else {
      // Final step — complete onboarding
      setSubmitting(true)
      try {
        await api.post('/onboarding/complete', { data: { ...answers, pack: pack.id } })
        await fetchMe()
        toast.success('Your Voice DNA is being woven together...')
        navigate('/dashboard')
      } catch (err: any) {
        toast.error(err.response?.data?.detail || 'Something went wrong')
        setSubmitting(false)
      }
    }
  }

  const handleBack = () => {
    previewAbortRef.current = true
    if (stepIndex > 0) setStepIndex(stepIndex - 1)
  }

  const updateAnswer = (value: any) => {
    setAnswers((prev) => ({ ...prev, [step.key]: value }))
  }

  const addTag = () => {
    if (!tagInput.trim()) return
    const lines = tagInput.split('\n').map((l) => l.trim()).filter(Boolean)
    updateAnswer([...(currentValue || []), ...lines])
    setTagInput('')
  }

  const removeTag = (idx: number) => {
    const updated = [...currentValue]
    updated.splice(idx, 1)
    updateAnswer(updated)
  }

  if (!packId) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-3xl">
          <div className="mb-10"><QuillLogo size="lg" animate={false} /></div>
          <p className="text-seal text-sm font-medium mb-2">Start your first manuscript</p>
          <h1 className="font-display text-display-md font-semibold mb-3">What are you writing?</h1>
          <p className="text-study-300 mb-8 max-w-2xl">This tailors the interview and the tools you'll see. You can change it later from your voice profile.</p>
          <div className="grid md:grid-cols-3 gap-5">
            {PACK_CHOICES.map((option) => (
              <button key={option.id} onClick={() => choosePack(option.id)} className="card p-6 text-left hover:border-seal transition-colors">
                {option.usesScripture ? <BookOpen size={24} className="text-seal mb-4" /> : option.isFiction ? <Feather size={24} className="text-seal mb-4" /> : <PenLine size={24} className="text-seal mb-4" />}
                <h2 className="font-display text-xl font-semibold mb-2">{option.name}</h2>
                <p className="text-sm text-study-300">{option.tagline}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  if (!chosenPath) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-3xl">
          <div className="mb-10"><QuillLogo size="lg" animate={false} /></div>
          <button onClick={() => setPackId(null)} className="btn-ghost text-sm flex items-center gap-1 mb-6">
            <ChevronLeft size={16} /> {pack.name}
          </button>
          <h1 className="font-display text-display-md font-semibold mb-3">How would you like The Scribe to learn your voice?</h1>
          <p className="text-study-300 mb-8 max-w-2xl">Choose the fastest path now. You can always enrich your profile later.</p>
          <div className="grid md:grid-cols-2 gap-5">
            <button onClick={startWithSources} disabled={submitting} className="card p-6 text-left hover:border-seal transition-colors disabled:opacity-50">
              <Sparkles size={24} className="text-seal mb-4" />
              <h2 className="font-display text-xl font-semibold mb-2">I have {pack.source.plural}</h2>
              <p className="text-sm text-study-300 mb-4">
                Upload completed {pack.source.plural} first. The Scribe will learn your recurring language
                {pack.usesScripture ? ', scriptures,' : ''} and stories, then help turn them into a book.
              </p>
              <span className="text-sm text-seal font-medium flex items-center gap-2">{submitting ? <Loader2 size={15} className="animate-spin" /> : null} Start with {pack.source.plural}</span>
            </button>
            <button onClick={() => setChosenPath(true)} className="card p-6 text-left hover:border-seal transition-colors">
              <ChevronRight size={24} className="text-seal mb-4" />
              <h2 className="font-display text-xl font-semibold mb-2">Interview me</h2>
              <p className="text-sm text-study-300 mb-4">
                {pack.usesScripture
                  ? 'Share your ministry background, style, signature phrases, scriptures, and writing samples in a guided interview.'
                  : 'Share your genre, audience, style, signature phrases, and writing samples in a guided interview.'}
              </p>
              <span className="text-sm text-seal font-medium">Begin voice interview</span>
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      {/* Header */}
      <header className="border-b border-paper-300 px-6 py-4 flex items-center justify-between">
        <QuillLogo size="sm" animate={false} />
        <span className="text-sm text-study-300">
          Step {stepIndex + 1} of {STEPS.length}
        </span>
      </header>

      {/* Progress bar */}
      <div className="h-1 bg-paper-200">
        <div
          className="h-full bg-seal transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-5">
        {/* Question panel */}
        <div className="lg:col-span-3 flex items-center justify-center px-6 py-12">
          <div className="w-full max-w-xl animate-fade-in-up" key={stepIndex}>
            <h1 className="font-display text-display-sm font-semibold mb-2">{step.question}</h1>
            <p className="text-study-300 mb-6">{step.subtext}</p>

            {step.type === 'text' && (
              <input
                type="text"
                value={currentValue || ''}
                onChange={(e) => updateAnswer(e.target.value)}
                className="input-field w-full"
                placeholder={step.placeholder}
                autoFocus
              />
            )}

            {step.type === 'textarea' && (
              <textarea
                value={currentValue || ''}
                onChange={(e) => updateAnswer(e.target.value)}
                className="input-field w-full h-40 resize-none"
                placeholder={step.placeholder}
                autoFocus
              />
            )}

            {step.type === 'select' && (
              <div className="space-y-2">
                {step.options!.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => updateAnswer(opt)}
                    className={`w-full text-left px-4 py-3 rounded-lg border transition-colors ${
                      currentValue === opt
                        ? 'border-seal bg-seal-50 text-seal-400'
                        : 'border-paper-300 hover:border-study-200 text-study-400'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}

            {step.type === 'multiselect' && (
              <div className="space-y-2">
                {step.options!.map((opt) => {
                  const selected = (currentValue || []).includes(opt)
                  return (
                    <button
                      key={opt}
                      onClick={() => {
                        const list = currentValue || []
                        updateAnswer(selected ? list.filter((o: string) => o !== opt) : [...list, opt])
                      }}
                      className={`w-full text-left px-4 py-3 rounded-lg border transition-colors flex items-center justify-between ${
                        selected
                          ? 'border-seal bg-seal-50 text-seal-400'
                          : 'border-paper-300 hover:border-study-200 text-study-400'
                      }`}
                    >
                      {opt}
                      {selected && (
                        <span className="text-xs text-seal">
                          #{(currentValue || []).indexOf(opt) + 1}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            )}

            {(step.type === 'tags' || step.type === 'samples') && (
              <div>
                <textarea
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  className={`input-field w-full resize-none ${step.type === 'samples' ? 'h-48' : 'h-24'}`}
                  placeholder={step.placeholder}
                  autoFocus
                />
                <button onClick={addTag} className="btn-ghost text-sm mt-2">
                  Add {step.type === 'samples' ? 'sample' : 'items'}
                </button>

                {currentValue && currentValue.length > 0 && (
                  <div className={step.type === 'samples' ? 'mt-3 space-y-2' : 'mt-3 flex flex-wrap gap-2'}>
                    {currentValue.map((item: string, idx: number) => (
                      <div
                        key={idx}
                        className={
                          step.type === 'samples'
                            ? 'bg-paper-100 border border-paper-300 rounded-lg p-3 text-sm text-study-400 flex justify-between items-start gap-2'
                            : 'bg-seal-50 border border-seal-300 text-seal-500 text-sm rounded-full px-3 py-1 flex items-center gap-2'
                        }
                      >
                        <span className={step.type === 'samples' ? 'line-clamp-3' : ''}>
                          {step.type === 'samples' ? `${item.slice(0, 200)}${item.length > 200 ? '...' : ''}` : item}
                        </span>
                        <button onClick={() => removeTag(idx)} className="text-study-300 hover:text-red-400 flex-shrink-0">
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Navigation */}
            <div className="flex items-center justify-between mt-8">
              <button
                onClick={handleBack}
                disabled={stepIndex === 0}
                className="btn-ghost text-sm flex items-center gap-1 disabled:opacity-30"
              >
                <ChevronLeft size={16} /> Back
              </button>
              <button
                onClick={handleNext}
                disabled={!isStepValid() || submitting}
                className="btn-primary flex items-center gap-1 disabled:opacity-50"
              >
                {submitting ? (
                  <>
                    <Loader2 size={16} className="animate-spin" /> Finalizing...
                  </>
                ) : stepIndex === STEPS.length - 1 ? (
                  'Complete Voice Interview'
                ) : (
                  <>
                    Next <ChevronRight size={16} />
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Live Voice Preview panel */}
        <div className="lg:col-span-2 bg-paper-200 border-l border-paper-300 px-6 py-12 flex flex-col">
          <div className="flex items-center gap-2 mb-4">
            <Sparkles size={18} className="text-seal" />
            <h2 className="font-display text-display-xs font-semibold">Live Voice Preview</h2>
          </div>
          <p className="text-sm text-study-300 mb-6">
            As you answer, watch The Scribe begin to write in your emerging voice.
          </p>

          <div className="flex-1 card p-5 relative overflow-hidden">
            {previewLoading && !preview && (
              <div className="flex items-center gap-2 text-study-300 text-sm">
                <Loader2 size={16} className="animate-spin text-seal" />
                Listening to your voice...
              </div>
            )}

            {!preview && !previewLoading && (
              <div className="text-study-400 text-sm italic">
                Your preview will appear here once you've shared a bit more about your voice —
                keep going.
              </div>
            )}

            {preview && (
              <p className="font-display text-lg leading-relaxed text-ink italic animate-fade-in-up">
                {preview}
                {previewLoading && <span className="inline-block w-2 h-4 bg-seal ml-1 animate-pulse" />}
              </p>
            )}
          </div>

          <div className="mt-4 text-xs text-study-400">
            This preview updates as you complete key sections of the interview.
          </div>
        </div>
      </div>
    </div>
  )
}
