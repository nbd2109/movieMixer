import React from 'react'
import { motion } from 'framer-motion'

const OPTIONS = [
  { id: null,     label: 'Todas' },
  { id: 'short',  label: '< 90 min' },
  { id: 'medium', label: '~ 2h' },
  { id: 'long',   label: '+ 2h30' },
]

export default function RuntimeFilter({ value, onChange }) {
  return (
    <div className="flex flex-col gap-1.5 w-full">
      <span
        className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
        style={{ color: 'rgba(255,255,255,0.45)' }}
      >
        Duración
      </span>
      <div className="flex gap-1.5">
        {OPTIONS.map((opt) => {
          const active = value === opt.id
          return (
            <motion.button
              key={String(opt.id)}
              onClick={() => onChange(opt.id)}
              whileTap={{ scale: 0.93 }}
              className="flex-1 py-1.5 rounded-md text-[10px] font-semibold tracking-wide select-none"
              style={{
                background: active ? 'rgba(232,160,32,0.15)' : 'rgba(255,255,255,0.04)',
                border:     `1px solid ${active ? 'rgba(232,160,32,0.45)' : 'rgba(255,255,255,0.07)'}`,
                color:      active ? '#e8a020' : 'rgba(255,255,255,0.35)',
              }}
            >
              {opt.label}
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
