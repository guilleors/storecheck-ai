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
        "Sos un desarrollador web independiente escribiendo un mail de contacto en frío. "
        "Tu única tarea es adaptar el texto de ejemplo al nombre y la web del prospecto, "
        "manteniendo exactamente el mismo tono educado, directo y natural de Argentina ('Mirá, me tomé el atrevimiento...'). "
        "No inventes párrafos nuevos ni cambies la estructura."
    )
    
    user_prompt = (
        f"Tomá como base este texto exacto y adaptalo para {nombre} que está a cargo de {web} (ubicado en {pais}):\n\n"
        f"Hola, {nombre}, ¿cómo estás?\n"
        f"Mirá, me tomé el atrevimiento de explorar {web} y noté algunos detalles de fricción en el checkout que seguramente estén interfiriendo en el flujo de ventas.\n"
        f"¿Podrá interesarte, sin compromiso, un pantallazo rápido con un par de ideas para corregirlo? No dudes en responderme y te lo envío.\n\n"
        "Devolvé únicamente el correo listo para enviar con esos datos:"
    )

    response = client.chat.completions.create(
        model=config.GROQ_MODEL,  # Carga el modelo configurado en config.py
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.2,  # Bien obediente para que respete el molde
        max_tokens=200
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
            row_lower = {k.lower(): v for k, v in row.items()}
            email = row_lower.get(email_col, "").strip()
            nombre = row_lower.get("nombre", row_lower.get("name", "emprendedor"))
            web = row_lower.get("web", row_lower.get("sitio", "su tienda"))
            pais = row_lower.get("pais", row_lower.get("country", "Latinoamérica"))

            if not email or email in enviados:
                continue

            print(f"\nGenerando correo para {nombre} ({email})...")
            cuerpo = generar_correo(nombre, web, pais)
            
            # Muestra el cuerpo generado en la terminal en tiempo real
            print("\n" + "="*40)
            print(cuerpo)
            print("="*40 + "\n")
            
            asunto = f"consulta sobre {web}"
            
            if enviar_email(email, asunto, cuerpo):
                registrar_enviado(email)
                print(f"-> ¡Correo enviado con éxito a {email}!")
                count += 1
                time.sleep(5)
            else:
                print(f"-> Falló el envío a {email}")

    print(f"\n--- Campaña finalizada. Total correos enviados: {count} ---")

if __name__ == "__main__":
    ejecutar_campana()
