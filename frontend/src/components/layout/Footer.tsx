const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const YEAR = new Date().getFullYear()

export function Footer() {
  return (
    <footer className="border-t border-border mt-auto">
      <div className="max-w-7xl mx-auto px-4 py-3 flex flex-col sm:flex-row items-center
        justify-between gap-2 text-[11px] uppercase tracking-wide text-foreground-subtle">
        <span>© {YEAR} Local AI Studio</span>
        <div className="flex items-center gap-4">
          <a
            href={`${API_BASE}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            Swagger
          </a>
          <a
            href={`${API_BASE}/redoc`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            ReDoc
          </a>
          <a
            href={`${API_BASE}/openapi.json`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-foreground transition-colors"
          >
            OpenAPI
          </a>
        </div>
      </div>
    </footer>
  )
}
