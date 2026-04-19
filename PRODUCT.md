# CINEMIX — Product Manifesto & Engineering Guide
> "No sabe qué ver. Nosotros sí."

---

## 0. La verdad incómoda

El 90% de las apps de descubrimiento de películas están construidas para el cinéfilo que ya sabe lo que quiere. CineMix existe para el otro 90% del mercado: la persona que abre Netflix un viernes por la noche, scrollea 20 minutos, y acaba viendo lo primero que ya había visto.

Esa persona no necesita más opciones. Necesita permiso para elegir.

---

## 1. El ICP — Una sola persona

**El perfil:** 26–40 años. Trabaja. Vive solo o tiene la casa para él/ella esa noche. Ha pagado 3 plataformas de streaming. Son las 21:30. Tiene energía para una peli pero cero energía para decidir cuál.

**Su estado mental:** No es que no tenga gustos. Es que tiene demasiados, y todos en conflicto. "Algo de acción pero no demasiado. Algo bueno pero que no me exija pensar mucho. Algo de esta década pero que no sea Marvel."

**Lo que necesita de nosotros:** Que le demos una respuesta, no un catálogo. Cuando CineMix le dice "esta noche: Zodiac", no es una sugerencia — es un veredicto. El ritual de mover los sliders le da la sensación de haber decidido él. El resultado le quita la ansiedad de hacerlo.

**Lo que NO es nuestro ICP:**
- El cinéfilo que ya tiene la lista en Letterboxd
- El que quiere buscar por director o actor concreto
- El que decide en grupo (ese no es el primario)

---

## 2. Principios de Producto

### 2.1 Time to Value < 3 segundos
El usuario abre la app y en menos de 3 segundos tiene una película sugerida. Sin onboarding, sin tutorial, sin login. La app arranca con valores por defecto razonables y ya hay una respuesta.

### 2.2 El ritual importa más que el resultado
Mover los sliders y activar los pads no es un medio para llegar a la película — **es el producto**. El usuario está jugando con su propia identidad cinéfila. Si el resultado no le convence, el REMIX le da otra oportunidad sin romper el ritual.

### 2.3 Cero fricción social
Este es un acto privado. El usuario no quiere explicarle a nadie qué está viendo. El compartir existe pero nunca se empuja. La app no pregunta por email, no pide valoraciones, no muestra qué ve nadie más.

### 2.4 Memoria sin login
La app recuerda. Cuando el usuario vuelve, sus sliders están donde los dejó. Si pasaron más de 24 horas, hay un mensaje humano: *"La última vez buscabas algo oscuro de los 90. ¿Seguimos?"*. La retención se construye con memoria del navegador, no con bases de datos de usuarios.

### 2.5 Una decisión por sesión
El objetivo de cada sesión es llegar a UNA película y ponérsela. No guardar 10 para luego. No explorar catálogos. Cuando el usuario hace click en "¿Dónde verla?", la sesión ha terminado con éxito.

---

## 3. Arquitectura de Growth

### 3.1 SEO Programático (Futuro)
La arquitectura actual es Vite SPA — no indexable. La migración a Next.js App Router es prioritaria para escalar tráfico orgánico.

**Estructura de URLs objetivo:**
```
/mezcla/thriller-psicologico-anos-90          → SEO long-tail
/mezcla/comedia-familiar-clasicos             → SEO long-tail
/pelicula/zodiac-2007                         → Página de película indexable
```

**Meta tags dinámicos por combinación:**
```html
<title>Las mejores películas de thriller psicológico de los 90 | CineMix</title>
<meta name="description" content="Deja que CineMix elija por ti.
Tu próxima obsesión está a un slider de distancia.">
```

### 3.2 Tracking de Eventos (Data Layer)
Implementar desde día 1, aunque aún no esté conectado a ningún proveedor.
Todos los eventos pasan por `src/lib/track.js`:

```
mix_generated        → cuántas mezclas por sesión
remix_clicked        → índice de satisfacción inverso (más remix = menos satisfacción inicial)
pad_toggled          → qué géneros activa la gente (insight de contenido)
slider_adjusted      → qué sliders mueven más y hacia dónde
where_to_watch_clicked → conversión real (el KPI principal)
share_clicked        → K-factor / coeficiente viral
ticket_downloaded    → intención de recordar / compartir diferido
session_returned     → retención D1, D7, D30
```

### 3.3 Bucle Viral (K-Factor)
El vector de crecimiento primario es el ticket compartible y las URLs de mezcla.

**Open Graph obligatorio:**
```html
<meta property="og:title" content="Mi mezcla: Zodiac · Thriller · 2007">
<meta property="og:description" content="CineMix me encontró esta joya. ¿Qué te encuentra a ti?">
<meta property="og:image" content="/api/og?title=Zodiac&genres=Thriller,Crime&year=2007">
```

**Web Share API** (móvil): botón nativo que abre directamente WhatsApp/Instagram/X sin intermediarios.

### 3.4 Retención sin Login
```js
// localStorage keys
CINEMIX_LAST_SLIDERS     → estado de sliders al cerrar
CINEMIX_LAST_GENRES      → pads activos al cerrar  
CINEMIX_LAST_MOVIE       → última película sugerida
CINEMIX_SESSION_COUNT    → número de sesiones
CINEMIX_LAST_VISIT       → timestamp última visita
```

**Mensaje de retorno** (si han pasado >8h):
- < 24h: *"¿Encontraste algo bueno anoche?"*
- 1–3 días: *"La última vez buscabas [géneros]. ¿Seguimos?"*
- > 7 días: *"Llevas tiempo sin mezclar. Toca."*

---

## 4. Backlog Priorizado por ICP

### P0 — Rompe si no está
- [ ] **Botón REMIX** — pedir otra película sin cambiar nada
- [ ] **¿Dónde verla?** — watch providers de TMDB (cierra el journey)
- [ ] **Persistencia localStorage** — la app recuerda al usuario

### P1 — Diferenciador real
- [ ] **Mensaje de bienvenida** — retorno personalizado por tiempo
- [ ] **URLs de mezcla compartibles** — slug legible + OG image
- [ ] **Tracking layer** — `src/lib/track.js` sin dependencias externas

### P2 — Mejora la experiencia
- [ ] **Historial / setlist** — últimas 5 películas de la sesión
- [ ] **Duración** — filtro corto/normal/largo (requiere re-importar IMDb con runtimeMinutes)
- [ ] **Migración a Next.js** — SSR para SEO programático

### P3 — Pulido
- [ ] **Web Share API** — compartir nativo en móvil
- [ ] **Presets de mezcla** — "Noche de terror", "Domingo tranquilo", etc.
- [ ] **Animación de REMIX** — feedback visual del re-mix

---

## 5. Lo que nunca haremos

- Sistema de login o registro
- Recomendaciones basadas en historial personal (somos un mezclador, no un algoritmo)
- Publicidad dentro del producto
- Menús de navegación tradicionales
- Ratings o reviews de usuarios
- Comparación social ("X personas vieron esto")

---

## 6. Stack Actual

| Capa | Tecnología | Estado |
|------|-----------|--------|
| Frontend | React + Vite + Tailwind + Framer Motion | Producción |
| Backend | FastAPI + Python | Producción |
| BD principal | SQLite local (144k películas IMDb) | Producción |
| Metadatos | TMDB API (poster + sinopsis + watch providers) | Parcial |
| SEO | — | Pendiente (requiere Next.js) |
| Analytics | — | Pendiente (data layer listo) |
| Auth | Ninguno (por diseño) | Permanente |

---

## 7. Métricas de Éxito

| KPI | Objetivo | Cómo medirlo |
|-----|----------|-------------|
| Time to Value | < 3 seg | Tiempo hasta primera película mostrada |
| REMIX rate | < 3 por sesión | `remix_clicked` / `mix_generated` |
| Where to Watch CTR | > 40% | `where_to_watch_clicked` / `mix_generated` |
| D1 Retention | > 35% | `session_returned` con delta < 24h |
| K-factor | > 0.3 | `share_clicked` / sesiones únicas |

---

*Este documento es la fuente de verdad del producto. Cualquier decisión técnica que contradiga estos principios debe cuestionarse.*
