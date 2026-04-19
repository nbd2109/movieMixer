import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PosterBackground from './components/PosterBackground'
import MovieDisplay from './components/MovieDisplay'
import MixerSlider from './components/MixerSlider'
import YearRangeSlider from './components/YearRangeSlider'
import SamplePads from './components/SamplePads'
import TicketGenerator from './components/TicketGenerator'
import TmdbAttribution from './components/TmdbAttribution'
import WatchProviders from './components/WatchProviders'
import { useMix } from './hooks/useMix'
import { useRetention } from './hooks/useRetention'
import { track, Events } from './lib/track'

const INITIAL_SLIDERS = {
  genres: [],
  tone: 40,
  cerebro: 50,
  yearFrom: 1920,
  yearTo: 2024,
}

export default function App() {
  const { getInitialSliders, saveSliders, welcomeMessage } = useRetention(INITIAL_SLIDERS)
  const [sliders, setSliders] = useState(() => getInitialSliders())
  const [panelOpen, setPanelOpen] = useState(true)
  const [remixKey, setRemixKey] = useState(0)
  const [remixSpinning, setRemixSpinning] = useState(false)

  const { movie, loading, error } = useMix(sliders, remixKey)

  function handleRemix() {
    setRemixKey((k) => k + 1)
    setRemixSpinning(true)
    setTimeout(() => setRemixSpinning(false), 600)
    track(Events.REMIX_CLICKED, { genres: sliders.genres, tone: sliders.tone, cerebro: sliders.cerebro })
  }

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

  return (
    <div className="relative w-full h-screen overflow-hidden bg-black select-none">

      {/* ── Layer 0: Poster background ── */}
      <PosterBackground posterUrl={movie?.posterUrl} loading={loading} />

      {/* ── Layer 10: Movie info ── */}
      <div
        className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4"
        style={{ paddingBottom: panelOpen ? '58vh' : '0' }}
      >
        <MovieDisplay movie={movie} loading={loading} />
        <WatchProviders tmdbId={movie?.tmdbId} movieTitle={movie?.title} />
      </div>

      {/* ── Badges de estado ── */}
      <AnimatePresence>
        {error === 'backend_offline' && (
          <motion.div
            key="offline"
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full glass text-xs text-white/50 tracking-widest uppercase border border-white/10"
          >
            Modo demo · backend offline
          </motion.div>
        )}
        {error?.code === 'no_genre_match' && (
          <motion.div
            key="no-match"
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-2xl glass border border-red-500/40 text-center"
          >
            <p className="text-red-400 text-xs font-black tracking-widest uppercase">Sin resultados</p>
            <p className="text-white/40 text-xs mt-0.5">Esa combinacion de samples no tiene pelicula</p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Welcome back message ── */}
      <AnimatePresence>
        {welcomeMessage && (
          <motion.div
            key="welcome"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.4 }}
            className="absolute top-16 left-1/2 -translate-x-1/2 z-50 px-5 py-2.5 rounded-2xl text-center pointer-events-none"
            style={{
              background: 'rgba(251,191,36,0.1)',
              border: '1px solid rgba(251,191,36,0.25)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <p className="text-amber-300 text-xs font-medium tracking-wide whitespace-nowrap">
              {welcomeMessage}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Logo ── */}
      <div className="absolute top-5 left-6 z-20 flex items-center gap-2 pointer-events-none">
        <span className="text-xl">🎬</span>
        <span className="text-white font-black text-lg tracking-tight">
          CINE<span className="text-amber-400">MIX</span>
        </span>
      </div>

      {/* ── TMDB Attribution (required by TMDB ToS) ── */}
      <div className="absolute bottom-4 left-5 z-30 flex flex-col gap-1" style={{ display: panelOpen ? 'none' : 'flex' }}>
        <TmdbAttribution />
        <p className="text-white/20 text-[8px] leading-tight max-w-[160px]">
          Not endorsed or certified by TMDB.
        </p>
      </div>

      {/* ── Panel toggle ── */}
      <motion.button
        onClick={() => setPanelOpen((o) => !o)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="absolute top-4 right-5 z-30 w-10 h-10 rounded-full glass flex items-center justify-center text-white/70 hover:text-white transition-colors border border-white/10"
      >
        <motion.span
          animate={{ rotate: panelOpen ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          className="text-sm leading-none"
        >
          ↓
        </motion.span>
      </motion.button>

      {/* ── REMIX button ── */}
      <motion.div
        className="absolute left-1/2 -translate-x-1/2 z-30"
        animate={{ bottom: panelOpen ? 'calc(62vh + 14px)' : '32px' }}
        transition={{ type: 'spring', damping: 32, stiffness: 260 }}
      >
        <motion.button
          onClick={handleRemix}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.92 }}
          disabled={loading}
          className="relative flex items-center justify-center rounded-full font-black text-black text-xl"
          style={{
            width: 60,
            height: 60,
            background: 'linear-gradient(135deg, #fbbf24 0%, #d97706 100%)',
            boxShadow: loading
              ? '0 0 16px rgba(251,191,36,0.2)'
              : '0 0 28px rgba(251,191,36,0.55), 0 4px 16px rgba(0,0,0,0.5)',
            opacity: loading ? 0.6 : 1,
          }}
        >
          <motion.span
            animate={{ rotate: remixSpinning ? 360 : 0 }}
            transition={{ duration: 0.55, ease: 'easeOut' }}
            style={{ display: 'inline-block', lineHeight: 1 }}
          >
            ↻
          </motion.span>
        </motion.button>
      </motion.div>

      {/* ══════════════════════════════════════════════
          MESA DE MEZCLAS
      ══════════════════════════════════════════════ */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            key="panel"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 260 }}
            className="absolute bottom-0 inset-x-0 z-20 rounded-t-3xl overflow-hidden"
            style={{
              maxHeight: '62vh',
              background: 'rgba(6,6,10,0.92)',
              backdropFilter: 'blur(32px)',
              borderTop: '1px solid rgba(255,255,255,0.07)',
            }}
          >
            {/* Drag handle */}
            <div
              className="w-10 h-1 bg-white/15 rounded-full mx-auto mt-3 mb-0 cursor-pointer"
              onClick={() => setPanelOpen(false)}
            />

            {/* Scrollable board */}
            <div
              className="overflow-y-auto px-4 pb-5 pt-3 flex flex-col gap-4"
              style={{ maxHeight: 'calc(62vh - 20px)' }}
            >

              {/* ── Header de la mesa ── */}
              <div className="flex items-center gap-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 opacity-80" />
                  <span className="w-2 h-2 rounded-full bg-yellow-500 opacity-80" />
                  <span className="w-2 h-2 rounded-full bg-green-500 opacity-80" />
                </div>
                <p className="text-white/25 text-[10px] tracking-[0.35em] uppercase font-medium">
                  Mesa de Mezclas
                </p>
              </div>

              {/* ── FADERS DE CANAL ── */}
              <div
                className="rounded-2xl p-3 flex flex-col gap-3"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <p className="text-white/20 text-[9px] tracking-[0.3em] uppercase">Canales</p>
                <MixerSlider
                  label="Tono"
                  emoji="🎭"
                  leftLabel="Comedia · Familiar"
                  rightLabel="Oscuro · Tension"
                  value={sliders.tone}
                  onChange={set('tone')}
                  color="#a855f7"
                />
                <MixerSlider
                  label="Cerebro"
                  emoji="🧠"
                  leftLabel="Blockbuster"
                  rightLabel="Cine de autor"
                  value={sliders.cerebro}
                  onChange={set('cerebro')}
                  color="#3b82f6"
                />
              </div>

              {/* ── SAMPLE PADS ── */}
              <div
                className="rounded-2xl p-3"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <SamplePads
                  selected={sliders.genres}
                  onChange={set('genres')}
                />
              </div>

              {/* ── ÉPOCA ── */}
              <div
                className="rounded-2xl p-3"
                style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
              >
                <YearRangeSlider
                  yearFrom={sliders.yearFrom}
                  yearTo={sliders.yearTo}
                  onChangeFrom={set('yearFrom')}
                  onChangeTo={set('yearTo')}
                />
              </div>

              {/* ── TICKET ── */}
              <TicketGenerator movie={movie} sliders={sliders} />

              {/* ── TMDB Attribution (always visible in panel) ── */}
              <div className="flex flex-col items-center gap-1 pt-1">
                <TmdbAttribution />
                <p className="text-white/15 text-[8px] text-center leading-tight max-w-xs">
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
