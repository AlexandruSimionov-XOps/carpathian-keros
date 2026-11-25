# API reference

Base URL: wherever the app is served, e.g. `http://127.0.0.1:5000`. Nothing needs authentication.

## `GET /api/cities`

Returns the allow-list: Romania's 319 official cities and towns. The UI uses it for autocomplete.

```json
{
  "count": 319,
  "source": "https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia",
  "cities": [
    { "name": "Abrud", "county": "Alba", "population": 4360, "query": "Abrud" },
    { "name": "București", "county": null, "population": 1716961, "query": "București" },
    { "name": "Ștefănești", "county": "Argeș", "population": 15931, "query": "Ștefănești, Argeș" }
  ]
}
```

- Sorted alphabetically (ignoring diacritics).
- `county` is `null` only for București.
- `population` comes from the 2021 census.
- **`query`** is the canonical string to pass as `city=`. It's the plain name, except when two towns share a name, in which case it's `"Name, County"` (only Ștefănești today).
- Response header: `Cache-Control: public, max-age=86400`. The list only changes when the app is redeployed.

## `GET /api/weather`

Returns current conditions, the next 24 hours and a 7-day forecast for one of the cities on the list.

| Query param | Required | Notes |
|---|---|---|
| `city` | yes | 1–100 characters. Must match a city from `/api/cities` exactly. Case, diacritics and hyphens are ignored, and partial names don't match. |

Accepted forms of `city`:

| Form | Example |
|---|---|
| Name | `Iași`, `iasi`, `TARGU MURES`, `Slanic-Moldova` |
| English alias | `Bucharest` |
| Name + county, to pick between towns that share a name | `Ștefănești, Botoșani`, `Stefanesti (jud. Botosani)`, `Ștefănești, Botoșani County` |

A shared name with no county gives the more populous town (`Ștefănești` → Argeș).

```bash
curl "http://127.0.0.1:5000/api/weather?city=Cluj"
```

### 200 response

`hourly` normally has 24 entries and `daily` has 7. Both are shortened here:

```json
{
  "location": {
    "name": "Cluj-Napoca",
    "query": "Cluj-Napoca",
    "county": "Cluj",
    "region":  { "en": "Cluj County", "ro": "Județul Cluj" },
    "country": { "en": "Romania",     "ro": "România" },
    "latitude": 46.76667,
    "longitude": 23.6,
    "elevation": 352.0
  },
  "timezone": "Europe/Bucharest",
  "units": {
    "temperature": "°C", "wind_speed": "km/h", "humidity": "%",
    "precipitation": "mm", "precipitation_probability": "%"
  },
  "current": {
    "time": "2026-11-25T11:45",
    "temperature": 1.4,
    "feels_like": -2.5,
    "humidity": 63,
    "wind_speed": 7.6,
    "weather_code": 1,
    "is_day": true
  },
  "hourly": [
    { "time": "2026-11-25T11:00", "temperature": 0.9, "precipitation": 0.0,
      "precipitation_probability": 0, "weather_code": 0 }
  ],
  "daily": [
    { "date": "2026-11-25", "weather_code": 3, "temp_max": 2.1, "temp_min": -2.8,
      "precipitation_probability": 8, "precipitation_sum": 0.0 }
  ],
  "fetched_at": "2026-11-25T09:54:29+00:00",
  "stale": false
}
```

### Field notes

| Field | Meaning |
|---|---|
| `location.name` | The official Romanian name, with comma-below diacritics (`ș`, `ț`). |
| `location.query` | Canonical query for this city. Use it for follow-up calls and the PDF link (`iasi` → `Iași`). |
| `location.county` | County name, or `null` for București. |
| `location.region` | Localized county label: `Județul Cluj` / `Cluj County`. For București it's `Municipiul București` / `Bucharest Municipality`. |
| `location.latitude/longitude/elevation` | From `data/cities_ro.json` (looked up once with Open-Meteo Geocoding at build time). |
| `current.time`, `hourly[].time` | **Local** Europe/Bucharest time, ISO 8601 without an offset. Don't parse them as UTC. |
| `current.is_day` | `false` between sunset and sunrise. |
| `weather_code` | [WMO weather interpretation code](i18n.md#wmo-weather-codes). |
| `hourly` | 24 entries, starting at the current local hour (inclusive). |
| `daily[].date` | Local date, `YYYY-MM-DD`. The first entry is today. |
| `daily[].precipitation_probability` | Maximum hourly probability for that day. |
| `daily[].hourly` | That day's hours, 00:00–23:00 local time: 24 rows with the same fields as the top-level `hourly`. The UI uses it when you click a day. |
| `fetched_at` | UTC time the data was fetched from Open-Meteo. On a cache hit this is older than the request. |
| `stale` | `true` if Open-Meteo failed and an **expired** cache entry was served instead. The UI shows a notice when this happens. |

Values can be `null` if Open-Meteo doesn't provide them for a timestep.

The API returns Open-Meteo's values **unrounded** (temperatures to 0.1 °C). Rounding to whole degrees happens only when they're displayed, in the UI and the PDF. API clients get the full precision and can round however they like.

## `GET /api/report/export`

Generates a one-page A4 PDF report and returns it as a download.

| Query param | Required | Notes |
|---|---|---|
| `city` | yes | Same rules as `/api/weather` |
| `lang` | no | `en` (default) or `ro`. Any other value falls back to `en`. The web UI defaults to Romanian but always sends `lang` explicitly. |

```bash
curl -OJ "http://127.0.0.1:5000/api/report/export?city=Brașov&lang=ro"
```

- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename=carpathian-keros_<city-slug>_<lang>_<YYYYMMDD>.pdf`. The slug is the ASCII form of the canonical query (e.g. `brasov`, `stefanesti-botosani`).
- `Cache-Control: max-age=0`. The PDF always reflects the data cached at request time.

It uses the same cache as `/api/weather`, so exporting right after viewing a city doesn't call Open-Meteo again.

## `GET /healthz`

A liveness check for Cloud Run, CI smoke tests and the Docker `HEALTHCHECK`.

```json
{ "status": "ok", "version": "1.0.0" }
```

- `version` comes from `pyproject.toml` (it's `"unknown"` if that file is missing).
- **It never calls Open-Meteo.** An upstream outage must not make the platform restart a healthy container; upstream problems show up as `502 upstream_error` on the data endpoints instead.
- `Cache-Control: no-store`.

## Errors

Both endpoints return errors as JSON:

```json
{ "error": "city_not_found", "message": "'Atlantis' is not on the list of Romanian cities" }
```

| HTTP | `error` | When |
|---|---|---|
| 400 | `invalid_city` | `city` is missing, blank or longer than 100 characters |
| 404 | `city_not_found` | Not one of the 319 listed cities: villages, communes, foreign places, typos and partial names |
| 502 | `upstream_error` | Open-Meteo timed out or failed, and no cached copy (fresh or expired) exists |

`error` is a stable, machine-readable code, and the frontend translates it (see `errors.*` in `static/js/i18n.js`). `message` is English text and may change; don't show it to users or match on it.
- For 4xx errors, `message` describes the input problem.
- For 5xx errors it's always the generic `"The weather service is temporarily unavailable"`. The real cause (timeout, HTTP status, connection error) is written to the server log, never to the response.

## Response headers

Every response, including errors and static files, carries:

| Header | Value |
|---|---|
| `Content-Security-Policy` | `default-src 'self'`; scripts only from self, `cdn.tailwindcss.com` and `cdn.jsdelivr.net` (no inline, no eval); `connect-src 'self'`; `frame-ancestors 'none'`; `object-src 'none'` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | camera, microphone, geolocation and payment disabled |

`Strict-Transport-Security` is left to the TLS-terminating reverse proxy.

## Caching behaviour

| Cache | Key | TTL |
|---|---|---|
| Forecast | city coordinates, rounded to 3 decimals | 10 min |

- City names are resolved in memory from `data/cities_ro.json`, so no geocoding happens at request time. Every spelling of the same city (`Iasi`, `Iași`) shares one cache entry.
- The cache holds up to 256 entries per process.
- Upstream requests use a 3 s connect / 8 s read timeout and retry up to 2 times on 429 and 5xx responses.
- If the upstream fails, an expired entry is served if one exists (`"stale": true`). Otherwise you get a 502.
