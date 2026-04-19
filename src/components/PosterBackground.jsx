import React, { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export default function PosterBackground({ posterUrl, loading }) {
  // Keep previous URL while the new one loads for a smooth crossfade
  const [displayed, setDisplayed] = useState(posterUrl)

  useEffect(() => {
    if (!loading && posterUrl) setDisplayed(posterUrl)
  }, [posterUrl, loading])

  return (
    <div className="absolute inset-0 z-0 overflow-hidden">
      <AnimatePresence mode="sync">
        <motion.div
          key={displayed}
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.2, ease: 'easeInOut' }}
        >
          {/* Poster image */}
          <div
            className="absolute inset-0 bg-center bg-cover"
            style={{ backgroundImage: `url(${displayed})` }}
          />
          {/* Heavy vignette + dark overlay so text stays readable */}
          <div className="absolute inset-0 bg-black/65" />
          <div className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse at center, transparent 20%, rgba(0,0,0,0.85) 100%)',
            }}
          />
        </motion.div>
      </AnimatePresence>

      {/* Subtle scanline texture */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)',
        }}
      />
    </div>
  )
}
