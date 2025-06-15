import os
import requests
from fpdf import FPDF
from fpdf.enums import XPos, YPos  # <-- importem les constants noves
from datetime import datetime
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import glob
import math

load_dotenv()
CLAU_API = os.getenv("CLAU_API")
CIUTAT = "Salou"
PAIS = "ES"

PDF_NOM = "previsio_compacta.pdf"

IDIOMES_DIES = {
    "ca": ["Dill", "Dim", "Dime", "Dij", "Div", "Dis", "Diu"],
    "es": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "fr": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
}

# Traducció curta per descripcions comunes (sense accents ni majúscules per uniformitat)
DESC_TRADUCCIONS = {
    "clear sky": {"ca": "cel clar", "es": "cielo claro", "en": "clear sky", "fr": "ciel clair"},
    "few clouds": {"ca": "pocs núvols", "es": "pocos nubes", "en": "few clouds", "fr": "quelques nuages"},
    "scattered clouds": {"ca": "núvols dispersos", "es": "nubes dispersas", "en": "scattered clouds", "fr": "nuages épars"},
    "broken clouds": {"ca": "núvols trencats", "es": "nubes rotas", "en": "broken clouds", "fr": "nuages fragmentés"},
    "shower rain": {"ca": "ruixat", "es": "chubasco", "en": "shower rain", "fr": "averse"},
    "rain": {"ca": "pluja", "es": "lluvia", "en": "rain", "fr": "pluie"},
    "thunderstorm": {"ca": "tempesta", "es": "tormenta", "en": "thunderstorm", "fr": "orage"},
    "snow": {"ca": "neu", "es": "nieve", "en": "snow", "fr": "neige"},
    "mist": {"ca": "boira", "es": "niebla", "en": "mist", "fr": "brume"},
    # afegeix més si vols
}

def traduir_desc(desc):
    desc = desc.lower()
    if desc in DESC_TRADUCCIONS:
        return ", ".join([DESC_TRADUCCIONS[desc][lang] for lang in ["ca", "es", "en", "fr"]])
    return desc  # si no troba, retorna original

def color_uv(uv):
    if uv is None:
        return (0, 0, 0), "No disponible"
    if uv < 3:
        return (0, 128, 0), "Baix"
    elif uv < 6:
        return (255, 165, 0), "Mitjà"
    elif uv < 8:
        return (255, 0, 0), "Alt"
    else:
        return (128, 0, 128), "Molt alt"

def dibuixar_fletxa(pdf, x, y, mida, graus):
    rad = math.radians(graus - 90)
    llarg = mida * 0.7
    dx = llarg * math.cos(rad)
    dy = llarg * math.sin(rad)

    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.3)
    pdf.line(x, y, x + dx, y + dy)

    angle_fletxa = math.radians(30)
    mida_fletxa = mida * 0.25
    xf, yf = x + dx, y + dy
    xl = xf - mida_fletxa * math.cos(rad - angle_fletxa)
    yl = yf - mida_fletxa * math.sin(rad - angle_fletxa)
    xr = xf - mida_fletxa * math.cos(rad + angle_fletxa)
    yr = yf - mida_fletxa * math.sin(rad + angle_fletxa)
    pdf.line(xf, yf, xl, yl)
    pdf.line(xf, yf, xr, yr)

class MeteoPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, f"Previsió meteorològica (5 dies) - {CIUTAT}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
        self.ln(2)

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
    idx = dt.weekday()
    return IDIOMES_DIES.get(idioma, IDIOMES_DIES["ca"])[idx]

def afegir_taula_horaria(pdf, entrades_dia, x_inicial, y_inicial):
    pdf.set_xy(x_inicial, y_inicial)
    pdf.set_font("Helvetica", "B", 8)

    cols = ["Hora", "Icona", "Temp (°C)", "Vent", "Pluja (mm)"]
    col_ample = [15, 15, 20, 20, 20]
    # Amplada total: 15+15+20+20+20 = 90 aprox, deixa marge per imprimir

    for i, col in enumerate(cols):
        pdf.cell(col_ample[i], 7, col, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", "", 7.5)

    for e in entrades_dia:
        dt = datetime.strptime(e["dt_txt"], "%Y-%m-%d %H:%M:%S")
        hora = dt.strftime("%H:%M")

        icon_id = e["weather"][0]["icon"]
        img = descarregar_icona(icon_id)
        img = img.resize((12, 12))  # Ajusta la mida aquí
        img_path = f"temp_icon_{e['dt_txt'].replace(' ', '_').replace(':', '')}.png"
        img.save(img_path)

        pdf.cell(col_ample[0], 9, hora, border=1, align="C")

        x_img = pdf.get_x()
        y_img = pdf.get_y() - 8  # Ajust vertical perquè encaixi

        pdf.cell(col_ample[1], 9, "", border=1)
        pdf.image(img_path, x=x_img + 2, y=y_img + 1.5, w=12, h=12)

        temp = e["main"]["temp"]
        pdf.cell(col_ample[2], 9, f"{temp:.1f}", border=1, align="C")

        vent = e["wind"]["speed"]
        direccio = e["wind"].get("deg", 0)

        x_vent = pdf.get_x() + col_ample[3] / 2
        y_vent = pdf.get_y() - 5
        pdf.cell(col_ample[3], 9, "", border=1)
        dibuixar_fletxa(pdf, x_vent, y_vent, 8, direccio)

        pluja = e.get("rain", {}).get("3h", 0)
        pdf.cell(col_ample[4], 9, f"{pluja:.1f}", border=1, align="C")

        pdf.ln()

        os.remove(img_path)

def afegir_prediccio(pdf, data, entrades_dia, uv=None):
    dt = datetime.strptime(data, "%Y-%m-%d")
    dia_cat = grau_dia_setmana(data, "ca")
    dia_esp = grau_dia_setmana(data, "es")
    dia_eng = grau_dia_setmana(data, "en")
    dia_fra = grau_dia_setmana(data, "fr")

    pred_12 = next((e for e in entrades_dia if "12:00:00" in e["dt_txt"]), entrades_dia[0])
    desc_original = pred_12["weather"][0]["description"].lower()
    desc_4idiomes = traduir_desc(desc_original)

    icon_id = pred_12["weather"][0]["icon"]
    vent = max(e["wind"]["speed"] for e in entrades_dia)
    direccio = pred_12["wind"].get("deg", 0)
    pluja = sum(e.get("rain", {}).get("3h", 0) for e in entrades_dia)

    temp_min, temp_max = obtenir_min_max(entrades_dia)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"{dia_cat} / {dia_esp} / {dia_eng} / {dia_fra}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"{desc_4idiomes}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    x_icon = pdf.get_x()
    y_icon = pdf.get_y() + 2
    pdf.image(f"http://openweathermap.org/img/wn/{icon_id}@2x.png", x=x_icon, y=y_icon, w=30, h=30)
    pdf.ln(30)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 7, f"Temp mín: {temp_min:.1f} °C   Temp màx: {temp_max:.1f} °C", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    pdf.set_font("Helvetica", "", 10)
    x_vent = pdf.get_x()
    y_vent = pdf.get_y() + 3
    dibuixar_fletxa(pdf, x_vent + 20, y_vent, 15, direccio)
    pdf.set_xy(x_vent, y_vent - 3)
    pdf.cell(0, 7, f"Vent: {vent:.1f} m/s", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    pdf.cell(0, 7, f"Pluja: {pluja:.1f} mm", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    if uv is not None:
        (r, g, b), nivell = color_uv(uv)
        pdf.set_fill_color(r, g, b)
        pdf.cell(0, 8, f"Índex UV: {uv:.1f} ({nivell})", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L", fill=True)
    else:
        pdf.cell(0, 8, f"Índex UV: No disponible", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")

    pdf.ln(4)

def generar_pdf(dades):
    pdf = MeteoPDF()
    pdf.add_page()

    dies = agrupar_per_dia(dades)

    lat, lon = obtenir_lat_lon(CIUTAT, PAIS)
    uv = obtenir_uv(lat, lon)

    for i, (data, entrades) in enumerate(dies.items()):
        if i == 5:
            break  # 5 dies

        afegir_prediccio(pdf, data, entrades, uv)

        x_inicial = pdf.get_x()
        y_inicial = pdf.get_y()
        afegir_taula_horaria(pdf, entrades, x_inicial, y_inicial)

        pdf.ln(15)

    pdf.output(PDF_NOM)
    print(f"PDF generat: {PDF_NOM}")

def main():
    dades = obtenir_dades()
    generar_pdf(dades)

if __name__ == "__main__":
    main()
