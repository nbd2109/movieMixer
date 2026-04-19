import { useState, useEffect } from 'react'

export function useWatchProviders(tmdbId) {
  const [providers, setProviders] = useState(null)

  useEffect(() => {
    if (!tmdbId) {
      setProviders(null)
      return
    }
    const controller = new AbortController()
    fetch(`/api/movies/${tmdbId}/watch-providers?country=ES`, {
      signal: controller.signal,
    })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setProviders(data) })
      .catch(() => {})
    return () => controller.abort()
  }, [tmdbId])

  return providers
}
