import { useState, useEffect, useRef } from 'react'
import { useDebounce } from './useDebounce'
import { track, Events } from '../lib/track'

const FALLBACKS = [
  {
    title: 'Blade Runner 2049',
    year: 2017,
    overview: 'Un oficial de policía descubre un secreto que amenaza con sumir a lo que queda de la humanidad en el caos.',
    posterUrl: 'https://image.tmdb.org/t/p/original/gajva2L0rPYkEWjzgFlBXCAVBE5.jpg',
    genres: ['Sci-Fi', 'Drama', 'Thriller'],
    rating: 8.0,
  },
  {
    title: 'Interstellar',
    year: 2014,
    overview: 'Un equipo de exploradores viaja a través de un agujero de gusano en el espacio.',
    posterUrl: 'https://image.tmdb.org/t/p/original/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg',
    genres: ['Sci-Fi', 'Adventure', 'Drama'],
    rating: 8.6,
  },
  {
    title: 'Parasite',
    year: 2019,
    overview: 'Toda la familia Ki-taek está en paro y se interesa vivamente en la adinerada familia Park.',
    posterUrl: 'https://image.tmdb.org/t/p/original/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg',
    genres: ['Thriller', 'Drama', 'Comedy'],
    rating: 8.5,
  },
  {
    title: 'Mad Max: Fury Road',
    year: 2015,
    overview: 'En un apocalíptico y yermo futuro, Max se une a Furiosa para escapar de un tirano de culto.',
    posterUrl: 'https://image.tmdb.org/t/p/original/8tZYtuWezp8JbcsvHYO0O46tFbo.jpg',
    genres: ['Action', 'Adventure', 'Sci-Fi'],
    rating: 8.1,
  },
]

export function useMix(sliders, remixKey = 0) {
  const debouncedSliders = useDebounce(sliders, 350)
  const [movie, setMovie]   = useState(null)   // null = estado inicial, sin fetch automático
  const [loading, setLoading] = useState(false)
  const [error, setError]   = useState(null)
  const mixCountRef = useRef(0)

  useEffect(() => {
    // No lanzar fetch en carga inicial — esperar al primer clic en Mezclar
    if (remixKey === 0) return

    const controller = new AbortController()

    async function fetchMix() {
      setLoading(true)
      setError(null)
      try {
        const RUNTIME_BOUNDS = {
          short:  { runtimeMax: 89 },
          medium: { runtimeMin: 90, runtimeMax: 140 },
          long:   { runtimeMin: 141 },
        }
        const runtimeParams = RUNTIME_BOUNDS[debouncedSliders.runtime] ?? {}

        const params = new URLSearchParams({
          genres:   debouncedSliders.genres.join(','),
          tone:     debouncedSliders.tone,
          cerebro:  debouncedSliders.cerebro,
          yearFrom: debouncedSliders.yearFrom,
          yearTo:   debouncedSliders.yearTo,
          ...runtimeParams,
        })
        const res = await fetch(`/api/movies/mix?${params}`, {
          signal: controller.signal,
        })

        if (res.status === 404) {
          const body = await res.json()
          setError({ code: 'no_genre_match', genres: body.detail?.genres_requested ?? [] })
          setLoading(false)
          return
        }

        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const data = await res.json()
        setMovie(data)
        mixCountRef.current += 1
        track(Events.MIX_GENERATED, {
          mix_number:   mixCountRef.current,
          genres:       debouncedSliders.genres,
          tone:         debouncedSliders.tone,
          cerebro:      debouncedSliders.cerebro,
          year_from:    debouncedSliders.yearFrom,
          year_to:      debouncedSliders.yearTo,
          result_title: data.title,
          result_year:  data.year,
          genre_match:  data.genre_match,
        })
      } catch (err) {
        if (err.name === 'AbortError') return
        // Backend offline: usar fallback solo si ya hay una sesión activa
        if (!movie) setMovie(FALLBACKS[Math.floor(Math.random() * FALLBACKS.length)])
        setError('backend_offline')
      } finally {
        setLoading(false)
      }
    }

    fetchMix()
    return () => controller.abort()
  }, [debouncedSliders, remixKey])

  return { movie, loading, error }
}
