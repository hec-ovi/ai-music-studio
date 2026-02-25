import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'

type ThemePreference = 'system' | 'light' | 'dark'

const STORAGE_KEY = 'theme-preference'

function applyResolvedTheme(pref: ThemePreference) {
  const root = document.documentElement
  const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches
  const resolved = pref === 'system' ? (prefersLight ? 'light' : 'dark') : pref
  root.classList.toggle('light', resolved === 'light')
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemePreference>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored
    }
    return 'system'
  })

  useEffect(() => {
    applyResolvedTheme(theme)
    localStorage.setItem(STORAGE_KEY, theme)
  }, [theme])

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: light)')
    const onChange = () => {
      if (theme === 'system') {
        applyResolvedTheme(theme)
      }
    }
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [theme])

  return (
    <div
      role="group"
      aria-label="Theme selector"
      className="inline-flex border border-border"
    >
      {[
        { key: 'system', label: 'System' },
        { key: 'light', label: 'Light' },
        { key: 'dark', label: 'Dark' },
      ].map((option) => (
        <motion.button
          key={option.key}
          whileTap={{ scale: 0.98 }}
          type="button"
          onClick={() => setTheme(option.key as ThemePreference)}
          className={`px-2.5 py-1 text-[11px] tracking-wide uppercase transition-colors border-l border-border first:border-l-0 ${
            theme === option.key
              ? 'bg-surface-raised text-foreground'
              : 'text-foreground-subtle hover:text-foreground hover:bg-surface'
          }`}
        >
          {option.label}
        </motion.button>
      ))}
    </div>
  )
}
