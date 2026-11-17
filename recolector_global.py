import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

ARCHIVO_MAESTRO = "leads_globales.csv"
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
    {"pais": "Asia Oriental (JP/KR/CN/TW)", "query": '"Shopify" OR "カート" OR "장바구니" OR "购物车" OR "加入購物車" site:.jp OR site:.kr OR site:.cn OR site:.tw'},
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
    with open(ARCHIVO_MAESTRO, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["web"] for row in reader if row.get("web")}

def guardar_lead_maestro(nombre, email, web, pais):
    """Guarda el contacto listo para que lo consuma batch_auditor.py"""
    existe = os.path.exists(ARCHIVO_MAESTRO)
    with open(ARCHIVO_MAESTRO, mode="a", newline="", encoding="utf-8") as f:
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
    dominio = re.sub(r"^https?://(www\.)?", "", url).split("/")[0].lower()
    return dominio

def extraer_email_de_web(dominio):
    """Entra a la home y páginas de contacto buscando emails públicos válidos"""
    rutas = ["", "/contact", "/contacto", "/pages/contact", "/pages/contacto", "/aviso-legal"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    patron_email = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    
    basura = ["sentry.io", "wixpress.com", "example.com", "shopify.com", "domain.com", ".png", ".jpg"]

    for ruta in rutas:
        url = f"https://{dominio}{ruta}"
        try:
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code != 200:
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            texto = soup.get_text(" ")
            encontrados = re.findall(patron_email, texto)
            
            for mail in encontrados:
                mail_limpio = mail.lower()
                if not any(b in mail_limpio for b in basura):
                    return mail_limpio
        except Exception:
            continue
    return None

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
                nombre = "Equipo"
                email = extraer_email_de_web(dominio)

                if not email:
                    nombre_hunter, email_hunter = buscar_en_hunter(dominio)
                    if email_hunter:
                        nombre = nombre_hunter
                        email = email_hunter

                if email:
                    print(f"   ✅ ¡Lead capturado! {email} ({pais})")
                    guardar_lead_maestro(nombre, email, dominio, pais)
                else:
                    print(f"   ❌ Sin email público visible en {dominio}")

                time.sleep(1.5)

    print(f"\n🏁 Recolección terminada. Base actualizada en '{ARCHIVO_MAESTRO}'.")

if __name__ == "__main__":
    ejecutar_recoleccion(resultados_por_pais=5)
