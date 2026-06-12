import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, ChevronLeft, Sparkles, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import QuillLogo from '@/components/ui/QuillLogo'
import { api, streamSSE } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

interface StepConfig {
  key: string
  question: string
  subtext: string
  type: 'text' | 'textarea' | 'select' | 'multiselect' | 'tags' | 'samples'
  options?: string[]
  placeholder?: string
  previewTrigger?: boolean // whether to refresh live preview after this step
}

const STEPS: StepConfig[] = [
  {
    key: 'ministry_background',
    question: 'Tell us about your ministry background.',
    subtext: 'Where do you preach, teach, or minister? What is your spiritual journey?',
    type: 'textarea',
    placeholder: 'I have pastored for 12 years, focused on prophetic ministry and discipleship...',
  },
  {
    key: 'theological_lens',
    question: 'Which best describes your theological lens?',
    subtext: 'This shapes how The Scribe frames every generation.',
    type: 'select',
    options: ['Apostolic', 'Prophetic', 'Spirit-filled / Charismatic', 'Pentecostal', 'Word of Faith'],
    previewTrigger: true,
  },
  {
    key: 'target_audience',
    question: 'Who are you writing for?',
    subtext: 'Describe your ideal reader — their struggles, their hunger, their stage of faith.',
    type: 'textarea',
    placeholder: 'Believers who feel called but unsure of their purpose, often discouraged by...',
  },
  {
    key: 'tone_preferences',
    question: 'What tones define your writing?',
    subtext: 'Select all that resonate. Order matters — most important first.',
    type: 'multiselect',
    options: ['Teaching', 'Exhortation', 'Narrative / Storytelling', 'Devotional', 'Prophetic Declaration', 'Apologetic'],
    previewTrigger: true,
  },
  {
    key: 'preferred_translation',
    question: 'Which Bible translation do you primarily use?',
    subtext: 'The Scribe will cite scriptures in this translation.',
    type: 'select',
    options: ['NKJV', 'KJV', 'NIV', 'ESV', 'NLT', 'AMP'],
  },
  {
    key: 'signature_phrases',
    question: 'What are some phrases you say or write often?',
    subtext: 'Things you find yourself repeating — your verbal fingerprints. One per line.',
    type: 'tags',
    placeholder: 'e.g. "This is your set time"\ne.g. "Let that sink in"\ne.g. "Can I be honest with you?"',
    previewTrigger: true,
  },
  {
    key: 'anchor_scriptures',
    question: 'Which scriptures do you return to again and again?',
    subtext: 'Your anchor scriptures — the ones that shape your message. One reference per line.',
    type: 'tags',
    placeholder: 'e.g. Isaiah 61:1-3\ne.g. Jeremiah 29:11\ne.g. Joel 2:28-29',
    previewTrigger: true,
  },
  {
    key: 'writing_samples',
    question: 'Paste a sample of your writing.',
    subtext: 'A sermon transcript, a devotional, a social post — anything in your authentic voice. The more, the better.',
    type: 'samples',
    placeholder: 'Paste your writing sample here...',
    previewTrigger: true,
  },
  {
    key: 'personal_testimony',
    question: 'Share one personal testimony or story.',
    subtext: "This goes into your Testimony Vault — The Scribe will weave it into your manuscript when it fits.",
    type: 'textarea',
    placeholder: 'There was a season when I was in the wilderness, and God spoke to me through...',
  },
]

export default function Onboarding() {
  const [stepIndex, setStepIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<string, any>>({
    tone_preferences: [],
    signature_phrases: [],
    anchor_scriptures: [],
    writing_samples: [],
  })
  const [tagInput, setTagInput] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [preview, setPreview] = useState('')
  const [previewLoading, setPreviewLoading] = useState(false)
  const navigate = useNavigate()
  const { fetchMe } = useAuthStore()

  const step = STEPS[stepIndex]
  const progress = ((stepIndex + 1) / STEPS.length) * 100
  const previewAbortRef = useRef<boolean>(false)

  const currentValue = answers[step.key]

  const isStepValid = () => {
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
        await api.post('/onboarding/complete', { data: answers })
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

  // Trigger initial preview after first preview-eligible step
  useEffect(() => {
    if (stepIndex === 1 && answers.theological_lens) {
      // Triggered via handleNext already
    }
  }, [stepIndex])

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
              <div className="text-ink0 text-sm italic">
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

          <div className="mt-4 text-xs text-ink0">
            This preview updates as you complete key sections of the interview.
          </div>
        </div>
      </div>
    </div>
  )
}
