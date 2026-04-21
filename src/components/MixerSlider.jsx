import React, { useId, useState, useEffect } from 'react'
import { motion, useMotionValue, useMotionValueEvent, useSpring, useTransform, useVelocity } from 'framer-motion'

export default function MixerSlider({ label, leftLabel, rightLabel, value, onChange, color = '#ffffff', formatValue }) {
  const id = useId()

  // Odómetro: spring suaviza el valor → digits intermedios visibles al arrastrar
  const raw      = useMotionValue(value)
  const spring   = useSpring(raw, { stiffness: 550, damping: 30, mass: 0.45 })
  const velocity = useVelocity(spring)
  const yOffset  = useTransform(velocity, [-500, 0, 500], [5, 0, -5])
  const [counter, setCounter] = useState(value)
  useMotionValueEvent(spring, 'change', (v) => setCounter(Math.round(v)))
  useEffect(() => { raw.set(value) }, [value, raw])

  const displayValue = formatValue ? formatValue(counter) : counter

  // Neón: --thumb-shadow se inyecta como CSS var y la lee el pseudo-elemento en index.css
  const [isDragging, setIsDragging] = useState(false)
  const [isHovered,  setIsHovered]  = useState(false)
  const thumbShadow = isDragging
    ? `0 0 0 2px rgba(255,255,255,0.12), 0 2px 12px rgba(0,0,0,0.8), 0 0 20px ${color}, 0 0 40px ${color}55`
    : isHovered
    ? `0 0 0 1px rgba(255,255,255,0.18), 0 2px 10px rgba(0,0,0,0.7), 0 0 12px ${color}65`
    : `0 0 0 1px rgba(255,255,255,0.15), 0 2px 8px rgba(0,0,0,0.7)`

  return (
    <div className="flex flex-col gap-1.5 w-full">

      <div className="flex items-baseline justify-between">
        <label
          htmlFor={id}
          className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
          style={{ color: 'rgba(255,255,255,0.45)' }}
        >
          {label}
        </label>
        <div className="overflow-hidden" style={{ height: '1.1em', lineHeight: '1.1em', minWidth: '2.5em', textAlign: 'right' }}>
          <motion.span
            className="block text-xs font-mono tabular-nums"
            style={{ color: 'rgba(255,255,255,0.6)', y: yOffset }}
          >
            {displayValue}
          </motion.span>
        </div>
      </div>

      <input
        id={id}
        type="range"
        min={0} max={100} step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => { setIsHovered(false); setIsDragging(false) }}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        className="mixer-slider"
        style={{
          background: `linear-gradient(to right, ${color} ${value}%, rgba(255,255,255,0.1) ${value}%)`,
          '--thumb-shadow': thumbShadow,
        }}
      />

      <div className="flex justify-between text-[10px] select-none" style={{ color: 'rgba(255,255,255,0.22)' }}>
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>

    </div>
  )
}
