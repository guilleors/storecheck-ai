import os
import csv
import json
import time
import requests
import resend
from groq import Groq

# 1. Credenciales desde variables de entorno
resend.api_key = os.getenv("RESEND_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")

ARCHIVO_LOG = "historial_invitaciones_globales.csv"

def cargar_emails_enviados():
    """Evita volver a escribirle a alguien que ya fue contactado"""
    if not os.path.exists(ARCHIVO_LOG):
        return set()
    with open(ARCHIVO_LOG, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["email"] for row in reader if row.get("email")}

def guardar_en_log(datos):
    """Guarda cada registro para control de la Fase 1"""
    archivo_existe = os.path.exists(ARCHIVO_LOG)
    with open(ARCHIVO_LOG, mode="a", newline="", encoding="utf-8") as f:
        campos = ["fecha", "nombre", "email", "web", "pais", "idioma", "asunto", "estado"]
        writer = csv.DictWriter(f, fieldnames=campos)
        if not archivo_existe:
            writer.writeheader()
        writer.writerow(datos)

def buscar_prospectos_apollo(pagina=1, cantidad=5):
    """Busca decisores de e-commerce usando Apollo.io"""
    url = "https://api.apollo.io/api/v1/mixed_people/api_search"
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "x-api-key": APOLLO_API_KEY
    }
    payload = {
        "person_titles": ["Ecommerce Manager", "Head of Ecommerce", "Founder", "CEO"],
        "q_organization_keyword_tags": ["ecommerce", "retail", "online store"],
        "contact_email_status": ["verified"],
        "per_page": cantidad,
        "page": pagina
    }
    
    print(f"🌐 Buscando empresas e-commerce en Apollo.io (Página {pagina})...")
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        return response.json().get("people", [])
    else:
        print(f"❌ Error en Apollo: {response.status_code} - {response.text}")
        return []

def redactar_por_pais_de_origen(nombre, web, pais):
    """Regla estricta: El país de la empresa determina 100% el idioma del correo"""
    prompt = f"""
    Actúa como un especialista en optimización de tiendas online (CRO).
    
    Datos del prospecto:
    - Nombre del contacto: {nombre}
    - Sitio web: {web}
    - País donde está radicada la empresa: {pais}
    
    Regla de idioma estricta:
    Determina el idioma oficial del país "{pais}" y redacta el correo en ESE idioma nativo.
    Ejemplos:
    - Francia -> Francés
    - Perú / España / México -> Español
    - Brasil -> Portugués
    - Alemania -> Alemán
    - EE.UU. / Reino Unido / Canadá -> Inglés
    (Si el país es desconocido o no figura, usa inglés por defecto).
    
    Plantilla base a traducir/adaptar al idioma oficial del país:
    "Hola {nombre}, me tomé el atrevimiento de explorar {web} y observé algunos detalles que pueden estar afectando el flujo de ventas. ¿Te interesaría un reporte rápido y sin costo con algunos puntos a mejorar?"
    
    Instrucciones:
    1. Traduce la plantilla de forma natural, fluida y humana al idioma oficial de {pais}.
    2. Crea un asunto (subject) corto en ese mismo idioma (ej. "Una consulta sobre {web}").
    3. Responde ÚNICAMENTE con un JSON válido con las claves: "idioma_usado", "asunto", "cuerpo".
    """
    
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

def ejecutar_fase1():
    ya_contactados = cargar_emails_enviados()
    prospectos = buscar_prospectos_apollo(pagina=1, cantidad=5)
    
    if not prospectos:
        print("No se encontraron prospectos.")
        return

    print(f"✅ Se obtuvieron {len(prospectos)} prospectos para evaluar.\n")

    for p in prospectos:
        nombre = p.get("first_name") or p.get("name", "hola")
        email = p.get("email")
        org = p.get("organization", {})
        web = org.get("primary_domain") or org.get("name", "su sitio web")
        pais = org.get("country") or p.get("country") or "Desconocido"

        if not email or not web:
            continue

        if email in ya_contactados:
            print(f"⏭️ Saltando {email} (ya procesado previamente).")
            continue

        print(f"📍 Empresa radicada en: {pais} | Contacto: {nombre} | Web: {web}")
        
        resultado = redactar_por_pais_de_origen(nombre, web, pais)
        idioma = resultado.get("idioma_usado")
        asunto = resultado.get("asunto")
        cuerpo = resultado.get("cuerpo")

        print(f"🗣️ Idioma asignado: {idioma}")
        print(f"📌 Asunto: {asunto}")
        print(f"✉️ Mensaje:\n{cuerpo}\n")

        try:
            params = {
                "from": "StoreCheck AI <onboarding@resend.dev>",
                "to": [email],
                "subject": asunto,
                "html": f"<p>{cuerpo}</p>"
            }
            # Descomentar al tener el dominio final en Resend:
            # resend.Emails.send(params)
            
            guardar_en_log({
                "fecha": time.strftime("%Y-%m-%d %H:%M"),
                "nombre": nombre,
                "email": email,
                "web": web,
                "pais": pais,
                "idioma": idioma,
                "asunto": asunto,
                "estado": "Invitacion enviada"
            })
            ya_contactados.add(email)
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ Error con {email}: {e}\n")

if __name__ == "__main__":
    ejecutar_fase1()
