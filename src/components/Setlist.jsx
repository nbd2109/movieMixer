import React from 'react'
import { AnimatePresence, motion } from 'framer-motion'

export default function Setlist({ items, currentTitle, onRestore }) {
  // Solo mostrar cuando hay al menos una película anterior
  const previous = items.filter(m => m.title !== currentTitle)
  if (previous.length === 0) return null

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 8 }}
        transition={{ duration: 0.3 }}
        className="flex items-center gap-2 flex-wrap justify-center"
      >
        <span
          className="text-[8px] tracking-[0.2em] uppercase flex-shrink-0"
          style={{ color: 'rgba(255,255,255,0.18)' }}
        >
          Antes
        </span>
        {previous.map((m) => (
          <motion.button
            key={m.title + m.year}
            onClick={() => onRestore(m)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[9px] tracking-wide truncate max-w-[140px]"
            style={{
              background:  'rgba(255,255,255,0.04)',
              border:      '1px solid rgba(255,255,255,0.08)',
              color:       'rgba(255,255,255,0.35)',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'rgba(255,255,255,0.65)'}
            onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.35)'}
            title={`${m.title} (${m.year})`}
          >
            <span className="truncate">{m.title}</span>
            <span style={{ color: 'rgba(255,255,255,0.2)', flexShrink: 0 }}>{m.year}</span>
          </motion.button>
        ))}
      </motion.div>
    </AnimatePresence>
  )
}
