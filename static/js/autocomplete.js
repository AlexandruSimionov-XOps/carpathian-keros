/* Carpathian Keros — city search combobox: suggestions, inline completion, keyboard handling.
 *
 * Pure matching functions (prepareCities, findMatches, completion, resolveInput) are exported for unit tests.
 * `mount()` wires them to the DOM. It knows nothing about weather; it reports choices through callbacks.
 */
(function () {
  "use strict";

  const { escapeHtml } = window.CK_UTIL;
  const MAX_SUGGESTIONS = 8;
  const ALIASES = { bucharest: "București" }; // folded English exonym → official name (mirror of services/cities.py)

  // ------------------------------------------------------------- pure matching
  /** Per-character fold that keeps string length, so match indices map back onto the original name. */
  const foldChars = (s) => Array.from(s || "", (ch) =>
    ch === "-" ? " " : ch.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().charAt(0) || ch).join("");
  const foldQuery = (s) => foldChars(s).trim().replace(/\s+/g, " ");

  /** Precompute folded keys once for the ~320 cities from /api/cities. */
  function prepareCities(list) {
    return list.map((c) => ({ ...c, _name: foldChars(c.name), _county: foldQuery(c.county || ""), _query: foldQuery(c.query) }));
  }

  /**
   * Ranked matches: 0 = name prefix, 1 = word prefix, 2 = substring; ties by population, then name.
   * "Name, County" filters by county prefix. Returns [{ city, score, index, length }], index -1 = no highlight.
   */
  function findMatches(cities, raw, max = MAX_SUGGESTIONS) {
    const [namePart, countyPart = ""] = (raw || "").split(",");
    const q = foldQuery(namePart);
    const cq = foldQuery(countyPart);
    if (!q || !cities) return [];
    const scored = [];
    for (const city of cities) {
      if (cq && !city._county.startsWith(cq)) continue;
      let index = city._name.indexOf(q);
      let score;
      if (index === 0) score = 0;
      else if (index > 0 && city._name[index - 1] === " ") score = 1;
      else if (index > 0) score = 2;
      else {
        const alias = Object.keys(ALIASES).find((a) => a.startsWith(q) && ALIASES[a] === city.name);
        if (!alias) continue;
        score = 0;
        index = -1;
      }
      scored.push({ city, score, index, length: q.length });
    }
    scored.sort((a, b) => a.score - b.score || (b.city.population || 0) - (a.city.population || 0)
      || a.city.name.localeCompare(b.city.name, "ro"));
    return scored.slice(0, max);
  }

  /** Untyped remainder of the best match, only when it's a real prefix of what was typed ("cl" → "uj-Napoca"). */
  function completion(raw, matches) {
    const top = matches[0];
    if (!top || top.score !== 0 || top.index !== 0) return "";
    return foldChars(raw) === top.city._name.slice(0, raw.length) ? top.city.name.slice(raw.length) : "";
  }

  /** What Enter should open: an exact match (name, canonical query or alias), else the best suggestion, else null. */
  function resolveInput(cities, raw) {
    const q = foldQuery(raw);
    if (!q || !cities) return null;
    const exact = cities.find((c) => c._name === q || c._query === q || ALIASES[q] === c.name);
    return exact || findMatches(cities, raw)[0]?.city || null;
  }

  // ------------------------------------------------------------- DOM binding
  /**
   * @param {object} o
   * @param {HTMLInputElement} o.input   combobox input
   * @param {HTMLElement} o.list         listbox <ul>
   * @param {HTMLElement} o.ghost        inline-completion overlay (.ghost-typed + .ghost-rest)
   * @param {(key: string, vars?: object) => string} o.t   translator for the active language
   * @param {(n: number, decimals: number) => string} o.fmt number formatter for the active language
   * @param {(query: string) => void} o.onSelect  called with a canonical query (or raw text if the list is unavailable)
   * @param {(code: string) => void} o.onError    called with "invalid_city" / "city_not_found"
   */
  function mount({ input, list, ghost, t, fmt, onSelect, onError }) {
    const ui = { cities: null, suggestions: [], activeIndex: -1, open: false };
    const ghostTyped = ghost.querySelector(".ghost-typed");
    const ghostRest = ghost.querySelector(".ghost-rest");

    function meta(city) {
      const where = city.county ? t("countyLabel", { county: city.county }) : t("capitalLabel");
      const pop = city.population ? ` · ${t("population", { n: fmt(city.population, 0) })}` : "";
      return where + pop;
    }

    function ghostText() {
      if (ui.activeIndex > 0 || document.activeElement !== input || input.selectionStart !== input.value.length) return "";
      return completion(input.value, ui.suggestions);
    }

    function renderGhost() {
      const rest = ghostText();
      ghostTyped.textContent = rest ? input.value : "";
      ghostRest.textContent = rest;
    }

    function render() {
      const raw = input.value;
      const visible = ui.open && document.activeElement === input && raw.trim() !== "" && !!ui.cities;
      list.classList.toggle("hidden", !visible);
      input.setAttribute("aria-expanded", String(visible));
      if (!visible) {
        input.removeAttribute("aria-activedescendant");
        renderGhost();
        return;
      }
      if (!ui.suggestions.length) {
        list.innerHTML = `<li class="suggestion-empty" role="option" aria-disabled="true">${escapeHtml(t("noMatches", { query: raw.trim() }))}</li>`;
      } else {
        list.innerHTML = ui.suggestions.map(({ city, index, length }, i) => {
          const name = index >= 0
            ? `${escapeHtml(city.name.slice(0, index))}<mark>${escapeHtml(city.name.slice(index, index + length))}</mark>${escapeHtml(city.name.slice(index + length))}`
            : escapeHtml(city.name);
          return `<li id="city-opt-${i}" class="suggestion${i === ui.activeIndex ? " is-active" : ""}" role="option"
                      aria-selected="${i === ui.activeIndex}" data-index="${i}">
                    <span class="sug-name">${name}</span><span class="sug-meta">${escapeHtml(meta(city))}</span>
                  </li>`;
        }).join("");
      }
      if (ui.activeIndex >= 0) {
        input.setAttribute("aria-activedescendant", `city-opt-${ui.activeIndex}`);
        list.querySelector(`#city-opt-${ui.activeIndex}`)?.scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
      renderGhost();
    }

    function update() {
      ui.suggestions = findMatches(ui.cities, input.value);
      ui.activeIndex = -1;
      ui.open = true;
      render();
    }

    function close() {
      ui.suggestions = [];
      ui.activeIndex = -1;
      ui.open = false;
      render();
    }

    function acceptGhost() {
      if (!ghostText()) return false;
      input.value = ui.suggestions[0].city.name;
      update();
      return true;
    }

    function choose(city) {
      input.value = city.query;
      close();
      input.blur();
      onSelect(city.query);
    }

    function submit() {
      if (ui.activeIndex >= 0 && ui.suggestions[ui.activeIndex]) return choose(ui.suggestions[ui.activeIndex].city);
      const raw = input.value.trim();
      if (!raw) return onError("invalid_city");
      if (!ui.cities) return onSelect(raw); // list unavailable: the server still enforces the allow-list
      const city = resolveInput(ui.cities, raw);
      if (city) return choose(city);
      close();
      return onError("city_not_found");
    }

    input.addEventListener("input", update);
    input.addEventListener("focus", update);
    input.addEventListener("blur", close);
    input.addEventListener("click", renderGhost); // caret moved
    input.addEventListener("keydown", (e) => {
      const count = ui.suggestions.length;
      switch (e.key) {
        case "ArrowDown":
        case "ArrowUp":
          if (!count) return;
          e.preventDefault();
          ui.activeIndex = e.key === "ArrowDown"
            ? (ui.activeIndex + 1) % count
            : (ui.activeIndex <= 0 ? count - 1 : ui.activeIndex - 1);
          render();
          break;
        case "Tab":
          if (!e.shiftKey && acceptGhost()) e.preventDefault();
          break;
        case "ArrowRight":
        case "End":
          if (acceptGhost()) e.preventDefault();
          break;
        case "Enter":
          e.preventDefault();
          submit();
          break;
        case "Escape":
          if (ui.open) {
            e.preventDefault();
            close();
          }
          break;
        default:
          requestAnimationFrame(renderGhost); // Home/Left etc. move the caret
      }
    });
    // mousedown (not click) so the input doesn't blur and close the list first.
    list.addEventListener("mousedown", (e) => {
      const item = e.target.closest(".suggestion");
      if (!item) return;
      e.preventDefault();
      choose(ui.suggestions[Number(item.dataset.index)].city);
    });
    list.addEventListener("mousemove", (e) => {
      const item = e.target.closest(".suggestion");
      if (!item || Number(item.dataset.index) === ui.activeIndex) return;
      ui.activeIndex = Number(item.dataset.index);
      render();
    });

    return {
      setCities(cities) {
        ui.cities = prepareCities(cities);
        if (document.activeElement === input) update();
      },
      refresh() { if (ui.open) render(); }, // re-localize labels after a language switch
      submit,
    };
  }

  window.CK_Autocomplete = Object.freeze({ prepareCities, findMatches, completion, resolveInput, mount, MAX_SUGGESTIONS });
})();
