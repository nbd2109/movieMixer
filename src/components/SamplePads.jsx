import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { track, Events } from '../lib/track'

export const PADS = [
  // Row 1
  { id: 'Action',      label: 'Acción',     color: '#c0392b' },
  { id: 'Adventure',   label: 'Aventura',   color: '#d35400' },
  { id: 'Thriller',    label: 'Thriller',   color: '#922b21' },
  { id: 'Crime',       label: 'Crimen',     color: '#7b241c' },
  // Row 2
  { id: 'Drama',       label: 'Drama',      color: '#1a5276' },
  { id: 'Romance',     label: 'Romance',    color: '#76448a' },
  { id: 'Comedy',      label: 'Comedia',    color: '#1e8449' },
  { id: 'Horror',      label: 'Terror',     color: '#512e5f' },
  // Row 3
  { id: 'Sci-Fi',      label: 'Sci-Fi',     color: '#0e6655' },
  { id: 'Fantasy',     label: 'Fantasía',   color: '#4a235a' },
  { id: 'Mystery',     label: 'Misterio',   color: '#154360' },
  { id: 'Documentary', label: 'Doc.',       color: '#1a5276' },
  // Row 4
  { id: 'Biography',   label: 'Biografía',  color: '#7d6608' },
  { id: 'History',     label: 'Historia',   color: '#784212' },
  { id: 'War',         label: 'Guerra',     color: '#4d5656' },
  { id: 'Animation',   label: 'Animación',  color: '#0e6251' },
]

export default function SamplePads({ selected, onChange }) {
  function toggle(id) {
    const next = selected.includes(id)
      ? selected.filter(g => g !== id)
      : [...selected, id]
    onChange(next)
    track(Events.PAD_TOGGLED, { genre: id, active: !selected.includes(id), total_active: next.length })
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      <div className="flex items-center justify-between">
        <span
          className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
          style={{ color: 'rgba(255,255,255,0.45)' }}
        >
          Géneros
        </span>
        <AnimatePresence>
          {selected.length > 0 && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => onChange([])}
              className="text-[10px] tracking-widest uppercase transition-colors"
              style={{ color: 'rgba(255,255,255,0.25)' }}
            >
              limpiar
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      <div className="grid gap-1" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        {PADS.map((pad) => {
          const active = selected.includes(pad.id)
          return (
            <motion.button
              key={pad.id}
              onClick={() => toggle(pad.id)}
              whileTap={{ scale: 0.93 }}
              className="relative flex items-center justify-center rounded-md py-2 select-none overflow-hidden"
              style={{
                background: active ? pad.color : 'rgba(255,255,255,0.04)',
                border:     `1px solid ${active ? pad.color : 'rgba(255,255,255,0.07)'}`,
              }}
            >
              <span
                className="text-[9px] font-semibold tracking-wide relative z-10 leading-none"
                style={{ color: active ? 'rgba(255,255,255,0.95)' : 'rgba(255,255,255,0.35)' }}
              >
                {pad.label}
              </span>
            </motion.button>
          )
        })}
      </div>

      <p
        className="text-[10px] tracking-wide"
        style={{ color: 'rgba(255,255,255,0.2)' }}
      >
        {selected.length === 0
          ? 'Sin filtro de género'
          : selected.length === 1
          ? PADS.find(p => p.id === selected[0])?.label
          : selected.map(id => PADS.find(p => p.id === id)?.label ?? id).join(' · ')
        }
      </p>
    </div>
  )
}
