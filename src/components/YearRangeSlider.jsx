import React from 'react'
import { motion } from 'framer-motion'

const MIN_YEAR = 1920
const MAX_YEAR = 2026

export default function YearRangeSlider({ yearFrom, yearTo, onChangeFrom, onChangeTo }) {
  const range   = MAX_YEAR - MIN_YEAR
  const fromPct = ((yearFrom - MIN_YEAR) / range) * 100
  const toPct   = ((yearTo   - MIN_YEAR) / range) * 100

  return (
    <motion.div
      className="flex flex-col gap-2 w-full"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.15 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="flex items-center gap-2 text-white/90 font-semibold text-sm tracking-widest uppercase select-none">
          <span className="text-base">📅</span>
          Época
        </span>
        <motion.span
          key={`${yearFrom}-${yearTo}`}
          initial={{ scale: 1.3, opacity: 0.5 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="text-white font-mono font-bold text-sm tabular-nums"
        >
          {yearFrom} – {yearTo}
        </motion.span>
      </div>

      {/* Track container */}
      <div className="relative h-8 flex items-center">
        {/* Base track */}
        <div className="absolute inset-x-0 h-2 rounded-full bg-white/10" />

        {/* Filled range */}
        <div
          className="absolute h-2 rounded-full bg-amber-400"
          style={{ left: `${fromPct}%`, width: `${toPct - fromPct}%` }}
        />

        {/* FROM input — pointer-events: none on track, all on thumb (via CSS) */}
        <input
          type="range"
          min={MIN_YEAR}
          max={MAX_YEAR}
          step={1}
          value={yearFrom}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v < yearTo) onChangeFrom(v)
          }}
          className="year-slider from"
        />

        {/* TO input */}
        <input
          type="range"
          min={MIN_YEAR}
          max={MAX_YEAR}
          step={1}
          value={yearTo}
          onChange={(e) => {
            const v = Number(e.target.value)
            if (v > yearFrom) onChangeTo(v)
          }}
          className="year-slider to"
        />
      </div>

      {/* Axis labels */}
      <div className="flex justify-between px-1 text-white/35 text-xs select-none">
        <span>{MIN_YEAR}</span>
        <span>Clasico &larr; &rarr; Moderno</span>
        <span>{MAX_YEAR}</span>
      </div>
    </motion.div>
  )
}
