// Loads the browser scripts into an isolated context with a fake `window`, so their pure logic can be tested in Node.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const root = fileURLToPath(new URL("../../", import.meta.url));

export function loadScripts(...files) {
  const context = { window: {}, Intl, console };
  vm.createContext(context);
  for (const file of files) vm.runInContext(readFileSync(root + file, "utf8"), context, { filename: file });
  return context.window;
}

/** Copy a value out of the vm realm: its arrays/objects have a different prototype, which deepStrictEqual rejects. */
export const plain = (value) => JSON.parse(JSON.stringify(value));

export const CITIES = JSON.parse(readFileSync(root + "data/cities_ro.json", "utf8")).cities.map((c) => ({
  name: c.name, county: c.county, population: c.population,
  query: c.name === "Ștefănești" ? `${c.name}, ${c.county}` : c.name,
}));
