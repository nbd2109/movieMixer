import React, { useId, useRef, useState, useEffect } from 'react'
import {
  motion,
  useMotionValue,
  useMotionValueEvent,
  useSpring,
  useTransform,
  useVelocity,
} from 'framer-motion'

// ── Haptic helper — safe fallback para iOS y navegadores sin soporte ──────────
function vibrate(pattern) {
  try {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(pattern)
    }
  } catch (_) {}
}

export default function MixerSlider({
  label,
  leftLabel,
  rightLabel,
  value,
  onChange,
  color = '#ffffff',
}) {
  const id = useId()

  // ── 3. ODÓMETRO — spring counter + parallax vertical por velocidad ────────────
  // raw   → MotionValue que recibe el valor directo del slider
  // spring → versión suavizada con resorte (produce valores intermedios visibles)
  // velocity → derivada del spring para calcular dirección
  // yOffset → desplaza el número ±5px en sentido opuesto al movimiento,
  //           recortado por overflow-hidden → efecto ruleta/slot
  const raw      = useMotionValue(value)
  const spring   = useSpring(raw, { stiffness: 550, damping: 30, mass: 0.45 })
  const velocity = useVelocity(spring)
  const yOffset  = useTransform(velocity, [-500, 0, 500], [5, 0, -5])

  const [counter, setCounter] = useState(value)
  useMotionValueEvent(spring, 'change', (v) => setCounter(Math.round(v)))

  // Sincronizar cuando el valor cambia externamente (ej. carga de retención)
  useEffect(() => { raw.set(value) }, [value, raw])

  // ── 1. NEÓN DINÁMICO — CSS custom property que inyecta el glow al pseudo-elemento ──
  // El box-shadow del ::-webkit-slider-thumb lee --thumb-shadow via CSS.
  // La transición en CSS hace el fade in/out suave.
  const [isDragging, setIsDragging] = useState(false)
  const [isHovered,  setIsHovered]  = useState(false)

  const thumbShadow = isDragging
    ? `0 0 0 2px rgba(255,255,255,0.12), 0 2px 12px rgba(0,0,0,0.8), 0 0 20px ${color}, 0 0 40px ${color}55`
    : isHovered
    ? `0 0 0 1px rgba(255,255,255,0.18), 0 2px 10px rgba(0,0,0,0.7), 0 0 12px ${color}65`
    : `0 0 0 1px rgba(255,255,255,0.15), 0 2px 8px rgba(0,0,0,0.7)`

  // ── 2. FEEDBACK HÁPTICO — milestones cada 25% + paradas duras en 0/100 ────────
  const prevRef = useRef(value)
  function handleChange(newVal) {
    onChange(newVal)
    const prev = prevRef.current
    prevRef.current = newVal
    if (newVal === 0 || newVal === 100) {
      vibrate([50])                                      // parada dura — más intenso
    } else if (Math.floor(prev / 25) !== Math.floor(newVal / 25)) {
      vibrate([20])                                      // cruce de 25 / 50 / 75
    }
  }

  return (
    <div className="flex flex-col gap-1.5 w-full">

      {/* ── Cabecera: label + contador odómetro ── */}
      <div className="flex items-baseline justify-between">
        <label
          htmlFor={id}
          className="text-[10px] font-semibold tracking-[0.2em] uppercase select-none"
          style={{ color: 'rgba(255,255,255,0.45)' }}
        >
          {label}
        </label>

        {/*
          overflow-hidden recorta los píxeles superiores/inferiores del span.
          El yOffset mueve el texto verticalmente al ritmo del spring,
          creando la ilusión de que los dígitos ruedan dentro de una ventanilla.
        */}
        <div
          className="overflow-hidden"
          style={{ height: '1.1em', lineHeight: '1.1em', minWidth: '2.5em', textAlign: 'right' }}
        >
          <motion.span
            className="block text-xs font-mono tabular-nums"
            style={{ color: 'rgba(255,255,255,0.6)', y: yOffset }}
          >
            {counter}
          </motion.span>
        </div>
      </div>

      {/* ── Slider ── */}
      <input
        id={id}
        type="range"
        min={0} max={100} step={1}
        value={value}
        onChange={(e) => handleChange(Number(e.target.value))}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => { setIsHovered(false); setIsDragging(false) }}
        onMouseDown={() => setIsDragging(true)}
        onMouseUp={() => setIsDragging(false)}
        onTouchStart={() => setIsDragging(true)}
        onTouchEnd={() => setIsDragging(false)}
        className="mixer-slider"
        style={{
          background: `linear-gradient(to right, ${color} ${value}%, rgba(255,255,255,0.1) ${value}%)`,
          '--thumb-shadow': thumbShadow,  // CSS custom property → leída por el pseudo-elemento en index.css
        }}
      />

      {/* ── Etiquetas extremos ── */}
      <div
        className="flex justify-between text-[10px] select-none"
        style={{ color: 'rgba(255,255,255,0.22)' }}
      >
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>

    </div>
  )
}
