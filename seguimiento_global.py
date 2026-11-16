import os
import csv
import json
import time
import imaplib
import email
from email.utils import parsedate_to_datetime
import unicodedata
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from bs4 import BeautifulSoup
from groq import Groq

# Importamos las credenciales desde el archivo local privado (config.py)
try:
    from config import GMAIL_USER, GMAIL_APP_PASSWORD, GROQ_API_KEY
except ImportError:
    GMAIL_USER = os.getenv("GMAIL_USER", "storecheckai@gmail.com")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

groq_client = Groq(api_key=GROQ_API_KEY)

ARCHIVO_HISTORIAL = "historial_invitaciones_globales.csv"
STREAMLIT_URL = "https://storecheck-ai.streamlit.app/"
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


def raspar_tienda_rapido(url):
    """Extrae datos reales de la tienda del prospecto para armar un teaser preciso."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        }
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "Sin título"
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        if desc_tag:
            meta_desc = desc_tag.get("content", "").strip()

        html_content = resp.text.lower()
        platform = "Personalizada / Genérica"
        if "shopify" in html_content or "cdn.shopify.com" in html_content:
            platform = "Shopify"
        elif "woocommerce" in html_content or "wp-content" in html_content:
            platform = "WooCommerce / WordPress"
        elif "prestashop" in html_content:
            platform = "PrestaShop"
        elif "tiendanube" in html_content or "nuvemshop" in html_content:
            platform = "Tiendanube"

        has_cart = bool(soup.find_all(class_=lambda x: x and "cart" in x.lower())) or "carrito" in html_content or "bag" in html_content
        has_checkout = "checkout" in html_content or "finalizar" in html_content or "pagar" in html_content

        gateways = []
        if "mercadopago" in html_content: gateways.append("MercadoPago")
        if "paypal" in html_content: gateways.append("PayPal")
        if "stripe" in html_content: gateways.append("Stripe")
        if "transferencia" in html_content or "transfer" in html_content: gateways.append("Transferencia Bancaria")

        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        visible_text = soup.get_text(separator=" ", strip=True)[:1500]

        return {
            "platform": platform,
            "title": title,
            "meta_description": meta_desc,
            "has_cart": has_cart,
            "has_checkout": has_checkout,
            "gateways": gateways if gateways else ["No detectadas explícitamente"],
            "snippet": visible_text,
        }
    except Exception:
        return None


def generar_y_enviar_teaser(nombre, email_dest, web, pais, asunto_original):
    """Genera el pre-informe SOLO si logra extraer datos reales de la tienda. Nunca inventa."""
    idioma = obtener_idioma_por_pais(pais)
    saludo = nombre if nombre and nombre.lower() not in ["equipo", "team", "emprendedor", ""] else "hola"

    print(f"   🔎 Analizando {web} en vivo para armar el pre-informe...")
    datos_web = raspar_tienda_rapido(web)

    # FRENO DE SEGURIDAD: Si no se pudo leer la web real, NO se envía nada para evitar inventar datos
    if not datos_web:
        print(f"   🛑 ALERTA: No se pudo acceder a {web} (no existe, está caída o bloquea bots).")
        print("   🛑 Envío cancelado automáticamente para no inventar información.")
        return "WEB_INACCESIBLE"

    contexto_tecnico = f"""
    Datos reales extraídos del código HTML de {web}:
    - Plataforma detectada: {datos_web['platform']}
    - Título de la página: {datos_web['title']}
    - Meta descripción: {datos_web['meta_description'] or 'No tiene meta descripción configurada'}
    - Botón de carrito detectado en la home: {'Sí' if datos_web['has_cart'] else 'No detectado'}
    - Flujo/enlace de checkout detectado: {'Sí' if datos_web['has_checkout'] else 'No detectado'}
    - Pasarelas de pago visibles: {', '.join(datos_web['gateways'])}
    - Fragmento de texto visible en la tienda: {datos_web['snippet'][:900]}
    """

    prompt = f"""
    Sos un especialista en optimización de conversión (CRO) escribiendo un correo de respuesta a {saludo} ({web}), quien pidió recibir el pantallazo gratuito que le ofreciste.

    {contexto_tecnico}

    REGLAS ESTRICTAS DE VERACIDAD:
    - Basate ÚNICAMENTE en los datos reales extraídos arriba.
    - NO inventes problemas ni supongas cosas que no surjan de esos datos. Si un dato aparece como "No detectado" o vacío, señalalo como una oportunidad concreta de mejora.

    REGLAS ESTRICTAS DE FORMATO Y LEGIBILIDAD:
    - Redactá en {idioma} natural, cercano y profesional (tono directo de colega, sin sonar robótico).
    - Usá doble salto de línea (párrafos bien separados) entre cada idea para que sea muy fácil y cómodo de leer.
    - Estructurá el correo exactamente así:

    Párrafo 1: Saludo breve agradeciendo la respuesta (ej: "¡Hola {saludo}! Gracias por responder. Estuve revisando {web} y te paso 3 puntos concretos que vi:").

    [Línea en blanco]

    Lista con 3 viñetas (usando "• ") separadas entre sí por una línea en blanco. Cada viñeta debe tener un título corto seguido de dos puntos y una explicación de máximo 2 líneas basada en los datos reales.

    [Línea en blanco]

    Párrafo de cierre: Invitalo sin presión a que, si quiere el informe técnico completo en PDF por $19 USD con la guía paso a paso (o los snippets de código listos para aplicar en {datos_web['platform']}), puede generarlo al instante desde acá: {STREAMLIT_URL}

    [Línea en blanco]

    Despedida breve en una sola línea (SIN NINGUNA COMA AL FINAL, por ejemplo: escribí exactamente "Un saludo" o "Abrazo" sin signos de puntuación finales).

    Devolvé ÚNICAMENTE el cuerpo del correo listo para enviar (sin asunto ni comillas).
    """

    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            max_tokens=650,
        )
        cuerpo_teaser = chat_completion.choices[0].message.content.strip()
    except Exception:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="qwen/qwen3.8-27b",
            temperature=0.2,
            max_tokens=650,
        )
        cuerpo_teaser = chat_completion.choices[0].message.content.strip()

    asunto_respuesta = asunto_original if asunto_original.lower().startswith("re:") else f"Re: {asunto_original or f'consulta sobre {web}'}"

    print(f"   ✉️ Enviando pre-informe real y formateado a {email_dest}...")
    exito = enviar_correo_smtp(email_dest, asunto_respuesta, cuerpo_teaser)
    return "ENVIADO" if exito else "ERROR_SMTP"


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
    """Revisa storecheckai@gmail.com vía IMAP, clasifica la respuesta y dispara el teaser si hay interés."""
    if not GMAIL_APP_PASSWORD:
        print("⚠️ No se detectó GMAIL_APP_PASSWORD. Se omite el chequeo automático de bandeja.\n")
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
                    cuerpo_cliente = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                cuerpo_cliente = part.get_payload(decode=True).decode(errors="ignore")
                                break
                    else:
                        cuerpo_cliente = msg.get_payload(decode=True).decode(errors="ignore")

                    intencion = clasificar_respuesta_cliente(cuerpo_cliente)

                    if intencion == "Interesado":
                        print(f"🔥 ¡Interés detectado de {email_prospecto}! Verificando tienda real...")
                        nombre = get_col(fila, "nombre")
                        web = get_col(fila, "web")
                        pais = get_col(fila, "pais", "Argentina")
                        asunto = get_col(fila, "asunto")

                        resultado_teaser = generar_y_enviar_teaser(nombre, email_prospecto, web, pais, asunto)

                        if resultado_teaser == "ENVIADO":
                            set_col(fila, "estado", "Teaser enviado")
                            set_col(fila, "fecha", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                            print(f"🚀 ¡Pre-informe enviado con éxito a {email_prospecto}! Estado: Teaser enviado")
                        elif resultado_teaser == "WEB_INACCESIBLE":
                            set_col(fila, "estado", "Interesado - Revisar web manual")
                            print(f"⚠️ {email_prospecto} está interesado, pero {web} no respondió. Queda marcado para revisión manual.")
                        else:
                            set_col(fila, "estado", "Interesado - Error envio teaser")
                            print(f"⚠️ Hubo interés de {email_prospecto}, pero falló el envío SMTP.")

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


def enviar_correo_smtp(destinatario, asunto, cuerpo):
    """Envía el correo mediante el servidor SMTP oficial de Gmail usando TLS."""
    try:
        msg = MIMEMultipart()
        msg['From'] = GMAIL_USER
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(cuerpo, 'plain', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, destinatario, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[-] Error al enviar correo por SMTP a {destinatario}: {e}")
        return False


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

    respuestas_nuevas = detectar_respuestas_gmail(filas)

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

                exito = enviar_correo_smtp(email_dest, asunto, cuerpo)

                if exito:
                    set_col(fila, "estado", "Seguimiento enviado")
                    set_col(fila, "fecha", ahora.strftime("%Y-%m-%d %H:%M:%S"))
                    seguimientos_enviados += 1
                    print(f"✅ Seguimiento enviado a {email_dest}.\n")
                else:
                    print(f"❌ Falló el envío SMTP de seguimiento a {email_dest}.\n")

                time.sleep(1.5)

            except Exception as e:
                print(f"❌ Error procesando seguimiento para {email_dest}: {e}\n")

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
