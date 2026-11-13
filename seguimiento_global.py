import os
import csv
import json
import time
import imaplib
import email
from email.utils import parsedate_to_datetime
import unicodedata
from datetime import datetime
import resend
from groq import Groq

# Configuración de credenciales
resend.api_key = os.getenv("RESEND_API_KEY")
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GMAIL_USER = "storecheckai@gmail.com"
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

ARCHIVO_HISTORIAL = "historial_invitaciones_globales.csv"
DIAS_ESPERA = 4

def normalizar_texto(texto):
    if not texto:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', str(texto)) if unicodedata.category(c) != 'Mn').lower().strip()

def get_col(fila, nombre_col, default=""):
    """Busca una columna sin importar mayúsculas/minúsculas."""
    for k, v in fila.items():
        if k and k.strip().lower() == nombre_col.lower():
            return str(v).strip() if v is not None else default
    return default

def set_col(fila, nombre_col, valor):
    """Actualiza una columna respetando su nombre original."""
    for k in fila.keys():
        if k and k.strip().lower() == nombre_col.lower():
            fila[k] = valor
            return
    fila[nombre_col] = valor

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

def clasificar_respuesta_cliente(texto_respuesta):
    """Usa IA para clasificar la intención del cliente en la respuesta recibida."""
    prompt = f"""
    Clasifica el siguiente mensaje de correo electrónico recibido de un prospecto de B2B.
    Responde ÚNICAMENTE con un JSON válido con una clave "categoria" que tenga uno de estos tres valores exactos:
    - "Interesado" (si dijo que sí, pidió los apuntes, mostró interés o hizo una pregunta para avanzar).
    - "No interesado" (si dijo que no le interesa, pidió que no le escribas o rechazó la oferta).
    - "Otro" (si es una respuesta ambigua o fuera de contexto).

    Mensaje del cliente:
    \"\"\"{texto_respuesta}\"\"\"
    """
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="qwen/qwen3.8-27b",
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        resultado = json.loads(chat_completion.choices[0].message.content)
        return resultado.get("categoria", "Otro")
    except Exception:
        return "Otro"

def detectar_respuestas_gmail(filas):
    """Revisa storecheckai@gmail.com vía IMAP, clasifica la respuesta y actualiza el estado."""
    if not GMAIL_APP_PASSWORD:
        print("⚠️ No se detectó GMAIL_APP_PASSWORD en PowerShell. Se omite el chequeo automático de bandeja.\n")
        return 0

    pendientes = {}
    for f in filas:
        est = get_col(f, "estado")
        em = get_col(f, "email").lower()
        if est in ["Invitacion enviada", "Seguimiento enviado"] and em:
            pendientes[em] = f

    if not pendientes:
        return 0

    marcados = 0
    try:
        print(f"📥 Conectando a {GMAIL_USER} para verificar respuestas recibidas...")
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        mail.select("inbox")

        for email_prospecto, fila in pendientes.items():
            status, messages = mail.search(None, f'(FROM "{email_prospecto}")')
            if status == "OK" and messages[0]:
                msg_ids = messages[0].split()
                _, msg_data = mail.fetch(msg_ids[-1], "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                fecha_mail_str = msg.get("Date")
                fecha_envio_str = get_col(fila, "fecha")[:10]

                es_posterior = True
                if fecha_mail_str and fecha_envio_str:
                    try:
                        dt_mail = parsedate_to_datetime(fecha_mail_str).replace(tzinfo=None)
                        dt_envio = datetime.strptime(fecha_envio_str, "%Y-%m-%d")
                        es_posterior = dt_mail >= dt_envio
                    except Exception:
                        es_posterior = True

                if es_posterior:
                    # Extraer el cuerpo del mensaje del cliente
                    cuerpo_cliente = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                cuerpo_cliente = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        cuerpo_cliente = msg.get_payload(decode=True).decode(errors="ignore")

                    # Clasificar con IA
                    intencion = clasificar_respuesta_cliente(cuerpo_cliente)

                    if intencion == "Interesado":
                        set_col(fila, "estado", "Interesado - Enviar Reporte")
                        print(f"🔥 ¡Interés detectado de {email_prospecto}! Estado: Interesado - Enviar Reporte")
                    elif intencion == "No interesado":
                        set_col(fila, "estado", "No interesado")
                        print(f"❌ {email_prospecto} desestimó la oferta. Estado: No interesado")
                    else:
                        set_col(fila, "estado", "Respondido")
                        print(f"💬 Respuesta recibida de {email_prospecto}. Estado: Respondido (revisión manual)")

                    marcados += 1

        mail.logout()
    except Exception as e:
        print(f"⚠️ Error al revisar Gmail por IMAP: {e}")

    print(f"📊 Chequeo de bandeja finalizado: {marcados} respuestas procesadas.\n")
    return marcados

def redactar_seguimiento_inteligente(nombre, web, pais):
    idioma = obtener_idioma_por_pais(pais)
    saludo_nombre = nombre if nombre and nombre.lower() not in ["equipo", "team", ""] else "equipo"

    prompt = f"""
    Eres un consultor experto en optimización de conversión (CRO) de tiendas online.
    Redacta un ÚNICO correo de seguimiento (follow-up) muy breve, cero agresivo y amable, dirigido a {saludo_nombre} de la tienda {web}.
    Contexto: Hace 4 días le enviaste un correo ofreciéndole un pantallazo rápido y gratuito con puntos de mejora para su tienda, pero no respondió.
    
    Requisitos estrictos:
    1. Idioma: Redacta TODO (asunto y cuerpo) en {idioma} natural y profesional.
    2. Tono: Casual, de colega a colega, asumiendo que estuvo ocupado con el movimiento de la semana. Cero presión.
    3. Contenido: Dile que escribes rápido por si el correo anterior se perdió. Menciona que sigues teniendo a mano los apuntes sobre mejoras de conversión para {web}. Si le sirve que se los pases (sin compromiso), pídele que responda con un simple "sí". Si están a fuego con otras prioridades, deséale éxitos.
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

def ejecutar_seguimientos():
    if not os.path.exists(ARCHIVO_HISTORIAL):
        print(f"❌ No se encontró el archivo '{ARCHIVO_HISTORIAL}'.")
        return

    with open(ARCHIVO_HISTORIAL, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columnas = reader.fieldnames
        filas = list(reader)

    if not filas:
        print("📭 El historial está vacío.")
        return

    # Paso 1: Detectar y clasificar respuestas automáticamente en storecheckai@gmail.com
    respuestas_nuevas = detectar_respuestas_gmail(filas)

    # Paso 2: Enviar seguimiento a los que siguen en "Invitacion enviada" tras 4 días
    ahora = datetime.now()
    seguimientos_enviados = 0

    print(f"🔍 Buscando prospectos sin respuesta con >= {DIAS_ESPERA} días de espera...\n")

    for fila in filas:
        estado = get_col(fila, "estado")
        fecha_str = get_col(fila, "fecha")
        email_dest = get_col(fila, "email")
        web = get_col(fila, "web")
        nombre = get_col(fila, "nombre") or get_col(fila, "contacto")
        pais = get_col(fila, "pais", "Estados Unidos")

        if estado != "Invitacion enviada" or not fecha_str:
            continue

        try:
            fecha_envio = datetime.strptime(fecha_str[:10], "%Y-%m-%d")
        except ValueError:
            print(f"⚠️ Formato de fecha inválido para {email_dest}: {fecha_str}")
            continue

        dias_transcurridos = (ahora - fecha_envio).days

        if dias_transcurridos >= DIAS_ESPERA:
            print(f"⏳ {web} ({email_dest}) lleva {dias_transcurridos} días sin responder. Preparando seguimiento...")
            try:
                ia = redactar_seguimiento_inteligente(nombre, web, pais)
                asunto = ia.get("asunto", f"Re: Una consulta sobre {web}")
                cuerpo = ia.get("cuerpo", "")

                print(f"👤 Idioma: {obtener_idioma_por_pais(pais)} | Asunto: {asunto}")
                print(f"✉️ Mensaje:\n{cuerpo}\n")

                params = {
                    "from": "StoreCheck AI <onboarding@resend.dev>", # <-- Cambiar por dominio propio al salir a producción
                    "to": [email_dest],
                    "reply_to": "storecheckai@gmail.com",
                    "subject": asunto,
                    "text": cuerpo
                }

                # DESCOMENTAR ESTA LÍNEA PARA ENVIAR SEGUIMIENTOS REALES:
                # resend.Emails.send(params)

                set_col(fila, "estado", "Seguimiento enviado")
                set_col(fila, "fecha", ahora.strftime("%Y-%m-%d %H:%M:%S"))
                seguimientos_enviados += 1
                time.sleep(1.5)

            except Exception as e:
                print(f"❌ Error procesando seguimiento para {email_dest}: {e}\n")

    # Paso 3: Guardar CSV si hubo cambios
    if respuestas_nuevas > 0 or seguimientos_enviados > 0:
        with open(ARCHIVO_HISTORIAL, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columnas)
            writer.writeheader()
            writer.writerows(filas)
        print(f"✅ Historial actualizado ({respuestas_nuevas} respuestas procesadas, {seguimientos_enviados} seguimientos enviados).")
    else:
        print("✅ Proceso finalizado. Sin novedades ni seguimientos pendientes por hoy.")

if __name__ == "__main__":
    ejecutar_seguimientos()
