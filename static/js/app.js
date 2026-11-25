/* Carpathian Keros — dashboard logic: data fetching, i18n, GSAP animations, ApexCharts. */
(function () {
  "use strict";

  const I18N = window.CK_I18N;
  const { escapeHtml, fold } = window.CK_UTIL;
  const gsap = window.gsap;
  const ApexCharts = window.ApexCharts;
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const LANG_KEY = "ck-lang";
  const CITY_KEY = "ck-city";
  const DEFAULT_CITY = "București";
  const COLORS = { temp: "#f59e0b", precip: "#38bdf8", grid: "rgba(148,163,184,0.12)", ink: "#94a3b8" };

  const TEMP_DECIMALS = 0; // temperatures are shown as whole degrees everywhere
  const DROP_ICON = '<svg class="inline h-3 w-3 -mt-0.5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.5c-.4 0-.8.2-1 .6C8.4 7 5 11.6 5 15a7 7 0 0 0 14 0c0-3.4-3.4-8-6-11.9-.2-.4-.6-.6-1-.6Z"/></svg>';
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  const state = {
    lang: I18N.normalizeLang(safeStorage("get", LANG_KEY)),
    city: safeStorage("get", CITY_KEY) || DEFAULT_CITY,
    data: null,
    errorCode: null,
    requestId: 0,
    controller: null,
    charts: { temp: null, precip: null, range: null },
    sceneKey: null,
    sceneTimeline: null,
    revealed: false,
    selectedDate: null,  // "YYYY-MM-DD" when a 7-day card is selected; null = "next 24 hours"
  };

  if (gsap) document.documentElement.classList.add("js-anim");

  // ---------------------------------------------------------------- utilities
  function safeStorage(op, key, value) {
    try {
      return op === "get" ? window.localStorage.getItem(key) : window.localStorage.setItem(key, value);
    } catch (_) {
      return null; // storage disabled (private mode, etc.)
    }
  }

  const t = (key, vars) => I18N.t(state.lang, key, vars);
  const fmt = (v, d = 1) => I18N.formatNumber(v, state.lang, d);

  // ------------------------------------------------------- weather visuals
  function categoryFor(code) {
    if (code === 0) return "clear";
    if (code === 1 || code === 2) return "partly";
    if (code === 3) return "cloudy";
    if (code === 45 || code === 48) return "fog";
    if (code >= 51 && code <= 57) return "drizzle";
    if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
    if ((code >= 71 && code <= 77) || code === 85 || code === 86) return "snow";
    if (code >= 95) return "thunder";
    return "cloudy";
  }

  let svgUid = 0;

  function sunSVG(cx, cy, r, uid) {
    const rays = Array.from({ length: 8 }, (_, i) => {
      const a = (i * Math.PI) / 4;
      const r1 = r + 7, r2 = r + 14;
      return `<line x1="${(Math.cos(a) * r1).toFixed(1)}" y1="${(Math.sin(a) * r1).toFixed(1)}" x2="${(Math.cos(a) * r2).toFixed(1)}" y2="${(Math.sin(a) * r2).toFixed(1)}"/>`;
    }).join("");
    return `<defs><radialGradient id="sun-${uid}"><stop offset="0%" stop-color="#fde68a"/><stop offset="100%" stop-color="#f59e0b"/></radialGradient></defs>
      <g transform="translate(${cx} ${cy})">
        <g class="wx-rays" stroke="#fbbf24" stroke-width="3.5" stroke-linecap="round">${rays}</g>
        <circle class="wx-sun" r="${r}" fill="url(#sun-${uid})"/>
      </g>`;
  }

  function moonSVG(cx, cy, r, uid, withStars) {
    const stars = withStars
      ? [[30, 30], [130, 24], [120, 70], [40, 90], [140, 100]]
          .map(([x, y]) => `<circle class="wx-star" cx="${x}" cy="${y}" r="1.6" fill="#e2e8f0"/>`).join("")
      : "";
    return `${stars}<defs><mask id="moon-${uid}"><rect x="0" y="0" width="160" height="128" fill="#fff"/>
        <circle cx="${cx + r * 0.55}" cy="${cy - r * 0.35}" r="${r * 0.85}" fill="#000"/></mask></defs>
      <circle class="wx-moon" cx="${cx}" cy="${cy}" r="${r}" fill="#e2e8f0" mask="url(#moon-${uid})"/>`;
  }

  function cloudSVG(cls, dx, dy, scale, fill) {
    return `<g transform="translate(${dx} ${dy}) scale(${scale})"><g class="${cls}" fill="${fill}">
        <circle cx="70" cy="74" r="16"/><circle cx="92" cy="62" r="22"/><circle cx="114" cy="76" r="14"/>
        <rect x="56" y="72" width="70" height="20" rx="10"/></g></g>`;
  }

  function sceneSVG(category, isDay) {
    const uid = ++svgUid;
    const dark = ["rain", "thunder", "drizzle", "snow"].includes(category);
    const front = dark ? "#94a3b8" : "#e2e8f0";
    const back = dark ? "#475569" : "#64748b";
    const celestial = (cx, cy, r, stars) => (isDay ? sunSVG(cx, cy, r, uid) : moonSVG(cx, cy, r, uid, stars));
    let body = "";

    switch (category) {
      case "clear":
        body = celestial(80, 62, 26, true);
        break;
      case "partly":
        body = celestial(58, 46, 20, false) + cloudSVG("wx-cloud", 0, 6, 1, front);
        break;
      case "cloudy":
        body = cloudSVG("wx-cloud wx-cloud-back", -28, -16, 0.85, back) + cloudSVG("wx-cloud", 0, 4, 1, front);
        break;
      case "fog":
        body = cloudSVG("wx-cloud", 0, -10, 1, "#94a3b8") +
          [96, 106, 116].map((y, i) => `<line class="wx-fog" x1="${44 + i * 6}" y1="${y}" x2="${128 - i * 4}" y2="${y}" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round" opacity=".7"/>`).join("");
        break;
      case "drizzle":
      case "rain": {
        const xs = category === "rain" ? [70, 84, 98, 112] : [76, 96, 112];
        const len = category === "rain" ? 10 : 5;
        body = cloudSVG("wx-cloud wx-cloud-back", -24, -18, 0.8, back) + cloudSVG("wx-cloud", 0, -6, 1, front) +
          xs.map((x) => `<line class="wx-drop" x1="${x}" y1="96" x2="${x - 3}" y2="${96 + len}" stroke="${COLORS.precip}" stroke-width="3" stroke-linecap="round"/>`).join("");
        break;
      }
      case "snow":
        body = cloudSVG("wx-cloud wx-cloud-back", -24, -18, 0.8, back) + cloudSVG("wx-cloud", 0, -6, 1, front) +
          [70, 86, 102, 116].map((x) => `<circle class="wx-flake" cx="${x}" cy="100" r="3.2" fill="#f8fafc"/>`).join("");
        break;
      case "thunder":
        body = cloudSVG("wx-cloud wx-cloud-back", -24, -18, 0.8, "#334155") + cloudSVG("wx-cloud", 0, -6, 1, "#64748b") +
          `<polygon class="wx-bolt" points="94,90 82,110 92,110 86,126 106,102 96,102 102,90" fill="#fbbf24"/>` +
          [72, 116].map((x) => `<line class="wx-drop" x1="${x}" y1="96" x2="${x - 3}" y2="106" stroke="${COLORS.precip}" stroke-width="3" stroke-linecap="round"/>`).join("");
        break;
    }
    return `<svg viewBox="0 0 160 128" xmlns="http://www.w3.org/2000/svg" role="img">${body}</svg>`;
  }

  function animateScene(root) {
    if (state.sceneTimeline) state.sceneTimeline.kill();
    if (!gsap) return;
    const tl = gsap.timeline();
    state.sceneTimeline = tl;
    tl.fromTo(root.querySelector("svg"), { autoAlpha: 0, scale: 0.85, transformOrigin: "50% 50%" },
      { autoAlpha: 1, scale: 1, duration: 0.7, ease: "back.out(1.6)" });
    if (reducedMotion) return;

    const q = (sel) => root.querySelectorAll(sel);
    const loop = (targets, vars, position = 0) => targets.length && tl.to(targets, { repeat: -1, ...vars }, position);

    loop(q(".wx-rays"), { rotation: 360, transformOrigin: "50% 50%", duration: 24, ease: "none" });
    loop(q(".wx-sun"), { scale: 1.07, transformOrigin: "50% 50%", yoyo: true, duration: 2.2, ease: "sine.inOut" });
    loop(q(".wx-moon"), { y: -3, yoyo: true, duration: 3, ease: "sine.inOut" });
    loop(q(".wx-star"), { opacity: 0.2, yoyo: true, duration: 1.4, ease: "sine.inOut", stagger: { each: 0.35, repeat: -1, yoyo: true } });
    loop(q(".wx-cloud:not(.wx-cloud-back)"), { x: 7, yoyo: true, duration: 3.4, ease: "sine.inOut" });
    loop(q(".wx-cloud-back"), { x: -6, yoyo: true, duration: 4.2, ease: "sine.inOut" });
    loop(q(".wx-fog"), { x: 8, yoyo: true, duration: 2.6, ease: "sine.inOut", stagger: { each: 0.4, repeat: -1, yoyo: true } });

    const drops = q(".wx-drop");
    if (drops.length) {
      tl.fromTo(drops, { y: -8, opacity: 0 }, {
        keyframes: { y: [-8, 6, 18], opacity: [0, 1, 0] }, duration: 0.8, ease: "none",
        stagger: { each: 0.2, repeat: -1 },
      }, 0);
    }
    const flakes = q(".wx-flake");
    if (flakes.length) {
      tl.fromTo(flakes, { y: -8, opacity: 0 }, {
        keyframes: { y: [-8, 4, 14, 24], x: [0, 4, -4, 0], opacity: [0, 1, 1, 0] }, duration: 2.6, ease: "none",
        stagger: { each: 0.55, repeat: -1 },
      }, 0);
    }
    const bolt = q(".wx-bolt");
    if (bolt.length) {
      const flash = gsap.timeline({ repeat: -1, repeatDelay: 2.2 });
      flash.set(bolt, { opacity: 0 }).to(bolt, { opacity: 1, duration: 0.06 }).to(bolt, { opacity: 0.2, duration: 0.08 })
        .to(bolt, { opacity: 1, duration: 0.06 }).to(bolt, { opacity: 0, duration: 0.4, delay: 0.25 });
      tl.add(flash, 0.4);
    }
  }

  function renderScene(code, isDay, force) {
    const key = `${categoryFor(code)}:${isDay}`;
    if (!force && key === state.sceneKey) return;
    state.sceneKey = key;
    const root = $("#weather-scene");
    root.innerHTML = sceneSVG(categoryFor(code), isDay);
    animateScene(root);
  }

  // ------------------------------------------------------------- numbers
  function setNumber(el, target, animate) {
    const decimals = Number(el.dataset.decimals || 0);
    if (target === null || target === undefined) {
      el.textContent = "–";
      el._ckValue = undefined;
      return;
    }
    const from = typeof el._ckValue === "number" ? el._ckValue : 0;
    el._ckValue = target;
    if (!animate || !gsap || reducedMotion) {
      el.textContent = fmt(target, decimals);
      return;
    }
    const proxy = { v: from };
    gsap.killTweensOf(el._ckProxy || {});
    el._ckProxy = proxy;
    gsap.to(proxy, {
      v: target, duration: 1.3, ease: "power2.out",
      onUpdate: () => { el.textContent = fmt(proxy.v, decimals); },
      onComplete: () => { el.textContent = fmt(target, decimals); },
    });
  }

  // -------------------------------------------------------------- charts
  function baseChart(extra) {
    return {
      background: "transparent",
      foreColor: COLORS.ink,
      fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
      toolbar: { show: false },
      zoom: { enabled: false },
      animations: {
        enabled: !reducedMotion,
        easing: "easeinout",
        speed: 800,
        animateGradually: { enabled: true, delay: 40 },
        dynamicAnimation: { enabled: true, speed: 650 },
      },
      ...extra,
    };
  }

  const commonOptions = () => ({
    theme: { mode: "dark" },
    dataLabels: { enabled: false },
    grid: { borderColor: COLORS.grid, strokeDashArray: 3, padding: { left: 6, right: 10 } },
    legend: { show: false }, // single series per chart: captions above each chart name them
  });

  const Y_LABEL_WIDTH = 46; // identical width keeps the two synced hourly charts aligned

  /** The hours the hourly charts show: the selected day (00–23), or the next 24 hours. */
  function selectedHours(data) {
    const day = state.selectedDate && data.daily.find((d) => d.date === state.selectedDate);
    return day?.hourly?.length ? day.hourly : data.hourly;
  }

  function hourlyLabels(hourly) {
    return hourly.map((h) => h.time.slice(11, 16));
  }

  function tempChartOptions(hourly) {
    const hours = hourlyLabels(hourly);
    return {
      ...commonOptions(),
      chart: baseChart({ id: "ck-temp", group: "ck-hourly", type: "area", height: 190 }),
      series: [{ name: t("chart.temperature"), data: hourly.map((h) => h.temperature) }],
      colors: [COLORS.temp],
      stroke: { curve: "smooth", width: 2 },
      fill: { type: "gradient", gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 100] } },
      markers: { size: 0, strokeColors: "#0b1426", strokeWidth: 2, hover: { size: 5 } },
      xaxis: {
        categories: hours,
        labels: { show: false },
        axisBorder: { show: false },
        axisTicks: { show: false },
        tooltip: { enabled: false },
      },
      yaxis: {
        tickAmount: 4,
        labels: { minWidth: Y_LABEL_WIDTH, maxWidth: Y_LABEL_WIDTH, formatter: (v) => `${fmt(v, 0)}°` },
      },
      tooltip: {
        theme: "dark",
        x: { formatter: (_v, { dataPointIndex }) => `${t("chart.hour")} ${hours[dataPointIndex] ?? ""}` },
        y: { formatter: (v) => `${fmt(v, TEMP_DECIMALS)} °C` },
      },
    };
  }

  function precipChartOptions(hourly) {
    const hours = hourlyLabels(hourly);
    const prob = hourly.map((h) => h.precipitation_probability);
    return {
      ...commonOptions(),
      chart: baseChart({ id: "ck-precip", group: "ck-hourly", type: "bar", height: 150 }),
      series: [{ name: t("chart.precipitation"), data: hourly.map((h) => h.precipitation) }],
      colors: [COLORS.precip],
      plotOptions: { bar: { columnWidth: "55%", borderRadius: 3, borderRadiusApplication: "end" } },
      states: { hover: { filter: { type: "lighten", value: 0.12 } } },
      xaxis: {
        categories: hours,
        labels: {
          rotate: 0,
          hideOverlappingLabels: true,
          formatter: (v) => (v && Number(v.slice(0, 2)) % 3 === 0 ? v : ""),
        },
        axisBorder: { color: COLORS.grid },
        axisTicks: { show: false },
        tooltip: { enabled: false },
      },
      yaxis: {
        min: 0,
        max: (m) => Math.max(m, 1),
        tickAmount: 2,
        labels: { minWidth: Y_LABEL_WIDTH, maxWidth: Y_LABEL_WIDTH, formatter: (v) => fmt(v, 1) },
      },
      tooltip: {
        theme: "dark",
        x: { formatter: (_v, { dataPointIndex }) => `${t("chart.hour")} ${hours[dataPointIndex] ?? ""}` },
        y: {
          formatter: (v, { dataPointIndex }) =>
            `${fmt(v, 1)} mm · ${t("chart.precipChance")} ${fmt(prob[dataPointIndex], 0)}%`,
        },
      },
    };
  }

  function dayLabel(date, index) {
    return index === 0 ? t("today") : I18N.weekday(date, state.lang, "short");
  }

  function rangeChartOptions(data) {
    const daily = data.daily;
    return {
      ...commonOptions(),
      chart: baseChart({
        id: "ck-range", type: "rangeBar", height: 260,
        // Clicking a bar selects that day, like clicking its card.
        events: { dataPointSelection: (_e, _ctx, { dataPointIndex }) => toggleDay(daily[dataPointIndex]?.date) },
      }),
      states: { active: { filter: { type: "none" } } }, // selection is shown on the cards, not by darkening the bar
      series: [{
        name: t("chart.range"),
        data: daily.map((d, i) => ({ x: dayLabel(d.date, i), y: [d.temp_min, d.temp_max] })),
      }],
      // Vertical gradient runs top -> bottom: warm (max) at the top, cool (min) at the bottom.
      colors: [COLORS.precip],
      fill: { type: "gradient", gradient: { type: "vertical", gradientToColors: [COLORS.temp], stops: [0, 100] } },
      plotOptions: { bar: { horizontal: false, columnWidth: "34%", borderRadius: 5 } },
      xaxis: { axisBorder: { color: COLORS.grid }, axisTicks: { show: false }, tooltip: { enabled: false } },
      yaxis: { tickAmount: 5, labels: { minWidth: Y_LABEL_WIDTH, formatter: (v) => `${fmt(v, 0)}°` } },
      tooltip: {
        theme: "dark",
        custom: ({ dataPointIndex }) => {
          const d = daily[dataPointIndex];
          if (!d) return "";
          const title = `${I18N.weekday(d.date, state.lang, "long")} · ${I18N.shortDate(d.date, state.lang)}`;
          return `<div class="ck-tooltip">
            <strong>${escapeHtml(title)}</strong><br>
            <span class="muted">${escapeHtml(I18N.wmoLabel(d.weather_code, state.lang))}</span><br>
            ${escapeHtml(t("chart.max"))}: <strong>${fmt(d.temp_max, TEMP_DECIMALS)} °C</strong><br>
            ${escapeHtml(t("chart.min"))}: <strong>${fmt(d.temp_min, TEMP_DECIMALS)} °C</strong><br>
            ${escapeHtml(t("chart.precipChance"))}: ${fmt(d.precipitation_probability, 0)}%
          </div>`;
        },
      },
    };
  }

  function renderCharts(data, keys = ["temp", "precip", "range"]) {
    if (!ApexCharts) return;
    const hourly = selectedHours(data);
    const builders = {
      temp: ["#chart-temp", () => tempChartOptions(hourly)],
      precip: ["#chart-precip", () => precipChartOptions(hourly)],
      range: ["#chart-range", () => rangeChartOptions(data)],
    };
    keys.map((key) => [key, builders[key][0], builders[key][1]()]).forEach(([key, sel, opts]) => {
      if (state.charts[key]) {
        // updateSyncedCharts=false: otherwise ApexCharts pushes these options onto every chart in the group.
        state.charts[key].updateOptions(opts, false, true, false);
      } else {
        state.charts[key] = new ApexCharts($(sel), opts);
        state.charts[key].render();
      }
    });
  }

  // ------------------------------------------------------------- rendering
  function renderDailyCards(data, animate) {
    const container = $("#daily-cards");
    container.classList.toggle("has-selection", !!state.selectedDate); // only one card looks highlighted at a time
    container.innerHTML = data.daily.map((d, i) => {
      const selected = i > 0 && d.date === state.selectedDate;
      const label = t("dayCardLabel", { day: `${I18N.weekday(d.date, state.lang, "long")} ${I18N.shortDate(d.date, state.lang)}` });
      return `
      <button type="button" class="day-card${i === 0 ? " is-today" : ""}${selected ? " is-selected" : ""}" data-date="${d.date}"
              aria-pressed="${selected || (i === 0 && !state.selectedDate)}" aria-label="${escapeHtml(label)}"
              title="${escapeHtml(I18N.wmoLabel(d.weather_code, state.lang))}">
        <p class="text-sm font-semibold">${escapeHtml(dayLabel(d.date, i))}</p>
        <p class="text-xs text-slate-500">${escapeHtml(I18N.shortDate(d.date, state.lang))}</p>
        <div class="mini-icon" aria-hidden="true">${sceneSVG(categoryFor(d.weather_code), true)}</div>
        <p class="text-sm tabular-nums"><span class="font-bold">${fmt(d.temp_max, TEMP_DECIMALS)}°</span>
          <span class="text-slate-500">${fmt(d.temp_min, TEMP_DECIMALS)}°</span></p>
        <p class="text-xs tabular-nums text-sky-300" title="${escapeHtml(t("chart.precipChance"))}">${DROP_ICON} ${fmt(d.precipitation_probability, 0)}%</p>
      </button>`;
    }).join("");
    if (animate && gsap && !reducedMotion) {
      gsap.fromTo(container.children, { autoAlpha: 0, y: 14 },
        { autoAlpha: 1, y: 0, duration: 0.45, ease: "power2.out", stagger: 0.06, delay: 0.25 });
    }
  }

  function revealCards() {
    const cards = $$(".reveal");
    if (!gsap) return;
    if (reducedMotion) {
      gsap.set(cards, { autoAlpha: 1 });
      return;
    }
    gsap.fromTo(cards, { autoAlpha: 0, y: state.revealed ? 14 : 28 },
      { autoAlpha: 1, y: 0, duration: 0.65, ease: "power3.out", stagger: 0.12, overwrite: true });
    state.revealed = true;
  }

  function render(animate) {
    const data = state.data;
    if (!data) return;
    const { location, current } = data;

    $("#loc-name").textContent = location.name;
    const region = [location.region?.[state.lang], location.country?.[state.lang]]
      .filter((p) => p && p !== location.name).join(", ");
    $("#loc-region").textContent = region || " ";
    $("#condition").textContent = I18N.wmoLabel(current.weather_code, state.lang);
    $("#stale").classList.toggle("hidden", !data.stale);

    setNumber($("#m-temp"), current.temperature, animate);
    setNumber($("#m-feels"), current.feels_like, animate);
    setNumber($("#m-humidity"), current.humidity, animate);
    setNumber($("#m-wind"), current.wind_speed, animate);

    if (animate) revealCards();
    renderScene(current.weather_code, current.is_day, animate);
    renderDailyCards(data, animate);
    renderHourlyHeader();
    renderCharts(data);
    updatePdfLink();
    updatePresetState();
  }

  function renderHourlyHeader() {
    const date = state.selectedDate;
    $("#hourly-title").textContent = date
      ? t("hourlyTitleDay", { day: `${I18N.weekday(date, state.lang, "long")}, ${I18N.shortDate(date, state.lang)}` })
      : t("hourlyTitle");
    $("#hourly-reset").classList.toggle("hidden", !date);
  }

  /** Select a 7-day card (or deselect it: "today", the selected day again, or null → next 24 hours). */
  function toggleDay(date) {
    if (!state.data || !date) return;
    const isToday = date === state.data.daily[0]?.date;
    state.selectedDate = isToday || date === state.selectedDate ? null : date;
    renderDailyCards(state.data, false);
    renderHourlyHeader();
    renderCharts(state.data, ["temp", "precip"]);
    // The hourly charts sit right below the 7-day section: scroll down only as far as needed to show them.
    if (state.selectedDate) {
      $("#hourly-section").scrollIntoView({ behavior: reducedMotion ? "auto" : "smooth", block: "nearest" });
    }
  }

  function updatePdfLink() {
    const link = $("#pdf-link");
    if (!state.data) {
      link.setAttribute("aria-disabled", "true");
      link.removeAttribute("href");
      return;
    }
    const params = new URLSearchParams({ city: state.city, lang: state.lang });
    link.href = `/api/report/export?${params}`;
    link.setAttribute("aria-disabled", "false");
  }

  function updatePresetState() {
    const query = fold(state.data?.location?.query);
    $$(".preset-chip").forEach((chip) => {
      const active = fold(chip.dataset.city) === query;
      chip.classList.toggle("is-active", active);
      chip.setAttribute("aria-pressed", String(active));
    });
  }

  // ------------------------------------------------------------- i18n
  function applyTranslations() {
    document.documentElement.lang = state.lang;
    const vars = { count: document.body.dataset.cityCount || "" };
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n, vars); });
    $$("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder, vars); });
    $$("[data-i18n-aria]").forEach((el) => { el.setAttribute("aria-label", t(el.dataset.i18nAria)); });
    $$("[data-lang-option]").forEach((el) => el.classList.toggle("is-active", el.dataset.langOption === state.lang));
    $$(".preset-chip").forEach((chip) => {
      chip.textContent = state.lang === "ro" ? chip.dataset.labelRo : chip.dataset.labelEn;
    });
    if (state.errorCode) showError(state.errorCode);
    autocomplete?.refresh(); // re-localize county / population labels
  }

  function setLanguage(lang) {
    state.lang = I18N.normalizeLang(lang);
    safeStorage("set", LANG_KEY, state.lang);
    applyTranslations();
    render(false); // re-localize text, charts, and PDF link; keep the current city
  }

  // ------------------------------------------------------------- status
  function setLoading(on) {
    $("#loading").classList.toggle("hidden", !on);
    $("#loading").classList.toggle("flex", on);
    $("#dashboard").classList.toggle("is-loading", on && !!state.data);
    $("#search-btn").disabled = on;
  }

  function showError(code) {
    state.errorCode = code;
    const el = $("#error");
    el.textContent = t(`errors.${code}`) === `errors.${code}` ? t("errors.upstream_error") : t(`errors.${code}`);
    el.classList.remove("hidden");
    if (gsap && !reducedMotion) gsap.fromTo(el, { x: -8 }, { x: 0, duration: 0.4, ease: "elastic.out(1, 0.4)" });
  }

  function clearError() {
    state.errorCode = null;
    $("#error").classList.add("hidden");
  }

  // ------------------------------------------------------------- data
  let autocomplete = null; // controller from CK_Autocomplete.mount(), created in init()

  /** The allow-list for suggestions. If it fails, searching still works: the server enforces the list. */
  async function loadCityList() {
    try {
      const res = await fetch("/api/cities", { headers: { Accept: "application/json" } });
      if (res.ok) autocomplete.setCities((await res.json()).cities);
    } catch (_) {
      /* no suggestions; see docs/troubleshooting.md */
    }
  }

  async function loadCity(rawQuery, { fallbackToDefault = false } = {}) {
    const query = (rawQuery || "").trim();
    if (!query) {
      showError("invalid_city");
      return;
    }
    if (state.controller) state.controller.abort();
    const controller = new AbortController();
    state.controller = controller;
    const requestId = ++state.requestId;

    clearError();
    setLoading(true);
    try {
      const res = await fetch(`/api/weather?${new URLSearchParams({ city: query })}`, {
        signal: controller.signal,
        headers: { Accept: "application/json" },
      });
      const body = await res.json().catch(() => ({}));
      if (requestId !== state.requestId) return;
      if (!res.ok) {
        // A remembered city that is no longer valid (e.g. from an older version) shouldn't strand the user.
        if (fallbackToDefault && body.error === "city_not_found" && query !== DEFAULT_CITY) {
          setLoading(false);
          return loadCity(DEFAULT_CITY);
        }
        showError(body.error || "upstream_error");
        return;
      }
      // Keep a selected day when switching city, as long as the new forecast has that date.
      if (state.selectedDate && !body.daily?.some((d, i) => i > 0 && d.date === state.selectedDate)) {
        state.selectedDate = null;
      }
      state.data = body;
      state.city = body.location?.query || query; // canonical form: "iasi" → "Iași"
      safeStorage("set", CITY_KEY, state.city);
      render(true);
    } catch (err) {
      if (err.name === "AbortError" || requestId !== state.requestId) return;
      showError("network");
    } finally {
      if (requestId === state.requestId) setLoading(false);
    }
  }

  // ------------------------------------------------------------- wiring
  function init() {
    applyTranslations();
    updatePdfLink();

    $("#lang-toggle").addEventListener("click", () => setLanguage(state.lang === "en" ? "ro" : "en"));
    $("#daily-cards").addEventListener("click", (e) => toggleDay(e.target.closest(".day-card")?.dataset.date));
    $("#hourly-reset").addEventListener("click", () => {
      state.selectedDate = null;
      toggleDay(state.data?.daily[0]?.date); // "today" → back to the next 24 hours
    });
    autocomplete = window.CK_Autocomplete.mount({
      input: $("#city-input"),
      list: $("#city-suggestions"),
      ghost: $("#city-ghost"),
      t,
      fmt,
      onSelect: (query) => loadCity(query),
      onError: showError,
    });
    $("#search-form").addEventListener("submit", (e) => {
      e.preventDefault();
      autocomplete.submit();
    });
    loadCityList();
    $$(".preset-chip").forEach((chip) => chip.addEventListener("click", () => {
      $("#city-input").value = "";
      loadCity(chip.dataset.city);
    }));

    loadCity(state.city, { fallbackToDefault: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
