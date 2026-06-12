import { Link } from 'react-router-dom'
import { Feather, BookOpen, Sparkles, ScrollText, GitBranch, Target } from 'lucide-react'
import QuillLogo from '@/components/ui/QuillLogo'

const features = [
  {
    icon: Feather,
    title: 'Voice DNA',
    description: 'A structured interview captures your theological lens, signature phrases, cadence, and anchor scriptures — building a living profile of your voice.',
  },
  {
    icon: Sparkles,
    title: 'Live Voice Preview',
    description: 'Watch your voice come alive in real time as you answer onboarding questions. See exactly how The Scribe is learning to write like you.',
  },
  {
    icon: ScrollText,
    title: 'Testimony Vault',
    description: 'Store your personal stories and testimonies. The Scribe weaves them into your manuscript naturally — as revelation, not insertion.',
  },
  {
    icon: BookOpen,
    title: 'Manuscript Studio',
    description: 'Chapter-by-chapter editor with full chapter memory — your AI ghostwriter remembers what you said three chapters ago.',
  },
  {
    icon: Target,
    title: 'Voice Drift Scoring',
    description: 'Every generated passage is scored against your voice profile. Know instantly if something doesn\'t sound like you.',
  },
  {
    icon: GitBranch,
    title: 'Voice Evolution',
    description: 'Your voice profile evolves like a git history — track how your writing identity sharpens over time.',
  },
]

export default function Landing() {
  return (
    <div className="min-h-screen bg-ink-950 text-parchment overflow-x-hidden">
      {/* Nav */}
      <header className="border-b border-ink-700/50">
        <div className="max-w-6xl mx-auto px-6 py-5 flex items-center justify-between">
          <QuillLogo size="md" />
          <div className="flex items-center gap-3">
            <Link to="/login" className="btn-ghost text-sm">Log in</Link>
            <Link to="/signup" className="btn-gold text-sm">Get started</Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div className="absolute inset-0 bg-glow-gold pointer-events-none" />
        <div className="max-w-4xl mx-auto px-6 pt-24 pb-20 text-center relative">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-gold-700 bg-gold-800/40 text-gold-300 text-xs font-medium mb-8">
            <Sparkles size={14} />
            Built for apostolic, prophetic & Spirit-filled voices
          </div>
          <h1 className="font-display text-display-lg md:text-display-2xl font-semibold leading-tight mb-6">
            A ghostwriter who has
            <br />
            <span className="text-gold-400 italic">studied you for years.</span>
          </h1>
          <p className="text-lg text-ink-300 max-w-2xl mx-auto mb-10 leading-relaxed">
            The Scribe learns your theological voice — your phrases, your scriptures, your stories,
            your cadence — and ghostwrites your manuscript exactly as you would write it yourself.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link to="/signup" className="btn-gold px-8 py-3 text-base">
              Begin Your Voice Interview
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map(({ icon: Icon, title, description }) => (
            <div key={title} className="card p-6 animate-fade-in-up">
              <div className="w-10 h-10 rounded-lg bg-gold-800/60 flex items-center justify-center mb-4">
                <Icon size={20} className="text-gold-400" />
              </div>
              <h3 className="font-display text-display-xs font-semibold mb-2">{title}</h3>
              <p className="text-sm text-ink-300 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Scripture-style quote block */}
      <section className="max-w-3xl mx-auto px-6 pb-24">
        <div className="scripture-block text-lg md:text-xl">
          "And they overcame him by the blood of the Lamb and by the word of their testimony."
          <div className="text-sm text-gold-400 not-italic mt-2 font-body">— Revelation 12:11</div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-ink-700/50 py-8">
        <div className="max-w-6xl mx-auto px-6 text-center text-sm text-ink-400">
          The Scribe — built for those who carry a Word.
        </div>
      </footer>
    </div>
  )
}
