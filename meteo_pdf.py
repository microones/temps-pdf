import os
import requests
from fpdf import FPDF
from datetime import datetime
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import glob

load_dotenv()
CLAU_API = os.getenv("CLAU_API")
CIUTAT = "Salou"
PAIS = "ES"

PDF_NOM = "previsio_visual.pdf"

IDIOMES_DIES = {
    "ca": ["Dill", "Dim", "Dime", "Dij", "Div", "Dis", "Diu"],
    "es": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "fr": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
}

class MeteoPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, f"Previsió meteorològica (5 dies): {CIUTAT}", ln=True, align="C")
        self.ln(5)

def obtenir_dades():
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={CIUTAT},{PAIS}&units=metric&lang=ca&appid={CLAU_API}"
    resposta = requests.get(url)
    dades = resposta.json()
    if resposta.status_code != 200 or "list" not in dades:
        raise Exception(f"Error en obtenir dades: {dades.get('message', 'Desconegut')}")
    return dades

def obtenir_lat_lon(ciutat, pais):
    url = f"http://api.openweathermap.org/geo/1.0/direct?q={ciutat},{pais}&limit=1&appid={CLAU_API}"
    resposta = requests.get(url)
    res = resposta.json()
    if not res:
        raise Exception("No s'ha pogut obtenir lat/lon")
    return res[0]['lat'], res[0]['lon']

def obtenir_uv(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/uvi?lat={lat}&lon={lon}&appid={CLAU_API}"
    resposta = requests.get(url)
    if resposta.status_code != 200:
        return None
    dades = resposta.json()
    return dades.get('value', None)

def agrupar_per_dia(dades):
    dies = {}
    for entrada in dades["list"]:
        data = entrada["dt_txt"].split(" ")[0]
        if data not in dies:
            dies[data] = []
        dies[data].append(entrada)
    return dies

def obtenir_min_max(dia_entrades):
    temps_min = min(e["main"]["temp_min"] for e in dia_entrades)
    temps_max = max(e["main"]["temp_max"] for e in dia_entrades)
    return temps_min, temps_max

def descarregar_icona(icon_id):
    url = f"http://openweathermap.org/img/wn/{icon_id}@2x.png"
    resposta = requests.get(url)
    return Image.open(BytesIO(resposta.content))

def grau_dia_setmana(data_str, idioma="ca"):
    dt = datetime.strptime(data_str, "%Y-%m-%d")
    idx = dt.weekday()  # 0 dilluns .. 6 diumenge
    return IDIOMES_DIES.get(idioma, IDIOMES_DIES["ca"])[idx]

def afegir_prediccio(pdf, data, entrades_dia, uv=None):
    dt = datetime.strptime(data, "%Y-%m-%d")
    dia_cat = grau_dia_setmana(data, "ca")
    dia_esp = grau_dia_setmana(data, "es")
    dia_eng = grau_dia_setmana(data, "en")
    dia_fra = grau_dia_setmana(data, "fr")

    # Fem servir la predicció de les 12:00 per icona i descripció
    pred_12 = next((e for e in entrades_dia if "12:00:00" in e["dt_txt"]), entrades_dia[0])

    desc = pred_12["weather"][0]["description"].capitalize()
    icon_id = pred_12["weather"][0]["icon"]
    vent = max(e["wind"]["speed"] for e in entrades_dia)
    direccio = pred_12["wind"].get("deg", 0)
    pluja = sum(e.get("rain", {}).get("3h", 0) for e in entrades_dia)
    temp_min, temp_max = obtenir_min_max(entrades_dia)

    # Baixa i guarda la icona
    img = descarregar_icona(icon_id)
    img_path = f"temp_{data}.png"
    img.save(img_path)

    # Icona
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.image(img_path, x=x, y=y, w=25)

    # Text al costat
    pdf.set_xy(x + 30, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"{dia_cat} / {dia_esp} / {dia_eng} / {dia_fra}, {dt.strftime('%d %B %Y')}", ln=True)
    pdf.set_x(x + 30)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        f"{desc}\n"
        f"Temperatura: {temp_min:.1f}°C (mín) - {temp_max:.1f}°C (màx)\n"
        f"Vent màxim: {vent:.1f} km/h ({direccio}°)\n"
        f"Pluja acumulada: {pluja:.1f} mm\n"
        f"Índex UV: {uv if uv is not None else 'No disponible'}"
    )
    pdf.ln(5)

def netejar_icones_temporals():
    for fitxer in glob.glob("temp_*.png"):
        os.remove(fitxer)

def generar_pdf(dades, ciutat):
    pdf = MeteoPDF()
    pdf.add_page()

    lat, lon = obtenir_lat_lon(ciutat, PAIS)
    uv = obtenir_uv(lat, lon)

    dies = agrupar_per_dia(dades)
    dies_ordenats = sorted(dies.keys())[:5]

    for dia in dies_ordenats:
        afegir_prediccio(pdf, dia, dies[dia], uv)

    pdf.output(PDF_NOM)
    print(f"PDF generat: {PDF_NOM}")
    netejar_icones_temporals()

def main():
    dades = obtenir_dades()
    generar_pdf(dades, CIUTAT)

if __name__ == "__main__":
    main()
