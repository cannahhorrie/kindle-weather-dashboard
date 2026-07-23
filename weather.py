import base64
import datetime
from pathlib import Path

import requests
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


def duck_data_uri(name):
    data = (HERE / "assets" / f"duck_{name}.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def wicon_data_uri(name):
    data = (HERE / "assets" / f"wicon_{name}.png").read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode()


def wicon_img(name):
    return f'<img src="{wicon_data_uri(name)}">'


def wicon_moon_cloud_img():
    # No moon+cloud icon in the sprite sheet - composite the existing moon and
    # cloud crops ourselves, peeking the moon out from behind the cloud the
    # same way the sheet's own sun_cloud icon does for daytime.
    return f"""<div class="moon-cloud-icon">
      <img class="mc-moon" src="{wicon_data_uri('moon')}">
      <img class="mc-cloud" src="{wicon_data_uri('cloud')}">
    </div>"""


def format_12h(iso_str):
    dt = datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M")
    hour12 = dt.hour % 12 or 12
    ampm = "AM" if dt.hour < 12 else "PM"
    return f"{hour12}:{dt.minute:02d} {ampm}"


# ---- Weather condition icons ----
# Cropped from the "Ultimate Weather Icon Sprite Sheet": 11 named icons
# (sun/cloud/drizzle/heavy-rain/storm/snow, day + moon variants), plus a plain
# "cloud" cropped separately (the sheet has no standalone overcast icon) — used
# for daytime overcast/fog and partly-cloudy-night, the two gaps the sheet doesn't cover.

def icon_sunrise():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <line x1="2" y1="18" x2="22" y2="18"/>
      <path d="M6 18a6 6 0 0 1 12 0" fill="#eaeaea"/>
      <line x1="12" y1="2" x2="12" y2="7"/>
      <polyline points="9,6 12,2 15,6"/>
      <line x1="3" y1="10.5" x2="5.5" y2="12.5"/>
      <line x1="21" y1="10.5" x2="18.5" y2="12.5"/>
    </svg>"""


def icon_sunset():
    return """<svg viewBox="0 0 24 24" fill="none" stroke="#000" stroke-width="1.5"
      stroke-linecap="round" stroke-linejoin="round">
      <line x1="2" y1="18" x2="22" y2="18"/>
      <path d="M6 18a6 6 0 0 1 12 0" fill="#eaeaea"/>
      <line x1="12" y1="3" x2="12" y2="8"/>
      <polyline points="9,5 12,8 15,5"/>
      <line x1="3" y1="12.5" x2="5.5" y2="10.5"/>
      <line x1="21" y1="12.5" x2="18.5" y2="10.5"/>
    </svg>"""


def weather_icon_for(code, night=False):
    if code in (0, 1):
        return wicon_img("moon" if night else "sun")
    if code == 2:
        return wicon_moon_cloud_img() if night else wicon_img("sun_cloud")
    if code == 3:
        return wicon_moon_cloud_img() if night else wicon_img("cloud")  # no plain overcast icon in the set
    if code in (45, 48):
        return wicon_img("moon_mist" if night else "cloud")  # no daytime mist icon in the set
    if code in (51, 53, 55, 56, 57):
        return wicon_img("moon_rain" if night else "drizzle")
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return wicon_img("moon_rain" if night else "heavy_rain")
    if code in (71, 73, 75, 77, 85, 86):
        return wicon_img("moon_snow" if night else "snow")
    if code in (95, 96, 99):
        return wicon_img("moon_storm" if night else "storm")
    return wicon_img("cloud")


def rain_chart_svg(hourly_pop, width=480, height=64):
    n = len(hourly_pop)
    pad_l, pad_r, pad_t, pad_b = 4, 4, 4, 14
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    base_y = pad_t + plot_h

    pts = [
        (pad_l + (i / (n - 1)) * plot_w, pad_t + plot_h - (min(p, 100) / 100) * plot_h)
        for i, p in enumerate(hourly_pop)
    ]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = f"M{pts[0][0]:.1f},{base_y:.1f} " + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts) + f" L{pts[-1][0]:.1f},{base_y:.1f} Z"
    threshold_y = pad_t + plot_h - (30 / 100) * plot_h

    ticks = {0: "12AM", 6: "6AM", 12: "12PM", 18: "6PM", 23: "11PM"}
    tick_svg = []
    for h, tlabel in ticks.items():
        x = pad_l + (h / (n - 1)) * plot_w
        anchor = "start" if h == 0 else "end" if h == 23 else "middle"
        tick_svg.append(f'<line x1="{x:.1f}" y1="{base_y:.1f}" x2="{x:.1f}" y2="{base_y + 3:.1f}" stroke="#000" stroke-width="1"/>')
        tick_svg.append(f'<text x="{x:.1f}" y="{height:.1f}" font-size="9" text-anchor="{anchor}" font-family="Arial" fill="#777777">{tlabel}</text>')

    return f"""
    <svg viewBox="0 0 {width} {height}" width="{width}" height="{height}">
      <line x1="{pad_l}" y1="{threshold_y:.1f}" x2="{width - pad_r}" y2="{threshold_y:.1f}" stroke="#999999" stroke-width="1" stroke-dasharray="3,3"/>
      <path d="{area}" fill="#cccccc" opacity="0.7"/>
      <polyline points="{poly}" fill="none" stroke="#000000" stroke-width="2"/>
      <line x1="{pad_l}" y1="{base_y:.1f}" x2="{width - pad_r}" y2="{base_y:.1f}" stroke="#000000" stroke-width="1.5"/>
      {"".join(tick_svg)}
    </svg>
    """


DUCK_FOR_SLOT = {
    "morning": "commute",
    "afternoon": "break",
    "evening": "evening_relax",
}

# ---- 1. Fetch hourly + current weather, sunrise/sunset (no API key needed) ----
url = (
    f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}"
    "&hourly=temperature_2m,weathercode,precipitation_probability,precipitation,wind_speed_10m"
    "&current=temperature_2m,wind_speed_10m"
    "&daily=sunrise,sunset&timezone=auto&forecast_days=1&wind_speed_unit=mph"
)

print("Fetching weather...")
data = requests.get(url).json()

hourly_time = data["hourly"]["time"]
hourly_temp = data["hourly"]["temperature_2m"]
hourly_code = data["hourly"]["weathercode"]
hourly_pop = data["hourly"]["precipitation_probability"]
hourly_precip = data["hourly"]["precipitation"]
hourly_wind = data["hourly"]["wind_speed_10m"]
sunrise = format_12h(data["daily"]["sunrise"][0])
sunset = format_12h(data["daily"]["sunset"][0])
current_temp = round(data["current"]["temperature_2m"])
current_wind = round(data["current"]["wind_speed_10m"])

# Use the API's own location-local timestamp, not the machine's system
# clock - GitHub's runners are UTC, and London is UTC+1 in summer, so
# "now" by system clock can land on the wrong calendar day for roughly an
# hour each night (right after London midnight but before UTC midnight),
# causing hour_index() to look up a date that isn't in that day's hourly
# data at all.
now = datetime.datetime.strptime(data["current"]["time"], "%Y-%m-%dT%H:%M")


def hour_index(target_hour):
    target_str = now.strftime(f"%Y-%m-%dT{target_hour:02d}:00")
    return hourly_time.index(target_str)


idx_8am = hour_index(8)
idx_3pm = hour_index(15)
idx_9pm = hour_index(21)

slots = [
    ("MORNING", "8 AM", "morning", hourly_temp[idx_8am], hourly_code[idx_8am], hourly_wind[idx_8am], False),
    ("AFTERNOON", "3 PM", "afternoon", hourly_temp[idx_3pm], hourly_code[idx_3pm], hourly_wind[idx_3pm], False),
    ("EVENING", "9 PM", "evening", hourly_temp[idx_9pm], hourly_code[idx_9pm], hourly_wind[idx_9pm], True),
]

# ---- 2. Build the row HTML ----
row_html = []
for label, time_str, key, temp, code, wind, is_night in slots:
    row_html.append(f"""
    <div class="row">
      <div class="time-col"><div class="time-badge">{time_str}</div></div>
      <div class="duck-col"><img src="{duck_data_uri(DUCK_FOR_SLOT[key])}"></div>
      <div class="icon-col">{weather_icon_for(code, is_night)}</div>
      <div class="wind-col">
        <img class="wind-icon" src="{wicon_data_uri('wind')}">
        <div class="wind-value">{round(wind)} <span class="wind-unit">mph</span></div>
      </div>
      <div class="info-col">
        <div class="info-label">{label}</div>
        <div class="info-temp"><span class="num">{round(temp)}</span><span class="deg">&deg;</span><span class="unit">C</span></div>
        <div class="info-desc">{describe(code)}</div>
      </div>
    </div>""")

max_pop = max(hourly_pop)
total_precip = sum(hourly_precip)

# Probability and amount come from somewhat independent parts of the forecast
# model, so a marginal day can show a real chance of rain (e.g. 31%) alongside
# a negligible expected amount (0.0mm) - not worth an umbrella warning unless
# both agree there's actually meaningful rain coming.
will_rain = max_pop >= 30 and total_precip >= 0.2

rain_value = "Yes" if will_rain else "Unlikely"
rain_sub = f"({round(max_pop)}% chance)"
rain_duck = "rain_probable" if will_rain else "sunny"
umbrella_html = ""
rain_chart_html = ""
if will_rain:
    umbrella_html = f'<div class="umbrella">~{total_precip:.1f}mm expected — don\'t forget your umbrella!</div>'
    rain_chart_html = f"""
    <div class="rain-chart-row">
      <div class="rain-chart-label">HOURLY CHANCE OF RAIN</div>
      {rain_chart_svg(hourly_pop)}
    </div>"""

template = (HERE / "dashboard_template.html").read_text()
html = (
    template
    .replace("{{LOCATION}}", LOCATION)
    .replace("{{DATE}}", now.strftime("%A, %b %d").upper())
    .replace("{{SUNRISE_ICON}}", icon_sunrise())
    .replace("{{SUNRISE_TIME}}", sunrise)
    .replace("{{SUNSET_ICON}}", icon_sunset())
    .replace("{{SUNSET_TIME}}", sunset)
    .replace("{{CURRENT_TEMP}}", str(current_temp))
    .replace("{{CURRENT_WIND}}", str(current_wind))
    .replace("{{ROWS}}", "".join(row_html))
    .replace("{{RAIN_DUCK}}", f'<img src="{duck_data_uri(rain_duck)}">')
    .replace("{{RAIN_VALUE}}", rain_value)
    .replace("{{RAIN_PERCENT}}", str(round(max_pop)))
    .replace("{{RAIN_SUB}}", rain_sub)
    .replace("{{UMBRELLA}}", umbrella_html)
    .replace("{{RAIN_CHART}}", rain_chart_html)
    .replace("{{LAST_UPDATED}}", now.strftime("%a %d %b, %H:%M"))
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
