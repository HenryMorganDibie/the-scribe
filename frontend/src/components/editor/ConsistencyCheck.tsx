import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Loader2, ShieldCheck } from 'lucide-react'
import toast from 'react-hot-toast'
import { api } from '@/lib/api'

interface Issue {
  entry: string
  quote: string
  issue: string
}

interface Props {
  projectId: string
  chapterId: string
  disabled?: boolean
  /** Save the editor first so the check reads the latest text. */
  beforeCheck: () => Promise<void>
}

/** Checks the saved chapter against the book bible (one AI request). */
export default function ConsistencyCheck({ projectId, chapterId, disabled, beforeCheck }: Props) {
  const [checking, setChecking] = useState(false)
  const [result, setResult] = useState<{ checked_entries: number; issues: Issue[] } | null>(null)

  const run = async () => {
    setChecking(true)
    try {
      await beforeCheck()
      const res = await api.post(`/projects/${projectId}/chapters/${chapterId}/consistency-check`)
      setResult(res.data)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Consistency check failed')
    } finally {
      setChecking(false)
    }
  }

  return (
    <div className="card p-3">
      <button onClick={run} disabled={disabled || checking} className="w-full text-left flex items-start gap-3 disabled:opacity-50">
        <ShieldCheck size={18} className="text-seal flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-medium text-sm">Check Consistency</h3>
          <p className="text-xs text-study-300">Compare this chapter with your book bible.</p>
        </div>
        {checking && <Loader2 size={14} className="animate-spin text-seal ml-auto" />}
      </button>

      {result && (
        <div className="mt-3 ml-8 space-y-2 text-xs">
          {result.checked_entries === 0 ? (
            <p className="text-study-300">
              Nothing to check against yet — add characters, places and facts to the{' '}
              <Link to={`/projects/${projectId}/bible`} className="text-seal underline">book bible</Link>.
            </p>
          ) : result.issues.length === 0 ? (
            <p className="text-study-400">No contradictions found against {result.checked_entries} relevant {result.checked_entries === 1 ? 'entry' : 'entries'}.</p>
          ) : (
            result.issues.map((issue, i) => (
              <div key={i} className="bg-seal-50 border border-seal-100 rounded p-2">
                <p className="font-medium text-seal-400">{issue.entry}</p>
                <p className="italic text-study-400 my-1">“{issue.quote}”</p>
                <p className="text-study-400">{issue.issue}</p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
