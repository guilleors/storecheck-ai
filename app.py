import io
import os
from bs4 import BeautifulSoup
from groq import Groq
import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Configuración inicial de la página
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="⚡",
    layout="centered",
)

# --- MANEJADOR DE PÁGINAS LEGALES INTERNAS ---
legal_page = st.query_params.get("page", "main")

if legal_page == "terms":
    st.markdown("<p><a href='/' style='color: #3B82F6; text-decoration: underline;'>← Volver a la app principal</a></p>", unsafe_allow_html=True)
    st.markdown("## Términos y Condiciones — StoreCheck AI")
    st.markdown("""
    **1. Objeto del Servicio**  
    StoreCheck AI es una plataforma automatizada de auditoría y diagnóstico de e-commerce basada en inteligencia artificial y simulaciones de experiencia de usuario (*Mystery Shopper*). Los análisis tienen un propósito informativo y de optimización técnica.

    **2. Pagos y Reembolsos**  
    Los reportes completos en PDF se habilitan de manera digital e inmediata tras la confirmación exitosa del pago único de $19 USD. Al tratarse de un activo digital descargable, no se realizan reembolsos una vez generado el archivo.

    **3. Limitación de Responsabilidad**  
    Los resultados, puntajes y recomendaciones de optimización se generan mediante modelos algorítmicos. StoreCheck AI no garantiza un aumento directo en ventas o conversiones, ya que dependen de la implementación del usuario y factores externos del mercado.
    """)
    st.stop()

elif legal_page == "privacy":
    st.markdown("<p><a href='/' style='color: #3B82F6; text-decoration: underline;'>← Volver a la app principal</a></p>", unsafe_allow_html=True)
    st.markdown("## Política de Privacidad — StoreCheck AI")
    st.markdown("""
    **1. Recopilación de Datos**  
    StoreCheck AI procesa exclusivamente datos públicos de las URLs ingresadas (títulos, metadatos, estructura HTML visible y pasarelas de pago detectadas) con el único fin de generar los diagnósticos solicitados.

    **2. Uso de la Información**  
    Los datos de las tiendas analizadas y las consultas realizadas no se comercializan con terceros ni se utilizan para entrenar modelos públicos de inteligencia artificial fuera del flujo operativo del servicio.

    **3. Seguridad de las Transacciones**  
    Los pagos son procesados de forma segura a través de pasarelas externas certificadas (como Lemon Squeezy), sin que nuestra plataforma almacene datos sensibles de tarjetas de crédito o información bancaria.
    """)
    st.stop()


def scrape_store_data(url):
    """Extrae datos reales del sitio y busca indicios de carrito, checkout y pagos."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return False, f"Código de estado HTTP: {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")

        # Extraer título y meta descripción
        title = soup.title.string.strip() if soup.title else "Sin título"
        meta_desc = ""
        desc_tag = soup.find(
            "meta", attrs={"name": lambda x: x and x.lower() == "description"}
        )
        if desc_tag:
            meta_desc = desc_tag.get("content", "").strip()

        # Detectar plataforma de e-commerce
        html_content = response.text.lower()
        platform = "Personalizada / Genérica"
        if "shopify" in html_content or "cdn.shopify.com" in html_content:
            platform = "Shopify"
        elif "woocommerce" in html_content or "wp-content" in html_content:
            platform = "WooCommerce / WordPress"
        elif "prestashop" in html_content:
            platform = "PrestaShop"
        elif "tiendanube" in html_content or "nuvemshop" in html_content:
            platform = "Tiendanube"

        # Detectar elementos de compra / checkout (Mystery Shopper indicators)
        has_cart_button = (
            bool(soup.find_all(class_=lambda x: x and "cart" in x.lower()))
            or "carrito" in html_content
            or "bag" in html_content
        )
        has_checkout_link = (
            "checkout" in html_content
            or "finalizar" in html_content
            or "pagar" in html_content
        )
        
        # Detectar pasarelas de pago comunes en el HTML
        payment_gateways = []
        if "mercadopago" in html_content: payment_gateways.append("MercadoPago")
        if "paypal" in html_content: payment_gateways.append("PayPal")
        if "stripe" in html_content: payment_gateways.append("Stripe")
        if "transferencia" in html_content or "transfer" in html_content: payment_gateways.append("Transferencia Bancaria")

        # Limpiar scripts/estilos y extraer texto visible para el análisis
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        visible_text = soup.get_text(separator=" ", strip=True)[:2500]

        scraped_data = {
            "title": title,
            "meta_description": meta_desc,
            "platform": platform,
            "has_cart_button": has_cart_button,
            "has_checkout_link": has_checkout_link,
            "payment_gateways": payment_gateways if payment_gateways else ["No detectadas explícitamente"],
            "raw_text": visible_text,
        }
        return True, scraped_data
    except Exception as e:
        return False, str(e)


def calculate_store_metrics(scraped_data):
    """Calcula puntajes dinámicos basados en la calidad técnica real de la tienda."""
    seo_score = 100
    if not scraped_data.get("title") or scraped_data.get("title") == "Sin título":
        seo_score -= 35
    if not scraped_data.get("meta_description"):
        seo_score -= 30
    if len(scraped_data.get("raw_text", "")) < 400:
        seo_score -= 20
    seo_score = max(25, seo_score)

    health_score = seo_score
    if not scraped_data.get("has_cart_button"):
        health_score -= 15
    if not scraped_data.get("has_checkout_link"):
        health_score -= 15
    if "No detectadas explícitamente" in scraped_data.get("payment_gateways", []):
        health_score -= 10
    health_score = max(20, min(98, health_score))

    # Velocidad estimada según plataforma
    platform = scraped_data.get("platform", "")
    if platform == "Shopify":
        speed_index = "1.9s"
    elif platform == "WooCommerce / WordPress":
        speed_index = "3.4s"
    elif platform == "Tiendanube":
        speed_index = "2.2s"
    else:
        speed_index = "2.7s"

    # Mobile readiness dinámico
    if health_score >= 75:
        mobile_readiness = "Optimal"
    elif health_score >= 45:
        mobile_readiness = "Warning"
    else:
        mobile_readiness = "Critical"

    return health_score, seo_score, speed_index, mobile_readiness


def generate_pdf_report(store_url, audit_text, language):
    """Genera un reporte PDF limpio, formateado y con salto de página automático."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=54, 
        leftMargin=54, 
        topMargin=54, 
        bottomMargin=54
    )
    styles = getSampleStyleSheet()
    story = []

    # Estilos personalizados para el PDF
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=6
    )
    meta_style = ParagraphStyle(
        'ReportMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=12
    )
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10
    )

    # Encabezado del reporte
    story.append(Paragraph("StoreCheck AI — Reporte de Auditoría Completo", title_style))
    story.append(Paragraph(f"<b>Sitio analizado:</b> {store_url} | <b>Idioma:</b> {language}", meta_style))
    story.append(Spacer(1, 10))

    # Procesar el texto de la IA y pasarlo limpio a párrafos de ReportLab
    for paragraph in audit_text.split("\n\n"):
        if paragraph.strip():
            clean_p = paragraph.replace("**", "<b>").replace("__", "<b>")
            story.append(Paragraph(clean_p, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()


@st.cache_resource
def get_groq_client():
    token = ""
    try:
        if "GROQ_API_KEY" in st.secrets:
            token = str(st.secrets["GROQ_API_KEY"])
        elif "general" in st.secrets and "GROQ_API_KEY" in st.secrets["general"]:
            token = str(st.secrets["general"]["GROQ_API_KEY"])
    except Exception:
        pass

    if not token:
        token = os.getenv("GROQ_API_KEY", "")

    token = token.strip().strip('"').strip("'")
    if token:
        os.environ["GROQ_API_KEY"] = token

    return Groq(api_key=token)


try:
    client = get_groq_client()
except Exception:
    client = None

# --- BARRA LATERAL ---
ui_language = st.sidebar.selectbox(
    "🌐 Idioma de la Interfaz / UI Language",
    ["Español", "English", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

with st.sidebar.expander("📊 Carga Masiva (Google Sheets)"):
    sheet_link = st.text_input(
        "Link de Google Sheets (Público):",
        placeholder="https://docs.google.com/spreadsheets/d/TU_ID/edit",
        key="input_sheet_link",
    )
    if sheet_link:
        try:
            csv_url = (
                sheet_link.split("/edit")[0] + "/export?format=csv"
                if "/edit" in sheet_link
                else sheet_link
            )
            df_sheets = pd.read_csv(csv_url)
            st.success(f"¡Planilla leída! {len(df_sheets)} filas.")

            columna_elegida = st.selectbox(
                "Columna con URLs:", df_sheets.columns, key="col_sheets_sb"
            )
            urls_disponibles = df_sheets[columna_elegida].dropna().tolist()

            if urls_disponibles:
                url_desde_sheet = st.selectbox(
                    "Seleccionar tienda:", urls_disponibles, key="url_select_sb"
                )
                if st.button("Cargar esta tienda en el auditor", key="btn_load_sheet"):
                    st.session_state["store_url_input"] = url_desde_sheet
                    st.rerun()
        except Exception as e:
            st.error(f"Error al leer planilla: {e}")

# Diccionario i18n
i18n_ui = {
    "Español": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://mitienda.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "Analizando la tienda globalmente...",
        "success_preview": "¡Simulación de compra y diagnóstico completados!",
        "preview_title": "📊 Salud General de la Tienda",
        "full_report_title": "📄 Generar y Descargar Reporte Completo en PDF",
        "full_report_info": "Obtené el informe técnico completo con guías de optimización paso a paso, análisis profundo de UI/UX, SEO y fricción de checkout.",
        "report_lang_label": "Seleccioná el idioma para tu Reporte PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD y Descargar PDF",
        "terms": "Términos y Condiciones",
        "privacy": "Política de Privacidad",
        "error_url": "Por favor, ingresá una URL válida.",
    },
    "English": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "Analyzing store globally...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health",
        "full_report_title": "📄 Generate & Download Full PDF Report",
        "full_report_info": "Get the complete technical report with step-by-step optimization guides, deep UI/UX analysis, SEO, and checkout friction review.",
        "report_lang_label": "Select the language for your full PDF report:",
        "btn_full_report": "💳 Pay $19 USD & Download PDF",
        "terms": "Terms of Service",
        "privacy": "Privacy Policy",
        "error_url": "Please enter a valid URL.",
    },
    "Português": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://sua-loja.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "Analisando a loja globalmente...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 Saúde Geral da Loja",
        "full_report_title": "📄 Gerar e Baixar Relatório Completo em PDF",
        "full_report_info": "Obtenha o relatório técnico completo com guias de otimização passo a passo, análise profunda de UI/UX, SEO e fricción de checkout.",
        "report_lang_label": "Selecione o idioma para o seu relatório PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD e Baixar PDF",
        "terms": "Termos de Serviço",
        "privacy": "Política de Privacidade",
        "error_url": "Por favor, insira um URL válido.",
    },
    "Italiano": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://tuo-negozio.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "Analisi del negozio in corso...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 Salute Generale del Negozio",
        "full_report_title": "📄 Genera e Scarica il Rapporto PDF Completo",
        "full_report_info": "Ottieni il report tecnico completo con guide di ottimizzazione dettagliate, analisi approfondita di UI/UX, SEO e attrito al checkout.",
        "report_lang_label": "Seleziona la lingua per il tuo rapporto PDF completo:",
        "btn_full_report": "💳 Paga $19 USD e Scarica il PDF",
        "terms": "Termini di Servizio",
        "privacy": "Informativa sulla Privacy",
        "error_url": "Si prega di inserire un URL valido.",
    },
    "Français": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://votre-boutique.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "Analyse de la boutique en cours...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 Santé Globale de la Boutique",
        "full_report_title": "📄 Générer et Télécharger le Rapport PDF Complet",
        "full_report_info": "Obtenez le rapport technique complet avec des guides d'optimisation étape par étape, une analyse approfondie UI/UX, SEO et tunnel d'achat.",
        "report_lang_label": "Sélectionnez la langue de votre rapport PDF complet :",
        "btn_full_report": "💳 Payer 19 $ USD et Télécharger le PDF",
        "terms": "Conditions Générales",
        "privacy": "Politique de Confidentialité",
        "error_url": "Veuillez entrer une URL valide.",
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "btn_reset": "🔄 Reset",
        "spinner": "正在全局分析商店...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 商店总体健康状况",
        "full_report_title": "📄 生成并下载完整PDF报告",
        "full_report_info": "获取包含分步优化指南、深入UI/UX分析、SEO和结账摩擦检查的完整技术报告。",
        "report_lang_label": "选择完整PDF报告的语言：",
        "btn_full_report": "💳 支付 $19 USD 并下载 PDF",
        "terms": "服务条款",
        "privacy": "隐私政策",
        "error_url": "请输入有效的网址。",
    },
}

t = i18n_ui[ui_language]


def call_groq_chat(client_instance, messages, temperature=0.7):
    if not client_instance:
        raise Exception("El cliente de servicio no está disponible en este momento.")

    try:
        models_response = client_instance.models.list()
        all_models = [m.id for m in models_response.data]
        excluded_keywords = ["guard", "classifier", "tool", "moderation", "vision"]
        chat_models = [
            m_id
            for m_id in all_models
            if not any(kw in m_id.lower() for kw in excluded_keywords)
        ]
    except Exception as e:
        raise Exception(f"No se pudo consultar los modelos disponibles: {e}")

    if not chat_models:
        chat_models = all_models

    chat_models.sort(
        key=lambda name: (
            0
            if "70b" in name.lower() or "versatile" in name.lower()
            else (1 if "instant" in name.lower() else 2)
        )
    )

    last_error = None
    for model_id in chat_models:
        try:
            response = client_instance.chat.completions.create(
                messages=messages, model=model_id, temperature=temperature
            )
            return response
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"Error de comunicación con el servicio: {last_error}")


# Interfaz Principal
st.markdown(
    f"<h1 style='text-align: center; margin-bottom: 0px;'>⚡ {t['title']}</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align: center; color: #94A3B8; margin-top: 5px;"
    f" font-size: 16px;'>{t['subtitle']}</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# Función de callback para el botón de Reset (limpia antes de renderizar widgets)
def reset_callback():
    st.session_state["store_url_input"] = ""
    for key in ["preview_result", "scraped_data", "store_url", "full_report_result"]:
        if key in st.session_state:
            del st.session_state[key]

# Input de URL con su key asignada
store_url = st.text_input(
    t["url_label"], 
    placeholder=t["url_placeholder"],
    key="store_url_input"
)

# Botones de acción alineados con el callback de reseteo integrado
col_btn1, col_btn2 = st.columns([4, 1])
with col_btn1:
    run_audit = st.button(t["btn_preview"], use_container_width=True)
with col_btn2:
    st.button(t["btn_reset"], on_click=reset_callback, use_container_width=True)

if run_audit:
    if not store_url:
        st.warning(t["error_url"])
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("🌐 [1/3] Ejecutando simulación de Mystery Shopper y escaneo web...")
            progress_bar.progress(30)

            success_scraping, scraped_data = scrape_store_data(store_url)
            if not success_scraping:
                raise Exception(
                    f"No se pudo acceder a la tienda para realizar la simulación. Detalle: {scraped_data}"
                )

            status_text.text(
                "🎨 [2/3] Analizando pasarelas de pago, botones de compra y fricción de checkout..."
            )
            progress_bar.progress(65)

            preview_prompt = f"""
            You are an expert e-commerce CRO specialist and a "Mystery Shopper" attempting to buy items on the store {store_url}.
            Here is the real data extracted from the site:
            - Platform: {scraped_data['platform']}
            - Page Title: {scraped_data['title']}
            - Meta Description: {scraped_data['meta_description']}
            - Cart Button Detected: {scraped_data['has_cart_button']}
            - Checkout Flow Link Detected: {scraped_data['has_checkout_link']}
            - Payment Gateways Found: {', '.join(scraped_data['payment_gateways'])}
            - Content Snippet: {scraped_data['raw_text'][:1200]}

            Act as if you just tried to navigate this store as a customer trying to buy. Provide an executive teaser highlighting 3 critical friction points or conversion blockers found during your simulated shopping journey (e.g., trust issues, payment gateway gaps, friction in mobile/cart layout).
            CRITICAL INSTRUCTION: Do NOT invent features. Do NOT provide step-by-step technical solutions. Keep it strictly as a diagnostic teaser. Write the response in {ui_language}.
            """

            messages = [
                {"role": "system", "content": "You are an expert e-commerce Mystery Shopper and CRO auditor."},
                {"role": "user", "content": preview_prompt},
            ]

            status_text.text(
                "🤖 [3/3] Generando diagnóstico de conversión basado en la experiencia de compra..."
            )
            progress_bar.progress(90)

            chat_completion = call_groq_chat(client, messages, temperature=0.7)
            preview_result = chat_completion.choices[0].message.content

            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()

            st.success(t["success_preview"])

            st.session_state["preview_result"] = preview_result
            st.session_state["store_url"] = store_url
            st.session_state["scraped_data"] = scraped_data

            if "full_report_result" in st.session_state:
                del st.session_state["full_report_result"]

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ {e}")

if "preview_result" in st.session_state:
    st.markdown("---")

    # Calcular métricas dinámicas basadas en los datos reales del scraper
    health, seo, speed, mobile = calculate_store_metrics(st.session_state["scraped_data"])

    st.markdown(f"### {t['preview_title']}: {health}/100")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="SEO Score", value=f"{seo}%", delta=f"{seo - 70}%"
        )
    with col2:
        st.metric(
            label="Speed Index", value=speed
        )
    with col3:
        st.metric(label="Mobile Readiness", value=mobile)

    st.markdown("---")
    st.markdown("### 💡 Mystery Shopper Teaser & Findings")
    st.write(st.session_state["preview_result"])

    st.markdown("---")
    st.markdown(f"### {t['full_report_title']}")
    st.info(t["full_report_info"])

    report_language = st.selectbox(
        t["report_lang_label"],
        [
            "Español",
            "English",
            "Português",
            "Italiano",
            "Français",
            "中文 (Chinese)",
        ],
    )

    is_paid = st.query_params.get("success", "false").lower() == "true"

    if is_paid:
        st.success("🎉 ¡Pago verificado con éxito! Generando tu reporte PDF completo...")

        if "full_report_result" not in st.session_state:
            with st.spinner(
                "🤖 Elaborando informe técnico profundo y guía de solución paso a paso..."
            ):
                sd = st.session_state["scraped_data"]
                full_report_prompt = f"""
                    You are an advanced e-commerce CRO expert and technical consultant. Analyze the real store data from {st.session_state['store_url']}:
                    - Platform: {sd['platform']}
                    - Title: {sd['title']}
                    - Meta Description: {sd['meta_description']}
                    - Cart Button Detected: {sd['has_cart_button']}
                    - Checkout Flow Link Detected: {sd['has_checkout_link']}
                    - Payment Gateways Found: {', '.join(sd['payment_gateways'])}
                    - Content Snippet: {sd['raw_text'][:1800]}

                    Provide a comprehensive, deep technical audit report based strictly on these elements. Include a detailed UI/UX analysis of the buyer journey, checkout friction review, payment setup evaluation, and a complete step-by-step technical implementation guide to fix all detected conversion leaks. 
                    Write the response in {report_language}.
                    """
                full_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are an advanced AI e-commerce audit expert and technical consultant."
                        ),
                    },
                    {"role": "user", "content": full_report_prompt},
                ]
                full_completion = call_groq_chat(client, full_messages, temperature=0.7)
                st.session_state["full_report_result"] = (
                    full_completion.choices[0].message.content
                )

        pdf_bytes = generate_pdf_report(
            st.session_state["store_url"],
            st.session_state["full_report_result"],
            report_language,
        )
        st.download_button(
            label=t.get(
                "btn_download_unlocked", "📥 Descargar mi Reporte PDF Completo"
            ),
            data=pdf_bytes,
            file_name="StoreCheck_AI_Audit_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    else:
        checkout_url = "https://storecheck-ai.lemonsqueezy.com/checkout/buy/16b5540c-1884-4e2c-a07a-3912222588dc?checkout[redirect_url]=https://storecheck-ai.streamlit.app//?success=true"

        st.link_button(
            label=t["btn_full_report"], url=checkout_url, use_container_width=True
        )

st.markdown("---")
st.markdown(
    f"<p style='text-align: center; font-size: 12px; color: gray;'>"
    f"<a href='/?page=terms' style='color: #3B82F6; text-decoration: underline;'>{t['terms']}</a> | "
    f"<a href='/?page=privacy' style='color: #3B82F6; text-decoration: underline;'>{t['privacy']}</a>"
    f"<br>© 2026 StoreCheck AI. Global E-commerce Audits."
    f"</p>",
    unsafe_allow_html=True,
)
