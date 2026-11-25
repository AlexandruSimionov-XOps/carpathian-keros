import assert from "node:assert/strict";
import { test } from "node:test";
import { CITIES, loadScripts, plain } from "./load.mjs";

const { CK_Autocomplete: AC } = loadScripts("static/js/util.js", "static/js/autocomplete.js");
const cities = AC.prepareCities(CITIES);
const names = (raw) => plain(AC.findMatches(cities, raw).map((m) => m.city.name));

test("prefix matches rank first, then word prefixes, then substrings; population breaks ties", () => {
  assert.equal(names("cl")[0], "Cluj-Napoca");
  assert.deepEqual(names("mures").slice(0, 2), ["Târgu Mureș", "Ocna Mureș"]);
  assert.deepEqual(names("bra").slice(0, 3), ["Brașov", "Brăila", "Bragadiru"]);
});

test("matching ignores case, diacritics and hyphens", () => {
  assert.equal(names("TARGU MURES")[0], "Târgu Mureș");
  assert.equal(names("slanic-moldova")[0], "Slănic Moldova");
  assert.equal(names("iasi")[0], "Iași");
});

test("highlight indices map onto the original (accented) name", () => {
  const [m] = AC.findMatches(cities, "bra").filter((x) => x.city.name === "Dumbrăveni");
  assert.equal(m.city.name.slice(m.index, m.index + m.length), "bră");
});

test("English alias finds București", () => {
  assert.equal(names("bucha")[0], "București");
});

test("'Name, County' filters by county", () => {
  assert.deepEqual(plain(AC.findMatches(cities, "stef, bo").map((m) => m.city.query)), ["Ștefănești, Botoșani"]);
});

test("at most 8 suggestions, and nothing for unlisted places", () => {
  assert.equal(AC.findMatches(cities, "a").length, 8);
  assert.deepEqual(names("paris"), []);
  assert.deepEqual(names("   "), []);
});

test("inline completion only for a prefix match typed at the start", () => {
  assert.equal(AC.completion("cl", AC.findMatches(cities, "cl")), "uj-Napoca");
  assert.equal(AC.completion("timi", AC.findMatches(cities, "timi")), "șoara");
  assert.equal(AC.completion("mures", AC.findMatches(cities, "mures")), ""); // word match, not prefix
  assert.equal(AC.completion("bucha", AC.findMatches(cities, "bucha")), ""); // alias: no inline text
});

test("resolveInput prefers an exact match, then the best suggestion", () => {
  assert.equal(AC.resolveInput(cities, "iasi").query, "Iași");
  assert.equal(AC.resolveInput(cities, "Bucharest").query, "București");
  assert.equal(AC.resolveInput(cities, "ştefăneşti, botoşani").query, "Ștefănești, Botoșani"); // cedilla input
  assert.equal(AC.resolveInput(cities, "orad").query, "Oradea");
  assert.equal(AC.resolveInput(cities, "paris"), null);
});
