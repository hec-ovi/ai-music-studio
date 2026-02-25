import type { InputHTMLAttributes, TextareaHTMLAttributes, ReactNode } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
  icon?: ReactNode
}

export function Input({ label, error, hint, icon, className = '', ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-foreground-muted">{label}</label>
      )}
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-foreground-subtle">
            {icon}
          </div>
        )}
        <input
          className={`
            w-full bg-surface-raised border rounded-none px-3 py-2 text-sm text-foreground
            placeholder:text-foreground-subtle
            focus:outline-none focus:border-primary
            transition-colors
            ${error ? 'border-error focus:border-error' : 'border-border'}
            ${icon ? 'pl-10' : ''}
            ${className}
          `}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-error">{error}</p>}
      {hint && !error && <p className="text-xs text-foreground-subtle">{hint}</p>}
    </div>
  )
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
  hint?: string
}

export function Textarea({ label, error, hint, className = '', ...props }: TextareaProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label className="text-sm font-medium text-foreground-muted">{label}</label>
      )}
      <textarea
        className={`
          w-full bg-surface-raised border rounded-none px-3 py-2 text-sm text-foreground
          placeholder:text-foreground-subtle resize-none
          focus:outline-none focus:border-primary
          transition-colors
          ${error ? 'border-error focus:border-error' : 'border-border'}
          ${className}
        `}
        {...props}
      />
      {error && <p className="text-xs text-error">{error}</p>}
      {hint && !error && <p className="text-xs text-foreground-subtle">{hint}</p>}
    </div>
  )
}
