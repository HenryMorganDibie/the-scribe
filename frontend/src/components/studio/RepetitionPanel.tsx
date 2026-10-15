import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Copy, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface PassageRef {
  chapter_id: string
  chapter_number: number
  chapter_title: string
  excerpt: string
}

interface Pair {
  similarity: number
  a: PassageRef
  b: PassageRef
}

/** On-demand scan for passages that repeat across chapters (no AI call, no quota). */
export default function RepetitionPanel({ projectId }: { projectId: string }) {
  const [pairs, setPairs] = useState<Pair[] | null>(null)
  const [scanning, setScanning] = useState(false)

  const scan = async () => {
    setScanning(true)
    try {
      const res = await api.get(`/projects/${projectId}/repetition`)
      setPairs(res.data.pairs)
    } catch {
      setPairs([])
    } finally {
      setScanning(false)
    }
  }

  const Passage = ({ p }: { p: PassageRef }) => (
    <Link to={`/projects/${projectId}/chapters/${p.chapter_id}`} className="block rounded border border-paper-300 bg-paper-100 p-2 hover:border-seal-300">
      <p className="text-xs text-seal mb-1">Ch. {p.chapter_number}: {p.chapter_title}</p>
      <p className="text-xs text-study-400 line-clamp-4">{p.excerpt}</p>
    </Link>
  )

  return (
    <div className="card p-4 mb-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wide text-study-300 flex items-center gap-1.5"><Copy size={13} /> Repetition check</p>
          <p className="text-sm text-study-400 mt-1">Find passages that say nearly the same thing in different chapters.</p>
        </div>
        <button onClick={scan} disabled={scanning} className="btn-secondary text-sm flex items-center gap-2 flex-shrink-0 disabled:opacity-50">
          {scanning && <Loader2 size={14} className="animate-spin" />} {pairs ? 'Scan again' : 'Scan manuscript'}
        </button>
      </div>

      {pairs && (
        pairs.length === 0 ? (
          <p className="text-sm text-study-300 mt-3">No repeated passages found. (Chapters are checked once they've been saved.)</p>
        ) : (
          <div className="space-y-3 mt-3">
            {pairs.map((pair, i) => (
              <div key={i}>
                <p className="text-xs text-study-300 mb-1">{Math.round(pair.similarity * 100)}% similar</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <Passage p={pair.a} />
                  <Passage p={pair.b} />
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
