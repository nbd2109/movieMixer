import React from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export default function MovieDisplay({ movie, loading }) {
  return (
    <div className="relative z-10 flex flex-col items-center justify-center text-center px-6 pointer-events-none select-none">
      {/* Loading shimmer */}
      <AnimatePresence>
        {loading && (
          <motion.div
            key="loader"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 flex items-center justify-center"
          >
            <div className="w-8 h-8 border-2 border-white/30 border-t-white rounded-full animate-spin" />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence mode="wait">
        <motion.div
          key={movie?.title}
          initial={{ opacity: 0, y: 20, filter: 'blur(8px)' }}
          animate={{ opacity: loading ? 0.3 : 1, y: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, y: -20, filter: 'blur(8px)' }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="flex flex-col items-center gap-3"
        >
          {/* Genre badges */}
          {movie?.genres?.length > 0 && (
            <div className="flex flex-wrap justify-center gap-2 mb-1">
              {movie.genres.map((g) => (
                <span
                  key={g}
                  className="px-3 py-1 text-xs font-semibold tracking-widest uppercase text-white/70 border border-white/20 rounded-full glass"
                >
                  {g}
                </span>
              ))}
            </div>
          )}

          {/* Title */}
          <h1 className="text-4xl sm:text-6xl lg:text-7xl font-black text-white leading-none tracking-tight text-shadow-lg">
            {movie?.title}
          </h1>

          {/* Year + Rating */}
          <div className="flex items-center gap-4 text-white/60 text-sm font-medium">
            <span>{movie?.year}</span>
            {movie?.rating && (
              <>
                <span className="w-1 h-1 rounded-full bg-white/30" />
                <span className="flex items-center gap-1">
                  <span className="text-amber-400">★</span>
                  {movie.rating.toFixed(1)}
                </span>
              </>
            )}
          </div>

          {/* Overview */}
          {movie?.overview && (
            <p className="max-w-lg text-white/55 text-sm leading-relaxed mt-1 line-clamp-3">
              {movie.overview}
            </p>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
