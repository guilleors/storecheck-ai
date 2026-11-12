import os
import csv
import json
import time
import unicodedata
import resend
from groq import Groq

# Configuración de credenciales
resend.api_key = os.getenv("RESEND_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ARCHIVO_MAESTRO = "leads_globales.csv"
ARCHIVO_LOG = "historial_invitaciones_globales.csv"

# Diccionario de equivalencias multilingües para unificar encabezados del CSV
ALIAS_COLUMNAS = {
    "nombre": [
        "nombre", "first name", "firstname", "name", "contact", "contacto",
        "prenom", "prénom", "nom", "nome", "vorname", "person", "姓名", "名字"
    ],
    "email": [
        "email", "e-mail", "mail", "correo", "correo electronico",
        "email address", "work email", "courriel", "adresse email", "e-mail-adresse", "邮箱", "電子郵件"
    ],
    "web": [
        "web", "website", "sitio web", "dominio", "domain", "url",
        "primary domain", "company website", "site web", "site", "webseite", "网站", "網址"
    ],
    "pais": [
        "pais", "country", "location", "ubicacion", "country/region",
        "company country", "organization country", "pays", "paese", "land", "国家", "國家"
    ]
}

def limpiar_texto_clave(texto):
    """Normaliza encabezados quitando tildes y espacios"""
    if not texto:
        return ""
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")

def obtener_campo_unificado(fila, clave_objetivo):
    """Busca el valor de un campo sin importar el idioma del encabezado"""
    alias_validos = ALIAS_COLUMNAS.get(clave_objetivo, [])
    for col_original, valor in fila.items():
        col_limpia = limpiar_texto_clave(col_original)
        if col_limpia in alias_validos and valor and valor.strip():
            return valor.strip()
    return ""

def cargar_emails_enviados():
    if not os.path.exists(ARCHIVO_LOG):
        return set()
    with open(ARCHIVO_LOG, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["email"].strip().lower() for row in reader if row.get("email")}

def guardar_en_log(datos):
    archivo_existe = os.path.exists(ARCHIVO_LOG)
    with open(ARCHIVO_LOG, mode="a", newline="", encoding="utf-8") as f:
        campos = ["fecha", "nombre", "email", "web", "pais", "idioma", "asunto", "estado"]
        writer = csv.DictWriter(f, fieldnames=campos)
        if not archivo_existe:
            writer.writeheader()
        writer.writerow(datos)

def leer_leads_maestros():
    if not os.path.exists(ARCHIVO_MAESTRO):
        print(f"⚠️ No se encontró '{ARCHIVO_MAESTRO}'. Ejecutá primero 'recolector_global.py'.")
        return []
    with open(ARCHIVO_MAESTRO, mode="r", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def redactar_invitacion_inteligente(nombre, web, pais):
    """Adapta el idioma según región macro y asegura saludo cálido con pregunta directa"""
    
    es_generico = not nombre or nombre.strip().lower() in ["equipo", "team", "hola", "info", "admin", "desconocido"]
    
    if es_generico:
        plantilla_base = f"¡Hola! Espero estés muy bien. Me tomé el atrevimiento de explorar {web} y observé algunos detalles que pueden estar afectando el flujo de ventas. ¿Te interesa un reporte rápido y sin costo con algunos puntos a mejorar?"
        instruccion_saludo = "Arranca el correo con un saludo cálido equivalente a '¡Hola! Espero estés muy bien.', sin mencionar nombres propios."
    else:
        plantilla_base = f"¡Hola, {nombre}! Espero estés muy bien. Me tomé el atrevimiento de explorar {web} y observé algunos detalles que pueden estar afectando el flujo de ventas. ¿Te interesa un reporte rápido y sin costo con algunos puntos a mejorar?"
        instruccion_saludo = f"Incluye el nombre '{nombre}' de forma natural en el saludo (en idiomas como el chino, integrándolo con total respeto comercial)."

    prompt = f"""
    Actúa como un especialista en optimización de tiendas online (CRO).
    
    Datos del prospecto:
    - Sitio web: {web}
    - País de origen de la empresa: {pais}
    
    Regla maestra de idioma y región:
    Analiza el país "{pais}" y determina su idioma oficial o comercial principal, aplicando su variante regional natural correspondiente:
    - Bloque Hispanoamérica y España -> Español natural y fluido.
    - Bloque Brasil y Portugal -> Portugués nativo.
    - Bloque Chino (China, Taiwán, etc.) -> Chino Mandarín comercial, educado y directo.
    - Bloque Angloparlante e Internacional (EE.UU., Reino Unido, resto de Europa o países globales) -> Inglés profesional y cercano.
    - Francia y países francófonos -> Francés.
    - Alemania y Europa central -> Alemán.
    (Si el país es desconocido o no se puede determinar, usa inglés por defecto).
    
    Plantilla base a traducir y adaptar de forma nativa (asegúrate de usar una pregunta directa como "¿Te interesa...?" o su equivalente comercial exacto en el idioma destino):
    "{plantilla_base}"
    
    Instrucciones:
    1. {instruccion_saludo}
    2. Traduce la plantilla manteniendo un tono cálido, cercano y ultra profesional al idioma correspondiente de {pais}.
    3. Crea un asunto (subject) corto y directo en ese mismo idioma (equivalente a "Una consulta sobre {web}").
    4. Responde ÚNICAMENTE con un JSON válido con las claves: "idioma_usado", "asunto", "cuerpo".
    """
    
    completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    return json.loads(completion.choices[0].message.content)

def ejecutar_fase1_lotes():
    ya_contactados = cargar_emails_enviados()
    leads = leer_leads_maestros()
    
    if not leads:
        return

    print(f"📂 Leyendo {len(leads)} prospectos desde '{ARCHIVO_MAESTRO}'...\n")
    procesados = 0

    for row in leads:
        nombre = obtener_campo_unificado(row, "nombre")
        email = obtener_campo_unificado(row, "email").lower()
        web = obtener_campo_unificado(row, "web")
        pais = obtener_campo_unificado(row, "pais") or "Desconocido"

        if not email or not web:
            continue

        if email in ya_contactados:
            print(f"⏭️ Saltando {email} (ya fue contactado previamente).")
            continue

        print(f"📍 País sede: {pais} | Web: {web} | Contacto: {nombre or 'Sin nombre'}")
        
        ia = redactar_invitacion_inteligente(nombre, web, pais)
        idioma = ia.get("idioma_usado")
        asunto = ia.get("asunto")
        cuerpo = ia.get("cuerpo")

        print(f"🗣️ Idioma: {idioma} | Asunto: {asunto}")
        print(f"✉️ Mensaje:\n{cuerpo}\n")

        try:
            params = {
                "from": "StoreCheck AI <onboarding@resend.dev>",
                "to": [email],
                "subject": asunto,
                "html": f"<p>{cuerpo}</p>"
            }
            # Descomentá cuando habilites el envío masivo real con Resend:
            # resend.Emails.send(params)
            
            guardar_en_log({
                "fecha": time.strftime("%Y-%m-%d %H:%M"),
                "nombre": nombre if nombre else "Sin nombre",
                "email": email,
                "web": web,
                "pais": pais,
                "idioma": idioma,
                "asunto": asunto,
                "estado": "Invitacion enviada"
            })
            ya_contactados.add(email)
            procesados += 1
            time.sleep(1.5)
            
        except Exception as e:
            print(f"❌ Error procesando {email}: {e}\n")

    print(f"✅ Proceso finalizado. Se prepararon {procesados} invitaciones nuevas.")

if __name__ == "__main__":
    ejecutar_fase1_lotes()
