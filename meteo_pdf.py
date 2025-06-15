import requests
from fpdf import FPDF
from PIL import Image
from io import BytesIO
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from collections import defaultdict, Counter

# ─── CONFIGURACIÓ ─────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("API_KEY")
CITY_NAME = "Salou"
CACHE_DIR = "icon_cache"
PDF_FILENAME = "previsio_salou_5dies_3h.pdf"

os.makedirs(CACHE_DIR, exist_ok=True)

# ─── OBTENIR LAT I LON A PARTIR DEL NOM DE CIUTAT ─────────────
def get_coordinates(city_name):
    url = "https://api.openweathermap.org/geo/1.0/direct"
    params = {
        "q": city_name,
        "limit": 1,
        "appid": API_KEY
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    if not data:
        raise ValueError(f"No s'han trobat coordenades per a '{city_name}'")
    return data[0]["lat"], data[0]["lon"]

# ─── OBTENIR PREVISIÓ 3 HORES / 5 DIES ────────────────────────
def get_forecast_3h(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric",
        "lang": "ca"
    }
    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json()

# ─── AGRUPAR DADES PER DIA ────────────────────────────────────
def process_forecast_data(forecast_json):
    days = defaultdict(list)
    for item in forecast_json["list"]:
        dt = datetime.utcfromtimestamp(item["dt"]) + timedelta(seconds=forecast_json["city"]["timezone"])
        date_str = dt.strftime("%Y-%m-%d")
        days[date_str].append(item)
    # només 5 dies
    keys_sorted = sorted(days.keys())
    days5 = {k: days[k] for k in keys_sorted[:5]}
    return days5

# ─── EXTRACCIÓ DE DADES PER DIA ───────────────────────────────
def extract_day_summary(day_data):
    temps_max = max(d["main"]["temp_max"] for d in day_data)
    temps_min = min(d["main"]["temp_min"] for d in day_data)
    humidity_avg = round(sum(d["main"]["humidity"] for d in day_data) / len(day_data))
    wind_avg = round(sum(d["wind"]["speed"] for d in day_data) / len(day_data) * 3.6)  # m/s a km/h
    pop_avg = round(sum(d.get("pop", 0) for d in day_data) / len(day_data) * 100)  # probabilitat de pluja %
    uvi = "N/D"  # no disponible en forecast 3h

    # Icona i descripció més freqüent
    icons = [d["weather"][0]["icon"] for d in day_data]
    icon_code = Counter(icons).most_common(1)[0][0]
    descriptions = [d["weather"][0]["description"].capitalize() for d in day_data]
    description = Counter(descriptions).most_common(1)[0][0]

    return {
        "temp_max": round(temps_max),
        "temp_min": round(temps_min),
        "humidity": humidity_avg,
        "wind_kmh": wind_avg,
        "pop": pop_avg,
        "icon_code": icon_code,
        "description": description
    }

# ─── DESCARREGAR ICONA AMB CACHE ─────────────────────────────
def download_icon(icon_code):
    icon_path = os.path.join(CACHE_DIR, f"{icon_code}.png")
    if not os.path.exists(icon_path):
        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        response = requests.get(icon_url)
        image = Image.open(BytesIO(response.content)).convert("RGBA")
        image.save(icon_path)
    return icon_path

# ─── GENERAR PDF ──────────────────────────────────────────────
def create_pdf(days_data, city_name):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_title(f"Previsió meteorològica {city_name}")

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Previsió meteorològica a {city_name} (propers 5 dies)", ln=True, align="C")

    cell_width = 55
    top = 20
    margin = 10

    for i, (date_str, day_data) in enumerate(days_data.items()):
        summary = extract_day_summary(day_data)
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        date_fmt = dt.strftime('%a %d/%m')

        x = margin + i * cell_width

        pdf.set_xy(x, top)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(cell_width, 8, date_fmt, align="C")

        icon_path = download_icon(summary["icon_code"])
        pdf.image(icon_path, x + 12, top + 10, 30, 30)

        pdf.set_font("Helvetica", "", 10)
        y = top + 43

        pdf.set_xy(x, y)
        pdf.cell(cell_width, 6, f"Màx: {summary['temp_max']}°C", ln=1, align="C")

        pdf.set_xy(x, y + 6)
        pdf.cell(cell_width, 6, f"Mín: {summary['temp_min']}°C", ln=1, align="C")

        pdf.set_xy(x, y + 12)
        pdf.cell(cell_width, 6, f"Humitat: {summary['humidity']}%", ln=1, align="C")

        pdf.set_xy(x, y + 18)
        pdf.cell(cell_width, 6, f"Vent: {summary['wind_kmh']} km/h", ln=1, align="C")

        pdf.set_xy(x, y + 24)
        pdf.cell(cell_width, 6, f"Pluja: {summary['pop']}%", ln=1, align="C")

        pdf.set_xy(x, y + 30)
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(cell_width, 4, summary["description"], align="C")

    pdf.output(PDF_FILENAME)
    print(f"✅ PDF creat: {PDF_FILENAME}")

# ─── EXECUCIÓ ─────────────────────────────────────────────────
if __name__ == "__main__":
    lat, lon = get_coordinates(CITY_NAME)
    forecast_json = get_forecast_3h(lat, lon)
    days_data = process_forecast_data(forecast_json)
    create_pdf(days_data, CITY_NAME)
