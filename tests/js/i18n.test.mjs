import assert from "node:assert/strict";
import { test } from "node:test";
import { loadScripts, plain } from "./load.mjs";

const { CK_I18N: I18N } = loadScripts("static/js/i18n.js");

test("temperatures round half away from zero (regression: Math.round(-3.5) === -3)", () => {
  const cases = [[3.4, "3"], [3.5, "4"], [3.6, "4"], [-3.4, "−3"], [-3.5, "−4"], [2.5, "3"], [-0.4, "0"], [-0.5, "−1"]];
  for (const [value, expected] of cases) assert.equal(I18N.formatNumber(value, "en", 0), expected, `value ${value}`);
});

test("Romanian uses a decimal comma, English a point; missing values show a dash", () => {
  assert.equal(I18N.formatNumber(6.45, "ro", 1), "6,5");
  assert.equal(I18N.formatNumber(6.45, "en", 1), "6.5");
  assert.equal(I18N.formatNumber(null, "en", 1), "–");
});

function keyPaths(obj, prefix = "") {
  return Object.entries(obj).flatMap(([k, v]) =>
    typeof v === "object" ? keyPaths(v, `${prefix}${k}.`) : [`${prefix}${k}`]).sort();
}

test("every UI string exists in both languages", () => {
  assert.deepEqual(plain(keyPaths(I18N.translations.ro)), plain(keyPaths(I18N.translations.en)));
});

test("every backend error code has a translation", () => {
  for (const lang of ["en", "ro"]) {
    for (const code of ["invalid_city", "city_not_found", "upstream_error", "network"]) {
      assert.ok(I18N.translations[lang].errors[code], `${lang}.errors.${code}`);
    }
  }
});

test("t() fills every placeholder occurrence and falls back to English, then the key", () => {
  assert.equal(I18N.t("ro", "noMatches", { query: "xyz" }), "Niciun oraș din România nu corespunde cu „xyz”");
  assert.equal(I18N.t("ro", "does.not.exist"), "does.not.exist");
});

test("weekdays are localized and dates don't drift across time zones", () => {
  assert.equal(I18N.weekday("2026-11-25", "en", "long"), "Wednesday");
  assert.equal(I18N.weekday("2026-11-25", "ro", "long"), "Miercuri");
});

test("Romanian is the default UI language; unknown or missing values fall back to it", () => {
  assert.equal(I18N.DEFAULT_LANG, "ro");
  assert.equal(I18N.normalizeLang("de"), "ro");
  assert.equal(I18N.normalizeLang(null), "ro");
  assert.equal(I18N.normalizeLang("en"), "en");
  assert.equal(I18N.wmoLabel(9999, "ro"), "Necunoscut");
});
