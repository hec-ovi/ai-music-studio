export interface AlbumRequest {
  concept: string
  num_songs: number
}

export interface CreateAlbumResponse {
  album_id: string
  status: string
}

export interface SongPlanDisplay {
  index: number
  name: string
  description: string
}

export interface SongPlanEditable {
  index: number
  name: string
  music_prompt: string
  lyrics: string
  instrumental: boolean
  duration_seconds: number
  bpm: number | null
  description: string
}

export interface AlbumPlanEditable {
  album_name: string
  album_description: string
  cover_prompt: string
  songs: SongPlanEditable[]
}

export interface SongResult {
  index: number
  name: string
  description: string
  duration_seconds: number
  audio_url: string
}

export interface AlbumResult {
  album_id: string
  album_name: string
  album_description: string
  cover_url: string | null
  songs: SongResult[]
}

export interface ExportArtifact {
  id?: number
  kind: string
  song_index: number | null
  file_name: string
  url: string
  status: string
  created_at?: string | null
}

export interface AlbumSummary {
  album_id: string
  folder: string
  album_name: string | null
  concept: string | null
  status: string
  cover_url: string | null
  songs_planned: number
  songs_ready: number
  include_cover: boolean
  cover_size: number
  song_length_seconds: number | null
  created_at: string
  updated_at: string
  error: string | null
}

export interface SessionSong extends SongPlanEditable {
  audio_url?: string | null
  status?: string
}

export interface AlbumSession {
  album_id: string
  folder: string
  concept: string
  requested_num_songs: number
  include_cover: boolean
  cover_size: number
  song_length_seconds: number | null
  status: string
  album_name: string | null
  album_description: string | null
  cover_url: string | null
  error: string | null
  created_at: string
  updated_at: string
  completed_at: string | null
  songs: SessionSong[]
  exports: ExportArtifact[]
}

export interface ExportTracksResponse {
  album_id: string
  album_name: string
  exported_tracks: number
  files: ExportArtifact[]
}

export interface YouTubePackageResponse {
  album_id: string
  album_name: string
  playlist_title: string
  files: ExportArtifact[]
}

export type GenerationEventType =
  | 'planning'
  | 'plan_ready'
  | 'plan_review_required'
  | 'cover_generating'
  | 'cover_ready'
  | 'song_start'
  | 'song_progress'
  | 'song_ready'
  | 'complete'
  | 'error'

export interface ProgressEvent {
  event: GenerationEventType
  message: string
  data: Record<string, unknown> | null
  progress: number
}

export type GenerationPhase =
  | 'idle'
  | 'planning'
  | 'review'
  | 'cover'
  | 'music'
  | 'complete'
  | 'error'

export interface GenerationState {
  phase: GenerationPhase
  progress: number
  message: string
  albumName: string | null
  albumDescription: string | null
  plannedSongs: SongPlanDisplay[]
  coverUrl: string | null
  coverSkipped: boolean
  completedSongs: SongResult[]
  currentSongIndex: number | null
  result: AlbumResult | null
  error: string | null
}
