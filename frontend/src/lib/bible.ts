/** Book bible entry kinds — mirrors backend/app/services/book_bible.py. */

export type EntryKind = 'character' | 'place' | 'term' | 'event' | 'source' | 'note' | 'research'

export interface BookEntry {
  id: string
  kind: EntryKind
  title: string
  body: string
  chapter_id: string | null
  when_label: string | null
  timeline_order: number | null
  created_at: string
  updated_at: string
}

export const ENTRY_KINDS: { kind: EntryKind; label: string; plural: string; hint: string }[] = [
  { kind: 'character', label: 'Character', plural: 'Characters', hint: 'People in the book — who they are, how they speak, what they want.' },
  { kind: 'place', label: 'Place', plural: 'Places', hint: 'Settings and locations, with the details that must stay consistent.' },
  { kind: 'term', label: 'Term', plural: 'Terms', hint: 'Names, concepts and vocabulary the book defines or relies on.' },
  { kind: 'event', label: 'Timeline event', plural: 'Timeline', hint: 'What happens when. The Scribe always sees the whole timeline, in order, and never reorders it.' },
  { kind: 'source', label: 'Source', plural: 'Sources', hint: 'Books, articles, interviews and quotes you are drawing on.' },
  { kind: 'research', label: 'Research', plural: 'Research', hint: 'Facts, findings and clippings to ground the writing.' },
  { kind: 'note', label: 'Note', plural: 'Notes', hint: 'Anything else: plans, reminders, ideas for later chapters.' },
]

export function kindLabel(kind: string) {
  return ENTRY_KINDS.find((k) => k.kind === kind)?.label ?? kind
}

/** Human labels for chapter version reasons. */
export const VERSION_REASONS: Record<string, string> = {
  autosave: 'While writing',
  manual: 'Saved',
  before_ai: 'Before AI draft',
  before_restore: 'Before restore',
}

/** Plain-text preview of stored chapter HTML (never injected as HTML). */
export function htmlToText(html: string) {
  const doc = new DOMParser().parseFromString(html, 'text/html')
  doc.querySelectorAll('p, br, h1, h2, h3, li, blockquote').forEach((el) => el.append('\n'))
  return (doc.body.textContent ?? '').replace(/\n{3,}/g, '\n\n').trim()
}
