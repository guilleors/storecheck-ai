import csv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import time
import random
import unicodedata
from datetime import datetime
from groq import Groq
import config

# Inicializar cliente de Groq con la clave centralizada
client = Groq(api_key=config.GROQ_API_KEY)

HISTORIAL_FILE = "historial_invitaciones_globales.csv"
MAX_ENVIOS_POR_TANDA = 15
PAUSA_MIN_SEG = 45
PAUSA_MAX_SEG = 90


def normalizar_texto(texto):
    if not texto:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", str(texto))
        if unicodedata.category(c) != "Mn"
    ).lower().strip()


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


def obtener_asunto_por_idioma(idioma, web):
    asuntos = {
        "Español": f"consulta sobre {web}",
        "Portugués": f"dúvida sobre {web}",
        "Francés": f"question concernant {web}",
        "Italiano": f"domanda su {web}",
        "Alemán": f"kurze Frage zu {web}",
        "Inglés": f"quick question about {web}",
    }
    return asuntos.get(idioma, f"quick question about {web}")


def cargar_historial():
    enviados = set()
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    for campo in row:
                        if "@" in campo and "." in campo:
                            enviados.add(campo.strip().lower())
    return enviados


def extraer_primer_nombre(nombre_crudo):
    if not nombre_crudo:
        return "emprendedor"
    limpio = nombre_crudo.strip()
    if not limpio or limpio.lower() in ["equipo", "team", "emprendedor", "contacto"]:
        return limpio if limpio else "emprendedor"
    return limpio.split()[0]


def registrar_enviado(nombre, email, web, pais, asunto):
    print(f"DEBUG: Intentando abrir/crear {HISTORIAL_FILE}...")
    file_exists = os.path.exists(HISTORIAL_FILE) and os.path.getsize(HISTORIAL_FILE) > 0
    idioma = obtener_idioma_por_pais(pais)
    with open(HISTORIAL_FILE, mode="a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            print("DEBUG: El archivo estaba vacío, escribiendo cabecera...")
            writer.writerow(["fecha", "nombre", "email", "web", "pais", "idioma", "asunto", "estado"])

        fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([fecha_actual, nombre, email, web, pais, idioma, asunto, "Invitacion enviada"])
    print(f"DEBUG: ¡Escritura completada con éxito en {HISTORIAL_FILE}!")


def generar_correo(nombre, web, pais):
    saludo = extraer_primer_nombre(nombre)
    idioma = obtener_idioma_por_pais(pais)

    system_prompt = (
        f"Sos un desarrollador web independiente escribiendo un mail de contacto en frío en {idioma}. "
        "Tu única tarea es adaptar el texto de ejemplo al nombre, la web y el idioma correspondiente al país del prospecto, "
        "manteniendo un tono educado, directo, natural y sin sonar robótico. "
        "No inventes párrafos nuevos ni cambies la estructura."
    )

    user_prompt = (
        f"Redactá TODO el correo en {idioma} natural y profesional, tomando como base la idea y estructura de este texto "
        f"para {saludo}, a cargo de {web} (ubicado en {pais}):\n\n"
        f"Hola, {saludo}, ¿cómo estás?\n"
        f"Me tomé el atrevimiento de explorar {web} y noté algunos detalles de fricción en el checkout que seguramente estén interfiriendo en el flujo de ventas.\n"
        f"¿Podrá interesarte, sin compromiso, un pantallazo rápido con un par de ideas para corregirlo?\n"
        f"No dudes en responderme y te lo envío con gusto.\n"
        f"Un abrazo\n\n"
        "Devolvé únicamente el correo listo para enviar (sin asunto ni comillas):"
    )

    modelos = [
        getattr(config, "GROQ_MODEL", None) or "llama-3.3-70b-versatile",
        "qwen/qwen3.8-27b",
    ]
    modelos_unicos = list(dict.fromkeys(modelos))

    last_error = None
    for modelo in modelos_unicos:
        try:
            response = client.chat.completions.create(
                model=modelo,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=300
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"No se pudo generar el correo con Groq: {last_error}")


def enviar_email(destinatario, asunto, cuerpo):
    msg = MIMEMultipart()
    msg['From'] = formataddr(("StoreCheck AI", config.GMAIL_USER))
    msg['To'] = destinatario
    msg['Subject'] = asunto

    msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(config.GMAIL_USER, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error al enviar a {destinatario}: {e}")
        return False


def ejecutar_campana(max_envios=MAX_ENVIOS_POR_TANDA):
    print(f"--- Iniciando barrido de prospectos (tope de tanda: {max_envios}) ---")
    enviados = cargar_historial()

    archivo_prospectos = None
    for posible in ["prospectos_storecheck.csv", "leads_globales.csv", "prospectos.csv", "campana_emails_li.csv"]:
        if os.path.exists(posible):
            archivo_prospectos = posible
            break

    if not archivo_prospectos:
        print("Error: No se encontró ningún archivo CSV de prospectos en la carpeta.")
        return

    print(f"📂 Usando archivo de prospectos: {archivo_prospectos}")

    with open(archivo_prospectos, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        if reader.fieldnames:
            fieldnames_lower = [fn.strip().lower() for fn in reader.fieldnames if fn]
            email_col = 'email' if 'email' in fieldnames_lower else ('mail' if 'mail' in fieldnames_lower else None)
        else:
            email_col = None

        if not email_col:
            print("Error: El CSV no tiene una columna de correo válida ('email' o 'mail').")
            return

        count = 0
        for row in reader:
            if count >= max_envios:
                print(f"\n🛑 Se alcanzó el límite de {max_envios} envíos para esta tanda.")
                break

            row_lower = {k.strip().lower(): (v.strip() if v else "") for k, v in row.items() if k}
            email = row_lower.get(email_col, "").strip()
            email_norm = email.lower()
            nombre = row_lower.get("nombre") or row_lower.get("name") or "emprendedor"
            web = row_lower.get("web") or row_lower.get("sitio") or "su tienda"
            pais = row_lower.get("pais") or row_lower.get("country") or "Latinoamérica"

            if not email_norm or email_norm in enviados:
                continue

            idioma = obtener_idioma_por_pais(pais)
            print(f"\nGenerando correo para {nombre} ({email}) | País: {pais} | Idioma: {idioma}...")
            try:
                cuerpo = generar_correo(nombre, web, pais)
            except Exception as e:
                print(f"-> Error generando correo para {email}: {e}")
                continue

            print("\n" + "="*40)
            print(cuerpo)
            print("="*40 + "\n")

            asunto = obtener_asunto_por_idioma(idioma, web)

            if enviar_email(email, asunto, cuerpo):
                registrar_enviado(nombre, email, web, pais, asunto)
                enviados.add(email_norm)
                print(f"-> ¡Correo enviado con éxito a {email} y registrado en el historial!")
                count += 1

                if count < max_envios:
                    pausa_segura = random.randint(PAUSA_MIN_SEG, PAUSA_MAX_SEG)
                    print(f"⏳ Pausando {pausa_segura} segundos para cuidar la reputación de la cuenta...")
                    time.sleep(pausa_segura)
            else:
                print(f"-> Falló el envío a {email}")

    print(f"\n--- Campaña finalizada. Total correos enviados en esta tanda: {count} ---")


if __name__ == "__main__":
    ejecutar_campana()
