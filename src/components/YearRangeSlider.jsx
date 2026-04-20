import React from 'react'

const MIN_YEAR = 1920
const MAX_YEAR = 2026

export default function YearRangeSlider({ yearFrom, yearTo, onChangeFrom, onChangeTo }) {
  const range   = MAX_YEAR - MIN_YEAR
  const fromPct = ((yearFrom - MIN_YEAR) / range) * 100
  const toPct   = ((yearTo   - MIN_YEAR) / range) * 100

  return (
    <div className="flex flex-col gap-1.5 w-full">
      <div className="flex items-baseline justify-between">
        <span
          className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
          style={{ color: 'rgba(255,255,255,0.45)' }}
        >
          Época
        </span>
        <span
          className="text-xs font-mono tabular-nums"
          style={{ color: 'rgba(255,255,255,0.6)' }}
        >
          {yearFrom} – {yearTo}
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
          min={MIN_YEAR} max={MAX_YEAR} step={1}
          value={yearFrom}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v < yearTo) onChangeFrom(v)
          }}
          className="year-slider from"
        />
        <input
          type="range"
          min={MIN_YEAR} max={MAX_YEAR} step={1}
          value={yearTo}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v > yearFrom) onChangeTo(v)
          }}
          className="year-slider to"
        />
      </div>

      <div
        className="flex justify-between text-[10px] select-none"
        style={{ color: 'rgba(255,255,255,0.22)' }}
      >
        <span>{MIN_YEAR}</span>
        <span>{MAX_YEAR}</span>
      </div>
    </div>
  )
}
