import React, { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

// Fondo inicial: sin película, gradiente cinematográfico discreto
function IdleBackground() {
  return (
    <div className="absolute inset-0">
      {/* Dos nebulosas de color muy sutiles */}
      <div
        className="absolute inset-0"
        style={{
          background: [
            'radial-gradient(ellipse 70% 60% at 25% 45%, rgba(60,30,90,0.35) 0%, transparent 70%)',
            'radial-gradient(ellipse 55% 50% at 75% 60%, rgba(15,40,70,0.3) 0%, transparent 70%)',
          ].join(', '),
        }}
      />
      {/* Vignette igual que con póster para mantener consistencia */}
      <div
        className="absolute inset-0"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 20%, rgba(8,8,16,0.92) 100%)',
        }}
      />
    </div>
  )
}

export default function PosterBackground({ posterUrl, loading }) {
  const [displayed, setDisplayed] = useState(posterUrl)

  useEffect(() => {
    if (!loading && posterUrl) setDisplayed(posterUrl)
  }, [posterUrl, loading])

  // Sin película todavía → fondo discreto
  if (!displayed) return <div className="absolute inset-0 z-0"><IdleBackground /></div>

  return (
    <div className="absolute inset-0 z-0 overflow-hidden">
      <AnimatePresence mode="sync">
        <motion.div
          key={displayed}
          className="absolute inset-0"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 1.4, ease: 'easeInOut' }}
        >
          <div
            className="absolute inset-0 bg-center bg-cover"
            style={{ backgroundImage: `url(${displayed})` }}
          />
          <div className="absolute inset-0" style={{ background: 'rgba(8,8,16,0.72)' }} />
          <div
            className="absolute inset-0"
            style={{
              background: 'radial-gradient(ellipse at center, transparent 25%, rgba(8,8,16,0.88) 100%)',
            }}
          />
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
