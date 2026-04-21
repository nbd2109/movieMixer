import React from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { useWatchProviders } from '../hooks/useWatchProviders'
import { track, Events } from '../lib/track'

const SPRING = { type: 'spring', damping: 36, stiffness: 280 }

function formatRuntime(minutes) {
  if (!minutes) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

function formatDate(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short' })
}

function HistoryCardProviders({ tmdbId, title }) {
  const providers = useWatchProviders(tmdbId)
  const streaming = providers?.flatrate ?? []
  const rent      = providers?.rent ?? []
  const link      = providers?.link

  if (!providers || (streaming.length === 0 && rent.length === 0)) return null

  const list = streaming.length > 0 ? streaming : rent
  const label = streaming.length > 0 ? 'Ver en' : 'Alquilar en'

  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-[8px] tracking-widest uppercase" style={{ color: 'rgba(255,255,255,0.2)' }}>
        {label}
      </span>
      {list.map(p => (
        <button
          key={p.id}
          title={p.name}
          onClick={() => {
            track(Events.WHERE_TO_WATCH_CLICKED, { provider: p.name, title, tmdb_id: tmdbId })
            if (link) window.open(link, '_blank', 'noopener')
          }}
          className="rounded-md overflow-hidden transition-opacity hover:opacity-80"
          style={{ width: 24, height: 24 }}
        >
          <img src={p.logo} alt={p.name} className="w-full h-full object-cover" loading="lazy" />
        </button>
      ))}
      {link && (
        <a
          href={link}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[8px] transition-colors"
          style={{ color: 'rgba(255,255,255,0.2)' }}
          onMouseEnter={e => e.target.style.color = 'rgba(255,255,255,0.5)'}
          onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.2)'}
        >
          JustWatch ↗
        </a>
      )}
    </div>
  )
}

function HistoryCard({ movie, index }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.04, duration: 0.3 }}
      className="flex gap-3 p-3 rounded-xl"
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Poster */}
      {movie.posterUrl && (
        <div className="flex-shrink-0 rounded-lg overflow-hidden" style={{ width: 52, height: 78 }}>
          <img
            src={movie.posterUrl}
            alt={movie.title}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        </div>
      )}

      {/* Info */}
      <div className="flex flex-col gap-1.5 min-w-0 flex-1">
        {/* Título + año */}
        <div className="flex items-baseline gap-2 flex-wrap">
          <span
            className="font-bold leading-tight"
            style={{ fontSize: 13, color: 'rgba(255,255,255,0.9)' }}
          >
            {movie.title}
          </span>
          <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)' }}>
            {movie.year}
          </span>
        </div>

        {/* Meta — rating · duración · géneros */}
        <div className="flex items-center gap-2 flex-wrap">
          {movie.rating && (
            <span style={{ fontSize: 10, color: '#e8a020', fontWeight: 600 }}>
              {movie.rating.toFixed(1)}
            </span>
          )}
          {movie.runtime && (
            <>
              <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 10 }}>·</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                {formatRuntime(movie.runtime)}
              </span>
            </>
          )}
          {movie.genres?.length > 0 && (
            <>
              <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 10 }}>·</span>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>
                {movie.genres.join(', ')}
              </span>
            </>
          )}
        </div>

        {/* Overview */}
        {movie.overview && (
          <p
            style={{
              fontSize: 10,
              color: 'rgba(255,255,255,0.3)',
              lineHeight: 1.5,
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {movie.overview}
          </p>
        )}

        {/* Links + providers */}
        <div className="flex items-center gap-3 flex-wrap mt-0.5">
          {movie.tmdbId && (
            <a
              href={`https://www.themoviedb.org/movie/${movie.tmdbId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[9px] tracking-wide transition-colors"
              style={{ color: 'rgba(255,255,255,0.2)' }}
              onMouseEnter={e => e.target.style.color = 'rgba(255,255,255,0.5)'}
              onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.2)'}
            >
              TMDB ↗
            </a>
          )}
          <HistoryCardProviders tmdbId={movie.tmdbId} title={movie.title} />
        </div>

        {/* Fecha */}
        {movie.addedAt && (
          <span style={{ fontSize: 8, color: 'rgba(255,255,255,0.15)', marginTop: 2 }}>
            {formatDate(movie.addedAt)}
          </span>
        )}
      </div>
    </motion.div>
  )
}

export default function HistorialPanel({ open, onClose, history, onClear }) {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="absolute inset-0 z-40"
            style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          />

          {/* Panel */}
          <motion.div
            key="panel"
            initial={{ x: '-100%' }}
            animate={{ x: 0 }}
            exit={{ x: '-100%' }}
            transition={SPRING}
            className="absolute left-0 inset-y-0 z-50 flex flex-col"
            style={{
              width: 340,
              background: 'rgba(8,8,16,0.97)',
              backdropFilter: 'blur(40px)',
              borderRight: '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {/* Header */}
            <div
              className="flex items-center justify-between px-5 py-4 flex-shrink-0"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
            >
              <div className="flex items-center gap-2">
                <span
                  className="font-black text-sm tracking-tight"
                  style={{ color: 'rgba(255,255,255,0.9)' }}
                >
                  Historial
                </span>
                {history.length > 0 && (
                  <span
                    className="text-[9px] px-1.5 py-0.5 rounded-full"
                    style={{
                      background: 'rgba(232,160,32,0.15)',
                      color: '#e8a020',
                    }}
                  >
                    {history.length}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {history.length > 0 && (
                  <button
                    onClick={onClear}
                    className="text-[9px] tracking-widest uppercase transition-colors"
                    style={{ color: 'rgba(255,255,255,0.2)' }}
                    onMouseEnter={e => e.target.style.color = 'rgba(255,255,255,0.5)'}
                    onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.2)'}
                  >
                    Limpiar
                  </button>
                )}
                <button
                  onClick={onClose}
                  style={{ color: 'rgba(255,255,255,0.3)', fontSize: 18, lineHeight: 1 }}
                  onMouseEnter={e => e.target.style.color = 'rgba(255,255,255,0.7)'}
                  onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.3)'}
                >
                  ×
                </button>
              </div>
            </div>

            {/* Lista */}
            <div className="flex-1 overflow-y-auto px-4 py-4 flex flex-col gap-3 min-h-0">
              {history.length === 0 ? (
                <div className="flex-1 flex flex-col items-center justify-center gap-2 text-center">
                  <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.2)' }}>
                    Ninguna mezcla todavía.
                  </p>
                  <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.12)' }}>
                    Las películas que mezcles aparecerán aquí.
                  </p>
                </div>
              ) : (
                history.map((movie, i) => (
                  <HistoryCard key={movie.title + movie.addedAt} movie={movie} index={i} />
                ))
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
