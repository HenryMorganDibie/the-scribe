import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, Quote } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface QuoteResult {
  quote: string
  status: 'verified' | 'close' | 'not_found'
  source_title: string | null
  source_excerpt: string | null
}

interface Props {
  projectId: string
  chapterId: string
  disabled?: boolean
  /** Save the editor first so the check reads the latest text. */
  beforeCheck: () => Promise<void>
}

const STATUS = {
  verified: { label: 'Verified', className: 'text-study-700 bg-study-50 border-study-300' },
  close: { label: 'Wording differs', className: 'text-seal-500 bg-seal-50 border-seal-200' },
  not_found: { label: 'No source found', className: 'text-red-700 bg-red-50 border-red-200' },
}

/** Non-fiction: check each quotation against the book's sources (free, no AI). */
export default function QuoteCheck({ projectId, chapterId, disabled, beforeCheck }: Props) {
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<{ checked_sources: number; quotes: QuoteResult[] } | null>(null)

  const run = async () => {
    setChecking(true)
    try {
      await beforeCheck()
      const res = await api.post(`/projects/${projectId}/chapters/${chapterId}/verify-quotes`)
      setResult(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Quote check failed')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="card p-3">
      <button onClick={run} disabled={disabled || checking} className="w-full text-left flex items-start gap-3 disabled:opacity-50">
        <Quote size={18} className="text-seal flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-medium text-sm">Verify Quotes</h3>
          <p className="text-xs text-study-300">Check quotations against this book's sources.</p>
        </div>
        {checking && <Loader2 size={14} className="animate-spin text-seal ml-auto" />}
      </button>

      {result && (
        <div className="mt-3 ml-8 space-y-2 text-xs">
          {result.quotes.length === 0 ? (
            <p className="text-study-300">No quotations of six words or more in this chapter.</p>
          ) : (
            <>
              {result.checked_sources === 0 && (
                <p className="text-study-300">
                  No sources to check against yet — link sources to this book or add Source entries to the{' '}
                  <Link to={`/projects/${projectId}/bible`} className="text-seal underline">book bible</Link>.
                </p>
              )}
              {result.quotes.map((q, i) => (
                <div key={i} className="border border-paper-300 rounded p-2">
                  <span className={`inline-block border rounded-sm px-1.5 py-0.5 mb-1 ${STATUS[q.status].className}`}>{STATUS[q.status].label}</span>
                  <p className="italic text-study-400">“{q.quote}”</p>
                  {q.source_title && <p className="text-study-300 mt-1">Source: {q.source_title}</p>}
                  {q.status === 'close' && q.source_excerpt && (
                    <p className="text-study-400 mt-1">The source says: “…{q.source_excerpt}…”</p>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}
