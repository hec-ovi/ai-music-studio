import type {
  AlbumPlanEditable,
  AlbumRequest,
  AlbumResult,
  AlbumSession,
  AlbumSummary,
  CreateAlbumResponse,
  ExportTracksResponse,
  YouTubePackageResponse,
} from '../types/album'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`HTTP ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

export const albumService = {
  /** Submit an album generation request, returns album_id */
  async createAlbum(req: AlbumRequest): Promise<CreateAlbumResponse> {
    const res = await fetch(`${BASE}/api/albums`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    })
    return handleResponse<CreateAlbumResponse>(res)
  },

  /** Build the SSE stream URL for a given album_id */
  streamUrl(
    albumId: string,
    concept: string,
    numSongs: number,
    includeCover: boolean,
    coverSize: 512 | 1024,
    songLengthSeconds: number | null,
    stopAfterPlan: boolean,
    useSavedPlan: boolean,
  ): string {
    const params = new URLSearchParams({
      concept,
      num_songs: String(numSongs),
      include_cover: String(includeCover),
      cover_size: String(coverSize),
      stop_after_plan: String(stopAfterPlan),
      use_saved_plan: String(useSavedPlan),
    })
    if (typeof songLengthSeconds === 'number' && Number.isFinite(songLengthSeconds)) {
      params.set('song_length_seconds', String(Math.round(songLengthSeconds)))
    }
    return `${BASE}/api/albums/${albumId}/stream?${params}`
  },

  /** Fetch the editable saved plan */
  async getPlan(albumId: string): Promise<AlbumPlanEditable> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/plan`)
    return handleResponse<AlbumPlanEditable>(res)
  },

  /** Update the saved plan before generation starts */
  async updatePlan(albumId: string, plan: AlbumPlanEditable): Promise<AlbumPlanEditable> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/plan`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(plan),
    })
    return handleResponse<AlbumPlanEditable>(res)
  },

  /** Fetch completed album result */
  async getAlbumResult(albumId: string): Promise<AlbumResult> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/result`)
    return handleResponse<AlbumResult>(res)
  },

  /** List persisted album sessions */
  async listAlbums(limit = 100): Promise<AlbumSummary[]> {
    const res = await fetch(`${BASE}/api/albums?limit=${limit}`)
    return handleResponse<AlbumSummary[]>(res)
  },

  /** Get full persisted album session detail */
  async getAlbumSession(albumId: string): Promise<AlbumSession> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/session`)
    return handleResponse<AlbumSession>(res)
  },

  /** Export one MP4 per generated song */
  async exportMp4(albumId: string): Promise<ExportTracksResponse> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/exports/mp4`, {
      method: 'POST',
    })
    return handleResponse<ExportTracksResponse>(res)
  },

  /** Export YouTube metadata package */
  async exportYouTubePackage(albumId: string): Promise<YouTubePackageResponse> {
    const res = await fetch(`${BASE}/api/albums/${albumId}/exports/youtube-package`, {
      method: 'POST',
    })
    return handleResponse<YouTubePackageResponse>(res)
  },

  /** Resolve a server-relative URL to an absolute URL */
  resolveUrl(path: string): string {
    if (path.startsWith('http')) return path
    return `${BASE}${path}`
  },
}
