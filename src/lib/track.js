/**
 * CineMix — Data Layer
 *
 * Capa de tracking ligera sin dependencias externas.
 * En desarrollo: logs en consola.
 * En producción: fire-and-forget a un endpoint o analytics provider.
 *
 * Para conectar a GA4/Mixpanel/Posthog, solo hay que modificar _dispatch().
 * El resto de la app llama a track() y no sabe nada del proveedor.
 *
 * KPIs que medimos (ver PRODUCT.md §3.2):
 *   mix_generated        — cuántas mezclas por sesión
 *   remix_clicked        — índice inverso de satisfacción
 *   pad_toggled          — qué géneros activa la gente
 *   slider_adjusted      — qué sliders mueven más y hacia dónde
 *   where_to_watch_clicked — conversión real (el KPI principal)
 *   share_clicked        — K-factor
 *   ticket_downloaded    — intención de recordar
 *   session_returned     — retención D1/D7/D30
 */

// ── Configuración ─────────────────────────────────────────────────────────────
const ENDPOINT = null  // Pon aquí tu endpoint cuando tengas analytics: '/api/events'
const MAX_SESSION_EVENTS = 200

// ── Session ID ────────────────────────────────────────────────────────────────
function getSessionId() {
  let id = sessionStorage.getItem('cmx_sid')
  if (!id) {
    id = Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
    sessionStorage.setItem('cmx_sid', id)
  }
  return id
}

// ── Dispatch ──────────────────────────────────────────────────────────────────
function _dispatch(payload) {
  // 1. Consola en desarrollo
  if (import.meta.env.DEV) {
    console.log(
      `%c[CineMix · ${payload.event}]`,
      'color:#fbbf24;font-weight:bold',
      payload.properties
    )
  }

  // 2. Beacon al endpoint cuando esté configurado (no bloquea el hilo)
  if (ENDPOINT) {
    try {
      navigator.sendBeacon(ENDPOINT, JSON.stringify(payload))
    } catch (_) {}
  }

  // 3. Buffer de sesión para análisis manual / debug
  try {
    const buf = JSON.parse(sessionStorage.getItem('cmx_events') || '[]')
    buf.push(payload)
    sessionStorage.setItem('cmx_events', JSON.stringify(buf.slice(-MAX_SESSION_EVENTS)))
  } catch (_) {}
}

// ── API pública ───────────────────────────────────────────────────────────────
export function track(event, properties = {}) {
  _dispatch({
    event,
    properties: {
      ...properties,
      ts:         new Date().toISOString(),
      session_id: getSessionId(),
    },
  })
}

// ── Helpers tipados para los eventos definidos en PRODUCT.md ─────────────────
export const Events = {
  MIX_GENERATED:          'mix_generated',
  REMIX_CLICKED:          'remix_clicked',
  PAD_TOGGLED:            'pad_toggled',
  SLIDER_ADJUSTED:        'slider_adjusted',
  WHERE_TO_WATCH_CLICKED: 'where_to_watch_clicked',
  SHARE_CLICKED:          'share_clicked',
  TICKET_DOWNLOADED:      'ticket_downloaded',
  SESSION_RETURNED:       'session_returned',
}
