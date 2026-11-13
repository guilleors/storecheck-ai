import os
import pandas as pd
from groq import Groq
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config  # Importa las credenciales desde config.py

# 1. Configuración de clientes
client = Groq(api_key=config.GROQ_API_KEY)

PROSPECTOS_FILE = "prospectos_storecheck.csv"
HISTORIAL_FILE = "historial_invitaciones_globales.csv"

def cargar_historial():
    """Carga el historial de correos enviados para evitar duplicados."""
    if os.path.exists(HISTORIAL_FILE):
        return pd.read_csv(HISTORIAL_FILE)
    else:
        return pd.DataFrame(columns=["nombre", "email", "web", "pais", "estado", "fecha"])

def guardar_en_historial(nombre, email, web, pais, estado):
    """Registra el envío exitoso en el archivo CSV de historial."""
    df_hist = cargar_historial()
    nuevo_registro = pd.DataFrame([{
        "nombre": nombre,
        "email": email,
        "web": web,
        "pais": pais,
        "estado": estado,
        "fecha": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }])
    df_hist = pd.concat([df_hist, nuevo_registro], ignore_index=True)
    df_hist.to_csv(HISTORIAL_FILE, index=False)

def generar_correo(nombre, web, pais):
    """Genera el mensaje ultra natural mediante la IA de Groq."""
    system_prompt = (
        "Sos un desarrollador y consultor técnico independiente especializado en optimización web. "
        "Tu objetivo es escribir un correo en frío ultra corto, directo y conversacional a otro dueño de negocio o colega digital. "
        "El tono tiene que ser relajado, de par a par, como si le escribieras a alguien que conociste en un foro o comunidad tech. "
        "REGLAS ESTRICTAS DE REDACCIÓN:\n"
        "1. Cero lenguaje de marketing agresivo o corporativo (nada de 'aumenta tus ventas 300%', 'exclusivo', 'gratis', 'urgente' ni signos de exclamación excesivos).\n"
        "2. No uses formato de plantilla obvia. El correo debe arrancar saludando por el nombre y mencionando al pasar la web de su tienda.\n"
        "3. Sé breve: máximo 3 párrafos cortos.\n"
        "4. Cerrá con una pregunta simple y abierta, sin links largos ni llamadas a la acción pesadas.\n"
        "5. Escribilo en el idioma correspondiente según el país del prospecto (español natural y cercano para España/Latinoamérica)."
    )

    user_prompt = f"""
    Redactá un correo en frío para:
    - Nombre: {nombre}
    - Tienda/Web: {web}
    - País: {pais}

    El enfoque debe ser que chusmeaste su tienda de pasada, notaste un par de detalles finos de fricción o velocidad que se podrían pulir, y le tirás la onda de charlarlo si le interesa.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.7,
        max_tokens=400
    )
    return response.choices[0].message.content.strip()

def enviar_email(destinatario, cuerpo_texto, nombre_tienda):
    """Envía el correo mediante el servidor SMTP seguro de Gmail."""
    remitente = config.GMAIL_USER
    password = config.GMAIL_APP_PASSWORD

    msg = MIMEMultipart()
    msg['From'] = remitente
    msg['To'] = destinatario
    msg['Subject'] = f"Consulta rápida sobre {nombre_tienda}"

    msg.attach(MIMEText(cuerpo_texto, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remitente, password)
            server.sendmail(remitente, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"Error al enviar correo a {destinatario}: {e}")
        return False

def ejecutar_campaña():
    """Procesa la lista de prospectos y ejecuta los envíos pendientes."""
    if not os.path.exists(PROSPECTOS_FILE):
        print(f"No se encontró el archivo {PROSPECTOS_FILE}")
        return

    df_prospectos = pd.read_csv(PROSPECTOS_FILE)
    historial = cargar_historial()
    enviados_set = set(historial['email'].values) if not historial.empty else set()

    print(f"--- Iniciando barrido de prospectos ({len(df_prospectos)} encontrados) ---")

    for index, row in df_prospectos.iterrows():
        nombre = row['nombre']
        email = row['email']
        web = row['web']
        pais = row['pais']

        if email in enviados_set:
            print(f"-> Saltando {email} (ya figura en el historial).")
            continue

        print(f"Generando correo personalizado para {nombre} ({email})...")
        cuerpo = generar_correo(nombre, web, pais)

        print(f"Enviando correo vía SMTP...")
        exito = enviar_email(email, cuerpo, web)

        if exito:
            guardar_en_historial(nombre, email, web, pais, "Invitacion enviada")
            print(f"¡Enviado con éxito a {email}!\n")
        else:
            print(f"Falló el envío a {email}.\n")

if __name__ == "__main__":
    ejecutar_campaña()
