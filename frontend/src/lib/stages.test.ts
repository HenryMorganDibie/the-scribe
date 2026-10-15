import { describe, expect, it } from 'vitest'
import { STAGES, stageOf } from './stages'

describe('chapter stages', () => {
  it('matches the statuses the API accepts, in order', () => {
    // backend/app/services/progress.py — STAGES
    expect(STAGES.map((s) => s.id)).toEqual(['draft', 'in_progress', 'revised', 'complete'])
    expect(STAGES.map((s) => s.label)).toEqual(['Outline', 'Drafted', 'Revised', 'Done'])
  })

  it('treats unknown or missing statuses as Outline', () => {
    expect(stageOf('revised').label).toBe('Revised')
    expect(stageOf('mystery').id).toBe('draft')
    expect(stageOf(undefined).id).toBe('draft')
  })
})
