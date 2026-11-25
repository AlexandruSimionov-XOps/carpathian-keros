/* Carpathian Keros — tiny shared helpers with no DOM or app dependencies. */
(function () {
  "use strict";

  const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

  /** Escape text before it goes into an HTML string (AGENTS.md V.1: output encoding). */
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => HTML_ESCAPES[c]);
  }

  /** Case- and diacritic-insensitive comparison key (whitespace trimmed). */
  function fold(s) {
    return (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  window.CK_UTIL = Object.freeze({ escapeHtml, fold });
})();
