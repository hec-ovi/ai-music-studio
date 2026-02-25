import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { useAlbumStore } from '../../stores/album.store'
import { useNavigationStore } from '../../stores/navigation.store'
import { albumService } from '../../services/album.service'
import type { ExportArtifact, SongResult } from '../../types/album'

export function AlbumResult() {
  const result = useAlbumStore((s) => s.result)
  const reset = useAlbumStore((s) => s.reset)
  const setView = useNavigationStore((s) => s.setView)
  const [activeSong, setActiveSong] = useState<number | null>(null)
  const [exportingMp4, setExportingMp4] = useState(false)
  const [exportingYouTube, setExportingYouTube] = useState(false)
  const [exportArtifacts, setExportArtifacts] = useState<ExportArtifact[]>([])
  const [exportError, setExportError] = useState<string | null>(null)

  if (!result) return null

  const handleStartOver = () => {
    reset()
    setView('home')
  }

  const handleExportMp4 = async () => {
    setExportError(null)
    setExportingMp4(true)
    try {
      const out = await albumService.exportMp4(result.album_id)
      setExportArtifacts(out.files)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'MP4 export failed')
    } finally {
      setExportingMp4(false)
    }
  }

  const handleExportYouTube = async () => {
    setExportError(null)
    setExportingYouTube(true)
    try {
      const out = await albumService.exportYouTubePackage(result.album_id)
      setExportArtifacts(out.files)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'YouTube package export failed')
    } finally {
      setExportingYouTube(false)
    }
  }

  const coverUrl = result.cover_url ? albumService.resolveUrl(result.cover_url) : null

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-4 py-6 grid grid-cols-1 xl:grid-cols-[320px_1fr] gap-4">
      <aside className="border border-border bg-surface p-4 space-y-4 h-fit">
        <div className="space-y-2">
          <Badge variant="success">Complete</Badge>
          <h1 className="text-sm uppercase tracking-wide text-foreground">{result.album_name}</h1>
          <p className="text-xs text-foreground-muted leading-relaxed">{result.album_description}</p>
        </div>

        <div className="aspect-square border border-border bg-surface-raised overflow-hidden flex items-center justify-center">
          {coverUrl ? (
            <img
              src={coverUrl}
              alt={result.album_name}
              className="w-full h-full object-cover"
            />
          ) : (
            <p className="text-xs uppercase tracking-wide text-foreground-subtle">No Cover</p>
          )}
        </div>

        <div className="text-xs text-foreground-subtle uppercase tracking-wide">
          {result.songs.length} Tracks · {formatTotalDuration(result.songs)}
        </div>

        <div className="grid grid-cols-1 gap-2">
          <Button
            variant="primary"
            size="md"
            onClick={() => handleDownloadAll(result.songs)}
          >
            Download All
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={() => void handleExportMp4()}
            loading={exportingMp4}
          >
            Export MP4
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={() => void handleExportYouTube()}
            loading={exportingYouTube}
          >
            YouTube Package
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={handleStartOver}
          >
            New Album
          </Button>
        </div>

        {exportError && (
          <p className="text-xs text-error">{exportError}</p>
        )}

        {exportArtifacts.length > 0 && (
          <div className="space-y-1.5 border border-border bg-surface-raised p-2">
            <p className="text-[10px] uppercase tracking-wide text-foreground-subtle">Exports</p>
            {exportArtifacts.map((artifact) => (
              <a
                key={`${artifact.kind}:${artifact.file_name}`}
                href={albumService.resolveUrl(artifact.url)}
                className="block text-xs text-foreground-subtle hover:text-foreground truncate"
                target="_blank"
                rel="noreferrer"
              >
                {artifact.file_name}
              </a>
            ))}
          </div>
        )}
      </aside>

      <section className="border border-border bg-surface p-4">
        <h2 className="text-xs uppercase tracking-wide text-foreground-muted mb-3">Tracks</h2>
        <div className="flex flex-col gap-2">
          {result.songs.map((song, i) => (
            <TrackRow
              key={song.index}
              song={song}
              trackNumber={i + 1}
              isActive={activeSong === song.index}
              onPlay={() => setActiveSong(activeSong === song.index ? null : song.index)}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

interface TrackRowProps {
  song: SongResult
  trackNumber: number
  isActive: boolean
  onPlay: () => void
}

function TrackRow({ song, trackNumber, isActive, onPlay }: TrackRowProps) {
  const audioUrl = albumService.resolveUrl(song.audio_url)

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: trackNumber * 0.03 }}
      className={`border transition-colors ${
        isActive ? 'border-border-strong bg-surface-raised' : 'border-border bg-surface'
      }`}
    >
      <div className="flex items-center gap-3 p-3">
        <button
          onClick={onPlay}
          className="w-8 h-8 border border-border bg-surface-raised text-foreground-muted hover:text-foreground transition-colors shrink-0"
          aria-label={isActive ? `Pause ${song.name}` : `Play ${song.name}`}
        >
          {isActive ? <PauseIcon /> : <PlayIcon />}
        </button>

        <div className="w-8 text-[11px] font-mono text-foreground-subtle shrink-0">
          {String(trackNumber).padStart(2, '0')}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm text-foreground truncate">{song.name}</p>
          {song.description && (
            <p className="text-xs text-foreground-subtle truncate">{song.description}</p>
          )}
        </div>

        <span className="text-[11px] text-foreground-subtle font-mono shrink-0">
          {formatDuration(song.duration_seconds)}
        </span>

        <a
          href={audioUrl}
          download={`${String(trackNumber).padStart(2, '0')}_${song.name}.mp3`}
          className="w-8 h-8 border border-border bg-surface-raised text-foreground-muted hover:text-foreground transition-colors flex items-center justify-center shrink-0"
          title="Download"
          onClick={(e) => e.stopPropagation()}
          aria-label={`Download ${song.name}`}
        >
          <DownloadIcon />
        </a>
      </div>

      <AnimatePresence>
        {isActive && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3">
              <audio src={audioUrl} controls autoPlay className="w-full h-10 accent-primary" />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function formatTotalDuration(songs: SongResult[]): string {
  const total = songs.reduce((acc, s) => acc + s.duration_seconds, 0)
  const m = Math.floor(total / 60)
  const s = Math.floor(total % 60)
  return `${m}m ${s}s`
}

function handleDownloadAll(songs: SongResult[]): void {
  songs.forEach((song, i) => {
    const url = albumService.resolveUrl(song.audio_url)
    const a = document.createElement('a')
    a.href = url
    a.download = `${String(i + 1).padStart(2, '0')}_${song.name}.mp3`
    a.click()
  })
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
