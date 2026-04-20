import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PosterBackground   from './components/PosterBackground'
import MovieDisplay       from './components/MovieDisplay'
import MixerSlider        from './components/MixerSlider'
import YearRangeSlider    from './components/YearRangeSlider'
import SamplePads         from './components/SamplePads'
import TmdbAttribution    from './components/TmdbAttribution'
import WatchProviders     from './components/WatchProviders'
import RuntimeFilter      from './components/RuntimeFilter'
import { useMix }         from './hooks/useMix'
import { useRetention }   from './hooks/useRetention'
import { track, Events }  from './lib/track'

const PANEL_W = '40%'
const SPRING  = { type: 'spring', damping: 36, stiffness: 280 }

const INITIAL_SLIDERS = {
  genres:   [],
  tone:     40,
  cerebro:  50,
  yearFrom: 1920,
  yearTo:   2024,
  runtime:  null,
}

export default function App() {
  const { getInitialSliders, saveSliders, welcomeMessage } = useRetention(INITIAL_SLIDERS)
  const [sliders, setSliders]     = useState(() => getInitialSliders())
  const [panelOpen, setPanelOpen] = useState(true)
  const [remixKey, setRemixKey]   = useState(0)
  const [spinning, setSpinning]   = useState(false)

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

      {/* ── Área de película — ocupa el lado izquierdo ── */}
      <motion.div
        className="absolute inset-y-0 left-0 z-10 flex flex-col items-center px-8"
        animate={{ right: panelOpen ? PANEL_W : '0%' }}
        transition={SPRING}
      >
        {/* Contenido centrado verticalmente */}
        <div className="flex-1 flex flex-col items-center justify-center gap-4 w-full min-h-0">
          <MovieDisplay movie={movie} loading={loading} />
          <WatchProviders tmdbId={movie?.tmdbId} movieTitle={movie?.title} />
        </div>

        {/* REMIX al fondo del mismo contenedor para que el centrado sea real */}
        <div className="pb-8 flex justify-center w-full flex-shrink-0">
          <motion.button
            onClick={handleRemix}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.93 }}
            disabled={loading}
            className="flex items-center gap-2 px-5 py-2 rounded-full font-semibold text-xs tracking-widest uppercase"
            style={{
              background:    'linear-gradient(135deg, #e8a020, #c07818)',
              color:         '#000',
              boxShadow:     loading ? 'none' : '0 0 20px rgba(232,160,32,0.4), 0 2px 12px rgba(0,0,0,0.6)',
              opacity:       loading ? 0.5 : 1,
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
        </div>
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

      {/* ── Toggle del panel — se mueve con el seam ── */}
      <motion.button
        onClick={() => setPanelOpen(o => !o)}
        whileTap={{ scale: 0.92 }}
        className="absolute top-4 z-30 flex items-center justify-center rounded-full"
        animate={{ right: panelOpen ? `calc(${PANEL_W} + 12px)` : '12px' }}
        transition={SPRING}
        style={{
          width: 32, height: 32,
          background: 'rgba(255,255,255,0.06)',
          border: '1px solid rgba(255,255,255,0.1)',
          color: 'rgba(255,255,255,0.5)',
          fontSize: 13,
        }}
      >
        <motion.span
          animate={{ rotate: panelOpen ? 0 : 180 }}
          transition={{ duration: 0.3 }}
          style={{ display: 'inline-block', lineHeight: 1 }}
        >
          →
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
            className="absolute top-14 z-50 px-4 py-1.5 rounded-full glass text-[10px] tracking-widest uppercase"
            style={{ left: '50%', transform: `translateX(-50%)`, color: 'rgba(255,255,255,0.35)' }}
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
            className="absolute top-14 z-50 px-5 py-2 rounded-xl glass text-center"
            style={{ left: '30%', transform: 'translateX(-50%)', border: '1px solid rgba(239,68,68,0.3)' }}
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
            className="absolute top-14 z-50 px-4 py-2 rounded-xl pointer-events-none"
            style={{
              left: '30%', transform: 'translateX(-50%)',
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

      {/* ══════════════════════════════════
          MESA DE MEZCLAS — panel lateral derecho
      ══════════════════════════════════ */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            key="panel"
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={SPRING}
            className="absolute right-0 inset-y-0 z-20 flex"
            style={{
              width:          PANEL_W,
              background:     'rgba(10,10,18,0.96)',
              backdropFilter: 'blur(40px)',
              borderLeft:     '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {/* Handle vertical — borde izquierdo del panel */}
            <div
              className="flex-shrink-0 flex items-center justify-center px-2 cursor-pointer"
              onClick={() => setPanelOpen(false)}
            >
              <div
                className="h-10 w-[3px] rounded-full"
                style={{ background: 'rgba(255,255,255,0.12)' }}
              />
            </div>

            {/* Contenido desplazable */}
            <div className="flex-1 overflow-y-auto py-5 pr-5 flex flex-col gap-5 min-h-0">

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

              <div style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }} />

              {/* Duración */}
              <section>
                <RuntimeFilter value={sliders.runtime} onChange={set('runtime')} />
              </section>

              {/* Attribution */}
              <div className="flex flex-col items-center gap-1 pt-1">
                <TmdbAttribution />
                <p
                  className="text-[8px] text-center leading-tight"
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
