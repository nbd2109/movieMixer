import React, { useRef } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

function formatRuntime(minutes) {
  if (!minutes) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m}min`
  if (m === 0) return `${h}h`
  return `${h}h ${m}min`
}

export default function MovieDisplay({ movie, loading }) {
  const overviewRef = useRef(null)

  return (
    <div className="flex flex-col items-center text-center px-8 w-full max-w-lg select-none pointer-events-none">
      <AnimatePresence mode="wait">
        <motion.div
          key={movie?.title ?? 'empty'}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: loading ? 0.35 : 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.45, ease: [0.25, 0.46, 0.45, 0.94] }}
          className="flex flex-col items-center gap-3 w-full"
        >
          {/* Genre tags */}
          {movie?.genres?.length > 0 && (
            <div className="flex flex-wrap justify-center gap-1.5">
              {movie.genres.map((g) => (
                <span
                  key={g}
                  className="text-[9px] font-semibold tracking-[0.18em] uppercase px-2 py-0.5 rounded"
                  style={{
                    color:      'rgba(255,255,255,0.45)',
                    background: 'rgba(255,255,255,0.06)',
                    border:     '1px solid rgba(255,255,255,0.1)',
                  }}
                >
                  {g}
                </span>
              ))}
            </div>
          )}

          {/* Title */}
          <h1
            className="font-black text-white leading-none tracking-tight text-shadow-film"
            style={{ fontSize: 'clamp(2rem, 8vw, 4rem)' }}
          >
            {movie?.title}
          </h1>

          {/* Metadata row */}
          <div
            className="flex items-center gap-3 text-sm font-medium"
            style={{ color: 'rgba(255,255,255,0.45)' }}
          >
            {movie?.year && <span>{movie.year}</span>}
            {movie?.rating && (
              <>
                <span style={{ color: 'rgba(255,255,255,0.2)' }}>·</span>
                <span style={{ color: '#e8a020' }}>
                  {movie.rating.toFixed(1)}
                </span>
              </>
            )}
            {movie?.runtime && (
              <>
                <span style={{ color: 'rgba(255,255,255,0.2)' }}>·</span>
                <span>{formatRuntime(movie.runtime)}</span>
              </>
            )}
          </div>

          {/* Synopsis + TMDB link when truncated */}
          {movie?.overview && (
            <div className="flex flex-col items-center gap-1 max-w-md w-full">
              <p
                ref={overviewRef}
                className="text-sm leading-relaxed text-center"
                style={{ color: 'rgba(255,255,255,0.38)' }}
              >
                {movie.overview}
              </p>
              {movie?.tmdbId && (
                <a
                  href={`https://www.themoviedb.org/movie/${movie.tmdbId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pointer-events-auto text-[10px] tracking-wide transition-colors"
                  style={{ color: 'rgba(255,255,255,0.25)' }}
                  onMouseEnter={e => e.target.style.color = 'rgba(255,255,255,0.5)'}
                  onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.25)'}
                >
                  Ver en TMDB ↗
                </a>
              )}
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      {/* Loading spinner */}
      <AnimatePresence>
        {loading && (
          <motion.div
            key="spinner"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute"
          >
            <div
              className="w-5 h-5 rounded-full border-t border-white/60 animate-spin"
              style={{ borderColor: 'transparent transparent transparent rgba(255,255,255,0.6)' }}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
