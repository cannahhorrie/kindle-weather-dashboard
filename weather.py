import requests
import datetime
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

LAT, LON = 51.5997, -0.0960  # N22 5LR
LOCATION = "London"

WEATHER_CODES = {
    0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Foggy",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    56: "Freezing Drizzle", 57: "Freezing Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    66: "Freezing Rain", 67: "Freezing Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow", 77: "Snow Grains",
    80: "Rain Showers", 81: "Rain Showers", 82: "Violent Showers",
    85: "Snow Showers", 86: "Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm + Hail", 99: "Thunderstorm + Hail",
}

HERE = Path(__file__).parent


def describe(code):
    return WEATHER_CODES.get(code, "Unknown")


# ---- SVG icons (Feather-style line icons, self-contained, no external assets) ----

def icon_sun():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="5" fill="#eaeaea"/>
      <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>"""


def icon_cloud():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <path d="M18 10h-1.26A8 8 0 1 0 9 22h9a5 5 0 0 0 0-10z" fill="#eaeaea"/>
    </svg>"""


def icon_partly_cloudy(night=False):
    small = icon_moon_glyph() if night else (
        '<circle cx="7" cy="7" r="3.4" fill="#eaeaea" stroke="#000" stroke-width="1.3"/>'
        '<line x1="7" y1="0.5" x2="7" y2="2" stroke="#000" stroke-width="1.3"/>'
        '<line x1="1.5" y1="7" x2="0" y2="7" stroke="#000" stroke-width="1.3"/>'
        '<line x1="2.6" y1="2.6" x2="1.6" y2="1.6" stroke="#000" stroke-width="1.3"/>'
    )
    return f"""<svg viewBox="0 0 24 24" fill="none" stroke-linecap="round" stroke-linejoin="round">
      <g transform="translate(0,-1)">{small}</g>
      <path d="M18 10h-1.26A8 8 0 1 0 9 22h9a5 5 0 0 0 0-10z" fill="#eaeaea" stroke="#000" stroke-width="1.5"/>
    </svg>"""


def icon_moon_glyph():
    return '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" fill="#eaeaea" stroke="#000" stroke-width="1.5"/>'


def icon_moon():
    return f"""<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      {icon_moon_glyph()}
      <path d="M18 3 L18.7 4.6 L20.3 5.3 L18.7 6 L18 7.6 L17.3 6 L15.7 5.3 L17.3 4.6 Z" fill="#000" stroke="none"/>
      <path d="M20.5 8.5 L20.9 9.4 L21.8 9.8 L20.9 10.2 L20.5 11.1 L20.1 10.2 L19.2 9.8 L20.1 9.4 Z" fill="#000" stroke="none"/>
    </svg>"""


def icon_rain():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25" fill="#eaeaea"/>
      <line x1="8" y1="18" x2="8" y2="21"/>
      <line x1="12" y1="19" x2="12" y2="22"/>
      <line x1="16" y1="18" x2="16" y2="21"/>
    </svg>"""


def icon_snow():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 16.58A5 5 0 0 0 18 7h-1.26A8 8 0 1 0 4 15.25" fill="#eaeaea"/>
      <line x1="8" y1="18" x2="8" y2="22"/><line x1="6" y1="20" x2="10" y2="20"/>
      <line x1="16" y1="18" x2="16" y2="22"/><line x1="14" y1="20" x2="18" y2="20"/>
    </svg>"""


def icon_for(code, night):
    if code in (0, 1):
        return icon_moon() if night else icon_sun()
    if code == 2:
        return icon_partly_cloudy(night)
    if code in (3, 45, 48):
        return icon_cloud()
    if code in (71, 73, 75, 77, 85, 86):
        return icon_snow()
    return icon_rain()  # any precipitation / thunderstorm code


# ---- 1. Fetch hourly weather (no API key needed) ----
url = (
    f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
    "&hourly=temperature_2m,weathercode,precipitation_probability,precipitation"
    "&timezone=auto&forecast_days=1"
)

print("Fetching weather...")
data = requests.get(url).json()

hourly_time = data["hourly"]["time"]
hourly_temp = data["hourly"]["temperature_2m"]
hourly_code = data["hourly"]["weathercode"]
hourly_pop = data["hourly"]["precipitation_probability"]
hourly_precip = data["hourly"]["precipitation"]

now = datetime.datetime.now()


def hour_index(target_hour):
    target_str = now.strftime(f"%Y-%m-%dT{target_hour:02d}:00")
    return hourly_time.index(target_str)


idx_8am = hour_index(8)
idx_3pm = hour_index(15)
idx_9pm = hour_index(21)

slots = [
    ("MORNING", "8 AM", hourly_temp[idx_8am], hourly_code[idx_8am], False),
    ("AFTERNOON", "3 PM", hourly_temp[idx_3pm], hourly_code[idx_3pm], False),
    ("EVENING", "9 PM", hourly_temp[idx_9pm], hourly_code[idx_9pm], True),
]

max_pop = max(hourly_pop)
total_precip = sum(hourly_precip)

# ---- 2. Build the card HTML ----
card_html = []
for label, time_str, temp, code, is_night in slots:
    card_html.append(f"""
    <div class="card">
      <div class="card-icon">{icon_for(code, is_night)}</div>
      <div class="card-mid">
        <div class="card-label">{label}<br>({time_str})</div>
        <div class="card-desc">{describe(code)}</div>
      </div>
      <div class="card-temp"><span class="num">{round(temp)}</span><span class="deg">&deg;</span><span class="unit">C</span></div>
    </div>""")

rain_value = "Unlikely" if max_pop < 30 else "Yes"
rain_sub = f"({round(max_pop)}% chance)"
umbrella_html = ""
if max_pop >= 30:
    umbrella_html = f'<div class="rain-sub">~{total_precip:.1f}mm expected</div><div class="umbrella">Don\'t forget your umbrella!</div>'

template = (HERE / "dashboard_template.html").read_text()
html = (
    template
    .replace("{{LOCATION}}", LOCATION)
    .replace("{{DATE}}", now.strftime("%A, %b %d").upper())
    .replace("{{CARDS}}", "".join(card_html))
    .replace("{{RAIN_ICON}}", icon_rain())
    .replace("{{RAIN_VALUE}}", rain_value)
    .replace("{{RAIN_SUB}}", rain_sub)
    .replace("{{UMBRELLA}}", umbrella_html)
)

rendered_path = HERE / "dashboard_rendered.html"
rendered_path.write_text(html)

# ---- 3. Screenshot via Playwright's bundled Chromium (same on macOS and CI) ----
raw_path = HERE / "dashboard_raw.png"
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 600, "height": 800})
    page.goto("file://" + str(rendered_path))
    page.screenshot(path=str(raw_path))
    browser.close()

# ---- 4. Flatten to grayscale for the Kindle ----
img = Image.open(raw_path).convert("L")
img.save(HERE / "dashboard.png")
print("Saved dashboard.png!")
