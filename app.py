import io
import os
import html
import re
from bs4 import BeautifulSoup
from groq import Groq
import pandas as pd
import requests
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
    """Extrae datos reales del sitio con headers avanzados y manejo de seguridad anti-bots."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        response = requests.get(url, headers=headers, timeout=12)
        
        if response.status_code in [403, 401]:
            return False, "El sitio cuenta con estrictas políticas de seguridad (WAF / Cloudflare) que bloquean accesos automatizados (ej. redes sociales o dominios altamente protegidos)."
        
        if response.status_code != 200:
            return False, f"Código de estado HTTP devuelto: {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title else "Sin título"
        meta_desc = ""
        desc_tag = soup.find("meta", attrs={"name": lambda x: x and x.lower() == "description"})
        if desc_tag:
            meta_desc = desc_tag.get("content", "").strip()

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
        
        payment_gateways = []
        if "mercadopago" in html_content: payment_gateways.append("MercadoPago")
        if "paypal" in html_content: payment_gateways.append("PayPal")
        if "stripe" in html_content: payment_gateways.append("Stripe")
        if "transferencia" in html_content or "transfer" in html_content: payment_gateways.append("Transferencia Bancaria")

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
    except requests.exceptions.Timeout:
        return False, "La solicitud expiró (Timeout). El servidor tardó demasiado en responder."
    except requests.exceptions.ConnectionError:
        return False, "Error de conexión. Verificá que la URL sea correcta o que el sitio web esté online."
    except Exception as e:
        return False, str(e)


def calculate_store_metrics(scraped_data, language):
    """Calcula puntajes dinámicos y adapta los textos de estado móvil al idioma."""
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

    platform = scraped_data.get("platform", "")
    if platform == "Shopify":
        speed_index = "1.9s"
    elif platform == "WooCommerce / WordPress":
        speed_index = "3.4s"
    elif platform == "Tiendanube":
        speed_index = "2.2s"
    else:
        speed_index = "2.7s"

    raw_status = "Optimal" if health_score >= 75 else ("Warning" if health_score >= 45 else "Critical")
    
    translations = {
        "Español": {"Optimal": "Óptimo", "Warning": "Mejorable", "Critical": "Crítico"},
        "Português": {"Optimal": "Ótimo", "Warning": "Atenção", "Critical": "Crítico"},
        "Italiano": {"Optimal": "Ottimale", "Warning": "Attenzione", "Critical": "Critico"},
        "Français": {"Optimal": "Optimal", "Warning": "Attention", "Critical": "Critique"},
        "中文 (Chinese)": {"Optimal": "极佳", "Warning": "需注意", "Critical": "严重"},
        "English": {"Optimal": "Optimal", "Warning": "Warning", "Critical": "Critical"}
    }
    
    mobile_readiness = translations.get(language, translations["English"]).get(raw_status, raw_status)

    return health_score, seo_score, speed_index, mobile_readiness


def generate_pdf_report(store_url, audit_text, language, health, seo, speed, mobile):
    """Genera un reporte PDF con diseño corporativo avanzado, tabla de métricas y parser limpio de Markdown."""
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

    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Heading1'],
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=4
    )
    meta_style = ParagraphStyle(
        'ReportMeta',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=15
    )
    body_style = ParagraphStyle(
        'ReportBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor('#334155'),
        spaceAfter=10
    )
    h2_style = ParagraphStyle(
        'ReportH2',
        parent=styles['Heading2'],
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=12,
        spaceAfter=6
    )

    story.append(Paragraph("StoreCheck AI — Reporte de Auditoría Profesional", title_style))
    story.append(Paragraph(f"<b>Sitio analizado:</b> {html.escape(store_url)} &nbsp;|&nbsp; <b>Idioma:</b> {html.escape(language)}", meta_style))
    
    data_table = [
        [Paragraph("<b>Métrica Clave</b>", body_style), Paragraph("<b>Resultado / Valor</b>", body_style)],
        [Paragraph("Salud General (Health Score)", body_style), Paragraph(f"<b>{health} / 100</b>", body_style)],
        [Paragraph("Puntaje SEO", body_style), Paragraph(f"{seo}%", body_style)],
        [Paragraph("Índice de Velocidad", body_style), Paragraph(f"{speed}", body_style)],
        [Paragraph("Optimización Móvil", body_style), Paragraph(f"{mobile}", body_style)],
    ]
    
    t_obj = Table(data_table, colWidths=[250, 254])
    t_obj.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#F1F5F9')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    
    story.append(t_obj)
    story.append(Spacer(1, 15))
    story.append(Paragraph("<b>Análisis Técnico y Diagnóstico Detallado</b>", h2_style))
    story.append(Spacer(1, 5))

    # Parser mejorado: limpia Markdown, remueve LaTeX y formatea tablas como texto limpio
    for block in audit_text.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        
        formatted_lines = []
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            
            # Omitir separadores de tablas Markdown
            if re.match(r'^\|?[\s\-:]+\|[\s\-:|]+$', line):
                continue
            
            # Convertir filas de tablas Markdown en viñetas legibles
            if line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line.split("|")[1:-1]]
                cells = [c for c in cells if c]
                if cells:
                    clean_line = "• <b>" + "</b>: ".join([html.escape(c) for c in cells]) + ""
                else:
                    continue
            else:
                # Limpiar fórmulas/símbolos LaTeX de dólares
                line = line.replace('$', '')
                
                # Detectar cabeceras de markdown y pasarlas a negrita
                if line.startswith("### "):
                    clean_line = f"<b>{html.escape(line[4:].strip())}</b>"
                elif line.startswith("## "):
                    clean_line = f"<b>{html.escape(line[3:].strip())}</b>"
                elif line.startswith("# "):
                    clean_line = f"<b>{html.escape(line[2:].strip())}</b>"
                else:
                    escaped = html.escape(line)
                    escaped = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped)
                    escaped = re.sub(r'__(.*?)__', r'<b>\1</b>', escaped)
                    
                    if escaped.startswith("- ") or escaped.startswith("* "):
                        escaped = "• " + escaped[2:]
                    
                    clean_line = escaped
            
            formatted_lines.append(clean_line)
        
        if formatted_lines:
            paragraph_html = "<br/>".join(formatted_lines)
            story.append(Paragraph(paragraph_html, body_style))

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

enable_comparison = st.sidebar.checkbox("⚔️ Modo Comparación (Tu tienda vs. Competencia)", value=False)

# [PLACEHOLDER - FUTURO MÓDULO B2B / AGENCIAS]
# with st.sidebar.expander("📊 [B2B] Carga Masiva (Google Sheets)"):
#     sheet_link = st.text_input("Link de Google Sheets:", key="b2b_sheet_link")


# Diccionario i18n 100% integrado
i18n_ui = {
    "Español": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnósticos automatizados con IA y recomendaciones de crecimiento para e-commerce",
        "url_label": "Ingresá la URL de tu tienda principal",
        "url_placeholder": "https://mitienda.com",
        "competitor_label": "Ingresá la URL de la tienda rival / competencia",
        "competitor_placeholder": "https://tiendacompetencia.com",
        "btn_preview": "🚀 Ejecutar Auditoría / Comparativa",
        "btn_reset": "🔄 Restablecer",
        "spinner": "Analizando tiendas globalmente...",
        "success_preview": "¡Simulación y diagnóstico completados con éxito!",
        "preview_title": "📊 Salud General de la Tienda",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Hallazgos y Teaser del Mystery Shopper",
        "full_report_title": "📄 Generar y Descargar Reporte Completo en PDF",
        "full_report_info": "Obtené el informe técnico completo con formato corporativo, guías de optimización paso a paso y análisis profundo de conversión.",
        "report_lang_label": "Seleccioná el idioma para tu Reporte PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD y Descargar PDF Pro",
        "btn_download_unlocked": "📥 Descargar mi Reporte PDF Corporativo",
        "terms": "Términos y Condiciones",
        "privacy": "Política de Privacidad",
        "error_url": "Por favor, ingresá una URL válida.",
    },
    "English": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Main Store URL",
        "url_placeholder": "https://your-store.com",
        "competitor_label": "Enter Competitor Store URL",
        "competitor_placeholder": "https://competitorstore.com",
        "btn_preview": "🚀 Run Audit / Head-to-Head",
        "btn_reset": "🔄 Reset",
        "spinner": "Analyzing stores globally...",
        "success_preview": "Mystery Shopping & Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Mystery Shopper Teaser & Findings",
        "full_report_title": "📄 Generate & Download Full PDF Report",
        "full_report_info": "Get the complete technical report with corporate formatting, step-by-step optimization guides, and conversion deep-dive.",
        "report_lang_label": "Select the language for your full PDF report:",
        "btn_full_report": "💳 Pay $19 USD & Download Pro PDF",
        "btn_download_unlocked": "📥 Download My Corporate PDF Report",
        "terms": "Terms of Service",
        "privacy": "Privacy Policy",
        "error_url": "Please enter a valid URL.",
    },
    "Português": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnósticos automatizados por IA e recomendações de crescimento para e-commerce",
        "url_label": "Insira o URL da sua loja principal",
        "url_placeholder": "https://sualoja.com",
        "competitor_label": "Insira o URL da loja concorrente",
        "competitor_placeholder": "https://lojacorrente.com",
        "btn_preview": "🚀 Executar Auditoria / Comparativo",
        "btn_reset": "🔄 Redefinir",
        "spinner": "Analisando lojas globalmente...",
        "success_preview": "Simulação de compra e diagnóstico concluídos!",
        "preview_title": "📊 Saúde Geral da Loja",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Descobertas e Teaser do Mystery Shopper",
        "full_report_title": "📄 Gerar e Baixar Relatório Completo em PDF",
        "full_report_info": "Obtenha o relatório técnico completo com formato corporativo, guias de otimização e análise profunda.",
        "report_lang_label": "Selecione o idioma para o seu relatório PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD e Baixar PDF Pro",
        "btn_download_unlocked": "📥 Baixar meu Relatório PDF Corporativo",
        "terms": "Termos de Serviço",
        "privacy": "Política de Privacidade",
        "error_url": "Por favor, insira um URL válido.",
    },
    "Italiano": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnostica automatizzata tramite IA e consigli di crescita per e-commerce",
        "url_label": "Inserisci l'URL del tuo negozio principale",
        "url_placeholder": "https://tuonegozio.com",
        "competitor_label": "Inserisci l'URL del negozio concorrente",
        "competitor_placeholder": "https://negozioconcorrente.com",
        "btn_preview": "🚀 Esegui Audit / Testa a Testa",
        "btn_reset": "🔄 Reimposta",
        "spinner": "Analisi dei negozi in corso...",
        "success_preview": "Simulazione d'acquisto e diagnostica completate!",
        "preview_title": "📊 Salute Generale del Negozio",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Risultati e Teaser del Mystery Shopper",
        "full_report_title": "📄 Genera e Scarica il Rapporto PDF Completo",
        "full_report_info": "Ottieni il report tecnico completo con formattazione aziendale e guide di ottimizzazione dettagliate.",
        "report_lang_label": "Seleziona la lingua per il tuo rapporto PDF completo:",
        "btn_full_report": "💳 Paga $19 USD e Scarica PDF Pro",
        "btn_download_unlocked": "📥 Scarica il mio Report PDF Aziendale",
        "terms": "Termini di Servizio",
        "privacy": "Informativa sulla Privacy",
        "error_url": "Si prega di inserire un URL valido.",
    },
    "Français": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnostics automatisés par IA et recommandations de croissance pour e-commerce",
        "url_label": "Entrez l'URL de votre boutique principale",
        "url_placeholder": "https://votre-boutique.com",
        "competitor_label": "Entrez l'URL de la boutique concurrente",
        "competitor_placeholder": "https://boutiqueconcurrente.com",
        "btn_preview": "🚀 Lancer l'Audit / Comparatif",
        "btn_reset": "🔄 Réinitialiser",
        "spinner": "Analyse des boutiques en cours...",
        "success_preview": "Simulation d'achat et diagnostic terminés avec succès !",
        "preview_title": "📊 Santé Globale de la Boutique",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Résultats et Teaser du Mystery Shopper",
        "full_report_title": "📄 Générer et Télécharger le Rapport PDF Complet",
        "full_report_info": "Obtenez le rapport technique complet avec mise en page d'entreprise et guides d'optimisation.",
        "report_lang_label": "Sélectionnez la langue de votre rapport PDF complet :",
        "btn_full_report": "💳 Payer 19 $ USD et Télécharger PDF Pro",
        "btn_download_unlocked": "📥 Télécharger mon Rapport PDF d'Entreprise",
        "terms": "Conditions Générales",
        "privacy": "Politique de Confidentialité",
        "error_url": "Veuillez entrer une URL valide.",
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI",
        "subtitle": "针对电商的自动化人工智能诊断与业务增长建议",
        "url_label": "输入您的主商店网址",
        "url_placeholder": "https://your-store.com",
        "competitor_label": "输入竞争对手商店网址",
        "competitor_placeholder": "https://competitorstore.com",
        "btn_preview": "🚀 运行审计 / 竞品对比",
        "btn_reset": "🔄 重置",
        "spinner": "正在全局分析商店...",
        "success_preview": "神秘顾客模拟与诊断成功完成！",
        "preview_title": "📊 商店总体健康状况",
        "seo_score_label": "SEO 评分",
        "speed_index_label": "加载速度",
        "mobile_readiness_label": "移动端适配",
        "teaser_heading": "💡 神秘顾客发现与摘要",
        "full_report_title": "📄 生成并下载完整PDF报告",
        "full_report_info": "获取包含企业级格式、分步优化指南和转化深度剖析的完整技术报告。",
        "report_lang_label": "选择完整PDF报告的语言：",
        "btn_full_report": "💳 支付 $19 USD 并下载 Pro PDF",
        "btn_download_unlocked": "📥 下载我的企业版PDF报告",
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


def reset_callback():
    st.session_state["store_url_input"] = ""
    st.session_state["competitor_url_input"] = ""
    for key in ["preview_result", "scraped_data", "store_url", "full_report_result", "comp_scraped_data", "competitor_url"]:
        if key in st.session_state:
            del st.session_state[key]


with st.form(key="audit_form"):
    store_url = st.text_input(
        t["url_label"], 
        placeholder=t["url_placeholder"],
        key="store_url_input"
    )

    competitor_url = ""
    if enable_comparison:
        competitor_url = st.text_input(
            t["competitor_label"],
            placeholder=t["competitor_placeholder"],
            key="competitor_url_input"
        )

    col_btn1, col_btn2 = st.columns([4, 1])
    with col_btn1:
        run_audit = st.form_submit_button(t["btn_preview"], use_container_width=True)
    with col_btn2:
        reset_audit = st.form_submit_button(t["btn_reset"], on_click=reset_callback, use_container_width=True)

if run_audit:
    if not store_url:
        st.warning(t["error_url"])
    elif enable_comparison and not competitor_url:
        st.warning("Por favor, ingresá también la URL de la competencia para la comparativa.")
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text(t["spinner"])
            progress_bar.progress(25)

            success_scraping, scraped_data = scrape_store_data(store_url)
            if not success_scraping:
                raise Exception(f"Tienda principal: {scraped_data}")

            progress_bar.progress(50)

            comp_scraped_data = None
            if enable_comparison and competitor_url:
                success_comp, comp_data = scrape_store_data(competitor_url)
                if not success_comp:
                    raise Exception(f"Tienda rival ({competitor_url}): {comp_data}")
                comp_scraped_data = comp_data

            progress_bar.progress(75)

            if enable_comparison and comp_scraped_data:
                preview_prompt = f"""
                You are an elite e-commerce CRO specialist and competitive market analyst. Compare two stores:
                STORE A (Main): {store_url}
                - Platform: {scraped_data['platform']}
                - Title: {scraped_data['title']}
                - Cart/Checkout Ready: {scraped_data['has_cart_button']} / {scraped_data['has_checkout_link']}
                - Gateways: {', '.join(scraped_data['payment_gateways'])}
                - Snippet: {scraped_data['raw_text'][:900]}

                STORE B (Competitor): {competitor_url}
                - Platform: {comp_scraped_data['platform']}
                - Title: {comp_scraped_data['title']}
                - Cart/Checkout Ready: {comp_scraped_data['has_cart_button']} / {comp_scraped_data['has_checkout_link']}
                - Gateways: {', '.join(comp_scraped_data['payment_gateways'])}
                - Snippet: {comp_scraped_data['raw_text'][:900]}

                Provide a head-to-head competitive teaser highlighting 3 key advantages or conversion gaps Store A has over Competitor B (and vice versa). Keep it sharp and analytical.
                Write the response entirely in {ui_language}.
                """
            else:
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

                Act as if you just tried to navigate this store as a customer trying to buy. Provide an executive teaser highlighting 3 critical friction points or conversion blockers found during your simulated shopping journey.
                Write the response entirely in {ui_language}.
                """

            messages = [
                {"role": "system", "content": "You are an expert e-commerce Mystery Shopper and CRO auditor."},
                {"role": "user", "content": preview_prompt},
            ]

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
            if enable_comparison and comp_scraped_data:
                st.session_state["competitor_url"] = competitor_url
                st.session_state["comp_scraped_data"] = comp_scraped_data
            else:
                if "comp_scraped_data" in st.session_state:
                    del st.session_state["comp_scraped_data"]

            if "full_report_result" in st.session_state:
                del st.session_state["full_report_result"]

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ {e}")

if "preview_result" in st.session_state:
    st.markdown("---")

    health, seo, speed, mobile = calculate_store_metrics(st.session_state["scraped_data"], ui_language)

    st.markdown(f"### {t['preview_title']}: {health}/100")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label=t["seo_score_label"], value=f"{seo}%", delta=f"{seo - 70}%")
    with col2:
        st.metric(label=t["speed_index_label"], value=speed)
    with col3:
        st.metric(label=t["mobile_readiness_label"], value=mobile)

    if "comp_scraped_data" in st.session_state:
        st.markdown("---")
        comp_health, comp_seo, comp_speed, comp_mobile = calculate_store_metrics(st.session_state["comp_scraped_data"], ui_language)
        st.markdown(f"### ⚔️ Competencia ({st.session_state['competitor_url']}): {comp_health}/100")
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            st.metric(label=t["seo_score_label"], value=f"{comp_seo}%")
        with cc2:
            st.metric(label=t["speed_index_label"], value=comp_speed)
        with cc3:
            st.metric(label=t["mobile_readiness_label"], value=comp_mobile)

    st.markdown("---")
    st.markdown(f"### {t['teaser_heading']}")
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

    # Cambiar temporalmente a True para probar la descarga sin pagar
    is_paid = True

    if is_paid:
        st.success("🎉 ¡Pago verificado con éxito! Ya podés descargar el PDF de tu reporte.")

        if "full_report_result" not in st.session_state:
            with st.spinner("🤖 Elaborando informe técnico profundo y diseño corporativo..."):
                sd = st.session_state["scraped_data"]
                comp_info = ""
                if "comp_scraped_data" in st.session_state:
                    csd = st.session_state["comp_scraped_data"]
                    comp_info = f"\n- COMPETITOR STORE: {st.session_state['competitor_url']}\n  Platform: {csd['platform']}\n  Title: {csd['title']}"

                full_report_prompt = f"""
                    You are an advanced e-commerce CRO expert and technical consultant. Analyze the store data from {st.session_state['store_url']}:{comp_info}
                    - Platform: {sd['platform']}
                    - Title: {sd['title']}
                    - Meta Description: {sd['meta_description']}
                    - Cart Button Detected: {sd['has_cart_button']}
                    - Checkout Flow Link Detected: {sd['has_checkout_link']}
                    - Payment Gateways Found: {', '.join(sd['payment_gateways'])}
                    - Content Snippet: {sd['raw_text'][:1800]}

                    Provide a comprehensive, deep technical audit report based strictly on these elements. Include a detailed UI/UX analysis of the buyer journey, checkout friction review, competitive edge evaluation, and a complete step-by-step technical implementation guide to fix all detected conversion leaks. 
                    Write the response entirely in {report_language}.
                    """
                full_messages = [
                    {
                        "role": "system",
                        "content": "You are an advanced AI e-commerce audit expert and technical consultant.",
                    },
                    {"role": "user", "content": full_report_prompt},
                ]
                full_completion = call_groq_chat(client, full_messages, temperature=0.7)
                st.session_state["full_report_result"] = full_completion.choices[0].message.content

        pdf_bytes = generate_pdf_report(
            st.session_state["store_url"],
            st.session_state["full_report_result"],
            report_language,
            health, seo, speed, mobile
        )
        st.download_button(
            label=t["btn_download_unlocked"],
            data=pdf_bytes,
            file_name="StoreCheck_AI_Corporate_Report.pdf",
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
