import React, { useId } from 'react'
import { motion } from 'framer-motion'

/**
 * Props:
 *  label      – string, e.g. "Adrenalina"
 *  emoji      – string, e.g. "⚡"
 *  leftLabel  – low-end description
 *  rightLabel – high-end description
 *  value      – number 0-100
 *  onChange   – (newValue: number) => void
 *  color      – tailwind-like hex or css color for the filled track
 */
export default function MixerSlider({
  label,
  emoji,
  leftLabel,
  rightLabel,
  value,
  onChange,
  color = '#ffffff',
}) {
  const id = useId()
  const pct = value // 0-100

  const trackStyle = {
    background: `linear-gradient(to right, ${color} ${pct}%, rgba(255,255,255,0.12) ${pct}%)`,
  }

  return (
    <motion.div
      className="flex flex-col gap-2 w-full"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
    >
      {/* Header row */}
      <div className="flex items-center justify-between px-1">
        <label htmlFor={id} className="flex items-center gap-2 text-white/90 font-semibold text-sm tracking-widest uppercase select-none">
          <span className="text-base">{emoji}</span>
          {label}
        </label>
        <motion.span
          key={value}
          initial={{ scale: 1.4, opacity: 0.5 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.2 }}
          className="text-white font-mono font-bold text-sm tabular-nums"
        >
          {pct}%
        </motion.span>
      </div>

      {/* Slider */}
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mixer-slider"
        style={trackStyle}
      />

      {/* Axis labels */}
      <div className="flex justify-between px-1 text-white/35 text-xs select-none">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </motion.div>
  )
}
