import React from 'react'

const MIN_VAL = 50   // = 5.0
const MAX_VAL = 81   // = >8

export function displayRating(v) {
  if (v >= 81) return '>8'
  return (v / 10).toFixed(1)
}

export default function RatingRangeSlider({ ratingFrom, ratingTo, onChangeFrom, onChangeTo }) {
  const range   = MAX_VAL - MIN_VAL
  const fromPct = ((ratingFrom - MIN_VAL) / range) * 100
  const toPct   = ((ratingTo   - MIN_VAL) / range) * 100

  return (
    <div className="flex flex-col gap-1.5 w-full">
      <div className="flex items-baseline justify-between">
        <span
          className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
          style={{ color: 'rgba(255,255,255,0.45)' }}
        >
          Nota
        </span>
        <span
          className="text-xs font-mono tabular-nums"
          style={{ color: 'rgba(255,255,255,0.6)' }}
        >
          {displayRating(ratingFrom)} – {displayRating(ratingTo)}
        </span>
      </div>

      <div className="relative h-6 flex items-center">
        <div className="absolute inset-x-0 h-[4px] rounded-full bg-white/10" />
        <div
          className="absolute h-[4px] rounded-full"
          style={{
            left:       `${fromPct}%`,
            width:      `${toPct - fromPct}%`,
            background: '#e8a020',
          }}
        />
        <input
          type="range"
          min={MIN_VAL} max={MAX_VAL} step={1}
          value={ratingFrom}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v < ratingTo) onChangeFrom(v)
          }}
          className="year-slider from"
        />
        <input
          type="range"
          min={MIN_VAL} max={MAX_VAL} step={1}
          value={ratingTo}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v > ratingFrom) onChangeTo(v)
          }}
          className="year-slider to"
        />
      </div>

      <div
        className="flex justify-between text-[10px] select-none"
        style={{ color: 'rgba(255,255,255,0.22)' }}
      >
        <span>Al menos, será entretenida.</span>
        <span>puede cambiar tu vida...</span>
      </div>
    </div>
  )
}
