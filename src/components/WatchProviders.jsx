import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { track, Events } from '../lib/track'
import { useWatchProviders } from '../hooks/useWatchProviders'

export default function WatchProviders({ tmdbId, movieTitle }) {
  const providers = useWatchProviders(tmdbId)

  const streaming = providers?.flatrate ?? []
  const rent      = providers?.rent ?? []
  const link      = providers?.link

  // Nada para mostrar todavía
  if (!providers || (streaming.length === 0 && rent.length === 0)) return null

  function handleClick(providerName) {
    track(Events.WHERE_TO_WATCH_CLICKED, {
      provider: providerName,
      title: movieTitle,
      tmdb_id: tmdbId,
    })
    if (link) window.open(link, '_blank', 'noopener')
  }

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.4, delay: 0.15 }}
        className="flex flex-col items-center gap-2 pointer-events-auto"
      >
        {streaming.length > 0 && (
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-white/30 text-[9px] tracking-[0.25em] uppercase">
              Ver en
            </span>
            <div className="flex items-center gap-2">
              {streaming.map((p) => (
                <motion.button
                  key={p.id}
                  onClick={() => handleClick(p.name)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                  title={p.name}
                  className="rounded-lg overflow-hidden"
                  style={{ width: 36, height: 36 }}
                >
                  <img
                    src={p.logo}
                    alt={p.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {streaming.length === 0 && rent.length > 0 && (
          <div className="flex flex-col items-center gap-1.5">
            <span className="text-white/30 text-[9px] tracking-[0.25em] uppercase">
              Alquilar en
            </span>
            <div className="flex items-center gap-2">
              {rent.map((p) => (
                <motion.button
                  key={p.id}
                  onClick={() => handleClick(p.name)}
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.95 }}
                  title={p.name}
                  className="rounded-lg overflow-hidden opacity-70"
                  style={{ width: 36, height: 36 }}
                >
                  <img
                    src={p.logo}
                    alt={p.name}
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </motion.button>
              ))}
            </div>
          </div>
        )}

        {/* JustWatch attribution — required by TMDB ToS when showing provider data */}
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => track(Events.WHERE_TO_WATCH_CLICKED, { provider: 'justwatch', title: movieTitle })}
            className="text-white/20 hover:text-white/40 text-[9px] tracking-wide transition-colors"
          >
            via JustWatch ↗
          </a>
        )}
      </motion.div>
    </AnimatePresence>
  )
}
