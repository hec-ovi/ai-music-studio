import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Button } from '../ui/Button'
import { Textarea } from '../ui/Input'
import { Slider } from '../ui/Slider'
import { albumService } from '../../services/album.service'
import { useAlbumStore } from '../../stores/album.store'
import { useNavigationStore } from '../../stores/navigation.store'
import { useGenerationStream } from '../../hooks/useGenerationStream'
import type { AlbumSummary } from '../../types/album'

export function AlbumCreator() {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [library, setLibrary] = useState<AlbumSummary[]>([])
  const [libraryLoading, setLibraryLoading] = useState(true)
  const [libraryError, setLibraryError] = useState<string | null>(null)
  const [actionAlbumId, setActionAlbumId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const concept = useAlbumStore((s) => s.concept)
  const numSongs = useAlbumStore((s) => s.numSongs)
  const approxSongLengthSec = useAlbumStore((s) => s.approxSongLengthSec)
  const withCover = useAlbumStore((s) => s.withCover)
  const coverSize = useAlbumStore((s) => s.coverSize)
  const reviewPlan = useAlbumStore((s) => s.reviewPlan)
  const setConcept = useAlbumStore((s) => s.setConcept)
  const setNumSongs = useAlbumStore((s) => s.setNumSongs)
  const setApproxSongLengthSec = useAlbumStore((s) => s.setApproxSongLengthSec)
  const setWithCover = useAlbumStore((s) => s.setWithCover)
  const setCoverSize = useAlbumStore((s) => s.setCoverSize)
  const setReviewPlan = useAlbumStore((s) => s.setReviewPlan)
  const setAlbumId = useAlbumStore((s) => s.setAlbumId)
  const hydrateSession = useAlbumStore((s) => s.hydrateSession)
  const reset = useAlbumStore((s) => s.reset)
  const setView = useNavigationStore((s) => s.setView)
  const { start: startStream } = useGenerationStream()

  const loadLibrary = async () => {
    setLibraryLoading(true)
    setLibraryError(null)
    try {
      const rows = await albumService.listAlbums(120)
      setLibrary(rows)
    } catch (err) {
      setLibraryError(err instanceof Error ? err.message : 'Failed to load album sessions')
    } finally {
      setLibraryLoading(false)
    }
  }

  useEffect(() => {
    void loadLibrary()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!concept.trim()) return

    setIsSubmitting(true)
    setError(null)
    reset()
    setConcept(concept)
    setNumSongs(numSongs)
    setApproxSongLengthSec(approxSongLengthSec)
    setWithCover(withCover)
    setCoverSize(coverSize)
    setReviewPlan(reviewPlan)

    try {
      const { album_id } = await albumService.createAlbum({ concept, num_songs: numSongs })
      setAlbumId(album_id)
      setView('generating')
      startStream(album_id, concept, numSongs, withCover, coverSize, {
        stopAfterPlan: reviewPlan,
        useSavedPlan: false,
        songLengthSeconds: approxSongLengthSec,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start generation')
    } finally {
      setIsSubmitting(false)
      void loadLibrary()
    }
  }

  const handleOpenSession = async (album: AlbumSummary) => {
    setActionAlbumId(album.album_id)
    setActionError(null)
    try {
      const session = await albumService.getAlbumSession(album.album_id)
      hydrateSession(session)
      setAlbumId(session.album_id)
      setView('result')
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to open album')
    } finally {
      setActionAlbumId(null)
    }
  }

  const handleResumeSession = async (album: AlbumSummary) => {
    setActionAlbumId(album.album_id)
    setActionError(null)
    try {
      const session = await albumService.getAlbumSession(album.album_id)
      hydrateSession(session)
      setAlbumId(session.album_id)
      setView('generating')
      startStream(
        session.album_id,
        session.concept || session.album_name || 'Album',
        session.songs.length || album.songs_planned || 7,
        session.include_cover,
        session.cover_size === 512 ? 512 : 1024,
        {
          useSavedPlan: true,
          stopAfterPlan: false,
          songLengthSeconds: null,
        },
      )
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to resume generation')
    } finally {
      setActionAlbumId(null)
    }
  }

  const handleExportMp4 = async (album: AlbumSummary) => {
    setActionAlbumId(album.album_id)
    setActionError(null)
    try {
      await albumService.exportMp4(album.album_id)
      await loadLibrary()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to export MP4 tracks')
    } finally {
      setActionAlbumId(null)
    }
  }

  const handleExportYouTube = async (album: AlbumSummary) => {
    setActionAlbumId(album.album_id)
    setActionError(null)
    try {
      await albumService.exportYouTubePackage(album.album_id)
      await loadLibrary()
    } catch (err) {
      setActionError(err instanceof Error ? err.message : 'Failed to export YouTube package')
    } finally {
      setActionAlbumId(null)
    }
  }

  return (
    <div className="flex-1 w-full max-w-[1600px] mx-auto px-4 py-8">
      <motion.form
        onSubmit={handleSubmit}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="grid grid-cols-1 xl:grid-cols-[1.5fr_0.95fr_1.15fr] gap-4"
      >
        <section className="border border-border bg-surface p-5 min-h-[420px] flex flex-col">
          <header className="mb-3">
            <h1 className="text-base tracking-wide uppercase text-foreground-muted">Create Album</h1>
          </header>
          <div className="flex-1">
            <Textarea
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="Album concept: style, instrumentation, pacing, constraints."
              rows={14}
              className="h-full min-h-[340px] text-sm leading-relaxed"
              required
            />
          </div>
          <p className="mt-3 text-xs text-foreground-subtle">
            Planning, audio, cover, and export run locally.
          </p>
        </section>

        <aside className="border border-border bg-surface p-5 space-y-4">
          <h2 className="text-xs uppercase tracking-wide text-foreground-muted">Settings</h2>

          <Slider
            label="Songs"
            value={numSongs}
            min={1}
            max={12}
            onChange={setNumSongs}
          />

          <Slider
            label="Approx Length"
            value={approxSongLengthSec}
            min={30}
            max={420}
            step={5}
            unit="s"
            onChange={setApproxSongLengthSec}
          />

          <label className="flex items-center justify-between border border-border bg-surface-raised px-3 py-2">
            <span className="text-xs uppercase tracking-wide text-foreground-muted">Cover</span>
            <input
              type="checkbox"
              checked={withCover}
              onChange={(e) => setWithCover(e.target.checked)}
              className="h-4 w-4 border-border rounded-none"
            />
          </label>

          {withCover && (
            <div className="border border-border bg-surface-raised p-3 space-y-2">
              <p className="text-xs uppercase tracking-wide text-foreground-muted">Cover Size</p>
              <div className="grid grid-cols-2 gap-2">
                {[512, 1024].map((size) => (
                  <button
                    key={size}
                    type="button"
                    onClick={() => setCoverSize(size as 512 | 1024)}
                    className={`px-2 py-1.5 border text-xs uppercase tracking-wide transition-colors ${
                      coverSize === size
                        ? 'border-border-strong bg-surface text-foreground'
                        : 'border-border text-foreground-subtle hover:text-foreground'
                    }`}
                  >
                    {size}
                  </button>
                ))}
              </div>
            </div>
          )}

          <label className="flex items-center justify-between border border-border bg-surface-raised px-3 py-2">
            <span className="text-xs uppercase tracking-wide text-foreground-muted">Review Plan</span>
            <input
              type="checkbox"
              checked={reviewPlan}
              onChange={(e) => setReviewPlan(e.target.checked)}
              className="h-4 w-4 border-border rounded-none"
            />
          </label>

          {error && (
            <div className="border border-error/35 bg-error/8 px-3 py-2 text-xs text-error">
              {error}
            </div>
          )}

          <Button
            type="submit"
            size="lg"
            loading={isSubmitting}
            disabled={!concept.trim()}
            className="w-full"
          >
            Generate
          </Button>
        </aside>

        <aside className="border border-border bg-surface p-4 min-h-[420px] flex flex-col">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs uppercase tracking-wide text-foreground-muted">Library</h2>
            <button
              type="button"
              className="text-[11px] uppercase tracking-wide text-foreground-subtle hover:text-foreground"
              onClick={() => void loadLibrary()}
            >
              Refresh
            </button>
          </div>

          {libraryLoading ? (
            <p className="text-xs text-foreground-subtle">Loading sessions…</p>
          ) : libraryError ? (
            <p className="text-xs text-error">{libraryError}</p>
          ) : !library.length ? (
            <p className="text-xs text-foreground-subtle">No albums yet.</p>
          ) : (
            <div className="space-y-2 overflow-y-auto pr-1">
              {library.map((album) => {
                const busy = actionAlbumId === album.album_id
                const canOpen = album.songs_ready > 0
                const canResume = !['complete', 'error'].includes(album.status)
                const canExport = album.songs_ready > 0
                const coverUrl = album.cover_url ? albumService.resolveUrl(album.cover_url) : null
                return (
                  <div key={album.album_id} className="border border-border bg-surface-raised p-2.5 space-y-2">
                    <div className="flex items-start gap-2">
                      <div className="w-12 h-12 border border-border overflow-hidden bg-surface shrink-0">
                        {coverUrl ? (
                          <img src={coverUrl} alt={album.album_name ?? album.folder} className="w-full h-full object-cover" />
                        ) : null}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs text-foreground truncate">{album.album_name ?? album.folder}</p>
                        <p className="text-[11px] text-foreground-subtle truncate">
                          {album.songs_ready}/{album.songs_planned} tracks · {album.status}
                        </p>
                        <p className="text-[10px] text-foreground-subtle">{formatUpdatedAt(album.updated_at)}</p>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        onClick={() => void handleOpenSession(album)}
                        className="border border-border px-2 py-1 text-[10px] uppercase tracking-wide text-foreground-subtle hover:text-foreground disabled:opacity-50"
                        disabled={busy || !canOpen}
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleResumeSession(album)}
                        className="border border-border px-2 py-1 text-[10px] uppercase tracking-wide text-foreground-subtle hover:text-foreground disabled:opacity-50"
                        disabled={busy || !canResume}
                      >
                        Resume
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExportMp4(album)}
                        className="border border-border px-2 py-1 text-[10px] uppercase tracking-wide text-foreground-subtle hover:text-foreground disabled:opacity-50"
                        disabled={busy || !canExport}
                      >
                        MP4
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExportYouTube(album)}
                        className="border border-border px-2 py-1 text-[10px] uppercase tracking-wide text-foreground-subtle hover:text-foreground disabled:opacity-50"
                        disabled={busy || !canExport}
                      >
                        YouTube
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {actionError && (
            <div className="mt-3 border border-error/35 bg-error/8 px-2.5 py-2 text-xs text-error">
              {actionError}
            </div>
          )}
        </aside>
      </motion.form>
    </div>
  )
}

function formatUpdatedAt(iso: string): string {
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  return dt.toLocaleString()
}
