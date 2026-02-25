import { useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { useAlbumStore } from '../../stores/album.store'
import { useNavigationStore } from '../../stores/navigation.store'
import { albumService } from '../../services/album.service'
import type { SongPlanDisplay, SongResult } from '../../types/album'

export function GenerationProgress() {
  const phase = useAlbumStore((s) => s.phase)
  const message = useAlbumStore((s) => s.message)
  const albumName = useAlbumStore((s) => s.albumName)
  const albumDescription = useAlbumStore((s) => s.albumDescription)
  const plannedSongs = useAlbumStore((s) => s.plannedSongs)
  const coverUrl = useAlbumStore((s) => s.coverUrl)
  const coverSkipped = useAlbumStore((s) => s.coverSkipped)
  const completedSongs = useAlbumStore((s) => s.completedSongs)
  const currentSongIndex = useAlbumStore((s) => s.currentSongIndex)
  const error = useAlbumStore((s) => s.error)
  const reset = useAlbumStore((s) => s.reset)
  const setView = useNavigationStore((s) => s.setView)
  const [activeSongIndex, setActiveSongIndex] = useState<number | null>(null)

  const completedSongsByIndex = useMemo(() => {
    const byIndex = new Map<number, SongResult>()
    completedSongs.forEach((song) => byIndex.set(song.index, song))
    return byIndex
  }, [completedSongs])

  const handleStartOver = () => {
    reset()
    setView('home')
  }

  if (phase === 'error') {
    return <ErrorView message={error ?? 'Unknown error'} onRetry={handleStartOver} />
  }

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 xl:grid-cols-[360px_1fr] gap-4">
      <aside className="border border-border bg-surface p-4 space-y-4 h-fit">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-foreground-subtle">Status</p>
          <h2 className="mt-1 text-sm uppercase tracking-wide text-foreground">
            {albumName || 'Generating'}
          </h2>
          {message && (
            <p className="mt-2 text-xs text-foreground-muted leading-relaxed">{message}</p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <Stat label="Planned" value={plannedSongs.length} />
          <Stat label="Ready" value={completedSongs.length} />
        </div>

        <CoverPanel
          coverUrl={coverUrl}
          coverSkipped={coverSkipped}
          phase={phase}
          albumName={albumName}
        />

        {albumDescription && (
          <p className="text-xs text-foreground-subtle leading-relaxed">{albumDescription}</p>
        )}
      </aside>

      <section className="border border-border bg-surface p-4 min-h-[420px]">
        <h3 className="text-xs uppercase tracking-wide text-foreground-muted mb-3">Tracks</h3>
        <TrackList
          plannedSongs={plannedSongs}
          completedSongsByIndex={completedSongsByIndex}
          currentIndex={currentSongIndex}
          activeSongIndex={activeSongIndex}
          onToggleSong={(songIndex) => setActiveSongIndex((prev) => (prev === songIndex ? null : songIndex))}
        />
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-border bg-surface-raised px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-foreground-subtle">{label}</p>
      <p className="text-sm font-medium text-foreground">{value}</p>
    </div>
  )
}

interface CoverPanelProps {
  coverUrl: string | null
  phase: string
  albumName: string | null
  coverSkipped: boolean
}

function CoverPanel({ coverUrl, phase, albumName, coverSkipped }: CoverPanelProps) {
  const resolvedUrl = coverUrl ? albumService.resolveUrl(coverUrl) : null

  return (
    <div className="aspect-square w-full overflow-hidden bg-surface-raised border border-border flex items-center justify-center">
      <AnimatePresence mode="wait">
        {resolvedUrl ? (
          <motion.img
            key="cover"
            src={resolvedUrl}
            alt={albumName ?? 'Album cover'}
            initial={{ opacity: 0.35 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.25 }}
            className="w-full h-full object-cover"
          />
        ) : (
          <motion.div
            key="placeholder"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="flex flex-col items-center gap-2 text-foreground-subtle p-6"
          >
            <Spinner size="sm" />
            <p className="text-xs text-center">
              {phase === 'cover'
                ? (coverSkipped ? 'Skipping cover generation' : 'Generating cover')
                : (coverSkipped ? 'Cover disabled' : 'Cover pending')}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

interface TrackListProps {
  plannedSongs: SongPlanDisplay[]
  completedSongsByIndex: Map<number, SongResult>
  currentIndex: number | null
  activeSongIndex: number | null
  onToggleSong: (songIndex: number) => void
}

function TrackList({
  plannedSongs,
  completedSongsByIndex,
  currentIndex,
  activeSongIndex,
  onToggleSong,
}: TrackListProps) {
  if (!plannedSongs.length) {
    return (
      <div className="h-full min-h-[320px] flex items-center justify-center text-center text-foreground-subtle">
        <div>
          <Spinner size="sm" className="mx-auto mb-2" />
          <p className="text-xs uppercase tracking-wide">Waiting for plan</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2 overflow-y-auto max-h-[72vh] pr-1">
      {plannedSongs.map((song) => {
        const completedSong = completedSongsByIndex.get(song.index)
        const done = Boolean(completedSong)
        const active = currentIndex === song.index
        const playbackOpen = activeSongIndex === song.index && Boolean(completedSong)
        const audioUrl = completedSong ? albumService.resolveUrl(completedSong.audio_url) : null

        return (
          <div
            key={song.index}
            className={`border p-3 transition-colors ${
              active
                ? 'border-border-strong bg-surface-raised'
                : 'border-border bg-surface'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className="w-7 h-7 border border-border text-[11px] font-mono text-foreground-muted flex items-center justify-center shrink-0">
                {String(song.index + 1).padStart(2, '0')}
              </div>

              <div className="flex-1 min-w-0">
                <p className="text-sm text-foreground truncate">{song.name}</p>
                {song.description && (
                  <p className="text-xs text-foreground-subtle truncate">{song.description}</p>
                )}
              </div>

              {done ? (
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => onToggleSong(song.index)}
                    className="w-8 h-8 border border-border bg-surface-raised text-foreground-muted hover:text-foreground transition-colors"
                    aria-label={playbackOpen ? `Pause ${song.name}` : `Play ${song.name}`}
                  >
                    {playbackOpen ? <PauseIcon /> : <PlayIcon />}
                  </button>
                  <a
                    href={audioUrl ?? '#'}
                    download={`${String(song.index + 1).padStart(2, '0')}_${song.name}.mp3`}
                    className="w-8 h-8 border border-border bg-surface-raised text-foreground-muted hover:text-foreground transition-colors flex items-center justify-center"
                    aria-label={`Download ${song.name}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <DownloadIcon />
                  </a>
                  <Badge variant="success">Ready</Badge>
                </div>
              ) : active ? (
                <Badge variant="primary">Running</Badge>
              ) : (
                <Badge variant="default">Queued</Badge>
              )}
            </div>

            <AnimatePresence>
              {playbackOpen && audioUrl && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.16 }}
                  className="overflow-hidden"
                >
                  <div className="pt-3">
                    <audio
                      src={audioUrl}
                      controls
                      autoPlay
                      className="w-full h-10 accent-primary"
                    />
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </div>
  )
}

function PlayIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="mx-auto">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function PauseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="mx-auto">
      <rect x="6" y="4" width="4" height="16" />
      <rect x="14" y="4" width="4" height="16" />
    </svg>
  )
}

function DownloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  )
}

interface ErrorViewProps {
  message: string
  onRetry: () => void
}

function ErrorView({ message, onRetry }: ErrorViewProps) {
  return (
    <div className="flex-1 flex items-center justify-center px-4 py-10">
      <div className="max-w-md w-full border border-error/40 bg-error/8 p-5 text-center space-y-4">
        <h2 className="text-sm uppercase tracking-wide text-error">Generation Failed</h2>
        <p className="text-xs text-foreground-muted">{message}</p>
        <Button onClick={onRetry} variant="secondary">
          Start Over
        </Button>
      </div>
    </div>
  )
}
