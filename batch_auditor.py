import csv
import os
import time
from bs4 import BeautifulSoup
from groq import Groq
import requests

# Configurar cliente de Groq (levanta la clave de las variables de entorno o ponela directo)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "TU_GROQ_API_KEY_AQUI")
client = Groq(api_key=GROQ_API_KEY)


def scrape_para_prospecto(url):
    """Reutiliza la lógica de scraping para evaluar la tienda del prospecto."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "es-ES,es;q=0.9",
        }
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, f"Error HTTP {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "Sin título"

        html_content = response.text.lower()
        platform = "Personalizada"
        if "shopify" in html_content:
            platform = "Shopify"
        elif "woocommerce" in html_content:
            platform = "WooCommerce"
        elif "tiendanube" in html_content:
            platform = "Tiendanube"

        has_cart = (
            bool(soup.find_all(class_=lambda x: x and "cart" in x.lower()))
            or "carrito" in html_content
        )
        has_checkout = "checkout" in html_content or "pagar" in html_content

        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        snippet = soup.get_text(separator=" ", strip=True)[:800]

        return {
            "platform": platform,
            "title": title,
            "has_cart": has_cart,
            "has_checkout": has_checkout,
            "snippet": snippet,
        }, "OK"
    except Exception as e:
        return None, str(e)


def generar_correo_en_frio(nombre, empresa, dominio, datos_tienda):
    """Le pide a Groq que redacte un correo de prospección corto, directo y con un teaser técnico."""
    prompt = f"""
    You are an expert e-commerce CRO consultant. Write a short, persuasive, and high-converting cold email addressed to {nombre}, Founder/Manager of {empresa} ({dominio}).
    
    Store technical details found:
    - Platform: {datos_tienda['platform']}
    - Title: {datos_tienda['title']}
    - Cart/Checkout operational: {datos_tienda['has_cart']} / {datos_tienda['has_checkout']}
    - Content sample: {datos_tienda['snippet'][:400]}

    Rules for the email:
    1. Do not use spammy corporate jargon. Be direct and conversational.
    2. Mention 1 specific technical friction point or observation found on their site based on the data.
    3. Pitch a low-friction solution: offer a complete automated CRO audit report ($19 USD) that details exact fixes to increase conversion rates.
    4. Write entirely in Spanish.
    5. Include placeholders for [Asunto] and [Cuerpo].
    """

    try:
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generando correo: {e}"


def procesar_prospectos():
    input_csv = "prospectos_storecheck.csv"
    output_csv = "campana_emails_listos.csv"

    if not os.path.exists(input_csv):
        print(
            f"❌ No se encontró el archivo '{input_csv}'. Ejecutá primero el script de Apollo."
        )
        return

    print(f"📂 Leyendo prospectos desde {input_csv}...")

    resultados_campana = []

    with open(input_csv, mode="r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            nombre = row.get("nombre", "Hola")
            empresa = row.get("empresa", "su tienda")
            dominio = row.get("dominio", "")
            email = row.get("email", "")

            if not dominio:
                continue

            print(
                f"\n🔍 Analizando tienda de {nombre} ({empresa}) -> {dominio}"
            )

            # 1. Scrapear la tienda del prospecto
            datos_tienda, estado = scrape_para_prospecto(dominio)

            if not datos_tienda:
                print(
                    f"⚠️ No se pudo auditar {dominio} ({estado}). Saltando..."
                )
                continue

            # 2. Generar el correo personalizado con IA
            print(f"🤖 Redactando correo personalizado con IA...")
            email_generado = generar_correo_en_frio(
                nombre, empresa, dominio, datos_tienda
            )

            resultados_campana.append(
                {
                    "email_destino": email,
                    "nombre": nombre,
                    "empresa": empresa,
                    "dominio": dominio,
                    "correo_propuesto": email_generado.replace(
                        "\n", " [BR] "
                    ),  # Limpieza para CSV
                }
            )

            # Pausa breve para no saturar la API de Groq
            time.sleep(1)

    # Guardar resultados listos para enviar
    campos = [
        "email_destino",
        "nombre",
        "empresa",
        "dominio",
        "correo_propuesto",
    ]
    with open(
        output_csv, mode="w", newline="", encoding="utf-8"
    ) as output_file:
        writer = csv.DictWriter(output_file, fieldnames=campos)
        writer.writeheader()
        writer.writerows(resultados_campana)

    print(
        f"\n🎉 ¡Proceso finalizado! Se generaron {len(resultados_campana)} correos personalizados en '{output_csv}'."
    )


if __name__ == "__main__":
    procesar_prospectos()
