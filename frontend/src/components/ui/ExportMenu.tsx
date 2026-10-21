import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, Loader2 } from 'lucide-react'

type Format = 'docx' | 'pdf'

/** One "Export" button with a small menu, instead of a button per format. */
export default function ExportMenu({
  onExport,
  busy = false,
  iconOnly = false,
}: {
  onExport: (format: Format) => void | Promise<void>
  busy?: boolean
  iconOnly?: boolean
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !ref.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])

  const pick = (format: Format) => {
    setOpen(false)
    onExport(format)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={busy}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={iconOnly ? 'Export' : undefined}
        title={iconOnly ? 'Export' : undefined}
        className={iconOnly ? 'icon-btn' : 'btn-secondary flex items-center gap-2 text-sm'}
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
        {!iconOnly && <>{busy ? 'Exporting…' : 'Export'} <ChevronDown size={14} /></>}
      </button>
      {open && (
        <div role="menu" className="absolute right-0 top-full mt-1 z-20 w-52 card py-1 shadow-paper-lift animate-fade-in-up">
          <button role="menuitem" onClick={() => pick('docx')} className="menu-item">Word document (.docx)</button>
          <button role="menuitem" onClick={() => pick('pdf')} className="menu-item">PDF</button>
        </div>
      )}
    </div>
  )
}
