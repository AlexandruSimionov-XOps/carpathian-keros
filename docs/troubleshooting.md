# Troubleshooting

## "127.0.0.1 refused to connect"

1. **Is the server running?** `ss -ltn | grep :5000` should show a `LISTEN` line. If it doesn't, start it with `python app.py`.
2. **WSL2 with a Windows browser:** start it with `HOST=0.0.0.0 python app.py`, then try `http://localhost:5000`. If that still fails, use the WSL IP (`hostname -I`). See [Setup → WSL2](setup.md#wsl2).
3. **Wrong port:** if you set `PORT`, use that port in the URL.

## The server won't stop / "Address already in use"

Another process is holding the port:

```bash
ss -ltnp | grep :5000          # shows which PID is listening
fuser -k 5000/tcp              # or: pkill -f "python app.py"
```

`deactivate` only leaves the virtual environment. It doesn't stop the server.

## "That place isn't on the official list of Romanian cities and towns"

- Only the 319 official cities and towns (municipii and orașe) are available. Villages, communes (e.g. Florești, Cluj) and foreign places return 404 by design.
- Pick a city from the suggestions. Typing part of the name is enough, and diacritics are optional.
- Two towns are called Ștefănești. Use the suggestion, or type `Ștefănești, Botoșani`.

## No suggestions appear when typing

The page couldn't load `/api/cities`; look for a failed request in the browser's network tab. Searching still works if you type the full name, because the server checks it against the list.

## A city that should be on the list is missing

The list is a snapshot taken when `data/cities_ro.json` was generated. Regenerate it with `scripts/build_cities.py` (see [Setup → Refreshing the city list](setup.md#refreshing-the-city-list)).

## "The weather service is unavailable"

The server couldn't reach Open-Meteo and had no cached data.

- From the server, run `curl -I https://api.open-meteo.com/v1/forecast`. If it fails, the problem is the network, a proxy or a firewall.
- Open-Meteo may be rate-limiting you (HTTP 429) or be down. Check https://open-meteo.com/ and try again later.
- The server log shows a `WARNING ... Upstream failure:` line with the reason.

## The page loads but has no styling, charts or animations

The browser couldn't load a CDN (`cdn.tailwindcss.com`, `cdn.jsdelivr.net`). Corporate networks and ad blockers sometimes block these. The data still shows without them. Check the browser's network tab.

## Console error: "Refused to execute inline script…" / "…violates the following Content Security Policy directive"

This is the CSP doing its job: someone added an inline `<script>`, an `onclick=` attribute, a string passed to `setTimeout`, or a script from a new host.
- Move the code into a file in `static/js/` and attach handlers with `addEventListener`.
- A genuinely new external host needs a change to `CONTENT_SECURITY_POLICY` in `app.py`. That widens a system boundary, so it needs approval (AGENTS.md V.2).

## A CDN script doesn't load: "Failed to find a valid digest in the 'integrity' attribute"

The script's version changed but its SRI hash didn't. Recompute the hash for the new URL (see [Setup → Updating dependencies](setup.md#updating-dependencies)) and update `integrity` in `templates/index.html`.

## Console warning: "cdn.tailwindcss.com should not be used in production"

This is expected with the Tailwind Play CDN and harmless. To remove it, compile Tailwind (see [Setup → Production](setup.md#production-deployment)).

## PDF shows "s" instead of "ș"

The server has no Unicode TTF font, so the PDF fell back to Helvetica with ASCII letters. Fix it with one of these:

```bash
sudo apt install fonts-dejavu-core            # Debian/Ubuntu
# or point at any TTF with Romanian glyphs:
CK_PDF_FONT=/path/Font-Regular.ttf CK_PDF_FONT_BOLD=/path/Font-Bold.ttf python app.py
```

## The PDF is in the wrong language

The PDF uses the `lang` from the download link, which follows the **RO | EN** toggle. If you switched language after copying the link, the copied link still has the old `lang`. Use the button on the page again.

## The numbers are old

Responses are cached for 10 minutes per city, and Open-Meteo's own "current" values update every 15 minutes. Restarting the server clears the cache. If you see *Live service unavailable*, you're looking on purpose at an expired cached copy, because the upstream failed.

## Lots of `fontTools.subset` log lines

These come from an older copy of `app.py`. The current version sets the `fontTools` logger to WARNING.

## Charts throw `Cannot read properties of undefined (reading 'call')`

This happens if someone changes `renderCharts()` to call `updateOptions()` without the 4th argument `false`. See [Frontend → Charts](frontend.md#charts-apexcharts).
