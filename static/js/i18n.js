/* Carpathian Keros — translation dictionary (mirrors services/i18n.py for WMO labels). */
(function () {
  "use strict";

  const translations = {
    en: {
      tagline: "Real-time weather across Romania",
      languageToggle: "Change language",
      searchPlaceholder: "Search {count} Romanian cities and towns…",
      suggestionsLabel: "City suggestions",
      noMatches: "No Romanian city or town matches “{query}”",
      countyLabel: "{county} County",
      capitalLabel: "Capital city",
      population: "pop. {n}",
      searchButton: "Search",
      searchLabel: "City",
      presetsLabel: "Quick select",
      currentConditions: "Current conditions",
      feelsLike: "Feels like",
      humidity: "Humidity",
      wind: "Wind",
      downloadPdf: "Download PDF report",
      hourlyTitle: "Next 24 hours",
      hourlyTitleDay: "Hourly forecast · {day}",
      showNext24h: "Back to next 24 hours",
      dayCardLabel: "Show the hourly forecast for {day}",
      hourlySubtitle: "Hourly temperature and precipitation",
      forecastTitle: "7-day forecast",
      rangeSubtitle: "Daily minimum and maximum temperature",
      loading: "Loading weather…",
      today: "Today",
      stale: "Live service unavailable — showing the most recent cached data.",
      footer: "Weather data by Open-Meteo.com (CC BY 4.0) · City list from Wikipedia (CC BY-SA 4.0).",
      errors: {
        city_not_found: "That place isn't on the official list of Romanian cities and towns. Pick one from the suggestions.",
        invalid_city: "Please enter a city name.",
        upstream_error: "The weather service is unavailable right now. Please try again shortly.",
        network: "Network error — check your connection and try again.",
      },
      chart: {
        temperature: "Temperature",
        precipitation: "Precipitation",
        precipChance: "Chance of precipitation",
        range: "Temperature range",
        min: "Min",
        max: "Max",
        hour: "Hour",
        tempAxis: "Temperature (°C)",
        precipAxis: "Precipitation (mm)",
      },
    },
    ro: {
      tagline: "Vremea în timp real în toată România",
      languageToggle: "Schimbă limba",
      searchPlaceholder: "Caută printre cele {count} orașe din România…",
      suggestionsLabel: "Sugestii de orașe",
      noMatches: "Niciun oraș din România nu corespunde cu „{query}”",
      countyLabel: "jud. {county}",
      capitalLabel: "Capitala",
      population: "{n} loc.",
      searchButton: "Caută",
      searchLabel: "Oraș",
      presetsLabel: "Selecție rapidă",
      currentConditions: "Condiții actuale",
      feelsLike: "Temperatură resimțită",
      humidity: "Umiditate",
      wind: "Vânt",
      downloadPdf: "Descarcă raportul PDF",
      hourlyTitle: "Următoarele 24 de ore",
      hourlyTitleDay: "Prognoză orară · {day}",
      showNext24h: "Înapoi la următoarele 24 de ore",
      dayCardLabel: "Afișează prognoza orară pentru {day}",
      hourlySubtitle: "Temperatura și precipitațiile orare",
      forecastTitle: "Prognoză pe 7 zile",
      rangeSubtitle: "Temperatura minimă și maximă zilnică",
      loading: "Se încarcă vremea…",
      today: "Azi",
      stale: "Serviciul live nu este disponibil — se afișează ultimele date din cache.",
      footer: "Date meteo de la Open-Meteo.com (CC BY 4.0) · Lista orașelor de pe Wikipedia (CC BY-SA 4.0).",
      errors: {
        city_not_found: "Această localitate nu se află pe lista oficială a orașelor din România. Alegeți una dintre sugestii.",
        invalid_city: "Introduceți numele unui oraș.",
        upstream_error: "Serviciul meteo nu este disponibil momentan. Încercați din nou în curând.",
        network: "Eroare de rețea — verificați conexiunea și încercați din nou.",
      },
      chart: {
        temperature: "Temperatură",
        precipitation: "Precipitații",
        precipChance: "Probabilitate precipitații",
        range: "Interval de temperatură",
        min: "Min",
        max: "Max",
        hour: "Ora",
        tempAxis: "Temperatură (°C)",
        precipAxis: "Precipitații (mm)",
      },
    },
  };

  const wmo = {
    0: { en: "Clear sky", ro: "Cer senin" },
    1: { en: "Mainly clear", ro: "Predominant senin" },
    2: { en: "Partly cloudy", ro: "Parțial noros" },
    3: { en: "Overcast", ro: "Cer acoperit" },
    45: { en: "Fog", ro: "Ceață" },
    48: { en: "Depositing rime fog", ro: "Ceață cu depunere de chiciură" },
    51: { en: "Light drizzle", ro: "Burniță slabă" },
    53: { en: "Moderate drizzle", ro: "Burniță moderată" },
    55: { en: "Dense drizzle", ro: "Burniță densă" },
    56: { en: "Light freezing drizzle", ro: "Burniță înghețată slabă" },
    57: { en: "Dense freezing drizzle", ro: "Burniță înghețată densă" },
    61: { en: "Slight rain", ro: "Ploaie slabă" },
    63: { en: "Moderate rain", ro: "Ploaie moderată" },
    65: { en: "Heavy rain", ro: "Ploaie puternică" },
    66: { en: "Light freezing rain", ro: "Ploaie înghețată slabă" },
    67: { en: "Heavy freezing rain", ro: "Ploaie înghețată puternică" },
    71: { en: "Slight snowfall", ro: "Ninsoare slabă" },
    73: { en: "Moderate snowfall", ro: "Ninsoare moderată" },
    75: { en: "Heavy snowfall", ro: "Ninsoare abundentă" },
    77: { en: "Snow grains", ro: "Grăunțe de zăpadă" },
    80: { en: "Slight rain showers", ro: "Averse slabe de ploaie" },
    81: { en: "Rain showers", ro: "Averse de ploaie" },
    82: { en: "Violent rain showers", ro: "Averse violente de ploaie" },
    85: { en: "Slight snow showers", ro: "Averse slabe de ninsoare" },
    86: { en: "Heavy snow showers", ro: "Averse puternice de ninsoare" },
    95: { en: "Thunderstorm", ro: "Furtună" },
    96: { en: "Thunderstorm with slight hail", ro: "Furtună cu grindină slabă" },
    99: { en: "Thunderstorm with heavy hail", ro: "Furtună cu grindină puternică" },
  };

  const unknown = { en: "Unknown", ro: "Necunoscut" };
  const locales = { en: "en-US", ro: "ro-RO" };
  const SUPPORTED = Object.keys(translations);
  const DEFAULT_LANG = "ro"; // first-visit UI language; a saved choice (localStorage ck-lang) wins

  /** Look up a dotted key ("chart.temperature") and fill {placeholders}. */
  function t(lang, key, vars) {
    const value = key.split(".").reduce((node, part) => (node ? node[part] : undefined), translations[lang]);
    const fallback = key.split(".").reduce((node, part) => (node ? node[part] : undefined), translations[DEFAULT_LANG]);
    let text = typeof value === "string" ? value : typeof fallback === "string" ? fallback : key;
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => { text = text.split(`{${k}}`).join(v); });
    }
    return text;
  }

  function wmoLabel(code, lang) {
    return (wmo[code] || unknown)[lang] || unknown.en;
  }

  /** Dates arrive as "YYYY-MM-DD" in Romanian local time; build them at local noon to avoid TZ drift. */
  function parseLocalDate(isoDate) {
    const [y, m, d] = isoDate.split("-").map(Number);
    return new Date(y, m - 1, d, 12);
  }

  function weekday(isoDate, lang, style = "short") {
    const name = new Intl.DateTimeFormat(locales[lang], { weekday: style }).format(parseLocalDate(isoDate));
    return name.charAt(0).toUpperCase() + name.slice(1);
  }

  function shortDate(isoDate, lang) {
    return new Intl.DateTimeFormat(locales[lang], { day: "numeric", month: "short" }).format(parseLocalDate(isoDate));
  }

  function formatNumber(value, lang, decimals = 1) {
    if (value === null || value === undefined || Number.isNaN(value)) return "–";
    // Round half away from zero: 3.5 → 4, 3.4 → 3, −3.5 → −4 (Math.round alone gives −3).
    // EPSILON absorbs binary noise such as 1.005 * 100 = 100.49999…
    const factor = 10 ** decimals;
    const rounded = (Math.sign(value) * Math.round((Math.abs(value) + Number.EPSILON) * factor)) / factor + 0; // "+ 0": no −0
    return new Intl.NumberFormat(locales[lang], {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(rounded).replace("-", "\u2212"); // typographic minus sign
  }

  function normalizeLang(lang) {
    return SUPPORTED.includes(lang) ? lang : DEFAULT_LANG;
  }

  window.CK_I18N = Object.freeze({
    translations, wmo, locales, SUPPORTED, DEFAULT_LANG,
    t, wmoLabel, weekday, shortDate, formatNumber, normalizeLang,
  });
})();
