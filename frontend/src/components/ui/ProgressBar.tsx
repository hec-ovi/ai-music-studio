import { motion } from 'framer-motion'

interface ProgressBarProps {
  value: number        // 0–1
  label?: string
  showPercent?: boolean
  gradient?: boolean
  className?: string
}

export function ProgressBar({
  value,
  label,
  showPercent = false,
  gradient = false,
  className = '',
}: ProgressBarProps) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {(label || showPercent) && (
        <div className="flex items-center justify-between">
          {label && <span className="text-xs text-foreground-muted">{label}</span>}
          {showPercent && <span className="text-xs text-foreground-subtle font-mono">{pct}%</span>}
        </div>
      )}
      <div className="h-1 bg-surface-raised overflow-hidden border border-border">
        <motion.div
          className={`h-full ${
            gradient
              ? 'bg-gradient-to-r from-primary to-accent'
              : 'bg-primary'
          }`}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.4, ease: 'easeOut' }}
        />
      </div>
    </div>
  )
}
