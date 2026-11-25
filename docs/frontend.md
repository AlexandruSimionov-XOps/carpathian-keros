# Frontend guide

The frontend is a single server-rendered page (`templates/index.html`) plus a few small scripts. There is no build step.

## Files and load order

| Order | File | Exposes | Role |
|---|---|---|---|
| 1 | Tailwind Play CDN + `static/js/tailwind-config.js` | `tailwind.config` | Utility classes; the theme adds the `keros-*` colours and the Inter font |
| 2 | GSAP, ApexCharts (CDN) | `gsap`, `ApexCharts` | Animation and charts |
| 3 | `static/js/i18n.js` | `CK_I18N` | Strings, locale formatting, rounding |
| 4 | `static/js/util.js` | `CK_UTIL` | `escapeHtml`, `fold` |
| 5 | `static/js/autocomplete.js` | `CK_Autocomplete` | City matching (pure functions) and the combobox UI |
| 6 | `static/js/app.js` | — | Page behaviour: data, rendering, charts, weather scene |

Each file depends only on what loads before it. The pure parts (`CK_I18N`, `CK_UTIL`, the matching functions in `CK_Autocomplete`) have no DOM dependencies and are unit-tested in Node (`tests/js`).

## Dependencies

| Library | Version | Source | Used for |
|---|---|---|---|
| Tailwind CSS | Play CDN (latest) | `cdn.tailwindcss.com` | Utility classes |
| GSAP | 3.12.5 | jsDelivr, with an **SRI hash** | Card reveals, count-ups, weather-scene loops |
| ApexCharts | 3.54.1 | jsDelivr, with an **SRI hash** | The three charts |
| Inter (variable 400–800) | Google Fonts build, v20 | **self-hosted** in `static/fonts/` (`latin` + `latin-ext` for ă ș ț), SIL OFL 1.1 | Typeface |

**Content Security Policy.** Scripts may only load from self, `cdn.tailwindcss.com` and `cdn.jsdelivr.net`, with **no inline code and no `eval`**. So:
- no `<script>…</script>` blocks
- no `onclick=` attributes
- no `setTimeout("string")` or `new Function`

Put code in `static/js/` and attach handlers with `addEventListener`. Styles may be inline, because Tailwind and ApexCharts need it. A violation shows up as a console error, and the e2e tests fail on it.

**Bumping a CDN version:** update the URL **and** the `integrity` hash, or the browser refuses to load the file:
```bash
curl -s https://cdn.jsdelivr.net/npm/gsap@X.Y.Z/dist/gsap.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```

`app.js` checks that `window.gsap` and `window.ApexCharts` exist before using them. If a CDN is blocked, the page still shows its data, just without animation or charts.

## `app.js` structure

Everything is inside one IIFE, with one `state` object. The autocomplete keeps its own state inside `CK_Autocomplete.mount()`.

```js
state = {
  lang, city,          // persisted in localStorage as ck-lang / ck-city
  data,                // last successful /api/weather payload
  errorCode,           // so the error banner can be re-translated on language switch
  requestId, controller,   // stops slow, superseded responses from overwriting newer ones
  charts: { temp, precip, range },
  sceneKey, sceneTimeline, // current weather illustration + its GSAP timeline
  revealed,
}
let autocomplete;      // controller returned by CK_Autocomplete.mount() in init()
```

| Function | Role |
|---|---|
| `loadCity(query, {fallbackToDefault})` | Fetches `/api/weather` and aborts any in-flight request. It ignores responses whose `requestId` is out of date. On success it stores `location.query` (the canonical form) as `state.city` and calls `render(true)`. On failure it shows a translated error and keeps the previous data on screen. At startup, a remembered city that's no longer valid falls back to București. |
| `render(animate)` | Paints everything from `state.data`. Called with `animate = true` after a fetch and `false` after a language switch. |
| `setLanguage(lang)` | Saves the language, runs `applyTranslations()`, then `render(false)`. |
| `applyTranslations()` | Fills static text from the `data-i18n*` attributes, updates preset labels, the active toggle state and `<html lang>`. |
| `renderCharts(data)` | Creates the charts on first call and updates them in place after that. |
| `renderScene(code, isDay)` | Rebuilds the SVG illustration only when its category or day/night changes. |
| `setNumber(el, value, animate)` | Locale-aware GSAP count-up that starts from the previous value. |
| `updatePdfLink()` | `href = /api/report/export?city=<state.city>&lang=<state.lang>` |
| `loadCityList()` | Fetches `/api/cities` once and hands it to `autocomplete.setCities()` |
| `toggleDay(date)` | Selects a 7-day card (or deselects it: today, the same day again, or the reset button) → `state.selectedDate`. Re-renders the cards, `renderHourlyHeader()` and only the two hourly charts, then scrolls `#hourly-section` into view with `block: "nearest"`. The section sits right below `#forecast-section`, so the page only scrolls down, and only as far as needed. Triggered by card clicks (delegated on `#daily-cards`), `#hourly-reset` and the range chart's `dataPointSelection` event. |
| `selectedHours(data)` | The hours the hourly charts show: `daily[i].hourly` for the selected day, otherwise the next-24-hours `hourly`. |

## City autocomplete

The search box is an ARIA combobox (`#city-input`, `role="combobox"`, listbox `#city-suggestions`). Everything lives in `static/js/autocomplete.js`, and matching happens entirely in the browser.

**Interface.** It knows nothing about weather; it reports through callbacks:
```js
const ac = CK_Autocomplete.mount({ input, list, ghost, t, fmt,
  onSelect: (query) => loadCity(query),   // canonical query, or raw text if the list is unavailable
  onError: showError });                  // "invalid_city" | "city_not_found"
ac.setCities(list);   // from /api/cities
ac.refresh();         // re-localize labels after a language switch
ac.submit();          // what the form's submit does
```
**Pure functions** (unit-tested in `tests/js/autocomplete.test.mjs`): `prepareCities`, `findMatches(cities, raw)`, `completion(raw, matches)`, `resolveInput(cities, raw)`.

**Matching** (`findMatches`):
- The input is folded per character: `foldChars` lowercases, strips diacritics and turns `-` into a space. Each character stays one character, so match positions line up with the original name and the matched part can be highlighted with `<mark>`.
- A ranked score:
  - `0`: name prefix (`cl` → Cluj-Napoca)
  - `1`: word prefix (`mures` → Târgu Mureș)
  - `2`: substring
- Ties are broken by population (largest first), then by the name in `ro` collation. At most 8 results (`MAX_SUGGESTIONS`).
- `Name, County` input filters by county prefix (`stef, bo` → Ștefănești, Botoșani).
- `ALIASES` maps English exonyms (`bucharest` → București). They match as a prefix, with no highlight.

**Inline completion** (`#city-ghost`): an overlay that mirrors the input's padding and font. It shows the typed text in transparent ink, followed by the rest of the top suggestion in grey.
- It only appears for a prefix match with the caret at the end of the text.
- **Tab**, **→** or **End** accept it.
- If you change the input's padding, font size or border, update `.city-ghost` in `style.css` to match, or the grey text will drift.

**Keys:**
- **↑ / ↓** cycle through the list.
- **Enter** picks the highlighted item. With nothing highlighted, it runs `submit()`, which uses `resolveInput`: exact match, then the first suggestion, then `onError("city_not_found")` without any request.
- **Esc** closes the list.
- The mouse uses `mousedown` with `preventDefault`, so the input doesn't blur before the click registers.

**Choosing** a city puts its canonical `query` in the input (e.g. `Ștefănești, Botoșani`) and calls `loadCity`.

If `/api/cities` fails, there are no suggestions and the raw input goes straight to the server, which still enforces the list.

## Animations (GSAP)

| Effect | Where | Notes |
|---|---|---|
| Staggered card reveal | `revealCards()` | Elements with `.reveal` are hidden by CSS only when GSAP has loaded (`html.js-anim .reveal`). Runs again on every city change. |
| Count-ups | `setNumber()` | Temperature, feels-like, humidity and wind. They tween from the previous city's value. |
| Day-card stagger | `renderDailyCards()` | |
| Weather scene | `sceneSVG()` + `animateScene()` | Inline SVG. Looping tweens: rotating sun rays, pulsing sun, drifting clouds, falling rain or snow, lightning flashes, twinkling stars. |
| Error shake | `showError()` | |

**Weather-code → scene category** (`categoryFor`):

| WMO codes | Category |
|---|---|
| 0 | clear (sun, or moon and stars at night) |
| 1, 2 | partly cloudy |
| 3 | cloudy |
| 45, 48 | fog |
| 51–57 | drizzle |
| 61–67, 80–82 | rain |
| 71–77, 85, 86 | snow |
| 95–99 | thunder |

**Reduced motion:** when `prefers-reduced-motion: reduce` is set, the looping animations, count-ups and chart animations are skipped. Content still appears, just without movement.

The previous scene's timeline is killed before a new one starts (`state.sceneTimeline.kill()`), so the loops don't pile up.

## Charts (ApexCharts)

| Chart | Element | Type | Notes |
|---|---|---|---|
| Hourly temperature | `#chart-temp` | `area` | id `ck-temp`, group `ck-hourly` |
| Hourly precipitation | `#chart-precip` | `bar` | id `ck-precip`, group `ck-hourly`; y-axis minimum 0, maximum at least 1 mm |
| 7-day range | `#chart-range` | `rangeBar` | Vertical gradient (amber at the top for max, sky blue at the bottom for min); custom HTML tooltip |

Rules and gotchas:

1. **Grouped charts must update with `updateSyncedCharts = false`:**
   ```js
   chart.updateOptions(opts, false, true, false);
   ```
   ApexCharts applies `updateOptions()` to **every chart in the group** by default. The temperature options would then be pushed onto the precipitation chart, which throws `Cannot read properties of undefined (reading 'call')` during the path animation.
2. **Synced charts need the same y-label width.** Both hourly charts use `Y_LABEL_WIDTH` (46 px) so their plot areas line up for the shared tooltip.
3. **Don't merge the hourly charts into one dual-axis chart.** Different units belong in separate, aligned panels.
4. Chart text comes from `t()` / `fmt()` while the options are being built. A language switch rebuilds all options, so nothing goes stale.
5. Hour labels show every 3rd hour on the axis (formatter). Tooltips use `tooltip.x.formatter` to show every hour.
6. Chart text always uses neutral ink colours. Series colours only mark data.

## Times and dates

The API sends **Romanian local** times without an offset. The frontend never passes them through `Date` as instants:
- Hours are read by slicing the string (`"2026-11-25T09:00".slice(11, 16)`).
- Dates are built at local noon (`new Date(y, m-1, d, 12)`) and only used to get a weekday or month name from `Intl.DateTimeFormat`.

This keeps the labels correct whatever time zone the viewer is in.

## Styling

- Tailwind utilities live in the markup. `style.css` holds the component classes (`card`, `preset-chip`, `lang-toggle`, `metric*`, `day-card`, `chart-*`), the mountain-silhouette background, tooltip theming and the spinner.
- Palette: `--ck-amber #f59e0b` (brand and temperature), `--ck-sky #38bdf8` (precipitation), dark navy surfaces.
- The page is dark-theme only.

## Adding a new metric (example: pressure)

1. Backend: add `surface_pressure` to the `current` param in `_fetch_forecast`, map it in `_shape_forecast`, and add a unit to `units`.
2. Markup: add a `.metric` block in `index.html` with `<span id="m-pressure" data-decimals="0">` and a `data-i18n="pressure"` label. Change the metrics grid from `sm:grid-cols-3` to `sm:grid-cols-4`.
3. i18n: add `pressure` to both `en` and `ro` in `static/js/i18n.js`. If it appears in the PDF, also add it to `LABELS` in `services/i18n.py` and a row in `build_report`.
4. `render()`: add `setNumber($("#m-pressure"), current.pressure, animate)`.
