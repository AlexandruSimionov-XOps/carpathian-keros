/* Tailwind Play CDN theme. Kept in a file (not an inline <script>) so the CSP can forbid inline scripts. */
/* global tailwind */
tailwind.config = {
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: { keros: { 950: "#070d1a", 900: "#0b1426", 800: "#111d35", 700: "#1a2a4a", amber: "#f59e0b", sky: "#38bdf8" } },
    },
  },
};
