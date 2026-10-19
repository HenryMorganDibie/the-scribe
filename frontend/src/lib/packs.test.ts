import { describe, expect, it } from 'vitest'
import { PACKS, cap, getPack } from './packs'

const CHRISTIAN_TERMS = /christian|scripture|bible|theolog|ministr|sermon|testimon|prophetic|\bgod\b|pulpit/i

describe('getPack', () => {
  it('falls back to general for missing or unknown ids', () => {
    expect(getPack(undefined).id).toBe('general')
    expect(getPack(null).id).toBe('general')
    expect(getPack('astrology').id).toBe('general')
    expect(getPack('christian').id).toBe('christian')
  })
})

describe('general pack', () => {
  const pack = PACKS.general

  it('uses neutral nav labels and no scripture tools', () => {
    expect(pack.nav).toEqual({ sources: 'Sources', stories: 'Stories', dna: 'Voice DNA' })
    expect(pack.usesScripture).toBe(false)
  })

  it('has no Christian wording anywhere in its interview', () => {
    for (const step of pack.steps) {
      const text = [step.question, step.subtext, step.placeholder, ...(step.options ?? [])].join(' ')
      expect(text, step.key).not.toMatch(CHRISTIAN_TERMS)
    }
  })

  it('asks about genre and style rules, not theology or translations', () => {
    const keys = pack.steps.map((s) => s.key)
    expect(keys).toContain('style_rules')
    expect(keys).not.toContain('preferred_translation')
    expect(keys).not.toContain('anchor_scriptures')
    expect(pack.steps.find((s) => s.key === 'theological_lens')?.question).toMatch(/kind of book/i)
  })
})

describe('fiction pack', () => {
  const pack = PACKS.fiction

  it('is selectable and has fiction tools, not non-fiction ones', () => {
    expect(getPack('fiction').id).toBe('fiction')
    expect(pack.isFiction).toBe(true)
    expect(pack.verifiesQuotes).toBe(false)
    expect(pack.usesScripture).toBe(false)
    expect(pack.section).toEqual({ singular: 'scene', plural: 'scenes' })
  })

  it('asks about point of view and tense, with no Christian wording', () => {
    expect(pack.steps.map((s) => s.key)).toContain('pov_tense')
    for (const step of pack.steps) {
      const text = [step.question, step.subtext, step.placeholder, ...(step.options ?? [])].join(' ')
      expect(text, step.key).not.toMatch(CHRISTIAN_TERMS)
    }
  })

  it('takes fiction out of the non-fiction pack', () => {
    const genres = PACKS.general.steps.find((s) => s.key === 'theological_lens')?.options ?? []
    expect(genres.some((g) => /fiction/i.test(g) && !/non-fiction/i.test(g))).toBe(false)
    expect(PACKS.general.verifiesQuotes).toBe(true)
  })
})

describe('christian pack', () => {
  it('keeps the original labels and interview for existing users', () => {
    const pack = PACKS.christian
    expect(pack.nav).toEqual({ sources: 'Sermons', stories: 'Testimonies', dna: 'Ministry DNA' })
    expect(pack.usesScripture).toBe(true)
    expect(pack.steps.map((s) => s.key)).toEqual([
      'ministry_background', 'theological_lens', 'target_audience', 'tone_preferences',
      'preferred_translation', 'signature_phrases', 'anchor_scriptures', 'writing_samples', 'personal_testimony',
    ])
  })
})

describe('cap', () => {
  it('capitalises the first letter', () => {
    expect(cap('sermon')).toBe('Sermon')
    expect(cap('')).toBe('')
  })
})
