import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { track } from '../lib/track'

export const EFFECTS = [
  {
    id:    'wildcard',
    label: 'AZAR',
    emoji: '🎲',
    color: '#f59e0b',
    desc:  'Rompe los filtros',
  },
  {
    id:    'cult',
    label: 'CULTO',
    emoji: '💎',
    color: '#8b5cf6',
    desc:  'Joyas ocultas',
  },
  {
    id:    'retro',
    label: 'RETRO',
    emoji: '📼',
    color: '#f97316',
    desc:  'Antes del 2000',
  },
  {
    id:    'dark',
    label: 'SOMBRA',
    emoji: '🌑',
    color: '#ef4444',
    desc:  'Solo oscuridad',
  },
]

// Multi-layer LED glow — da la sensación de backlight real
function glowShadow(color) {
  return [
    `0 0 0 1px ${color}55`,
    `0 0 8px  ${color}66`,
    `0 0 20px ${color}44`,
    `0 0 45px ${color}22`,
    `inset 0 0 16px ${color}18`,
  ].join(', ')
}

export default function FxUnit({ active, onChange }) {
  function toggle(id) {
    const isOn = active.includes(id)
    const next = isOn ? active.filter(f => f !== id) : [...active, id]
    onChange(next)
    track('fx_toggled', { fx: id, active: !isOn, total_active: next.length })
  }

  const anyActive = active.length > 0

  return (
    <div className="flex flex-col gap-2 w-full">

      {/* ── Header ── */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          {/* LED que cicla colores cuando hay FX activo */}
          <motion.div
            className="w-1.5 h-1.5 rounded-full"
            animate={anyActive
              ? {
                  backgroundColor: ['#f59e0b', '#8b5cf6', '#f97316', '#ef4444', '#f59e0b'],
                  boxShadow: [
                    '0 0 5px #f59e0b',
                    '0 0 5px #8b5cf6',
                    '0 0 5px #f97316',
                    '0 0 5px #ef4444',
                    '0 0 5px #f59e0b',
                  ],
                }
              : { backgroundColor: 'rgba(255,255,255,0.15)', boxShadow: 'none' }
            }
            transition={anyActive
              ? { duration: 3, repeat: Infinity, ease: 'linear' }
              : { duration: 0.3 }
            }
          />
          <span className="text-white/40 text-[10px] tracking-[0.25em] uppercase font-medium">
            Efectos
          </span>
        </div>

        <AnimatePresence>
          {anyActive && (
            <motion.button
              key="clear"
              initial={{ opacity: 0, x: 8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 8 }}
              onClick={() => onChange([])}
              className="text-white/30 hover:text-white/60 text-[10px] tracking-widest uppercase transition-colors"
            >
              clear
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* ── 2×2 grid ── */}
      <div className="grid grid-cols-2 gap-1.5">
        {EFFECTS.map((fx, i) => {
          const isActive = active.includes(fx.id)

          return (
            <motion.button
              key={fx.id}
              onClick={() => toggle(fx.id)}
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.2, delay: i * 0.04 }}
              whileTap={{ scale: 0.92 }}
              className="relative flex flex-col items-center justify-center py-3 px-2 rounded-xl overflow-hidden select-none"
              style={{
                background: isActive
                  ? `linear-gradient(145deg, ${fx.color}1a 0%, ${fx.color}0d 100%)`
                  : 'rgba(255,255,255,0.025)',
                border: `1px solid ${isActive ? fx.color + '88' : 'rgba(255,255,255,0.07)'}`,
                boxShadow: isActive ? glowShadow(fx.color) : 'none',
                transition: 'box-shadow 0.3s ease, border-color 0.3s ease, background 0.3s ease',
              }}
            >
              {/* Pulso radial cuando activo */}
              {isActive && (
                <motion.div
                  className="absolute inset-0 pointer-events-none rounded-xl"
                  animate={{ opacity: [0.2, 0.45, 0.2] }}
                  transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                  style={{
                    background: `radial-gradient(ellipse at 50% 40%, ${fx.color}55 0%, transparent 68%)`,
                  }}
                />
              )}

              {/* Bloom al activar — anillo que se expande y desvanece */}
              <AnimatePresence>
                {isActive && (
                  <motion.div
                    key="bloom"
                    className="absolute inset-0 rounded-xl pointer-events-none"
                    initial={{ opacity: 0.6, scale: 0.7 }}
                    animate={{ opacity: 0, scale: 1.4 }}
                    exit={{}}
                    transition={{ duration: 0.5, ease: 'easeOut' }}
                    style={{ border: `2px solid ${fx.color}`, borderRadius: '12px' }}
                  />
                )}
              </AnimatePresence>

              {/* LED dot */}
              <motion.div
                className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full"
                animate={isActive
                  ? {
                      backgroundColor: fx.color,
                      boxShadow: [`0 0 4px ${fx.color}`, `0 0 8px ${fx.color}`, `0 0 4px ${fx.color}`],
                    }
                  : { backgroundColor: 'rgba(255,255,255,0.12)', boxShadow: 'none' }
                }
                transition={isActive
                  ? { duration: 1.5, repeat: Infinity, ease: 'easeInOut' }
                  : { duration: 0.2 }
                }
              />

              {/* Emoji */}
              <motion.span
                className="text-xl leading-none mb-1 relative z-10"
                animate={isActive ? { scale: [1, 1.15, 1] } : { scale: 1 }}
                transition={isActive
                  ? { duration: 3, repeat: Infinity, ease: 'easeInOut' }
                  : {}
                }
              >
                {fx.emoji}
              </motion.span>

              {/* Label */}
              <span
                className="text-[9px] font-black tracking-[0.2em] leading-none relative z-10"
                style={{
                  color: isActive ? fx.color : 'rgba(255,255,255,0.35)',
                  textShadow: isActive ? `0 0 10px ${fx.color}88` : 'none',
                  transition: 'color 0.3s, text-shadow 0.3s',
                }}
              >
                {fx.label}
              </span>

              {/* Description */}
              <span
                className="text-[7px] mt-0.5 leading-none relative z-10 text-center"
                style={{
                  color: isActive ? `${fx.color}aa` : 'rgba(255,255,255,0.18)',
                  transition: 'color 0.3s',
                }}
              >
                {fx.desc}
              </span>
            </motion.button>
          )
        })}
      </div>
    </div>
  )
}
