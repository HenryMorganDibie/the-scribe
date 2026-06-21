import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, Activity, TrendingUp, TrendingDown, Minus, BookOpen } from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { api } from '@/lib/api'

interface TimelinePoint {
  date: string
  score: number
  chapter_id?: string
}

interface ChapterBreakdown {
  chapter_id: string
  project_id: string
  chapter_number: number
  chapter_title: string
  voice_match_score: number
}

interface DriftAnalytics {
  has_data: boolean
  message?: string
  timeline: TimelinePoint[]
  average_score: number | null
  trend: 'improving' | 'declining' | 'stable' | null
  total_checks?: number
  chapter_breakdown: ChapterBreakdown[]
}

const trendCopy: Record<string, { label: string; icon: typeof TrendingUp; color: string }> = {
  improving: { label: 'Trending toward your voice', icon: TrendingUp, color: 'text-green-700' },
  declining: { label: 'Drifting from your voice', icon: TrendingDown, color: 'text-seal' },
  stable: { label: 'Holding steady', icon: Minus, color: 'text-study-300' },
}

function gradeLabel(score: number) {
  if (score >= 0.9) return 'Excellent'
  if (score >= 0.8) return 'Strong'
  if (score >= 0.7) return 'Good'
  return 'Needs work'
}

export default function VoiceDriftAnalytics() {
  const [data, setData] = useState<DriftAnalytics | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/voice-profile/drift-analytics')
      .then((r) => setData(r.data))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-study-300">Loading drift analytics...</div>
  if (!data) return <div className="p-8 text-study-300">Couldn't load analytics.</div>

  const chartData = data.timeline.map((t, i) => ({
    check: `#${i + 1}`,
    score: Math.round(t.score * 100),
    date: new Date(t.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  }))

  const barData = data.chapter_breakdown.map((c) => ({
    chapter: `Ch. ${c.chapter_number}`,
    title: c.chapter_title,
    score: Math.round(c.voice_match_score * 100),
    chapter_id: c.chapter_id,
  }))

  const TrendIcon = data.trend ? trendCopy[data.trend].icon : null

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <Link to="/voice-profile" className="text-sm text-study-300 hover:text-seal flex items-center gap-1 mb-4">
        <ArrowLeft size={14} /> Back to Voice DNA
      </Link>

      <div className="flex items-center gap-3 mb-2">
        <Activity size={24} className="text-seal" />
        <h1 className="font-display text-display-md font-semibold">Voice Drift Analytics</h1>
      </div>
      <p className="text-study-300 mb-8">
        How closely generated content has matched your cadence, scripture usage, and signature phrases
        over every "Check My Voice" run.
      </p>

      {!data.has_data ? (
        <div className="bg-seal-50 border border-seal-100 rounded-lg p-6 text-seal-500">
          {data.message}
        </div>
      ) : (
        <>
          {/* Summary cards */}
          <div className="grid md:grid-cols-3 gap-4 mb-8">
            <div className="card p-5">
              <p className="text-xs text-study-300 uppercase tracking-wide mb-1">Average match</p>
              <p className="font-display text-display-sm font-semibold text-seal">
                {Math.round((data.average_score ?? 0) * 100)}%
              </p>
              <p className="text-xs text-study-300 mt-1">{gradeLabel(data.average_score ?? 0)}</p>
            </div>
            <div className="card p-5">
              <p className="text-xs text-study-300 uppercase tracking-wide mb-1">Total checks</p>
              <p className="font-display text-display-sm font-semibold">{data.total_checks}</p>
              <p className="text-xs text-study-300 mt-1">across all chapters</p>
            </div>
            <div className="card p-5">
              <p className="text-xs text-study-300 uppercase tracking-wide mb-1">Trend</p>
              {data.trend && TrendIcon ? (
                <div className={`flex items-center gap-1.5 ${trendCopy[data.trend].color}`}>
                  <TrendIcon size={20} />
                  <span className="font-display text-lg font-semibold">{trendCopy[data.trend].label}</span>
                </div>
              ) : (
                <p className="text-study-300 text-sm mt-1">Need a few more checks to tell</p>
              )}
            </div>
          </div>

          {/* Score over time */}
          {chartData.length > 1 && (
            <div className="card p-5 mb-6">
              <h3 className="font-display font-semibold mb-3">Voice match over time</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={chartData}>
                  <XAxis dataKey="check" stroke="#8a8175" fontSize={12} />
                  <YAxis stroke="#8a8175" fontSize={12} domain={[0, 100]} unit="%" />
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Voice match']}
                    labelFormatter={(label, payload) => payload?.[0]?.payload?.date || label}
                  />
                  <ReferenceLine y={75} stroke="#C8BCA3" strokeDasharray="4 4" />
                  <Line type="monotone" dataKey="score" stroke="#9a3412" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
              <p className="text-xs text-study-300 mt-2">
                Dashed line marks 75% — the threshold below which The Scribe offers specific feedback.
              </p>
            </div>
          )}

          {/* Per-chapter breakdown */}
          {barData.length > 0 && (
            <div className="card p-5">
              <h3 className="font-display font-semibold mb-1">By chapter</h3>
              <p className="text-xs text-study-300 mb-3">Latest voice match score recorded per chapter.</p>
              <ResponsiveContainer width="100%" height={Math.max(180, barData.length * 44)}>
                <BarChart data={barData} layout="vertical" margin={{ left: 16 }}>
                  <XAxis type="number" domain={[0, 100]} stroke="#8a8175" fontSize={12} unit="%" />
                  <YAxis type="category" dataKey="chapter" stroke="#8a8175" fontSize={12} width={60} />
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Voice match']}
                    labelFormatter={(_, payload) => payload?.[0]?.payload?.title || ''}
                  />
                  <Bar dataKey="score" fill="#9a3412" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap gap-2 mt-4">
                {data.chapter_breakdown.map((c) => (
                  <Link
                    key={c.chapter_id}
                    to={`/projects/${c.project_id}/chapters/${c.chapter_id}`}
                    className="inline-flex items-center gap-1 text-xs text-study-300 hover:text-seal transition-colors"
                  >
                    <BookOpen size={11} />
                    Ch. {c.chapter_number}: {c.chapter_title}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
