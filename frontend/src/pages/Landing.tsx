import { Link } from 'react-router-dom'
import QuillLogo from '@/components/ui/QuillLogo'

const capabilities = [
  {
    label: 'Voice Interview',
    body: 'A short, structured conversation about your genre, your reader, your recurring phrases and the rhythm of your sentences — or skip it and let The Scribe learn from talks and drafts you already have.',
  },
  {
    label: 'One Workspace per Book',
    body: 'Every manuscript keeps its own chapters, outline, sources and stories in one place, so the AI always works from your whole book — not from whatever fits in a single prompt.',
  },
  {
    label: 'Chapter Memory',
    body: "Every chapter is drafted with full awareness of what came before — the arguments you've made, the stories you've told, the references you've used — so the book holds together as one voice.",
  },
  {
    label: 'Manuscript Companion',
    body: 'Ask questions about your own book. "Have I covered this already?" "Which chapter introduces this idea?" "Am I repeating myself?" — answered from the manuscript, with the chapters cited.',
  },
  {
    label: 'Sources & Stories',
    body: 'Upload talks, lectures, interviews and drafts. The Scribe transcribes them, learns your voice from them, and pulls out the stories worth telling — ready to weave in when a chapter needs one.',
  },
  {
    label: 'Voice Check',
    body: "Any passage can be checked against your profile. The Scribe tells you, plainly, where a paragraph drifts from how you actually write — so the finished book still sounds like you.",
  },
]

const writers = [
  { label: 'Non-fiction & business', body: 'Turn your expertise, talks and client stories into a structured book.' },
  { label: 'Memoir', body: 'Keep years of memories, people and turning points straight across every chapter.' },
  { label: 'Fiction', body: 'Draft in your voice with every chapter aware of the story so far.' },
  { label: 'Academic & research', body: 'Shape a long argument chapter by chapter without losing the thread.' },
  { label: 'Christian writing', body: 'Sermons into books, with every scripture verified against a real index.' },
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
            <Link to="/signup" className="btn-primary text-sm px-4 py-1.5">Start your book</Link>
          </div>
        </div>
      </header>

      {/* Title page */}
      <section className="max-w-3xl mx-auto px-6 pt-20 pb-16">
        <p className="folio mb-4">An AI workspace for writing a book</p>
        <h1 className="font-display text-display-lg md:text-display-2xl font-semibold leading-tight mb-6 max-w-2xl">
          Most books aren't abandoned for lack of words. They're abandoned halfway.
        </h1>
        <p className="text-lg text-study-400 max-w-xl leading-relaxed mb-8">
          The Scribe gives every book its own workspace — chapters, sources, stories, style and
          progress — and an AI that has read all of it. It learns how you write, remembers what
          you've already said, and helps you get from first chapter to finished manuscript.
        </p>
        <Link to="/signup" className="btn-primary inline-block px-6 py-2.5 text-base">
          Start your book
        </Link>
        <p className="text-sm text-study-300 mt-3">About 10 minutes to set up. No manuscript required to start.</p>
      </section>

      {/* The promise — set as a manuscript excerpt, not a hero quote card */}
      <section className="max-w-3xl mx-auto px-6 pb-16">
        <div className="card p-8">
          <p className="folio mb-3">The difference</p>
          <p className="font-manuscript text-xl leading-relaxed text-ink">
            A chatbot writes a chapter and forgets it. The Scribe writes chapter nine knowing what you
            argued in chapter two, which story you've already told, and how your sentences sound —
            because it's your book's workspace, not a blank prompt.
          </p>
        </div>
      </section>

      {/* Capabilities — set as a table of contents / annotated list, not icon cards */}
      <section className="max-w-3xl mx-auto px-6 pb-16">
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

      {/* Who it's for */}
      <section className="max-w-3xl mx-auto px-6 pb-20">
        <h2 className="font-display text-display-sm font-semibold mb-2">Who it's for</h2>
        <p className="text-study-400 mb-8">Anyone with a book in progress — or one they keep meaning to start.</p>

        <div className="grid gap-x-8 gap-y-6 md:grid-cols-2">
          {writers.map((w) => (
            <div key={w.label}>
              <h3 className="font-display text-display-xs font-semibold mb-1">{w.label}</h3>
              <p className="text-study-400 leading-relaxed">{w.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-paper-300 py-8">
        <div className="max-w-3xl mx-auto px-6 flex items-center justify-between text-sm text-study-300">
          <span>The Scribe</span>
          <span>Built to help you finish.</span>
        </div>
      </footer>
    </div>
  )
}
