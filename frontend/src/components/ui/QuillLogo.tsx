export default function QuillLogo({ size = 'md', animate = true }: { size?: 'sm' | 'md' | 'lg'; animate?: boolean }) {
  const sizes = {
    sm: 'text-xl',
    md: 'text-2xl',
    lg: 'text-4xl',
  }

  return (
    <div className="inline-flex flex-col items-start group">
      <span className={`font-display font-semibold text-parchment ${sizes[size]} tracking-tight`}>
        The Scribe
      </span>
      <svg
        viewBox="0 0 100 8"
        className="w-full h-1.5 -mt-0.5"
        preserveAspectRatio="none"
      >
        <path
          d="M2,5 Q 25,1 50,4 T 98,3"
          fill="none"
          stroke="#C9A84C"
          strokeWidth="1.5"
          strokeLinecap="round"
          className={animate ? 'quill-underline animate' : 'quill-underline'}
          style={{ strokeDashoffset: animate ? undefined : 0 }}
        />
      </svg>
    </div>
  )
}
