import { useState, useCallback } from 'react'

const KEY      = 'cmx_history'
const MAX_SIZE = 10

function load() {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] }
}

function save(items) {
  localStorage.setItem(KEY, JSON.stringify(items))
}

export function useHistory() {
  const [history, setHistory] = useState(load)

  const addToHistory = useCallback((movie) => {
    if (!movie?.title) return
    setHistory(prev => {
      // FIFO: elimina duplicado por título, prepend, corta a MAX_SIZE
      const deduped = prev.filter(m => m.title !== movie.title)
      const next = [{ ...movie, addedAt: Date.now() }, ...deduped].slice(0, MAX_SIZE)
      save(next)
      return next
    })
  }, [])

  const clearHistory = useCallback(() => {
    localStorage.removeItem(KEY)
    setHistory([])
  }, [])

  return { history, addToHistory, clearHistory }
}
