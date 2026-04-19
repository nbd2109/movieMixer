import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import PosterBackground from './components/PosterBackground'
import MovieDisplay from './components/MovieDisplay'
import MixerSlider from './components/MixerSlider'
import YearRangeSlider from './components/YearRangeSlider'
import TicketGenerator from './components/TicketGenerator'
import { useMix } from './hooks/useMix'

const INITIAL_SLIDERS = {
  adrenaline: 60,
  tension: 40,
  cerebro: 50,
  yearFrom: 1990,
  yearTo: 2024,
}

export default function App() {
  const [sliders, setSliders] = useState(INITIAL_SLIDERS)
  const [panelOpen, setPanelOpen] = useState(true)

  const { movie, loading, error } = useMix(sliders)

  function set(key) {
    return (val) => setSliders((prev) => ({ ...prev, [key]: val }))
  }

  return (
    <div className="relative w-full h-screen overflow-hidden bg-black select-none">

      {/* ── Layer 0: Animated poster background ── */}
      <PosterBackground posterUrl={movie?.posterUrl} loading={loading} />

      {/* ── Layer 10: Movie info (center screen) ── */}
      <div
        className="absolute inset-0 z-10 flex flex-col items-center justify-center"
        style={{ paddingBottom: panelOpen ? '52vh' : '0' }}
      >
        <MovieDisplay movie={movie} loading={loading} />
      </div>

      {/* ── Offline badge ── */}
      <AnimatePresence>
        {error === 'backend_offline' && (
          <motion.div
            initial={{ opacity: 0, y: -16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -16 }}
            className="absolute top-4 left-1/2 -translate-x-1/2 z-50 px-4 py-2 rounded-full glass text-xs text-white/50 tracking-widest uppercase border border-white/10"
          >
            Modo demo · backend offline
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Logo top-left ── */}
      <div className="absolute top-5 left-6 z-20 flex items-center gap-2 pointer-events-none">
        <span className="text-xl">🎬</span>
        <span className="text-white font-black text-lg tracking-tight">
          CINE<span className="text-amber-400">MIX</span>
        </span>
      </div>

      {/* ── Panel toggle button ── */}
      <motion.button
        onClick={() => setPanelOpen((o) => !o)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        className="absolute top-4 right-5 z-30 w-10 h-10 rounded-full glass flex items-center justify-center text-white/70 hover:text-white transition-colors border border-white/10"
        title={panelOpen ? 'Ocultar controles' : 'Mostrar controles'}
      >
        <motion.span
          animate={{ rotate: panelOpen ? 180 : 0 }}
          transition={{ duration: 0.3 }}
          className="text-sm leading-none"
        >
          ↓
        </motion.span>
      </motion.button>

      {/* ── Layer 20: Bottom Glass Panel ── */}
      <AnimatePresence>
        {panelOpen && (
          <motion.div
            key="panel"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 32, stiffness: 260 }}
            className="absolute bottom-0 inset-x-0 z-20 glass rounded-t-3xl"
            style={{ maxHeight: '55vh' }}
          >
            {/* Drag handle */}
            <div
              className="w-10 h-1 bg-white/20 rounded-full mx-auto mt-3 mb-1 cursor-pointer"
              onClick={() => setPanelOpen(false)}
            />

            {/* Scrollable content */}
            <div className="overflow-y-auto px-5 pb-6 pt-3 flex flex-col gap-5"
              style={{ maxHeight: 'calc(55vh - 28px)' }}
            >

              {/* Section title */}
              <p className="text-center text-white/30 text-xs tracking-[0.3em] uppercase font-medium">
                Mesa de Mezclas
              </p>

              {/* Sliders */}
              <MixerSlider
                label="Adrenalina"
                emoji="⚡"
                leftLabel="Drama · Romance"
                rightLabel="Acción · Thriller"
                value={sliders.adrenaline}
                onChange={set('adrenaline')}
                color="#ef4444"
              />

              <MixerSlider
                label="Tensión"
                emoji="🔮"
                leftLabel="Comedia · Familiar"
                rightLabel="Terror · Misterio"
                value={sliders.tension}
                onChange={set('tension')}
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

              <YearRangeSlider
                yearFrom={sliders.yearFrom}
                yearTo={sliders.yearTo}
                onChangeFrom={set('yearFrom')}
                onChangeTo={set('yearTo')}
              />

              {/* Divider */}
              <div className="h-px bg-white/8" />

              {/* Ticket generator */}
              <TicketGenerator movie={movie} sliders={sliders} />

            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
