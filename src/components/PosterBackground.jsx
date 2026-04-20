import React, { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export default function PosterBackground({ posterUrl, loading }) {
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
          transition={{ duration: 1.4, ease: 'easeInOut' }}
        >
          <div
            className="absolute inset-0 bg-center bg-cover"
            style={{ backgroundImage: `url(${displayed})` }}
          />
          {/* Dark overlay */}
          <div className="absolute inset-0" style={{ background: 'rgba(8,8,16,0.72)' }} />
          {/* Vignette */}
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
