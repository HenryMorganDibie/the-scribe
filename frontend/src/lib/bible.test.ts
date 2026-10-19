import { describe, expect, it } from 'vitest'
import { ENTRY_KINDS, VERSION_REASONS, kindLabel } from './bible'

describe('book bible kinds', () => {
  it('matches the kinds the API accepts', () => {
    // backend/app/api/routes/book_bible.py — EntryKind
    expect(ENTRY_KINDS.map((k) => k.kind).sort()).toEqual(
      ['character', 'event', 'note', 'place', 'research', 'source', 'term'],
    )
  })

  it('labels kinds, falling back to the raw value', () => {
    expect(kindLabel('character')).toBe('Character')
    expect(kindLabel('mystery')).toBe('mystery')
  })
})

describe('version reasons', () => {
  it('has a label for every reason the API records', () => {
    // backend/app/services/chapter_versions.py + routes
    for (const reason of ['autosave', 'manual', 'before_ai', 'before_restore']) {
      expect(VERSION_REASONS[reason]).toBeTruthy()
    }
  })
})
