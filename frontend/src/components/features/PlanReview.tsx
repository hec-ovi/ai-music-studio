import { useEffect, useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Button } from '../ui/Button'
import { Spinner } from '../ui/Spinner'
import { albumService } from '../../services/album.service'
import { useAlbumStore } from '../../stores/album.store'
import { useNavigationStore } from '../../stores/navigation.store'
import { useGenerationStream } from '../../hooks/useGenerationStream'
import type { AlbumPlanEditable, SongPlanEditable } from '../../types/album'

export function PlanReview() {
  const albumId = useAlbumStore((s) => s.albumId)
  const concept = useAlbumStore((s) => s.concept)
  const withCover = useAlbumStore((s) => s.withCover)
  const coverSize = useAlbumStore((s) => s.coverSize)
  const numSongs = useAlbumStore((s) => s.numSongs)
  const reset = useAlbumStore((s) => s.reset)
  const setView = useNavigationStore((s) => s.setView)
  const { start: startStream } = useGenerationStream()

  const [plan, setPlan] = useState<AlbumPlanEditable | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [bulkDurationSec, setBulkDurationSec] = useState(90)

  useEffect(() => {
    if (!albumId) {
      setView('home')
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    albumService.getPlan(albumId)
      .then((data) => {
        if (!cancelled) {
          setPlan(data)
          const firstDuration = data.songs[0]?.duration_seconds
          if (typeof firstDuration === 'number' && Number.isFinite(firstDuration)) {
            setBulkDurationSec(Math.round(firstDuration))
          }
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load plan')
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false)
        }
      })

    return () => {
      cancelled = true
    }
  }, [albumId, setView])

  const canSubmit = useMemo(() => {
    if (!plan) return false
    return Boolean(plan.album_name.trim()) && plan.songs.length > 0
  }, [plan])

  const updateSong = (index: number, patch: Partial<SongPlanEditable>) => {
    setPlan((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        songs: prev.songs.map((song, i) => (i === index ? { ...song, ...patch } : song)),
      }
    })
  }

  const clampDuration = (value: number) => Math.max(30, Math.min(420, Math.round(value)))

  const applyDurationToAllSongs = () => {
    const nextDuration = clampDuration(bulkDurationSec)
    setBulkDurationSec(nextDuration)
    setPlan((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        songs: prev.songs.map((song) => ({ ...song, duration_seconds: nextDuration })),
      }
    })
  }

  const handleApprove = async () => {
    if (!albumId || !plan) return
    setSaving(true)
    setError(null)

    const normalized: AlbumPlanEditable = {
      ...plan,
      songs: plan.songs.map((song, idx) => ({ ...song, index: idx })),
    }

    try {
      const updated = await albumService.updatePlan(albumId, normalized)
      setPlan(updated)
      setView('generating')
      startStream(
        albumId,
        concept || updated.album_name,
        updated.songs.length || numSongs,
        withCover,
        coverSize,
        { useSavedPlan: true, stopAfterPlan: false, songLengthSeconds: null },
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save plan')
    } finally {
      setSaving(false)
    }
  }

  const handleStartOver = () => {
    reset()
    setView('home')
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center text-foreground-muted">
          <Spinner size="lg" className="mx-auto mb-3" />
          <p className="text-sm">Loading editable plan…</p>
        </div>
      </div>
    )
  }

  if (!plan) {
    return (
      <div className="flex-1 flex items-center justify-center px-4">
        <div className="max-w-md w-full border border-error/40 bg-error/10 p-5 text-center">
          <p className="text-sm text-error mb-3">{error ?? 'Plan not found'}</p>
          <Button onClick={handleStartOver} variant="secondary">Start Over</Button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 w-full max-w-6xl mx-auto px-4 py-6 space-y-4">
      <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <h2 className="text-sm uppercase tracking-wide text-foreground">Review Plan</h2>
        <p className="text-xs text-foreground-muted">
          Edit album metadata and song prompts before generation starts.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 border border-border bg-surface p-5">
        <label className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-foreground-muted">Album Name</span>
          <input
            value={plan.album_name}
            onChange={(e) => setPlan({ ...plan, album_name: e.target.value })}
            className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-foreground-muted">Album Description</span>
          <textarea
            value={plan.album_description}
            onChange={(e) => setPlan({ ...plan, album_description: e.target.value })}
            rows={3}
            className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
          />
        </label>
        <label className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-foreground-muted">Cover Prompt</span>
          <textarea
            value={plan.cover_prompt}
            onChange={(e) => setPlan({ ...plan, cover_prompt: e.target.value })}
            rows={3}
            className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
          />
        </label>
        <div className="space-y-1">
          <span className="text-xs uppercase tracking-wide text-foreground-muted">Song Time (all tracks)</span>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              type="number"
              min={30}
              max={420}
              value={bulkDurationSec}
              onChange={(e) => setBulkDurationSec(clampDuration(Number(e.target.value) || 30))}
              className="w-full sm:w-48 border border-border bg-surface-raised px-3 py-2 text-sm"
            />
            <Button type="button" variant="secondary" onClick={applyDurationToAllSongs}>
              Apply To All Songs
            </Button>
          </div>
          <p className="text-[11px] text-foreground-subtle">
            Sets all track durations in this plan. You can still tweak each song below.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {plan.songs.map((song, idx) => (
          <div key={song.index} className="border border-border bg-surface p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs uppercase tracking-wide text-foreground">Song {String(idx + 1).padStart(2, '0')}</h3>
              <label className="flex items-center gap-2 text-xs text-foreground-muted">
                <input
                  type="checkbox"
                  checked={song.instrumental}
                  onChange={(e) => updateSong(idx, { instrumental: e.target.checked })}
                  className="h-4 w-4 rounded border-border text-primary"
                />
                Instrumental
              </label>
            </div>

            <input
              value={song.name}
              onChange={(e) => updateSong(idx, { name: e.target.value })}
              className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
              placeholder="Song name"
            />
            <textarea
              value={song.description}
              onChange={(e) => updateSong(idx, { description: e.target.value })}
              rows={2}
              className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
              placeholder="Short description"
            />
            <textarea
              value={song.music_prompt}
              onChange={(e) => updateSong(idx, { music_prompt: e.target.value })}
              rows={3}
              className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
              placeholder="Music prompt"
            />
            <textarea
              value={song.lyrics}
              onChange={(e) => updateSong(idx, { lyrics: e.target.value })}
              rows={3}
              className="w-full border border-border bg-surface-raised px-3 py-2 text-sm font-mono"
              placeholder="[instrumental] or song lyrics"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <label className="space-y-1">
                <span className="text-[11px] uppercase tracking-wide text-foreground-muted">Duration (seconds)</span>
                <input
                  type="number"
                  min={30}
                  max={420}
                  value={Math.round(song.duration_seconds)}
                  onChange={(e) => updateSong(idx, { duration_seconds: Number(e.target.value) })}
                  className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
                />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] uppercase tracking-wide text-foreground-muted">BPM (optional)</span>
                <input
                  type="number"
                  min={40}
                  max={240}
                  value={song.bpm ?? ''}
                  onChange={(e) => {
                    const next = e.target.value.trim()
                    updateSong(idx, { bpm: next ? Number(next) : null })
                  }}
                  className="w-full border border-border bg-surface-raised px-3 py-2 text-sm"
                />
              </label>
            </div>
          </div>
        ))}
      </div>

      {error && (
        <div className="border border-error/40 bg-error/10 px-4 py-3 text-sm text-error">{error}</div>
      )}

      <div className="flex flex-wrap gap-3">
        <Button variant="secondary" onClick={handleStartOver}>Start Over</Button>
        <Button
          onClick={handleApprove}
          loading={saving}
          disabled={!canSubmit}
        >
          Save Plan & Generate
        </Button>
      </div>
    </div>
  )
}
