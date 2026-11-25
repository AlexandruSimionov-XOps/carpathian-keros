# User guide

## Finding a city

You can look up any of Romania's **319 official cities and towns** (municipii and orașe), as listed on [Wikipedia](https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia). Villages, communes and places outside Romania aren't available.

- **Quick select:** click one of the presets under the search bar: București (*Bucharest* in English), Cluj-Napoca, Constanța, Iași, Oradea, Timișoara.
- **Search with suggestions:** start typing. A list of up to 8 matching cities appears, each with its county and population.
  - Matches are found at the start of the name (`cl` → **Cl**uj-Napoca), at the start of a word (`mures` → Târgu **Mureș**) or anywhere in the name. Within each kind, bigger cities come first.
  - Diacritics, capitals and hyphens don't matter: `iasi`, `targu mures` and `slanic-moldova` all work. `Bucharest` finds București.
  - The rest of the best match appears in grey inside the box. Press **Tab** (or **→** / **End**) to complete it.
  - **↑ / ↓** move through the list, **Enter** opens the highlighted city, **Esc** closes the list. You can also click a suggestion.
  - Pressing **Enter** without highlighting anything opens the exact match, or the first suggestion if there's no exact match.
  - Two towns are called **Ștefănești** (in Argeș and Botoșani counties). Pick one from the list, or type `Ștefănești, Botoșani`.
  - If nothing on the list matches, the list says so. Pressing Enter then shows an error, and the current city stays on screen.

The app remembers the last city you viewed and opens it next time. If that city is no longer valid, it opens București instead.

## Reading the dashboard

### Current conditions
- **Animated illustration:** shows the current weather (sun or moon, clouds, rain, snow, fog or a thunderstorm). At night it shows a moon instead of a sun.
- **Temperature and condition:** for example *−2 °C, Mainly clear*. Temperatures everywhere (page, charts, tooltips and PDF) are shown in **whole degrees**, rounded to the nearest degree, with halves rounding up: 3.4 → 3, 3.5 → 4, and symmetrically −3.5 → −4.
- **Feels like / Humidity / Wind:** apparent temperature, relative humidity, and wind speed in km/h at 10 m height.

### 7-day forecast
- **Day cards:** weekday, date, an icon, high / low temperature, and the chance of precipitation (drop icon). Today's card is highlighted. On a phone the days form one row: swipe sideways to see the rest of the week.
- **Range chart:** one bar per day, from that day's minimum to its maximum temperature. Hover a bar for the full day name, the condition, min / max and the precipitation chance.
- **See a day hour by hour:** click a day card, or its bar in the range chart.
  - The selected card is outlined in amber.
  - The hourly charts, right below the 7-day forecast, now show that whole day (00:00–23:00) under the heading *Hourly forecast · Saturday, Nov 28*. If they're not fully on screen, the page scrolls down just enough to show them.
  - To go back to the next 24 hours, click **Back to next 24 hours**, **Today**, or the selected card again.
  - With the keyboard: **Tab** to a card, then **Enter** or **Space**.
  - The selection stays when you switch language or city.

### Next 24 hours
Below the 7-day forecast there are two charts on the same hourly timeline, starting at the current hour:
- **Top:** temperature (°C).
- **Bottom:** precipitation (mm) as bars.

Hover over either chart to see the values for that hour in both. The precipitation tooltip also shows the chance of precipitation.

## Switching language

Click the **RO | EN** button in the top-right corner. The active language is highlighted in amber.

- The whole page switches straight away: headings, conditions, weekday names, number formatting (wind `6.5` km/h in English, `6,5` in Romanian) and chart labels.
- The city you're viewing doesn't change.
- Your choice is saved in the browser and used on your next visit. On a first visit the site opens in **Romanian**.

## Downloading a PDF report

Click **Download PDF report** (*Descarcă raportul PDF*). You get a one-page A4 report for the current city, **in the language currently selected**, with:
- current conditions
- the next 24 hours, every 3 hours
- the 7-day forecast

The file is named like `carpathian-keros_brasov_ro_20261125.pdf`.

## Notices you may see

| Message | Meaning |
|---|---|
| *That place isn't on the official list of Romanian cities and towns* | What you typed isn't one of the 319 cities. Pick a city from the suggestions. |
| *The weather service is unavailable right now* | Open-Meteo couldn't be reached. Try again in a minute. |
| *Live service unavailable — showing the most recent cached data* | The live data couldn't be fetched, so you're seeing the last successful result (up to the cache lifetime). |
| *Network error* | Your browser couldn't reach the Carpathian Keros server. |

## Accessibility

- If your OS is set to **reduce motion**, the looping weather animations and count-ups are turned off.
- The language toggle, presets and search work with the keyboard, and focus is visible.
- Status and error messages are announced to screen readers.

## Data source

Weather data © [Open-Meteo.com](https://open-meteo.com/), licensed under CC BY 4.0. Forecasts are model output and can differ from what actually happens.
The city list and populations (2021 census) come from [Wikipedia](https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia) (CC BY-SA 4.0).
