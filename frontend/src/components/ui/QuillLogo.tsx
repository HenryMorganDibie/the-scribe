/**
 * Wordmark for The Scribe.
 * No glow, no gradient underline — a typeset mark, like an imprint on a title page.
 */
export default function QuillLogo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg'; animate?: boolean }) {
  const sizes = {
    sm: 'text-lg',
    md: 'text-xl',
    lg: 'text-3xl',
  }

  return (
    <span className={`font-display font-semibold tracking-tight ${sizes[size]}`}>
      The Scribe
    </span>
  )
}
