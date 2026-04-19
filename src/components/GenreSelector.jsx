import React from 'react'
import { motion } from 'framer-motion'

export const GENRES = [
  { id: 'Action',      label: 'Accion',     emoji: '💥' },
  { id: 'Adventure',   label: 'Aventura',   emoji: '🗺️' },
  { id: 'Animation',   label: 'Animacion',  emoji: '🎨' },
  { id: 'Biography',   label: 'Biografia',  emoji: '📖' },
  { id: 'Comedy',      label: 'Comedia',    emoji: '😂' },
  { id: 'Crime',       label: 'Crimen',     emoji: '🔫' },
  { id: 'Documentary', label: 'Documental', emoji: '🎥' },
  { id: 'Drama',       label: 'Drama',      emoji: '🎭' },
  { id: 'Fantasy',     label: 'Fantasia',   emoji: '🧙' },
  { id: 'History',     label: 'Historia',   emoji: '🏛️' },
  { id: 'Horror',      label: 'Terror',     emoji: '👻' },
  { id: 'Music',       label: 'Musica',     emoji: '🎵' },
  { id: 'Mystery',     label: 'Misterio',   emoji: '🔍' },
  { id: 'Romance',     label: 'Romance',    emoji: '❤️' },
  { id: 'Sci-Fi',      label: 'Sci-Fi',     emoji: '🚀' },
  { id: 'Thriller',    label: 'Thriller',   emoji: '😱' },
  { id: 'War',         label: 'Guerra',     emoji: '⚔️' },
  { id: 'Western',     label: 'Western',    emoji: '🤠' },
]

export default function GenreSelector({ selected, onChange }) {
  function toggle(id) {
    if (selected.includes(id)) {
      onChange(selected.filter((g) => g !== id))
    } else {
      onChange([...selected, id])
    }
  }

  return (
    <motion.div
      className="flex flex-col gap-3 w-full"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="flex items-center gap-2 text-white/90 font-semibold text-sm tracking-widest uppercase select-none">
          <span className="text-base">🎬</span>
          Generos
        </span>
        {selected.length > 0 && (
          <motion.button
            onClick={() => onChange([])}
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            className="text-white/30 hover:text-white/60 text-xs tracking-widest uppercase transition-colors"
          >
            limpiar
          </motion.button>
        )}
      </div>

      {/* Genre pills */}
      <div className="flex flex-wrap gap-2">
        {GENRES.map((g, i) => {
          const active = selected.includes(g.id)
          return (
            <motion.button
              key={g.id}
              onClick={() => toggle(g.id)}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2, delay: i * 0.02 }}
              whileTap={{ scale: 0.93 }}
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold
                tracking-wide border transition-all duration-200 select-none
                ${active
                  ? 'bg-amber-400 border-amber-400 text-black shadow-lg shadow-amber-400/20'
                  : 'glass border-white/10 text-white/60 hover:text-white hover:border-white/25'
                }
              `}
            >
              <span>{g.emoji}</span>
              <span>{g.label}</span>
            </motion.button>
          )
        })}
      </div>

      {/* Hint */}
      <p className="text-white/20 text-xs px-1">
        {selected.length === 0
          ? 'Sin filtro de genero — sorprendeme'
          : `${selected.length} genero${selected.length > 1 ? 's' : ''} seleccionado${selected.length > 1 ? 's' : ''}`
        }
      </p>
    </motion.div>
  )
}
