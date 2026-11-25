"""Backend translation labels (PDF export). Mirrors static/js/i18n.js."""

from __future__ import annotations

SUPPORTED_LANGS = ("en", "ro")
DEFAULT_LANG = "en"

WMO_CODES: dict[int, dict[str, str]] = {
    0: {"en": "Clear sky", "ro": "Cer senin"},
    1: {"en": "Mainly clear", "ro": "Predominant senin"},
    2: {"en": "Partly cloudy", "ro": "Parțial noros"},
    3: {"en": "Overcast", "ro": "Cer acoperit"},
    45: {"en": "Fog", "ro": "Ceață"},
    48: {"en": "Depositing rime fog", "ro": "Ceață cu depunere de chiciură"},
    51: {"en": "Light drizzle", "ro": "Burniță slabă"},
    53: {"en": "Moderate drizzle", "ro": "Burniță moderată"},
    55: {"en": "Dense drizzle", "ro": "Burniță densă"},
    56: {"en": "Light freezing drizzle", "ro": "Burniță înghețată slabă"},
    57: {"en": "Dense freezing drizzle", "ro": "Burniță înghețată densă"},
    61: {"en": "Slight rain", "ro": "Ploaie slabă"},
    63: {"en": "Moderate rain", "ro": "Ploaie moderată"},
    65: {"en": "Heavy rain", "ro": "Ploaie puternică"},
    66: {"en": "Light freezing rain", "ro": "Ploaie înghețată slabă"},
    67: {"en": "Heavy freezing rain", "ro": "Ploaie înghețată puternică"},
    71: {"en": "Slight snowfall", "ro": "Ninsoare slabă"},
    73: {"en": "Moderate snowfall", "ro": "Ninsoare moderată"},
    75: {"en": "Heavy snowfall", "ro": "Ninsoare abundentă"},
    77: {"en": "Snow grains", "ro": "Grăunțe de zăpadă"},
    80: {"en": "Slight rain showers", "ro": "Averse slabe de ploaie"},
    81: {"en": "Rain showers", "ro": "Averse de ploaie"},
    82: {"en": "Violent rain showers", "ro": "Averse violente de ploaie"},
    85: {"en": "Slight snow showers", "ro": "Averse slabe de ninsoare"},
    86: {"en": "Heavy snow showers", "ro": "Averse puternice de ninsoare"},
    95: {"en": "Thunderstorm", "ro": "Furtună"},
    96: {"en": "Thunderstorm with slight hail", "ro": "Furtună cu grindină slabă"},
    99: {"en": "Thunderstorm with heavy hail", "ro": "Furtună cu grindină puternică"},
}

WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "ro": ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"],
}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        "report_title": "Weather Report",
        "generated": "Generated",
        "coordinates": "Coordinates",
        "current_conditions": "Current conditions",
        "condition": "Condition",
        "temperature": "Temperature",
        "feels_like": "Feels like",
        "humidity": "Humidity",
        "wind_speed": "Wind speed",
        "observed": "Observed",
        "next_24h": "Next 24 hours",
        "hour": "Hour",
        "precipitation": "Precipitation",
        "precip_probability": "Precip. chance",
        "forecast_7d": "7-day forecast",
        "day": "Day",
        "date": "Date",
        "min": "Min",
        "max": "Max",
        "stale_notice": "Live data was unavailable; showing the most recent cached forecast.",
        "source": "Data: Open-Meteo.com (CC BY 4.0)",
        "page": "Page",
        "unknown": "Unknown",
    },
    "ro": {
        "report_title": "Raport meteo",
        "generated": "Generat",
        "coordinates": "Coordonate",
        "current_conditions": "Condiții actuale",
        "condition": "Condiție",
        "temperature": "Temperatură",
        "feels_like": "Resimțită",
        "humidity": "Umiditate",
        "wind_speed": "Viteza vântului",
        "observed": "Observat",
        "next_24h": "Următoarele 24 de ore",
        "hour": "Ora",
        "precipitation": "Precipitații",
        "precip_probability": "Prob. precip.",
        "forecast_7d": "Prognoză pe 7 zile",
        "day": "Ziua",
        "date": "Data",
        "min": "Min",
        "max": "Max",
        "stale_notice": "Datele live nu au fost disponibile; se afișează ultima prognoză din cache.",
        "source": "Date: Open-Meteo.com (CC BY 4.0)",
        "page": "Pagina",
        "unknown": "Necunoscut",
    },
}


def normalize_lang(lang: str | None) -> str:
    lang = (lang or "").strip().lower()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def wmo_label(code: int | None, lang: str) -> str:
    entry = WMO_CODES.get(code) if code is not None else None
    return entry[lang] if entry else LABELS[lang]["unknown"]
