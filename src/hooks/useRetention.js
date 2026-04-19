/**
 * useRetention — Memoria sin login (PRODUCT.md §3.4)
 *
 * Persiste los ajustes del usuario en localStorage.
 * Al volver, restaura su última mezcla y muestra un
 * mensaje de bienvenida contextual basado en el tiempo transcurrido.
 */

import { useEffect, useRef, useState } from 'react'
import { track, Events } from '../lib/track'

const KEYS = {
  SLIDERS:       'cmx_sliders',
  LAST_VISIT:    'cmx_last_visit',
  SESSION_COUNT: 'cmx_session_count',
}

// Mensajes de retorno — conversacionales, nunca técnicos
function buildWelcomeMessage(savedSliders, hoursAgo) {
  const genres = savedSliders?.genres ?? []
  const genreText = genres.length > 0
    ? genres.slice(0, 2).join(' + ').toLowerCase()
    : null

  if (hoursAgo < 1)   return null  // Misma sesión, no molestar
  if (hoursAgo < 8)   return null  // Pocas horas, no molestar

  if (hoursAgo < 24) {
    return genreText
      ? `¿Encontraste algo bueno con ${genreText}?`
      : '¿Encontraste algo bueno anoche?'
  }

  if (hoursAgo < 72) {
    return genreText
      ? `La última vez buscabas ${genreText}. ¿Seguimos?`
      : 'La última vez no encontraste nada. Hoy puede ser diferente.'
  }

  if (hoursAgo < 168) {  // < 1 semana
    return genreText
      ? `Llevas días sin mezclar. La última vez: ${genreText}.`
      : 'Llevas días sin mezclar. Toca.'
  }

  return 'Llevas tiempo sin mezclar. ¿Qué toca esta noche?'
}

export function useRetention(defaultSliders) {
  const [welcomeMessage, setWelcomeMessage] = useState(null)
  const saveTimerRef = useRef(null)

  // ── Carga inicial ──────────────────────────────────────────────────────────
  function getInitialSliders() {
    try {
      const raw = localStorage.getItem(KEYS.SLIDERS)
      if (raw) return { ...defaultSliders, ...JSON.parse(raw) }
    } catch (_) {}
    return defaultSliders
  }

  // ── Tracking de retención al montar ───────────────────────────────────────
  useEffect(() => {
    try {
      const lastVisit    = Number(localStorage.getItem(KEYS.LAST_VISIT) || 0)
      const sessionCount = Number(localStorage.getItem(KEYS.SESSION_COUNT) || 0)
      const savedSliders = (() => {
        try { return JSON.parse(localStorage.getItem(KEYS.SLIDERS)) } catch { return null }
      })()

      const hoursAgo = lastVisit ? (Date.now() - lastVisit) / 3_600_000 : Infinity
      const isReturn = sessionCount > 0

      // Evento de retención
      if (isReturn) {
        track(Events.SESSION_RETURNED, {
          hours_since_last_visit: Math.round(hoursAgo),
          session_count: sessionCount + 1,
        })
      }

      // Mensaje de bienvenida
      if (isReturn) {
        const msg = buildWelcomeMessage(savedSliders, hoursAgo)
        if (msg) {
          setWelcomeMessage(msg)
          setTimeout(() => setWelcomeMessage(null), 4500)
        }
      }

      // Actualizar contadores
      localStorage.setItem(KEYS.LAST_VISIT,    Date.now().toString())
      localStorage.setItem(KEYS.SESSION_COUNT, (sessionCount + 1).toString())
    } catch (_) {}
  }, [])

  // ── Guardar sliders con debounce para no saturar localStorage ─────────────
  function saveSliders(sliders) {
    clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      try {
        localStorage.setItem(KEYS.SLIDERS, JSON.stringify(sliders))
      } catch (_) {}
    }, 800)
  }

  return { getInitialSliders, saveSliders, welcomeMessage }
}
