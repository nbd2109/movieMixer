import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PosterBackground   from './components/PosterBackground'
import MovieDisplay       from './components/MovieDisplay'
import MixerSlider        from './components/MixerSlider'
import YearRangeSlider    from './components/YearRangeSlider'
import SamplePads         from './components/SamplePads'
import TmdbAttribution    from './components/TmdbAttribution'
import WatchProviders     from './components/WatchProviders'
import { useMix }         from './hooks/useMix'
import { useRetention }   from './hooks/useRetention'
import { track, Events }  from './lib/track'

const PANEL_H   = '50vh'
const SPRING    = { type: 'spring', damping: 36, stiffness: 280 }

const INITIAL_SLIDERS = {
  genres:   [],
  tone:     40,
  cerebro:  50,
  yearFrom: 1920,
  yearTo:   2024,
}

export default function App() {
  const { getInitialSliders, saveSliders, welcomeMessage } = useRetention(INITIAL_SLIDERS)
  const [sliders, setSliders]       = useState(() => getInitialSliders())
  const [panelOpen, setPanelOpen]   = useState(true)
  const [remixKey, setRemixKey]     = useState(0)
  const [spinning, setSpinning]     = useState(false)

  const { movie, loading, error } = useMix(sliders, remixKey)

  function set(key) {
    return (val) => {
      setSliders((prev) => {
        const next = { ...prev, [key]: val }
        saveSliders(next)
        return next
      })
      track(Events.SLIDER_ADJUSTED, { slider: key, value: val })
    }
  }

  function handleRemix() {
    setRemixKey(k => k + 1)
    setSpinning(true)
    setTimeout(() => setSpinning(false), 550)
    track(Events.REMIX_CLICKED, { genres: sliders.genres, tone: sliders.tone, cerebro: sliders.cerebro })
  }

  return (
    <div className="relative w-full h-screen overflow-hidden select-none" style={{ background: '#080810' }}>

      {/* ── Poster ── */}
      <PosterBackground posterUrl={movie?.posterUrl} loading={loading} />

      {/* ── Movie info — bounded above the panel ── */}
      <motion.div
        className="absolute inset-x-0 top-0 z-10 flex flex-col items-center justify-center gap-4 px-4"
        animate={{ bottom: panelOpen ? PANEL_H : '0' }}
        transition={SPRING}
      >
        <MovieDisplay movie={movie} loading={loading} />
        <WatchProviders tmdbId={movie?.tmdbId} movieTitle={movie?.title} />
      </motion.div>

      {/* ── Logo ── */}
      <div className="absolute top-5 left-5 z-20 pointer-events-none">
        <span
          className="font-black text-base tracking-tight"
          style={{ color: 'rgba(255,255,255,0.9)', letterSpacing: '-0.01em' }}
        >
          CINE<span style={{ color: '#e8a020' }}>MIX</span>
        </span>
      </div>

      {/* ── Panel toggle ── */}
      <motion.button
        onClick={() => setPanelOpen(o => !o)}
        whileTap={{ scale: 0.92 }}
        className="absolute top-4 right-4 z-30 flex items-center justify-center rounded-full"
        style={{
          width: 32, height: 32,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.1)',
          color: 'rgba(255,255,255,0.5)',
          fontSize: 13,
        }}
      >
        <motion.span
          animate={{ rotate: panelOpen ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          style={{ display: 'inline-block', lineHeight: 1 }}
        >
          ↓
        </motion.span>
      </motion.button>

      {/* ── Badges ── */}
      <AnimatePresence>
        {error === 'backend_offline' && (
          <motion.div
            key="offline"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="absolute top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-1.5 rounded-full glass text-[10px] tracking-widest uppercase"
            style={{ color: 'rgba(255,255,255,0.35)' }}
          >
            Backend offline · modo demo
          </motion.div>
        )}
        {error?.code === 'no_genre_match' && (
          <motion.div
            key="no-match"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            className="absolute top-14 left-1/2 -translate-x-1/2 z-50 px-5 py-2 rounded-xl glass text-center"
            style={{ border: '1px solid rgba(239,68,68,0.3)' }}
          >
            <p className="text-red-400 text-[10px] font-semibold tracking-widest uppercase">Sin resultados</p>
            <p className="text-[10px] mt-0.5" style={{ color: 'rgba(255,255,255,0.3)' }}>
              Esa combinación de géneros no tiene película
            </p>
          </motion.div>
        )}
        {welcomeMessage && (
          <motion.div
            key="welcome"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="absolute top-14 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-xl pointer-events-none"
            style={{
              background: 'rgba(232,160,32,0.08)',
              border:     '1px solid rgba(232,160,32,0.2)',
            }}
          >
            <p className="text-[11px] font-medium" style={{ color: 'rgba(232,160,32,0.85)' }}>
              {welcomeMessage}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── REMIX button — sits at the seam ── */}
      <motion.div
        className="absolute left-1/2 -translate-x-1/2 z-30"
        animate={{ bottom: panelOpen ? `calc(${PANEL_H} - 20px)` : '28px' }}
        transition={SPRING}
      >
        <motion.button
          onClick={handleRemix}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.93 }}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2 rounded-full font-semibold text-xs tracking-widest uppercase"
          style={{
            background:  'linear-gradient(135deg, #e8a020, #c07818)',
            color:       '#000',
            boxShadow:   loading ? 'none' : '0 0 20px rgba(232,160,32,0.4), 0 2px 12px rgba(0,0,0,0.6)',
            opacity:     loading ? 0.5 : 1,
            letterSpacing: '0.15em',
          }}
        >
          <motion.span
            animate={{ rotate: spinning ? 360 : 0 }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
            style={{ display: 'inline-block' }}
          >
            ↻
          </motion.span>
          Mezclar
        </motion.button>
      </motion.div>

      {/* ══════════════════════════════════
          MESA DE MEZCLAS
      ══════════════════════════════════ */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            key="panel"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={SPRING}
            className="absolute bottom-0 inset-x-0 z-20 rounded-t-2xl flex flex-col"
            style={{
              height:     PANEL_H,
              background: 'rgba(10,10,18,0.96)',
              backdropFilter: 'blur(40px)',
              borderTop:  '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {/* Handle */}
            <div className="flex-shrink-0 flex justify-center pt-2.5 pb-1">
              <div
                className="w-8 h-[3px] rounded-full cursor-pointer"
                style={{ background: 'rgba(255,255,255,0.12)' }}
                onClick={() => setPanelOpen(false)}
              />
            </div>

            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto px-5 pb-5 flex flex-col gap-5 min-h-0">

              {/* Canales */}
              <section className="flex flex-col gap-4">
                <MixerSlider
                  label="Tono"
                  leftLabel="Comedia · Familiar"
                  rightLabel="Oscuro · Tenso"
                  value={sliders.tone}
                  onChange={set('tone')}
                  color="#a57ce0"
                />
                <MixerSlider
                  label="Cerebro"
                  leftLabel="Blockbuster"
                  rightLabel="Autor"
                  value={sliders.cerebro}
                  onChange={set('cerebro')}
                  color="#5b9bd5"
                />
              </section>

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />

              {/* Pads */}
              <section>
                <SamplePads
                  selected={sliders.genres}
                  onChange={set('genres')}
                />
              </section>

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />

              {/* Época */}
              <section>
                <YearRangeSlider
                  yearFrom={sliders.yearFrom}
                  yearTo={sliders.yearTo}
                  onChangeFrom={set('yearFrom')}
                  onChangeTo={set('yearTo')}
                />
              </section>

              {/* Attribution */}
              <div className="flex flex-col items-center gap-1 pt-1">
                <TmdbAttribution />
                <p
                  className="text-[8px] text-center leading-tight max-w-xs"
                  style={{ color: 'rgba(255,255,255,0.12)' }}
                >
                  This application uses TMDB and the TMDB APIs but is not endorsed,
                  certified, or otherwise approved by TMDB.
                </p>
              </div>

            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </div>
  )
}
