import { Link } from 'react-router-dom'
import QuillLogo from '@/components/ui/QuillLogo'

const capabilities = [
  {
    label: 'Voice Interview',
    body: 'A structured conversation about your theological lens, your recurring phrases, the scriptures you return to, and the cadence of your sentences. Nothing generic — every answer becomes part of your profile.',
  },
  {
    label: 'Live Preview',
    body: "While you're still answering, The Scribe drafts a short passage in the voice it's learning. You see your own voice forming in real time, before onboarding even finishes.",
  },
  {
    label: 'Testimony Vault',
    body: 'Your personal stories, stored and indexed. When a chapter calls for a testimony, The Scribe retrieves the one that fits — and writes it in as revelation, not as a pasted anecdote.',
  },
  {
    label: 'Chapter Memory',
    body: "Every chapter is written with full awareness of what came before — the arguments you've made, the scriptures you've cited, the stories you've told — so the manuscript holds together as one voice.",
  },
  {
    label: 'Voice Match Scoring',
    body: 'Any passage can be checked against your profile. The Scribe tells you, plainly, where a paragraph drifts from how you actually write — and why.',
  },
  {
    label: 'Voice Evolution',
    body: 'Your profile is versioned. As you write and edit, The Scribe records what changed — new phrases, a shift in cadence — so your voice sharpens with use rather than staying fixed at onboarding.',
  },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-paper text-ink">
      {/* Header — like the running head of a printed page */}
      <header className="border-b border-paper-300">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center justify-between">
          <QuillLogo size="md" />
          <div className="flex items-center gap-6 text-sm">
            <Link to="/login" className="text-study-400 hover:text-seal transition-colors">Log in</Link>
            <Link to="/signup" className="btn-primary text-sm px-4 py-1.5">Begin the interview</Link>
          </div>
        </div>
      </header>

      {/* Title page */}
      <section className="max-w-3xl mx-auto px-6 pt-20 pb-16">
        <p className="folio mb-4">For apostolic, prophetic, and Spirit-filled writers</p>
        <h1 className="font-display text-display-lg md:text-display-2xl font-semibold leading-tight mb-6 max-w-2xl">
          Write the book only you could write — with a ghostwriter who studies how you write it.
        </h1>
        <p className="text-lg text-study-400 max-w-xl leading-relaxed mb-8">
          The Scribe is built around one idea: a generic AI cannot write your testimony, cite the
          scriptures you actually return to, or sound like the person standing behind your pulpit.
          So it doesn't try to. It learns your voice first — then writes in it.
        </p>
        <Link to="/signup" className="btn-primary inline-block px-6 py-2.5 text-base">
          Begin your voice interview
        </Link>
        <p className="text-sm text-study-300 mt-3">About 10 minutes. No manuscript required to start.</p>
      </section>

      {/* Scripture — set as a manuscript excerpt, not a hero quote card */}
      <section className="max-w-3xl mx-auto px-6 pb-16">
        <div className="card p-8">
          <p className="folio mb-3">Revelation 12:11 — NKJV</p>
          <blockquote className="font-manuscript text-xl leading-relaxed text-ink">
            "And they overcame him by the blood of the Lamb and by the word of their testimony,
            and they did not love their lives to the death."
          </blockquote>
        </div>
      </section>

      {/* Capabilities — set as a table of contents / annotated list, not icon cards */}
      <section className="max-w-3xl mx-auto px-6 pb-20">
        <h2 className="font-display text-display-sm font-semibold mb-2">What it does</h2>
        <p className="text-study-400 mb-8">Six parts of the system, in the order you'll meet them.</p>

        <div className="divide-y divide-paper-300">
          {capabilities.map((c, i) => (
            <div key={c.label} className="py-6 grid grid-cols-1 md:grid-cols-[3rem_10rem_1fr] gap-2 md:gap-6">
              <span className="folio">{String(i + 1).padStart(2, '0')}</span>
              <h3 className="font-display text-display-xs font-semibold">{c.label}</h3>
              <p className="text-study-400 leading-relaxed">{c.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-paper-300 py-8">
        <div className="max-w-3xl mx-auto px-6 flex items-center justify-between text-sm text-study-300">
          <span>The Scribe</span>
          <span>Built for those who carry a Word.</span>
        </div>
      </footer>
    </div>
  )
}
