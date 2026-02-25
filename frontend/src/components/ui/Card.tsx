import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  glow?: boolean
  hoverable?: boolean
}

export function Card({ children, className = '', glow = false, hoverable = false }: CardProps) {
  return (
    <div className={`
      bg-surface border border-border rounded-xl p-5
      ${glow ? 'glow-primary' : ''}
      ${hoverable ? 'hover:border-border-strong hover:bg-surface-raised transition-colors cursor-pointer' : ''}
      ${className}
    `}>
      {children}
    </div>
  )
}

interface CardHeaderProps {
  title: string
  description?: string
  action?: ReactNode
}

export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h3 className="font-semibold text-foreground">{title}</h3>
        {description && <p className="text-sm text-foreground-muted mt-0.5">{description}</p>}
      </div>
      {action}
    </div>
  )
}
