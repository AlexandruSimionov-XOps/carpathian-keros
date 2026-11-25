"""PDF weather report generation with fpdf2 (English / Romanian)."""

from __future__ import annotations

import os
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fpdf import FPDF, XPos, YPos
from fpdf.fonts import FontFace

from .i18n import LABELS, WEEKDAYS, normalize_lang, wmo_label

APP_NAME = "Carpathian Keros"

# (regular, bold) candidates, first match wins. Override with CK_PDF_FONT / CK_PDF_FONT_BOLD.
_FONT_CANDIDATES: list[tuple[str, str]] = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]

# Used only when no Unicode TTF font is available (core fonts are Latin-1 only).
_ASCII_FALLBACK = str.maketrans(
    {
        "ă": "a",
        "Ă": "A",
        "â": "a",
        "Â": "A",
        "î": "i",
        "Î": "I",
        "ș": "s",
        "Ș": "S",
        "ş": "s",
        "Ş": "S",
        "ț": "t",
        "Ț": "T",
        "ţ": "t",
        "Ţ": "T",
        "–": "-",
        "—": "-",
        "·": "-",
    }
)

BRAND = (30, 58, 95)  # deep Carpathian blue
ACCENT = (245, 158, 11)  # amber
MUTED = (100, 116, 139)
ROW_FILL = (241, 245, 249)


def _find_font() -> tuple[str, str] | None:
    env_regular = os.environ.get("CK_PDF_FONT")
    candidates = list(_FONT_CANDIDATES)
    if env_regular:
        candidates.insert(0, (env_regular, os.environ.get("CK_PDF_FONT_BOLD", env_regular)))
    for regular, bold in candidates:
        if os.path.isfile(regular):
            return regular, bold if os.path.isfile(bold) else regular
    return None


def _local_now() -> datetime:
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo("Europe/Bucharest"))
    except Exception:  # tzdata missing (e.g. bare Windows install)
        return datetime.now(timezone.utc)


TEMP_DECIMALS = 0  # temperatures are shown as whole degrees, matching the UI


def _fmt_num(value: Any, lang: str, decimals: int = 1) -> str:
    """Round half away from zero (3.5 → 4, 3.4 → 3, -3.5 → -4); comma decimals for Romanian.

    Python's round() is banker's rounding (round(2.5) == 2), so it isn't used here.
    """
    if value is None:
        return "–"
    rounded = Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    if rounded == 0:
        rounded = abs(rounded)  # no "-0"
    text = f"{rounded:.{decimals}f}"
    return text.replace(".", ",") if lang == "ro" else text


def _fmt_temp(value: Any, lang: str) -> str:
    return _fmt_num(value, lang, TEMP_DECIMALS)


FontPaths = tuple[str, str]  # (regular, bold) TTF paths


class _AutoDetect:
    """Sentinel: look for a Unicode TTF on this machine (`_find_font`)."""


AUTODETECT = _AutoDetect()


class _ReportPDF(FPDF):
    def __init__(self, lang: str, fonts: FontPaths | None):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.lang = lang
        self.labels = LABELS[lang]
        if fonts:
            self.add_font("Body", "", fonts[0])
            self.add_font("Body", "B", fonts[1])
            self.family_name = "Body"
            self.unicode_ok = True
        else:
            self.family_name = "Helvetica"
            self.unicode_ok = False
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(15, 15, 15)
        self.set_title(f"{APP_NAME} – {self.labels['report_title']}")
        self.set_author(APP_NAME)
        self.set_creator(APP_NAME)

    def t(self, text: str) -> str:
        if self.unicode_ok:
            return text
        return text.translate(_ASCII_FALLBACK).encode("latin-1", "replace").decode("latin-1")

    def font(self, size: float, bold: bool = False) -> None:
        self.set_font(self.family_name, "B" if bold else "", size)

    def header(self) -> None:
        self.set_fill_color(*BRAND)
        self.rect(0, 0, self.w, 24, style="F")
        self.set_fill_color(*ACCENT)
        self.rect(0, 24, self.w, 1.2, style="F")
        self.set_xy(15, 7)
        self.set_text_color(255, 255, 255)
        self.font(18, bold=True)
        self.cell(0, 10, self.t(APP_NAME), new_x=XPos.LMARGIN, new_y=YPos.TOP)
        self.font(10)
        self.set_xy(15, 8.5)
        self.cell(0, 8, self.t(self.labels["report_title"]), align="R")
        self.set_text_color(0, 0, 0)
        self.set_y(32)

    def footer(self) -> None:
        self.set_y(-13)
        self.font(8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, self.t(self.labels["source"]), new_x=XPos.RIGHT, new_y=YPos.TOP)
        self.set_x(15)
        self.cell(0, 6, self.t(f"{self.labels['page']} {self.page_no()}/{{nb}}"), align="R")

    def section(self, title: str) -> None:
        self.ln(3)
        self.font(13, bold=True)
        self.set_text_color(*BRAND)
        self.cell(0, 8, self.t(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.5)
        self.line(15, self.get_y(), 45, self.get_y())
        self.set_text_color(0, 0, 0)
        self.ln(2.5)

    def data_table(
        self, headings: list[str], rows: list[list[str]], col_widths: tuple[int, ...], align: tuple[str, ...]
    ) -> None:
        self.font(9.5)
        self.set_draw_color(203, 213, 225)
        self.set_line_width(0.2)
        heading_style = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=BRAND)
        with self.table(
            col_widths=col_widths,
            text_align=align,
            headings_style=heading_style,
            line_height=5.2,
            borders_layout="HORIZONTAL_LINES",
            cell_fill_color=ROW_FILL,
            cell_fill_mode="ROWS",
            padding=(1.2, 1.5),
        ) as table:
            head = table.row()
            for h in headings:
                head.cell(self.t(h))
            for r in rows:
                row = table.row()
                for value in r:
                    row.cell(self.t(value))


def build_report(
    weather: dict[str, Any],
    lang: str = "en",
    *,
    font_paths: FontPaths | _AutoDetect | None = AUTODETECT,
) -> bytes:
    """Render the one-page report. `font_paths=None` forces the core-font (ASCII) fallback."""
    lang = normalize_lang(lang)
    L = LABELS[lang]
    fonts = _find_font() if isinstance(font_paths, _AutoDetect) else font_paths
    pdf = _ReportPDF(lang, fonts)
    pdf.add_page()

    loc = weather["location"]
    cur = weather["current"]
    u = weather["units"]

    # Location block
    pdf.font(22, bold=True)
    pdf.cell(0, 11, pdf.t(loc["name"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.font(10)
    pdf.set_text_color(*MUTED)
    region = ", ".join(p for p in (loc["region"][lang], loc["country"][lang]) if p and p != loc["name"])
    coords = f"{L['coordinates']}: {_fmt_num(loc['latitude'], lang, 3)}°N, {_fmt_num(loc['longitude'], lang, 3)}°E"
    pdf.cell(0, 5.5, pdf.t(f"{region} · {coords}" if region else coords), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 5.5, pdf.t(f"{L['generated']}: {_local_now():%Y-%m-%d %H:%M}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    if weather.get("stale"):
        pdf.ln(2)
        pdf.set_text_color(180, 83, 9)
        pdf.font(9)
        pdf.multi_cell(0, 5, pdf.t(L["stale_notice"]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    # Current conditions
    pdf.section(L["current_conditions"])
    current_rows = [
        [L["condition"], wmo_label(cur["weather_code"], lang)],
        [L["temperature"], f"{_fmt_temp(cur['temperature'], lang)} {u['temperature']}"],
        [L["feels_like"], f"{_fmt_temp(cur['feels_like'], lang)} {u['temperature']}"],
        [L["humidity"], f"{_fmt_num(cur['humidity'], lang, 0)} {u['humidity']}"],
        [L["wind_speed"], f"{_fmt_num(cur['wind_speed'], lang)} {u['wind_speed']}"],
        [L["observed"], cur["time"].replace("T", " ")],
    ]
    pdf.font(10)
    pdf.set_draw_color(203, 213, 225)
    with pdf.table(
        col_widths=(45, 135),
        first_row_as_headings=False,
        line_height=5.2,
        borders_layout="HORIZONTAL_LINES",
        padding=(1.2, 1.5),
    ) as table:
        for label, value in current_rows:
            row = table.row()
            row.cell(pdf.t(label), style=FontFace(emphasis="BOLD", color=BRAND))
            row.cell(pdf.t(value))

    # Next 24 hours, every 3 hours
    pdf.section(L["next_24h"])
    hourly_rows = [
        [
            h["time"][11:16],
            wmo_label(h["weather_code"], lang),
            f"{_fmt_temp(h['temperature'], lang)} {u['temperature']}",
            f"{_fmt_num(h['precipitation'], lang)} {u['precipitation']}",
            f"{_fmt_num(h['precipitation_probability'], lang, 0)} %",
        ]
        for h in weather["hourly"][::3]
    ]
    pdf.data_table(
        [L["hour"], L["condition"], L["temperature"], L["precipitation"], L["precip_probability"]],
        hourly_rows,
        (20, 64, 32, 32, 32),
        ("CENTER", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
    )

    # 7-day forecast
    pdf.section(L["forecast_7d"])
    daily_rows = []
    for d in weather["daily"]:
        day = date.fromisoformat(d["date"])
        daily_rows.append(
            [
                WEEKDAYS[lang][day.weekday()],
                day.strftime("%d.%m"),
                wmo_label(d["weather_code"], lang),
                f"{_fmt_temp(d['temp_min'], lang)} {u['temperature']}",
                f"{_fmt_temp(d['temp_max'], lang)} {u['temperature']}",
                f"{_fmt_num(d['precipitation_probability'], lang, 0)} %",
            ]
        )
    pdf.data_table(
        [L["day"], L["date"], L["condition"], L["min"], L["max"], L["precip_probability"]],
        daily_rows,
        (26, 18, 60, 24, 24, 28),
        ("LEFT", "CENTER", "LEFT", "RIGHT", "RIGHT", "RIGHT"),
    )

    return bytes(pdf.output())
