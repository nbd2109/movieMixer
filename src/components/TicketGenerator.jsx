import React, { useRef } from 'react'
import { motion } from 'framer-motion'
import html2canvas from 'html2canvas'
import { TmdbAttributionInline } from './TmdbAttribution'
import { track, Events } from '../lib/track'

function SliderBar({ label, emoji, value, color }) {
  return (
    <div className="flex flex-col gap-1">
      <div className="flex justify-between items-center">
        <span className="text-xs font-bold tracking-widest uppercase text-white/80">
          {emoji} {label}
        </span>
        <span className="text-xs font-mono font-black text-white">{value}%</span>
      </div>
      <div className="h-2 rounded-full bg-white/10 overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
    </div>
  )
}

export default function TicketGenerator({ movie, sliders }) {
  const ticketRef = useRef(null)

  async function handleExtract() {
    if (!ticketRef.current) return
    try {
      const canvas = await html2canvas(ticketRef.current, {
        backgroundColor: null,
        scale: 3, // high-DPI for sharing
        useCORS: true,
        allowTaint: false,
      })
      const dataUrl = canvas.toDataURL('image/png')
      const a = document.createElement('a')
      a.href = dataUrl
      a.download = `cinemix-${movie.title.replace(/\s+/g, '-').toLowerCase()}.png`
      a.click()
      track(Events.TICKET_DOWNLOADED, { title: movie.title, year: movie.year })
    } catch (err) {
      console.error('html2canvas error:', err)
    }
  }

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Hidden ticket – rendered off-screen for capture */}
      <div
        ref={ticketRef}
        style={{
          position: 'fixed',
          left: '-9999px',
          top: 0,
          width: '390px',
          background: 'linear-gradient(160deg, #0a0a0f 0%, #12121a 100%)',
          borderRadius: '20px',
          overflow: 'hidden',
          padding: '0',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {/* Poster half */}
        <div
          style={{
            width: '100%',
            height: '280px',
            backgroundImage: `url(${movie?.posterUrl})`,
            backgroundSize: 'cover',
            backgroundPosition: 'center',
            position: 'relative',
          }}
        >
          <div style={{
            position: 'absolute', inset: 0,
            background: 'linear-gradient(to bottom, transparent 40%, rgba(10,10,15,1) 100%)',
          }} />
          <div style={{
            position: 'absolute', bottom: '20px', left: '24px', right: '24px',
          }}>
            <h2 style={{ color: '#fff', fontSize: '28px', fontWeight: 900, lineHeight: 1.1, margin: 0 }}>
              {movie?.title}
            </h2>
            <p style={{ color: 'rgba(255,255,255,0.5)', fontSize: '13px', margin: '6px 0 0' }}>
              {movie?.year} · ★ {movie?.rating?.toFixed(1)}
            </p>
          </div>
        </div>

        {/* Mix formula */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ color: 'rgba(255,255,255,0.35)', fontSize: '10px', letterSpacing: '3px', textTransform: 'uppercase', margin: 0 }}>
            Mi Fórmula Cinematográfica
          </p>

          {[
            { label: 'Adrenalina', emoji: '⚡', value: sliders.adrenaline, color: '#ef4444' },
            { label: 'Tensión', emoji: '🔮', value: sliders.tension, color: '#a855f7' },
            { label: 'Cerebro', emoji: '🧠', value: sliders.cerebro, color: '#3b82f6' },
          ].map((s) => (
            <div key={s.label} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '11px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase' }}>
                  {s.emoji} {s.label}
                </span>
                <span style={{ color: '#fff', fontSize: '11px', fontFamily: 'monospace', fontWeight: 900 }}>
                  {s.value}%
                </span>
              </div>
              <div style={{ height: '6px', borderRadius: '99px', background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                <div style={{ height: '100%', borderRadius: '99px', background: s.color, width: `${s.value}%` }} />
              </div>
            </div>
          ))}

          {/* Epoch */}
          <div style={{ paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.5)', fontSize: '12px' }}>
            📅 Época: <strong style={{ color: '#f59e0b' }}>{sliders.yearFrom} – {sliders.yearTo}</strong>
          </div>

          {/* Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
            <p style={{ color: 'rgba(255,255,255,0.2)', fontSize: '10px', letterSpacing: '2px' }}>
              CINE-MIXER
            </p>
            <TmdbAttributionInline />
          </div>
        </div>
      </div>

      {/* Visible CTA button */}
      <motion.button
        onClick={handleExtract}
        whileHover={{ scale: 1.04 }}
        whileTap={{ scale: 0.97 }}
        className="relative overflow-hidden w-full py-4 rounded-2xl font-bold text-sm tracking-widest uppercase text-black"
        style={{
          background: 'linear-gradient(135deg, #fbbf24 0%, #f59e0b 50%, #d97706 100%)',
          boxShadow: '0 0 32px rgba(251,191,36,0.35), 0 4px 16px rgba(0,0,0,0.5)',
        }}
      >
        {/* Shimmer sweep */}
        <motion.span
          className="absolute inset-0 pointer-events-none"
          style={{
            background: 'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.4) 50%, transparent 60%)',
          }}
          animate={{ x: ['-100%', '200%'] }}
          transition={{ duration: 2.5, repeat: Infinity, ease: 'easeInOut' }}
        />
        <span className="relative z-10">⬇ Extraer Mezcla</span>
      </motion.button>
    </div>
  )
}
