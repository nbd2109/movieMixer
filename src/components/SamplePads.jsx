import React from 'react'
import { motion } from 'framer-motion'
import { track, Events } from '../lib/track'

// 4x4 grid — ordered by group so each row has visual coherence
export const PADS = [
  // Row 1 — Alta energía
  { id: 'Action',      label: 'ACCION',    emoji: '💥', color: '#ef4444' },
  { id: 'Adventure',   label: 'AVENTURA',  emoji: '🗺️',  color: '#f97316' },
  { id: 'Thriller',    label: 'THRILLER',  emoji: '😱', color: '#dc2626' },
  { id: 'Crime',       label: 'CRIMEN',    emoji: '🔫', color: '#b91c1c' },
  // Row 2 — Emoción
  { id: 'Drama',       label: 'DRAMA',     emoji: '🎭', color: '#3b82f6' },
  { id: 'Romance',     label: 'ROMANCE',   emoji: '❤️',  color: '#ec4899' },
  { id: 'Comedy',      label: 'COMEDIA',   emoji: '😂', color: '#22c55e' },
  { id: 'Horror',      label: 'TERROR',    emoji: '👻', color: '#7c3aed' },
  // Row 3 — Mente
  { id: 'Sci-Fi',      label: 'SCI-FI',    emoji: '🚀', color: '#06b6d4' },
  { id: 'Fantasy',     label: 'FANTASIA',  emoji: '🧙', color: '#8b5cf6' },
  { id: 'Mystery',     label: 'MISTERIO',  emoji: '🔍', color: '#6366f1' },
  { id: 'Documentary', label: 'DOCUMENTAL',emoji: '🎥', color: '#0891b2' },
  // Row 4 — Especial
  { id: 'Biography',   label: 'BIOGRAFIA', emoji: '📖', color: '#eab308' },
  { id: 'History',     label: 'HISTORIA',  emoji: '🏛️',  color: '#d97706' },
  { id: 'War',         label: 'GUERRA',    emoji: '⚔️',  color: '#78716c' },
  { id: 'Animation',   label: 'ANIMACION', emoji: '🎨', color: '#10b981' },
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
      {/* Section label */}
      <div className="flex items-center justify-between px-1">
        <span className="text-white/40 text-[10px] tracking-[0.25em] uppercase font-medium">
          Samples
        </span>
        {selected.length > 0 && (
          <motion.button
            onClick={() => onChange([])}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-white/30 hover:text-white/60 text-[10px] tracking-widest uppercase transition-colors"
          >
            clear
          </motion.button>
        )}
      </div>

      {/* 4×4 pad grid */}
      <div
        className="grid gap-1.5 w-full"
        style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}
      >
        {PADS.map((pad, i) => {
          const active = selected.includes(pad.id)
          return (
            <motion.button
              key={pad.id}
              onClick={() => toggle(pad.id)}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.15, delay: i * 0.015 }}
              whileTap={{ scale: 0.88 }}
              className="relative flex flex-col items-center justify-center rounded-lg py-2 px-1 select-none overflow-hidden transition-all duration-150"
              style={{
                background: active
                  ? `${pad.color}`
                  : 'rgba(255,255,255,0.04)',
                border: `1px solid ${active ? pad.color : 'rgba(255,255,255,0.08)'}`,
                boxShadow: active
                  ? `0 0 12px ${pad.color}66, 0 0 24px ${pad.color}33`
                  : 'none',
              }}
            >
              {/* Active glow overlay */}
              {active && (
                <motion.div
                  className="absolute inset-0 rounded-lg"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: [0.3, 0.1, 0.3] }}
                  transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
                  style={{ background: `radial-gradient(circle, ${pad.color}66 0%, transparent 70%)` }}
                />
              )}

              <span className="text-base leading-none mb-0.5 relative z-10">
                {pad.emoji}
              </span>
              <span
                className="text-[8px] font-black tracking-widest leading-none relative z-10"
                style={{ color: active ? '#000' : 'rgba(255,255,255,0.4)' }}
              >
                {pad.label}
              </span>

              {/* Active indicator dot */}
              {active && (
                <div
                  className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
                  style={{ background: 'rgba(0,0,0,0.5)' }}
                />
              )}
            </motion.button>
          )
        })}
      </div>

      {/* Status line — conversacional, sin jerga técnica */}
      <p className="text-white/20 text-[10px] px-1 tracking-wide">
        {selected.length === 0
          ? 'Sorprendeme · sin filtro de genero'
          : selected.length === 1
          ? `Solo ${PADS.find(p => p.id === selected[0])?.label.toLowerCase() ?? selected[0]}`
          : `${selected.map(id => PADS.find(p => p.id === id)?.label.toLowerCase() ?? id).join(' + ')}`
        }
      </p>
    </div>
  )
}
