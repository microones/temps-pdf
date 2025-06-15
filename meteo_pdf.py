import os
from dotenv import load_dotenv
import requests
from fpdf import FPDF
from datetime import datetime

# Carrega el .env
load_dotenv()
CLAU_API = os.getenv("CLAU_API")

CIUTAT = "Salou"
PAIS = "ES"

def obtenir_dades():
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={CIUTAT},{PAIS}&units=metric&lang=ca&appid={CLAU_API}"
    resposta = requests.get(url)
    dades = resposta.json()
    
    if resposta.status_code != 200 or "list" not in dades:
        raise Exception(f"Error en obtenir dades: {dades.get('message', 'Desconegut')}")
    
    return dades

def generar_pdf(dades):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"Previsió meteorològica: {CIUTAT}", ln=True)

    pdf.set_font("Arial", "", 12)
    for entrada in dades["list"][:7*2]:
        dt_txt = entrada["dt_txt"]
        desc = entrada["weather"][0]["description"].capitalize()
        temp = entrada["main"]["temp"]
        text = f"{dt_txt}: {desc}, {temp:.1f}°C"
        pdf.cell(0, 10, text, ln=True)

    pdf.output("previsio_setmanal.pdf")

def main():
    dades = obtenir_dades()
    generar_pdf(dades)
    print("✅ PDF generat: previsio_setmanal.pdf")

if __name__ == "__main__":
    main()
