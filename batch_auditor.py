import os
import csv
import json
import time
import unicodedata
from datetime import datetime
import resend
from groq import Groq

# Configuración de credenciales
resend.api_key = os.getenv("RESEND_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ARCHIVO_PROSPECTOS = "prospectos_storecheck.csv"
ARCHIVO_HISTORIAL = "historial_invitaciones_globales.csv"
COLUMNAS_HISTORIAL = ["Fecha", "Email", "Web", "Contacto", "Pais", "Estado"]

def normalizar_texto(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def obtener_idioma_por_pais(pais):
    p = normalizar_texto(pais)
    if any(k in p for k in ["argentina", "mexico", "espana", "colombia", "chile", "peru", "uruguay", "ecuador", "panama", "costa rica", "guatemala"]):
        return "Español"
    elif any(k in p for k in ["brasil", "brazil", "portugal"]):
        return "Portugués"
    elif any(k in p for k in ["francia", "france", "belgica", "belgium"]):
        return "Francés"
    elif any(k in p for k in ["italia", "italy"]):
        return "Italiano"
    elif any(k in p for k in ["alemania", "germany", "austria", "suiza", "switzerland"]):
        return "Alemán"
    else:
        return "Inglés"

def cargar_emails_enviados():
    enviados = set()
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for fila in reader:
                email = fila.get("Email", "").strip().lower()
                if email:
                    enviados.add(email)
    return enviados

def obtener_valor_columna(fila, posibles_nombres, default=""):
    for k, v in fila.items():
        if normalizar_texto(k) in posibles_nombres and v and str(v).strip():
            return str(v).strip()
    return default

def redactar_invitacion_inteligente(nombre, web, pais):
    idioma = obtener_idioma_por_pais(pais)
    saludo_nombre = nombre if nombre and nombre.lower() not in ["equipo", "team", ""] else "equipo"

    prompt = f"""
    Eres un consultor experto en optimización de conversión (CRO) de tiendas online.
    Redacta un correo de primer contacto B2B muy breve, directo y amable dirigido a {saludo_nombre} de la tienda {web}.
    
    Requisitos estrictos:
    1. Idioma: Redacta TODO (asunto y cuerpo) en {idioma} natural y profesional.
    2. Tono: Cálido, directo y de colega a colega, sin sonar a vendedor agresivo ni usar palabras spam.
    3. Contenido: Saluda a {saludo_nombre}, comenta que exploraste {web} y observaste algunos detalles que podrían estar afectando el flujo de ventas. Pregunta si le interesa recibir un reporte rápido y sin costo con algunos puntos concretos a mejorar.
    4. Longitud: Máximo 45 palabras en el cuerpo.
    5. Formato de salida: Devuelve ÚNICAMENTE un JSON válido con las claves "asunto" y "cuerpo". Sin texto adicional.
    """

    modelos = [
        "qwen/qwen3.8-27b",
        "allam-2-7b"
    ]

    last_error = None
    for modelo in modelos:
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=modelo,
                temperature=0.6,
                response_format={"type": "json_object"}
            )
            return json.loads(chat_completion.choices[0].message.content)
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"No se pudo conectar con ningún modelo de Groq: {last_error}")

def procesar_lote():
    if not os.path.exists(ARCHIVO_PROSPECTOS):
        print(f"❌ No se encontró el archivo '{ARCHIVO_PROSPECTOS}'.")
        return

    emails_enviados = cargar_emails_enviados()

    with open(ARCHIVO_PROSPECTOS, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        prospectos = list(reader)

    print(f"📂 Leyendo {len(prospectos)} prospectos desde '{ARCHIVO_PROSPECTOS}'...\n")

    archivo_nuevo = not os.path.exists(ARCHIVO_HISTORIAL) or os.path.getsize(ARCHIVO_HISTORIAL) == 0
    nuevas_invitaciones = 0

    with open(ARCHIVO_HISTORIAL, mode="a", newline="", encoding="utf-8-sig") as f_hist:
        writer = csv.DictWriter(f_hist, fieldnames=COLUMNAS_HISTORIAL)
        if archivo_nuevo:
            writer.writeheader()

        for fila in prospectos:
            email = obtener_valor_columna(fila, ["email", "correo", "mail", "e-mail"]).lower()
            web = obtener_valor_columna(fila, ["web", "website", "url", "dominio", "tienda", "domain"])
            nombre = obtener_valor_columna(fila, ["contacto", "nombre", "name", "first name", "persona"], "Equipo")
            pais = obtener_valor_columna(fila, ["pais", "country", "ubicacion", "location", "sede"], "Estados Unidos")

            if not email or not web:
                continue

            if email in emails_enviados:
                continue

            print(f"📍 País sede: {pais} | Web: {web} | Contacto: {nombre}")
            try:
                ia = redactar_invitacion_inteligente(nombre, web, pais)
                asunto = ia.get("asunto", f"Una consulta sobre {web}")
                cuerpo = ia.get("cuerpo", "")

                print(f"👤 Idioma: {obtener_idioma_por_pais(pais)} | Asunto: {asunto}")
                print(f"✉️ Mensaje:\n{cuerpo}\n")

                params = {
                    "from": "StoreCheck AI <onboarding@resend.dev>", # <-- Cambiar por tu remitente verificado en Resend cuando salgas a producción
                    "to": [email],
                    "reply_to": "storecheckai@gmail.com",
                    "subject": asunto,
                    "text": cuerpo
                }

                # DESCOMENTAR ESTA LÍNEA PARA ENVIAR CORREOS REALES:
                # resend.Emails.send(params)

                writer.writerow({
                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "Email": email,
                    "Web": web,
                    "Contacto": nombre,
                    "Pais": pais,
                    "Estado": "Invitacion enviada"
                })
                f_hist.flush()

                emails_enviados.add(email)
                nuevas_invitaciones += 1
                time.sleep(1.5)

            except Exception as e:
                print(f"❌ Error procesando {email}: {e}\n")

    print(f"✅ Proceso finalizado. Se prepararon {nuevas_invitaciones} invitaciones nuevas.")

if __name__ == "__main__":
    procesar_lote()
