import { ThemeToggle } from '../ui/ThemeToggle'
import { ProgressBar } from '../ui/ProgressBar'
import type { View } from '../../stores/navigation.store'
import { useAlbumStore } from '../../stores/album.store'

interface HeaderProps {
  onNavigate: (view: View) => void
  currentView: View
}

export function Header({ onNavigate, currentView }: HeaderProps) {
  const phase = useAlbumStore((s) => s.phase)
  const progress = useAlbumStore((s) => s.progress)
  const message = useAlbumStore((s) => s.message)
  const albumName = useAlbumStore((s) => s.albumName)
  const showProgress = !['idle', 'complete', 'error'].includes(phase)

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/92 backdrop-blur-sm">
      <nav className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
        <button
          onClick={() => onNavigate('home')}
          className="flex items-center gap-3"
          aria-label="Studio home"
        >
          <div className="w-7 h-7 border border-border-strong bg-surface-raised flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="text-foreground-muted">
              <path d="M9 18V5l12-2v13" />
              <circle cx="6" cy="18" r="3" />
              <circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <span className="text-sm tracking-wide uppercase text-foreground-muted hidden sm:block">
            Studio
          </span>
        </button>

        <div className="flex items-center gap-1">
          <NavLink
            label="Create"
            active={currentView === 'home'}
            onClick={() => onNavigate('home')}
          />
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />
          <a
            href="http://localhost:8000/redoc"
            target="_blank"
            rel="noopener noreferrer"
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 text-[11px] uppercase tracking-wide text-foreground-subtle
              hover:text-foreground border border-border hover:border-border-strong transition-colors"
            aria-label="API documentation"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
            API Docs
          </a>
        </div>
      </nav>

      {showProgress && (
        <div className="border-t border-border bg-surface/50">
          <div className="max-w-7xl mx-auto px-4 py-2 flex items-center gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">
                {albumName ? `${albumName} · ${phaseLabel(phase)}` : phaseLabel(phase)}
              </p>
              {message && (
                <p className="text-xs text-foreground-muted truncate">{message}</p>
              )}
            </div>
            <ProgressBar value={progress} showPercent className="w-44 shrink-0" gradient={false} />
          </div>
        </div>
      )}
    </header>
  )
}

interface NavLinkProps {
  label: string
  active: boolean
  onClick: () => void
}

function NavLink({ label, active, onClick }: NavLinkProps) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-xs uppercase tracking-wide border transition-colors ${
        active
          ? 'bg-surface-raised border-border-strong text-foreground'
          : 'text-foreground-muted border-transparent hover:text-foreground hover:border-border'
      }`}
    >
      {label}
    </button>
  )
}

function phaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    planning: 'Planning',
    review: 'Review',
    cover: 'Cover',
    music: 'Music',
    complete: 'Complete',
    error: 'Error',
    idle: 'Idle',
  }
  return labels[phase] ?? 'Working'
}
