# Carpathian Keros — Documentation

Carpathian Keros is a bilingual (Romanian / English) weather dashboard for Romania's **319 official cities and towns** (orașe and municipii). It's a Flask app that serves an animated single-page UI, a JSON weather API and downloadable PDF reports. All weather data comes from [Open-Meteo](https://open-meteo.com/), which needs no API key.

## Who should read what

| You want to… | Read |
|---|---|
| Use the dashboard | [User guide](user-guide.md) |
| Install, run, stop or deploy it | [Setup & operations](setup.md) |
| Call the HTTP API or generate PDFs | [API reference](api.md) |
| Understand how the pieces fit together | [Architecture](architecture.md) |
| Change the UI, animations or charts | [Frontend guide](frontend.md) |
| Add or change translations | [Internationalization](i18n.md) |
| Fix something that isn't working | [Troubleshooting](troubleshooting.md) |
| Modify the codebase as an AI agent | [`AGENTS.md`](../AGENTS.md) (overview and constitution), then the [AI agent guide](ai-agents.md) |

## Quick start

```bash
cd carpathian-keros
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                      # → http://127.0.0.1:5000
```

On WSL2, if you browse from Windows, start it with `HOST=0.0.0.0 python app.py`. See [Setup](setup.md#wsl2).

## At a glance

- **Stack:** Python 3.10+, Flask 3, requests, fpdf2. The frontend loads Tailwind CSS, GSAP and ApexCharts from CDNs, so there's no build step.
- **Endpoints:** `/` (UI), `/api/cities`, `/api/weather`, `/api/report/export`.
- **Cities:** a fixed list in `data/cities_ro.json`, built from [Wikipedia](https://ro.wikipedia.org/wiki/Lista_ora%C8%99elor_din_Rom%C3%A2nia). Nothing outside it can be queried.
- **Languages:** Romanian (the UI default) and English, in both the UI and the PDF.
- **State:** nothing is stored on disk. There's a 10-minute in-memory cache on the server, and `localStorage` in the browser keeps the language and last city.
