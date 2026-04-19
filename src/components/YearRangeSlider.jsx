import React from 'react'
import { motion } from 'framer-motion'

const MIN_YEAR = 1970
const MAX_YEAR = 2026

export default function YearRangeSlider({ yearFrom, yearTo, onChangeFrom, onChangeTo }) {
  // Percentage positions for the visual fill
  const fromPct = ((yearFrom - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100
  const toPct = ((yearTo - MIN_YEAR) / (MAX_YEAR - MIN_YEAR)) * 100

  const trackFill = {
    left: `${fromPct}%`,
    width: `${toPct - fromPct}%`,
  }

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

      {/* Dual range container */}
      <div className="relative h-8 flex items-center">
        {/* Base track */}
        <div className="absolute inset-x-0 h-2 rounded-full bg-white/10" />
        {/* Filled range */}
        <div
          className="absolute h-2 rounded-full bg-amber-400"
          style={trackFill}
        />

        {/* FROM thumb */}
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
          className="absolute inset-0 w-full mixer-slider opacity-0 h-full cursor-pointer"
          style={{ zIndex: yearFrom > MAX_YEAR - 5 ? 5 : 3 }}
        />

        {/* TO thumb */}
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
          className="absolute inset-0 w-full mixer-slider opacity-0 h-full cursor-pointer"
          style={{ zIndex: 4 }}
        />

        {/* Visual thumbs */}
        <div
          className="absolute w-6 h-6 bg-white rounded-full shadow-lg border-2 border-black pointer-events-none z-10"
          style={{ left: `calc(${fromPct}% - 12px)` }}
        />
        <div
          className="absolute w-6 h-6 bg-amber-400 rounded-full shadow-lg border-2 border-black pointer-events-none z-10"
          style={{ left: `calc(${toPct}% - 12px)` }}
        />
      </div>

      {/* Axis labels */}
      <div className="flex justify-between px-1 text-white/35 text-xs select-none">
        <span>{MIN_YEAR}</span>
        <span>Clásico ← → Moderno</span>
        <span>{MAX_YEAR}</span>
      </div>
    </motion.div>
  )
}
