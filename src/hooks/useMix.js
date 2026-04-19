import { useState, useEffect } from 'react'
import { useDebounce } from './useDebounce'

// Fallback movies shown while waiting for the backend
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
    overview: 'Un equipo de exploradores viaja a través de un agujero de gusano en el espacio en un intento de garantizar la supervivencia de la humanidad.',
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

function pickFallback(sliders) {
  // Simple deterministic pick based on slider sum
  const sum = sliders.adrenaline + sliders.tension + sliders.cerebro
  return FALLBACKS[Math.floor(sum / 60) % FALLBACKS.length]
}

export function useMix(sliders) {
  const debouncedSliders = useDebounce(sliders, 350)
  const [movie, setMovie] = useState(FALLBACKS[0])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    const controller = new AbortController()

    async function fetchMix() {
      setLoading(true)
      setError(null)
      try {
        const params = new URLSearchParams({
          adrenaline: debouncedSliders.adrenaline,
          tension: debouncedSliders.tension,
          cerebro: debouncedSliders.cerebro,
          yearFrom: debouncedSliders.yearFrom,
          yearTo: debouncedSliders.yearTo,
        })
        const res = await fetch(`/api/movies/mix?${params}`, {
          signal: controller.signal,
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        setMovie(data)
      } catch (err) {
        if (err.name === 'AbortError') return
        // Backend not available yet → use smart fallback
        setMovie(pickFallback(debouncedSliders))
        setError('backend_offline')
      } finally {
        setLoading(false)
      }
    }

    fetchMix()
    return () => controller.abort()
  }, [debouncedSliders])

  return { movie, loading, error }
}
