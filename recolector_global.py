import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

ARCHIVO_MAESTRO = "prospectos_storecheck.csv"
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")  # Opcional

# Objetivos globales con cobertura real en los 5 continentes
OBJETIVOS_GLOBALES = [
    # --- AMÉRICA ---
    {"pais": "América del Norte (US/CA)", "query": '"Powered by Shopify" OR "WooCommerce" "add to cart" site:.com OR site:.ca'},
    {"pais": "Latinoamérica Hispana", "query": '"Powered by Shopify" OR "Tiendanube" "carrito" OR "comprar" site:.mx OR site:.co OR site:.cl OR site:.ar OR site:.pe'},
    {"pais": "Brasil", "query": '"Powered by Shopify" "adicionar ao carrinho" site:.br OR site:.com.br'},

    # --- EUROPA ---
    {"pais": "Europa Occidental (UK/IE)", "query": '"Powered by Shopify" "add to cart" site:.co.uk OR site:.ie'},
    {"pais": "Europa Continental (FR/DE/ES/IT)", "query": '"Powered by Shopify" "ajouter au panier" OR "in den Warenkorb" OR "añadir al carrito" site:.fr OR site:.de OR site:.es OR site:.it'},
    {"pais": "Europa del Norte / Nórdicos", "query": '"Powered by Shopify" "lägg i varukorg" OR "køb" site:.se OR site:.dk OR site:.no OR site:.fi'},

    # --- ASIA ---
    {"pais": "Asia Oriental (JP/KR/CN/TW)", "query": '"Powered by Shopify" "add to cart" OR "カートに入れる" OR "장바구니" site:.jp OR site:.kr OR site:.tw'},
    {"pais": "Sudeste Asiático & India (SG/IN/MY)", "query": '"Powered by Shopify" "add to cart" site:.sg OR site:.in OR site:.my OR site:.id'},
    {"pais": "Medio Oriente (AE/SA)", "query": '"Powered by Shopify" "add to cart" OR "أضف إلى السلة" site:.ae OR site:.sa'},

    # --- ÁFRICA ---
    {"pais": "África Subsahariana y del Sur (ZA/NG/KE)", "query": '"Powered by Shopify" "add to cart" site:.za OR site:.ng OR site:.ke'},
    {"pais": "África del Norte (EG/MA)", "query": '"Powered by Shopify" "add to cart" site:.eg OR site:.ma'},

    # --- OCEANÍA ---
    {"pais": "Oceanía (AU/NZ)", "query": '"Powered by Shopify" "add to cart" site:.au OR site:.nz'}
]


def cargar_webs_existentes():
    """Evita volver a raspar dominios que ya están en la base maestra"""
    if not os.path.exists(ARCHIVO_MAESTRO):
        return set()
    with open(ARCHIVO_MAESTRO, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {row["web"].strip().lower() for row in reader if row.get("web")}


def guardar_lead_maestro(nombre, email, web, pais):
    """Guarda el contacto listo para que lo consuma batch_auditor.py"""
    existe = os.path.exists(ARCHIVO_MAESTRO) and os.path.getsize(ARCHIVO_MAESTRO) > 0
    with open(ARCHIVO_MAESTRO, mode="a", newline="", encoding="utf-8-sig") as f:
        campos = ["nombre", "email", "web", "pais"]
        writer = csv.DictWriter(f, fieldnames=campos)
        if not existe:
            writer.writeheader()
        writer.writerow({
            "nombre": nombre,
            "email": email,
            "web": web,
            "pais": pais
        })


def limpiar_dominio(url):
    """Extrae el dominio base limpio"""
    dominio = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower().strip()
    return dominio


def validar_tienda_y_extraer_email(dominio):
    """
    1) Verifica que el sitio sea una tienda online real (plataforma e-commerce o carrito/checkout activo).
    2) Si es tienda real, busca emails públicos válidos en la home y páginas de contacto.
    """
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}
    patron_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    basura = ["sentry.io", "wixpress.com", "example.com", "shopify.com", "domain.com", ".png", ".jpg", ".jpeg", ".webp", ".svg"]

    # Paso 1: Verificar home para confirmar que es e-commerce real
    try:
        resp_home = requests.get(f"https://{dominio}", headers=headers, timeout=8)
        if resp_home.status_code != 200:
            return False, None
    except Exception:
        return False, None

    html_lower = resp_home.text.lower()

    senales_plataforma = [
        "cdn.shopify.com",
        "shopify.theme",
        "woocommerce",
        "wc-block",
        "tiendanube",
        "nuvemshop",
        "prestashop",
        "magento",
        "vtex",
        "bigcommerce"
    ]
    senales_compra = [
        "add-to-cart",
        "add_to_cart",
        "single_add_to_cart_button",
        "/cart",
        "/carrito",
        "/checkout",
        "/collections/",
        "/product/",
        "/producto/",
        "añadir al carrito",
        "agregar al carrito",
        "adicionar ao carrinho",
        "ajouter au panier",
        "in den warenkorb"
    ]

    es_tienda = any(s in html_lower for s in senales_plataforma) or sum(1 for s in senales_compra if s in html_lower) >= 2
    if not es_tienda:
        return False, None

    # Paso 2: Extraer email empezando por la home ya descargada y luego páginas de contacto
    paginas_html = [resp_home.text]
    rutas_contacto = ["/contact", "/contacto", "/pages/contact", "/pages/contacto", "/aviso-legal", "/policies/contact-information"]

    for ruta in rutas_contacto:
        try:
            r = requests.get(f"https://{dominio}{ruta}", headers=headers, timeout=6)
            if r.status_code == 200:
                paginas_html.append(r.text)
        except Exception:
            continue

    for html_doc in paginas_html:
        soup = BeautifulSoup(html_doc, "html.parser")
        # Buscar primero en enlaces mailto:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.lower().startswith("mailto:"):
                mail_limpio = href.split(":", 1)[1].split("?")[0].strip().lower()
                if re.match(patron_email, mail_limpio) and not any(b in mail_limpio for b in basura):
                    return True, mail_limpio

        # Buscar en el texto visible
        texto = soup.get_text(" ")
        encontrados = re.findall(patron_email, texto)
        for mail in encontrados:
            mail_limpio = mail.lower()
            if not any(b in mail_limpio for b in basura):
                return True, mail_limpio

    return True, None


def buscar_en_hunter(dominio):
    """Respaldo con API de Hunter.io si el scraping directo no halló mail"""
    if not HUNTER_API_KEY:
        return None, None
    url = f"https://api.hunter.io/v2/domain-search?domain={dominio}&api_key={HUNTER_API_KEY}&limit=1"
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            emails = r.json().get("data", {}).get("emails", [])
            if emails:
                dato = emails[0]
                nombre = dato.get("first_name") or "Equipo"
                return nombre, dato.get("value")
    except Exception:
        pass
    return None, None


def ejecutar_recoleccion(resultados_por_pais=5):
    webs_vistas = cargar_webs_existentes()
    print("🚀 Iniciando recolección autónoma global de tiendas (5 continentes)...\n")

    with DDGS() as ddgs:
        for obj in OBJETIVOS_GLOBALES:
            pais = obj["pais"]
            query = obj["query"]
            print(f"🌍 Rastreando tiendas en {pais}...")

            try:
                resultados = list(ddgs.text(query, max_results=resultados_por_pais))
            except Exception as e:
                print(f"⚠️ Error en búsqueda para {pais}: {e}")
                continue

            for res in resultados:
                url = res.get("href", "")
                dominio = limpiar_dominio(url)

                if not dominio or dominio in webs_vistas:
                    continue
                webs_vistas.add(dominio)

                print(f"   🔎 Analizando {dominio}...")
                es_tienda, email = validar_tienda_y_extraer_email(dominio)

                if not es_tienda:
                    print(f"   ⏭️ Descartado ({dominio} no parece una tienda con carrito activo)")
                    time.sleep(1.0)
                    continue

                nombre = "Equipo"
                if not email:
                    nombre_hunter, email_hunter = buscar_en_hunter(dominio)
                    if email_hunter:
                        nombre = nombre_hunter
                        email = email_hunter

                if email:
                    print(f"   ✅ ¡Tienda verificada y lead capturado! {email} ({pais})")
                    guardar_lead_maestro(nombre, email, dominio, pais)
                else:
                    print(f"   ❌ Tienda verificada, pero sin email público visible en {dominio}")

                time.sleep(1.5)

    print(f"\n🏁 Recolección terminada. Base actualizada en '{ARCHIVO_MAESTRO}'.")


if __name__ == "__main__":
    ejecutar_recoleccion(resultados_por_pais=5)
