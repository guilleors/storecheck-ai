import csv
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
from groq import Groq
import config

# Inicializar cliente de Groq con la clave centralizada
client = Groq(api_key=config.GROQ_API_KEY)

HISTORIAL_FILE = "historial_invitaciones_globales.csv"

def cargar_historial():
    enviados = set()
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    enviados.add(row[0].strip().lower())
    return enviados

def registrar_enviado(email):
    with open(HISTORIAL_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([email])

def generar_correo(nombre, web, pais):
    system_prompt = (
        "Eres un desarrollador independiente especializado en auditorías de e-commerce. "
        "Escribes correos de manera ultra natural, directos, conversacionales y tipo 'peer-to-peer', "
        "evitando por completo el tono comercial, corporativo o spam. "
        "El objetivo es ofrecer una auditoría inicial de conversión para StoreCheck AI."
    )
    
    user_prompt = (
        f"Escribe un correo de contacto en frío muy breve y humano para {nombre}, que está a cargo de {web} (ubicado en {pais}). "
        "Menciona que estuviste chusmeando su tienda y viste un par de detalles de fricción en el checkout o la conversión "
        "que se pueden optimizar rápido. Pregúntale si le interesa que le pases un pantallazo rápido sin compromiso."
    )

    response = client.chat.completions.create(
        model=config.GROQ_MODEL,  # <-- Usando la variable centralizada del config.py
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=400
    )
    return response.choices[0].message.content.strip()

def enviar_email(destinatario, asunto, cuerpo):
    msg = MIMEMultipart()
    msg['From'] = config.GMAIL_USER
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

def ejecutar_campana():
    print("--- Iniciando barrido de prospectos ---")
    enviados = cargar_historial()
    
    # Detectar automáticamente el archivo CSV disponible
    archivo_prospectos = None
    for posible in ["prospectos_storecheck.csv", "prospectos.csv", "campana_emails_li.csv"]:
        if os.path.exists(posible):
            archivo_prospectos = posible
            break
            
    if not archivo_prospectos:
        print("Error: No se encontró ningún archivo CSV de prospectos en la carpeta.")
        return

    with open(archivo_prospectos, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        
        # Mapeo flexible para tolerar 'mail' o 'email'
        if reader.fieldnames:
            fieldnames_lower = [fn.lower() for fn in reader.fieldnames]
            email_col = 'email' if 'email' in fieldnames_lower else ('mail' if 'mail' in fieldnames_lower else None)
        else:
            email_col = None
        
        if not email_col:
            print(f"Error: El CSV no tiene una columna de correo válida ('email' o 'mail').")
            return

        count = 0
        for row in reader:
            # Normalizar claves del diccionario a minúsculas
            row_lower = {k.lower(): v for k, v in row.items()}
            email = row_lower.get(email_col, "").strip()
            nombre = row_lower.get("nombre", row_lower.get("name", "emprendedor"))
            web = row_lower.get("web", row_lower.get("sitio", "su tienda"))
            pais = row_lower.get("pais", row_lower.get("country", "Latinoamérica"))

            if not email or email in enviados:
                continue

            print(f"Generando correo personalizado para {nombre} ({email})...")
            cuerpo = generar_correo(nombre, web, pais)
            
            asunto = f"consulta sobre optimización en {web}"
            
            if enviar_email(email, asunto, cuerpo):
                registrar_enviado(email)
                print(f"-> ¡Correo enviado con éxito a {email}!")
                count += 1
                # Pausa para cuidar la entrega y evitar bloqueos
                time.sleep(5)
            else:
                print(f"-> Falló el envío a {email}")

    print(f"--- Campaña finalizada. Total correos enviados en esta tanda: {count} ---")

if __name__ == "__main__":
    ejecutar_campana()
