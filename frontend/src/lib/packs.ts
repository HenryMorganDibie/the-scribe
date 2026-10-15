/**
 * Genre packs — frontend copy. Mirrors backend/app/services/packs.py.
 *
 * Routes and API field names stay as they are (/sermons, /testimonies,
 * theological_lens, anchor_scriptures...); a pack only changes what the
 * writer sees. Unknown or missing pack ids fall back to `general`.
 */

export type PackId = 'christian' | 'general'

export interface StepConfig {
  key: string
  question: string
  subtext: string
  type: 'text' | 'textarea' | 'select' | 'multiselect' | 'tags' | 'samples'
  options?: string[]
  placeholder?: string
  previewTrigger?: boolean // whether to refresh live preview after this step
}

export interface Pack {
  id: PackId
  name: string
  tagline: string
  nav: { sources: string; stories: string; dna: string }
  source: { singular: string; plural: string; hint: string }
  story: { singular: string; plural: string; vault: string }
  lensLabel: string
  rulesLabel: string
  referencesLabel: string
  usesScripture: boolean
  projectGenres: string[]
  steps: StepConfig[]
}

const CHRISTIAN_STEPS: StepConfig[] = [
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
    subtext: 'This goes into your Testimony Vault — The Scribe will weave it into your manuscript when it fits.',
    type: 'textarea',
    placeholder: 'There was a season when I was in the wilderness, and God spoke to me through...',
  },
]

const GENERAL_STEPS: StepConfig[] = [
  {
    key: 'theological_lens',
    question: 'What kind of book are you writing?',
    subtext: 'This shapes how The Scribe structures and frames every chapter.',
    type: 'select',
    options: ['Fiction', 'Memoir', 'Business / Professional', 'Self-help / Personal growth', 'Academic / Research', 'Other non-fiction'],
    previewTrigger: true,
  },
  {
    key: 'ministry_background',
    question: 'Tell us about yourself as a writer.',
    subtext: 'Your background, expertise, and what you bring to this book.',
    type: 'textarea',
    placeholder: 'I have run a design studio for ten years and teach workshops on...',
  },
  {
    key: 'target_audience',
    question: 'Who are you writing for?',
    subtext: 'Describe your ideal reader — what they want, what they already know, what they struggle with.',
    type: 'textarea',
    placeholder: 'First-time managers who were promoted for their technical skill and now...',
  },
  {
    key: 'tone_preferences',
    question: 'What tones define your writing?',
    subtext: 'Select all that resonate. Order matters — most important first.',
    type: 'multiselect',
    options: ['Instructive', 'Conversational', 'Narrative / Storytelling', 'Persuasive', 'Reflective', 'Humorous', 'Formal / Academic'],
    previewTrigger: true,
  },
  {
    key: 'signature_phrases',
    question: 'What are some phrases you say or write often?',
    subtext: 'Things you find yourself repeating — your verbal fingerprints. One per line.',
    type: 'tags',
    placeholder: 'e.g. "Here\'s the thing"\ne.g. "Let that sink in"\ne.g. "In other words"',
    previewTrigger: true,
  },
  {
    key: 'style_rules',
    question: 'Any style rules The Scribe should always follow?',
    subtext: 'House rules for your book — one per line. Skip-worthy only if you truly have none.',
    type: 'tags',
    placeholder: 'e.g. British spelling\ne.g. Present tense, first person\ne.g. Define every technical term',
  },
  {
    key: 'writing_samples',
    question: 'Paste a sample of your writing.',
    subtext: 'A chapter draft, a blog post, a talk transcript — anything in your authentic voice. The more, the better.',
    type: 'samples',
    placeholder: 'Paste your writing sample here...',
    previewTrigger: true,
  },
  {
    key: 'personal_testimony',
    question: 'Share one story you might tell in this book.',
    subtext: 'An anecdote, a case study, a turning point. The Scribe will weave stories like this in when they fit.',
    type: 'textarea',
    placeholder: 'The week our biggest client walked away, I learned...',
  },
]

export const PACKS: Record<PackId, Pack> = {
  christian: {
    id: 'christian',
    name: 'Christian writing',
    tagline: 'Sermons, teaching, devotionals — with verified scripture.',
    nav: { sources: 'Sermons', stories: 'Testimonies', dna: 'Ministry DNA' },
    source: { singular: 'sermon', plural: 'sermons', hint: 'Upload sermons (PDF, DOCX, audio) or paste a transcript.' },
    story: { singular: 'testimony', plural: 'testimonies', vault: 'Testimony Vault' },
    lensLabel: 'Theological Lens',
    rulesLabel: 'Theological Guardrails',
    referencesLabel: 'Anchor Scriptures',
    usesScripture: true,
    projectGenres: ['teaching', 'devotional', 'prophetic', 'memoir'],
    steps: CHRISTIAN_STEPS,
  },
  general: {
    id: 'general',
    name: 'Any other book',
    tagline: 'Fiction, memoir, business, academic, self-help and more.',
    nav: { sources: 'Sources', stories: 'Stories', dna: 'Voice DNA' },
    source: {
      singular: 'source',
      plural: 'sources',
      hint: 'Upload talks, lectures, interviews or drafts (PDF, DOCX, audio) or paste a transcript.',
    },
    story: { singular: 'story', plural: 'stories', vault: 'Story Bank' },
    lensLabel: 'Genre',
    rulesLabel: 'Style Rules',
    referencesLabel: 'Key References',
    usesScripture: false,
    projectGenres: ['non-fiction', 'fiction', 'memoir', 'business', 'self-help', 'academic'],
    steps: GENERAL_STEPS,
  },
}

export function getPack(id: string | null | undefined): Pack {
  return id === 'christian' || id === 'general' ? PACKS[id] : PACKS.general
}

/** Capitalise the first letter: "sermon" → "Sermon". */
export function cap(word: string) {
  return word.charAt(0).toUpperCase() + word.slice(1)
}
