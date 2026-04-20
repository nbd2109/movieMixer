import { useState, useEffect, useRef } from 'react'
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
  const slidersRef = useRef(sliders)
  slidersRef.current = sliders   // siempre actualizado, sin re-renders

  const [movie, setMovie]     = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const mixCountRef = useRef(0)

  useEffect(() => {
    // Solo dispara cuando el usuario pulsa "Mezclar" — nunca al mover sliders
    if (remixKey === 0) return

    const controller = new AbortController()
    const s = slidersRef.current   // snapshot en el momento del clic

    async function fetchMix() {
      setLoading(true)
      setError(null)
      try {
        const RUNTIME_BOUNDS = {
          short:  { runtimeMax: 89 },
          medium: { runtimeMin: 90, runtimeMax: 140 },
          long:   { runtimeMin: 141 },
        }
        const runtimeParams = RUNTIME_BOUNDS[s.runtime] ?? {}

        const params = new URLSearchParams({
          genres:   s.genres.join(','),
          tone:     s.tone,
          cerebro:  s.cerebro,
          yearFrom: s.yearFrom,
          yearTo:   s.yearTo,
          ...runtimeParams,
          ...(s.platform ? { platform: s.platform } : {}),
        })
        const res = await fetch(`/api/movies/mix?${params}`, {
          signal: controller.signal,
        })

        if (res.status === 404) {
          const body = await res.json()
          const code = body.detail?.code
          if (code === 'no_platform_match') {
            setError({ code: 'no_platform_match', platform: body.detail?.platform ?? '' })
          } else {
            setError({ code: 'no_genre_match', genres: body.detail?.genres_requested ?? [] })
          }
          setLoading(false)
          return
        }

        if (!res.ok) throw new Error(`HTTP ${res.status}`)

        const data = await res.json()
        setMovie(data)
        mixCountRef.current += 1
        track(Events.MIX_GENERATED, {
          mix_number:   mixCountRef.current,
          genres:       s.genres,
          tone:         s.tone,
          cerebro:      s.cerebro,
          year_from:    s.yearFrom,
          year_to:      s.yearTo,
          result_title: data.title,
          result_year:  data.year,
          genre_match:  data.genre_match,
        })
      } catch (err) {
        if (err.name === 'AbortError') return
        if (!movie) setMovie(FALLBACKS[Math.floor(Math.random() * FALLBACKS.length)])
        setError('backend_offline')
      } finally {
        setLoading(false)
      }
    }

    fetchMix()
    return () => controller.abort()
  }, [remixKey])

  return { movie, loading, error }
}
