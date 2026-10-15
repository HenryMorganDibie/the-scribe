/** Chapter stages — mirrors STAGES in backend/app/services/progress.py (stored in chapters.status). */

export type Stage = 'draft' | 'in_progress' | 'revised' | 'complete'

export const STAGES: { id: Stage; label: string; className: string }[] = [
  { id: 'draft', label: 'Outline', className: 'status-draft' },
  { id: 'in_progress', label: 'Drafted', className: 'status-in_progress' },
  { id: 'revised', label: 'Revised', className: 'status-revised' },
  { id: 'complete', label: 'Done', className: 'status-complete' },
]

export function stageOf(status: string | undefined) {
  return STAGES.find((s) => s.id === status) ?? STAGES[0]
}
