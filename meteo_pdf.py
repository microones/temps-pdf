import os
import requests
from fpdf import FPDF
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

PDF_NOM = "previsio_visual.pdf"

IDIOMES_DIES = {
    "ca": ["Dill", "Dim", "Dime", "Dij", "Div", "Dis", "Diu"],
    "es": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "fr": ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
}

# --- Nova funció per obtenir color i etiqueta UV segons valor ---
def color_uv(uv):
    if uv is None:
        return (0, 0, 0), "No disponible"
    if uv < 3:
        return (0, 128, 0), "Baix"  # Verd
    elif uv < 6:
        return (255, 165, 0), "Mitjà"  # Taronja
    elif uv < 8:
        return (255, 0, 0), "Alt"  # Vermell
    else:
        return (128, 0, 128), "Molt alt"  # Porpra

# --- Funció per dibuixar fletxa direcció vent ---
def dibuixar_fletxa(pdf, x, y, mida, graus):
    # Convertim graus a radians
    rad = math.radians(graus - 90)  # -90 perquè 0º és Nord (amunt)
    llarg = mida * 0.8
    dx = llarg * math.cos(rad)
    dy = llarg * math.sin(rad)

    # Dibuixar línia principal
    pdf.set_draw_color(0, 0, 0)
    pdf.line(x, y, x + dx, y + dy)

    # Fletxa al final
    angle_fletxa = math.radians(30)
    mida_fletxa = mida * 0.3

    # punt final de la línia
    xf, yf = x + dx, y + dy

    # punt esquerra fletxa
    xl = xf - mida_fletxa * math.cos(rad - angle_fletxa)
    yl = yf - mida_fletxa * math.sin(rad - angle_fletxa)

    # punt dreta fletxa
    xr = xf - mida_fletxa * math.cos(rad + angle_fletxa)
    yr = yf - mida_fletxa * math.sin(rad + angle_fletxa)

    # Dibuixa fletxa
    pdf.line(xf, yf, xl, yl)
    pdf.line(xf, yf, xr, yr)

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
    # Nota: API UVI antiga, es podria substituir per la nova "onecall"
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

def afegir_taula_horaria(pdf, entrades_dia, x_inicial, y_inicial, ample):
    pdf.set_xy(x_inicial, y_inicial)
    pdf.set_font("Helvetica", "B", 9)
    # Columnes: hora | icono | temp | vent (fletxa) | pluja | descripció curta
    cols = ["Hora", "Icona", "Temp (°C)", "Vent", "Pluja (mm)", "Descripció"]
    col_ample = [15, 15, 20, 20, 25, ample - 95]

    # Header taula
    for i, col in enumerate(cols):
        pdf.cell(col_ample[i], 7, col, border=1, align="C")
    pdf.ln()

    # Contingut
    pdf.set_font("Helvetica", "", 8)
    y_row = pdf.get_y()

    for e in entrades_dia:
        dt = datetime.strptime(e["dt_txt"], "%Y-%m-%d %H:%M:%S")
        hora = dt.strftime("%H:%M")

        # Icona meteorològica
        icon_id = e["weather"][0]["icon"]
        img = descarregar_icona(icon_id)
        img_path = f"temp_icon_{e['dt_txt'].replace(' ', '_').replace(':', '')}.png"
        img.save(img_path)

        # Hora
        pdf.cell(col_ample[0], 10, hora, border=1, align="C")

        # Icona (imatge petita)
        x_img = pdf.get_x()
        y_img = pdf.get_y() - 9  # ajust perquè el cell avança y
        pdf.cell(col_ample[1], 10, "", border=1)
        pdf.image(img_path, x=x_img + 2, y=y_img + 1, w=12)
        
        # Temp
        temp = e["main"]["temp"]
        pdf.cell(col_ample[2], 10, f"{temp:.1f}", border=1, align="C")

        # Vent: fletxa indicativa
        vent = e["wind"]["speed"]
        direccio = e["wind"].get("deg", 0)
        x_vent = pdf.get_x() + col_ample[3] / 2
        y_vent = pdf.get_y() - 5
        pdf.cell(col_ample[3], 10, "", border=1)
        dibuixar_fletxa(pdf, x_vent, y_vent, 8, direccio)

        # Pluja
        pluja = e.get("rain", {}).get("3h", 0)
        pdf.cell(col_ample[4], 10, f"{pluja:.1f}", border=1, align="C")

        # Descripció curta
        desc = e["weather"][0]["description"].capitalize()
        pdf.cell(col_ample[5], 10, desc, border=1)

        pdf.ln()

        # Elimina la icona temporal
        os.remove(img_path)

def afegir_prediccio(pdf, data, entrades_dia, uv=None):
    dt = datetime.strptime(data, "%Y-%m-%d")
    dia_cat = grau_dia_setmana(data, "ca")
    dia_esp = grau_dia_setmana(data, "es")
    dia_eng = grau_dia_setmana(data, "en")
    dia_fra = grau_dia_setmana(data, "fr")

    # Predicció de les 12:00 per icona i descripció general
    pred_12 = next((e for e in entrades_dia if "12:00:00" in e["dt_txt"]), entrades_dia[0])

    desc = pred_12["weather"][0]["description"].capitalize()
    icon_id = pred_12["weather"][0]["icon"]
    vent = max(e["wind"]["speed"] for e in entrades_dia)
    direccio = pred_12["wind"].get("deg", 0)
    pluja = sum(e.get("rain", {}).get("3h", 0) for e in entrades_dia)
    temp_min, temp_max = obtenir_min_max(entrades_dia)

    # Baixa i guarda la icona principal
    img = descarregar_icona(icon_id)
    img_path = f"temp_{data}.png"
    img.save(img_path)

    # Icona gran
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.image(img_path, x=x, y=y, w=25)

    # Text al costat (dia en 4 idiomes)
    pdf.set_xy(x + 30, y)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"{dia_cat} / {dia_esp} / {dia_eng} / {dia_fra}, {dt.strftime('%d %B %Y')}", ln=True)

    # UV color i text
    color, uv_text = color_uv(uv)

    pdf.set_x(x + 30)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6,
        f"{desc}\n"
        f"Temperatura: {temp_min:.1f}°C (mín) - {temp_max:.1f}°C (màx)\n"
        f"Vent màxim: {vent:.1f} km/h ({direccio}°)\n"
        f"Pluja acumulada: {pluja:.1f} mm\n"
        f"Índex UV: {uv} ({uv_text})"
    )
    # Dibuixar quadrat color UV
    uv_box_x = pdf.get_x() + 5
    uv_box_y = pdf.get_y() - 14
    pdf.set_fill_color(*color)
    pdf.rect(uv_box_x, uv_box_y, 10, 10, style="F")

    pdf.ln(10)

    # Afegim la taula horària amb la previsió detallada
    afegir_taula_horaria(pdf, entrades_dia, pdf.get_x(), pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin)
    pdf.ln(10)

    # Neteja icona temporal
    os.remove(img_path)

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
