import os
import re
import csv
import time
import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

ARCHIVO_MAESTRO = "leads_globales.csv"
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY")  # Opcional

# Objetivos globales con cobertura multirregional (incluyendo mercados de habla china)
OBJETIVOS_GLOBALES = [
    {"pais": "China", "query": '"Shopify" OR "购物车" OR "立即购买" site:.cn'},
    {"pais": "Taiwan", "query": '"Shopify" OR "加入購物車" site:.tw'},
    {"pais": "Spain", "query": '"Powered by Shopify" OR "carrito de compra" site:.es'},
    {"pais": "Mexico", "query": '"Powered by Shopify" OR "añadir al carrito" site:.mx'},
    {"pais": "Colombia", "query": '"Powered by Shopify" OR "carrito de compras" site:.co'},
    {"pais": "Chile", "query": '"Powered by Shopify" OR "carro de compras" site:.cl'},
    {"pais": "Brazil", "query": '"Powered by Shopify" OR "adicionar ao carrinho" site:.com.br'},
    {"pais": "Portugal", "query": '"Powered by Shopify" OR "adicionar ao carrinho" site:.pt'},
    {"pais": "France", "query": '"Propulsé par Shopify" OR "ajouter au panier" site:.fr'},
    {"pais": "United States", "query": '"Powered by Shopify" "add to cart" -site:shopify.com'}
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
    print("🚀 Iniciando recolección autónoma global de tiendas...\n")

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
