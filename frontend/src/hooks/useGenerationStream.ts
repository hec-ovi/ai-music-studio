import { useCallback, useRef } from 'react'
import { albumService } from '../services/album.service'
import { useAlbumStore } from '../stores/album.store'
import { useNavigationStore } from '../stores/navigation.store'
import type { ProgressEvent } from '../types/album'

interface StreamOptions {
  stopAfterPlan?: boolean
  useSavedPlan?: boolean
  songLengthSeconds?: number | null
}

export function useGenerationStream() {
  const applyEvent = useAlbumStore((s) => s.applyEvent)
  const setView = useNavigationStore((s) => s.setView)
  const esRef = useRef<EventSource | null>(null)
  const retryTimerRef = useRef<number | null>(null)

  const start = useCallback((
    albumId: string,
    concept: string,
    numSongs: number,
    includeCover: boolean,
    coverSize: 512 | 1024,
    options: StreamOptions = {},
  ) => {
    const {
      stopAfterPlan = false,
      useSavedPlan = false,
      songLengthSeconds = null,
    } = options

    // Close any existing stream
    esRef.current?.close()
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }

    let reconnectAttempts = 0
    const maxReconnectAttempts = 6

    const connect = (resumeFromSavedPlan: boolean) => {
      const url = albumService.streamUrl(
        albumId,
        concept,
        numSongs,
        includeCover,
        coverSize,
        songLengthSeconds,
        stopAfterPlan,
        resumeFromSavedPlan,
      )
      const es = new EventSource(url)
      esRef.current = es

      es.onmessage = (e) => {
        try {
          const evt: ProgressEvent = JSON.parse(e.data)
          applyEvent(evt)

          if (evt.event === 'complete' || evt.event === 'error' || evt.event === 'plan_review_required') {
            es.close()
            if (esRef.current === es) {
              esRef.current = null
            }
            if (retryTimerRef.current !== null) {
              window.clearTimeout(retryTimerRef.current)
              retryTimerRef.current = null
            }
            if (evt.event === 'complete') {
              setView('result')
            } else if (evt.event === 'plan_review_required') {
              setView('review')
            }
          }
        } catch {
          // Malformed event — ignore
        }
      }

      es.onerror = () => {
        es.close()
        if (esRef.current === es) {
          esRef.current = null
        }

        if (!stopAfterPlan && reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts += 1
          applyEvent({
            event: 'planning',
            message: `Connection dropped, resuming generation (${reconnectAttempts}/${maxReconnectAttempts})…`,
            data: null,
            progress: 0,
          })

          const delayMs = Math.min(2000 * reconnectAttempts, 10000)
          retryTimerRef.current = window.setTimeout(() => {
            connect(true)
          }, delayMs)
          return
        }

        applyEvent({
          event: 'error',
          message: 'Connection to generation service lost',
          data: null,
          progress: 0,
        })
      }
    }

    connect(useSavedPlan)
  }, [applyEvent, setView])

  const stop = useCallback(() => {
    esRef.current?.close()
    esRef.current = null
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }
  }, [])

  return { start, stop }
}
