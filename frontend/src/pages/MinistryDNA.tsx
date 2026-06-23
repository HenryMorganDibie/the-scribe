import { useEffect, useState } from 'react'
import { Fingerprint } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { api } from '@/lib/api'

interface DnaReport {
  metrics: {
    top_scriptures: { ref: string; count: number }[]
    top_phrases: { phrase: string; count: number }[]
    top_themes: { theme: string; count: number }[]
    ministry_focus: string
    timeline: { version: number; cadence_score: number | null; phrase_count: number | null; scripture_count: number | null }[]
  }
  narrative: string
  sermon_count: number
}

function RankedList({ title, items }: { title: string; items: { label: string; count: number }[] }) {
  return (
    <div className="card p-5">
      <h3 className="font-display font-semibold mb-3">{title}</h3>
      {items.length === 0 ? (
        <p className="text-study-300 text-sm">Nothing yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((it) => (
            <li key={it.label} className="flex justify-between text-sm">
              <span className="text-study-400">{it.label}</span>
              <span className="text-seal font-medium">{it.count}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function MinistryDNA() {
  const [report, setReport] = useState<DnaReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/voice/dna-report').then((r) => setReport(r.data)).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-study-300">Loading…</div>
  if (!report) return <div className="p-8 text-study-300">No report available yet.</div>

  const { metrics, narrative, sermon_count } = report

  return (
    <div className="px-4 py-6 md:p-8 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Fingerprint size={24} className="text-seal" />
        <h1 className="font-display text-display-md font-semibold">Ministry DNA</h1>
      </div>

      <div className="card p-6 mb-6">
        <p className="text-sm text-study-300 mb-1">Based on {sermon_count} ingested sermon(s)</p>
        <p className="font-display text-lg mb-3">{metrics.ministry_focus}</p>
        <p className="text-study-400 leading-relaxed">{narrative}</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <RankedList title="Most-quoted scriptures" items={metrics.top_scriptures.map((s) => ({ label: s.ref, count: s.count }))} />
        <RankedList title="Most-used phrases" items={metrics.top_phrases.map((p) => ({ label: p.phrase, count: p.count }))} />
        <RankedList title="Recurring themes" items={metrics.top_themes.map((t) => ({ label: t.theme, count: t.count }))} />
      </div>

      {metrics.timeline.length > 1 && (
        <div className="card p-5">
          <h3 className="font-display font-semibold mb-3">Voice over time</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={metrics.timeline}>
              <XAxis dataKey="version" stroke="#8a8175" fontSize={12} />
              <YAxis stroke="#8a8175" fontSize={12} />
              <Tooltip />
              <Line type="monotone" dataKey="phrase_count" stroke="#9a3412" strokeWidth={2} dot />
              <Line type="monotone" dataKey="scripture_count" stroke="#1E1E1E" strokeWidth={2} dot />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
