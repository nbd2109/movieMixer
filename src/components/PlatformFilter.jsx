import React from 'react'

const PLATFORMS = [
  { id: 'netflix', label: 'Netflix' },
  { id: 'prime',   label: 'Prime'   },
  { id: 'disney',  label: 'Disney+' },
  { id: 'max',     label: 'Max'     },
  { id: 'apple',   label: 'Apple TV+' },
]

export default function PlatformFilter({ value, onChange }) {
  return (
    <div className="flex flex-col gap-2">
      <span
        className="text-[9px] font-semibold tracking-[0.22em] uppercase"
        style={{ color: 'rgba(255,255,255,0.3)' }}
      >
        Plataforma
      </span>

      <div className="flex flex-wrap gap-1.5">
        {PLATFORMS.map((p) => {
          const active = value === p.id
          return (
            <button
              key={p.id}
              onClick={() => onChange(active ? null : p.id)}
              className="text-[10px] font-semibold tracking-[0.08em] px-2.5 py-1 rounded transition-all duration-150"
              style={{
                background: active ? 'rgba(232,160,32,0.15)' : 'rgba(255,255,255,0.04)',
                border:     `1px solid ${active ? 'rgba(232,160,32,0.45)' : 'rgba(255,255,255,0.08)'}`,
                color:      active ? '#e8a020' : 'rgba(255,255,255,0.35)',
              }}
            >
              {p.label}
            </button>
          )
        })}
      </div>

      <p className="text-[8px] leading-tight" style={{ color: 'rgba(255,255,255,0.12)' }}>
        Disponibilidad vía JustWatch · TMDB
      </p>
    </div>
  )
}
