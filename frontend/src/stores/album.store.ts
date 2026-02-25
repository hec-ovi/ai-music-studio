import { create } from 'zustand'
import type {
  AlbumResult,
  AlbumSession,
  GenerationState,
  ProgressEvent,
  SongPlanDisplay,
  SongResult,
} from '../types/album'

const initial: GenerationState = {
  phase: 'idle',
  progress: 0,
  message: '',
  albumName: null,
  albumDescription: null,
  plannedSongs: [],
  coverUrl: null,
  coverSkipped: false,
  completedSongs: [],
  currentSongIndex: null,
  result: null,
  error: null,
}

interface AlbumStore extends GenerationState {
  albumId: string | null
  concept: string
  numSongs: number
  approxSongLengthSec: number
  withCover: boolean
  coverSize: 512 | 1024
  reviewPlan: boolean

  setConcept: (concept: string) => void
  setNumSongs: (n: number) => void
  setApproxSongLengthSec: (seconds: number) => void
  setWithCover: (enabled: boolean) => void
  setCoverSize: (size: 512 | 1024) => void
  setReviewPlan: (enabled: boolean) => void
  setAlbumId: (id: string) => void
  hydrateSession: (session: AlbumSession) => void
  applyEvent: (evt: ProgressEvent) => void
  reset: () => void
}

export const useAlbumStore = create<AlbumStore>((set) => ({
  ...initial,
  albumId: null,
  concept: '',
  numSongs: 7,
  approxSongLengthSec: 90,
  withCover: true,
  coverSize: 1024,
  reviewPlan: false,

  setConcept: (concept) => set({ concept }),
  setNumSongs: (numSongs) => set({ numSongs }),
  setApproxSongLengthSec: (approxSongLengthSec) => set({ approxSongLengthSec }),
  setWithCover: (withCover) => set({ withCover }),
  setCoverSize: (coverSize) => set({ coverSize }),
  setReviewPlan: (reviewPlan) => set({ reviewPlan }),
  setAlbumId: (albumId) => set({ albumId }),
  hydrateSession: (session) => {
    const plannedSongs: SongPlanDisplay[] = session.songs.map((song) => ({
      index: song.index,
      name: song.name,
      description: song.description,
    }))
    const completedSongs: SongResult[] = session.songs
      .filter((song) => Boolean(song.audio_url))
      .map((song) => ({
        index: song.index,
        name: song.name,
        description: song.description,
        duration_seconds: song.duration_seconds,
        audio_url: song.audio_url as string,
      }))

    const result: AlbumResult = {
      album_id: session.album_id,
      album_name: session.album_name ?? 'Untitled',
      album_description: session.album_description ?? '',
      cover_url: session.cover_url,
      songs: completedSongs,
    }

    set({
      albumId: session.album_id,
      concept: session.concept ?? '',
      numSongs: session.requested_num_songs || Math.max(session.songs.length, 1),
      approxSongLengthSec: session.song_length_seconds ?? 90,
      withCover: session.include_cover,
      coverSize: (session.cover_size === 512 ? 512 : 1024),
      phase: session.status === 'complete' ? 'complete' : 'idle',
      message: session.status,
      progress: session.status === 'complete' ? 1 : 0,
      albumName: session.album_name,
      albumDescription: session.album_description,
      plannedSongs,
      completedSongs,
      coverUrl: session.cover_url,
      coverSkipped: !session.include_cover || !session.cover_url,
      result,
      error: session.error,
      currentSongIndex: null,
    })
  },

  applyEvent: (evt) =>
    set((state) => {
      switch (evt.event) {
        case 'planning':
          return { phase: 'planning', progress: evt.progress, message: evt.message }

        case 'plan_ready': {
          const d = evt.data as { album_name: string; album_description: string; songs: SongPlanDisplay[] }
          return {
            phase: 'planning',
            progress: evt.progress,
            message: evt.message,
            albumName: d.album_name,
            albumDescription: d.album_description,
            plannedSongs: d.songs,
          }
        }

        case 'plan_review_required':
          return { phase: 'review', progress: evt.progress, message: evt.message, currentSongIndex: null }

        case 'cover_generating':
          return { phase: 'cover', progress: evt.progress, message: evt.message, coverSkipped: false }

        case 'cover_ready': {
          const d = evt.data as { cover_url: string | null }
          return { phase: 'cover', progress: evt.progress, message: evt.message, coverUrl: d.cover_url, coverSkipped: !d.cover_url }
        }

        case 'song_start': {
          const d = evt.data as { index: number; name: string }
          return { phase: 'music', progress: evt.progress, message: evt.message, currentSongIndex: d.index }
        }

        case 'song_progress': {
          const d = evt.data as { index?: number }
          return {
            phase: 'music',
            progress: evt.progress,
            message: evt.message,
            currentSongIndex: typeof d.index === 'number' ? d.index : state.currentSongIndex,
          }
        }

        case 'song_ready': {
          const song = evt.data as unknown as SongResult
          return {
            phase: 'music',
            progress: evt.progress,
            completedSongs: [...state.completedSongs, song],
          }
        }

        case 'complete': {
          const result = evt.data as unknown as AlbumResult
          return { phase: 'complete', progress: 1, message: evt.message, result, currentSongIndex: null }
        }

        case 'error':
          return { phase: 'error', message: evt.message, error: evt.message }

        default:
          return {}
      }
    }),

  reset: () => set({
    ...initial,
    concept: '',
    numSongs: 7,
    approxSongLengthSec: 90,
    withCover: true,
    coverSize: 1024,
    reviewPlan: false,
    albumId: null,
  }),
}))
