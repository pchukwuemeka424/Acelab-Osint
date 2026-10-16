type MarkProps = {
  size?: number
  className?: string
}

export function AceLogo({ size = 32, className }: MarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      className={className}
      role="img"
      aria-label="AceLab"
    >
      <rect width="32" height="32" rx="7" fill="#0A1628" />
      <path d="M6.25 10.25V6.25H10.25" stroke="#2EC4A8" strokeWidth="1.35" fill="none" />
      <path d="M25.75 10.25V6.25H21.75" stroke="#2EC4A8" strokeWidth="1.35" fill="none" />
      <path d="M6.25 21.75V25.75H10.25" stroke="#2EC4A8" strokeWidth="1.35" fill="none" />
      <path d="M25.75 21.75V25.75H21.75" stroke="#2EC4A8" strokeWidth="1.35" fill="none" />
      <path d="M16 8.1L22.85 24.1" stroke="#F4F7FB" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M16 8.1L9.15 24.1" stroke="#F4F7FB" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M11.45 17.15H20.55" stroke="#2EC4A8" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  )
}

export function AceWordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-semibold tracking-tight text-slate-900 ${className}`}>
      Ace<span className="text-teal-800">Lab</span>
    </span>
  )
}
