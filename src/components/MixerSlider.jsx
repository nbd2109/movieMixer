import React, { useId } from 'react'

export default function MixerSlider({
  label,
  leftLabel,
  rightLabel,
  value,
  onChange,
  color = '#ffffff',
}) {
  const id  = useId()
  const pct = value

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
        <span
          className="text-xs font-mono tabular-nums"
          style={{ color: 'rgba(255,255,255,0.6)' }}
        >
          {pct}
        </span>
      </div>

      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mixer-slider"
        style={{
          background: `linear-gradient(to right, ${color} ${pct}%, rgba(255,255,255,0.1) ${pct}%)`,
        }}
      />

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
