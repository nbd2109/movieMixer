import React from 'react'

/**
 * TMDB Attribution — required by TMDB API Terms of Use.
 * https://www.themoviedb.org/documentation/api/terms-of-use
 *
 * Must display:
 *  - The TMDB logo linking to themoviedb.org
 *  - Text: "This application uses TMDB and the TMDB APIs but is not endorsed,
 *           certified, or otherwise approved by TMDB."
 */

// Official TMDB logo (hosted on their CDN)
const TMDB_LOGO =
  'https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg'

export default function TmdbAttribution({ className = '' }) {
  return (
    <a
      href="https://www.themoviedb.org"
      target="_blank"
      rel="noopener noreferrer"
      className={`flex items-center gap-1.5 opacity-40 hover:opacity-70 transition-opacity ${className}`}
      title="This application uses TMDB and the TMDB APIs but is not endorsed, certified, or otherwise approved by TMDB."
    >
      <img
        src={TMDB_LOGO}
        alt="The Movie Database (TMDB)"
        className="h-3"
        style={{ filter: 'brightness(0) invert(1)' }}
      />
    </a>
  )
}

/** Inline version for the downloadable ticket (uses inline styles, no Tailwind) */
export function TmdbAttributionInline() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <img
        src={TMDB_LOGO}
        alt="TMDB"
        style={{ height: '10px', opacity: 0.5, filter: 'brightness(0) invert(1)' }}
      />
      <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '9px', letterSpacing: '1px' }}>
        Data provided by TMDB
      </span>
    </div>
  )
}
