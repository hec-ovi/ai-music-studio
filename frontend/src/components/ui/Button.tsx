import { motion } from 'framer-motion'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: ReactNode
  children: ReactNode
}

const variantClasses: Record<Variant, string> = {
  primary: 'bg-primary text-white border border-primary hover:bg-primary-hover disabled:opacity-50',
  secondary: 'bg-surface-raised text-foreground border border-border hover:border-border-strong hover:bg-surface-overlay',
  ghost: 'text-foreground-muted border border-transparent hover:text-foreground hover:border-border hover:bg-surface',
  danger: 'bg-error/10 text-error border border-error/35 hover:bg-error/18',
}

const sizeClasses: Record<Size, string> = {
  sm: 'px-2.5 py-1 text-xs gap-1.5 uppercase tracking-wide',
  md: 'px-3 py-1.5 text-xs gap-2 uppercase tracking-wide',
  lg: 'px-4 py-2 text-sm gap-2 uppercase tracking-wide',
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  return (
    <motion.button
      whileTap={{ scale: 0.98 }}
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center font-medium rounded-none
        transition-colors cursor-pointer select-none
        disabled:cursor-not-allowed
        ${variantClasses[variant]}
        ${sizeClasses[size]}
        ${className}
      `}
      {...(props as any)}
    >
      {loading ? <Spinner size={size === 'lg' ? 'md' : 'sm'} /> : icon}
      {children}
    </motion.button>
  )
}

function Spinner({ size }: { size: 'sm' | 'md' }) {
  const s = size === 'sm' ? 14 : 16
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" className="animate-spin">
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.2" />
      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  )
}
