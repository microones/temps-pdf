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

# Nom del fitxer PDF final
PDF_NOM = "previsio_visual.pdf"

# FPDF configurat
class MeteoPDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 16)
        self.cell(0, 10, f"Previsió meteorològica (5 dies): {CIUTAT}", ln=True, align="C")
        self.ln(5)

def obtenir_dades():
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={CIUTAT},{PAIS}&units=metric&lang=ca&appid={CLAU_API}"
    resposta = requests.get(url)
    dades = resposta.json()
    
    if resposta.status_code != 200 or "list" not in dades:
        raise Exception(f"Error en obtenir dades: {dades.get('message', 'Desconegut')}")
    
    return dades

def filtrar_entrades_a_migdia(dades):
    prediccions = {}
    for entrada in dades["list"]:
        if "12:00:00" in entrada["dt_txt"]:
            data = entrada["dt_txt"].split(" ")[0]
            prediccions[data] = entrada
            if len(prediccions) == 5:
                break
    return prediccions

def descarregar_icona(icon_id):
    url = f"http://openweathermap.org/img/wn/{icon_id}@2x.png"
    resposta = requests.get(url)
    return Image.open(BytesIO(resposta.content))

def afegir_prediccio(pdf, data, entrada):
    dt = datetime.strptime(data, "%Y-%m-%d").strftime("%A, %d %B")
    desc = entrada["weather"][0]["description"].capitalize()
    temp = entrada["main"]["temp"]
    temp_min = entrada["main"]["temp_min"]
    temp_max = entrada["main"]["temp_max"]
    vent = entrada["wind"]["speed"]
    direccio = entrada["wind"].get("deg", 0)
    pluja = entrada.get("rain", {}).get("3h", 0)
    icona = entrada["weather"][0]["icon"]

    # Icona
    img = descarregar_icona(icona)
    img_path = f"temp_{data}.png"
    img.save(img_path)

    # Posició
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.image(img_path, x=x, y=y, w=20)

    # Text al costat
    pdf.set_xy(x + 25, y)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, dt, ln=True)
    pdf.set_x(x + 25)
    pdf.set_font("Arial", "", 11)
    pdf.multi_cell(0, 6,
        f"{desc}\n"
        f"Temperatura: {temp:.1f}°C (mín: {temp_min:.1f}°C, màx: {temp_max:.1f}°C)\n"
        f"Vent: {vent:.1f} km/h ({direccio}°)\n"
        f"Pluja prevista: {pluja} mm"
    )
    pdf.ln(5)

def netejar_icones_temporals():
    for fitxer in glob.glob("temp_*.png"):
        os.remove(fitxer)

def generar_pdf(prediccions):
    pdf = MeteoPDF()
    pdf.add_page()

    for data, entrada in prediccions.items():
        afegir_prediccio(pdf, data, entrada)

    pdf.output(PDF_NOM)
    print(f"PDF generat: {PDF_NOM}")
    netejar_icones_temporals()

def main():
    dades = obtenir_dades()
    prediccions = filtrar_entrades_a_migdia(dades)
    generar_pdf(prediccions)

if __name__ == "__main__":
    main()
