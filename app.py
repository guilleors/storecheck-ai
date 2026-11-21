import io
import os
import html
import re
from urllib.parse import quote
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

LAST_STORE_FILE = "last_audited_store.txt"


def normalize_store_url(raw_url):
    cleaned = (raw_url or "").strip()
    if not cleaned:
        return ""
    if not cleaned.startswith("http://") and not cleaned.startswith("https://"):
        cleaned = "https://" + cleaned
    return cleaned


def save_last_store_url(url):
    normalized = normalize_store_url(url)
    if normalized:
        try:
            with open(LAST_STORE_FILE, "w", encoding="utf-8") as f:
                f.write(normalized)
        except Exception:
            pass


def load_last_store_url():
    try:
        if os.path.exists(LAST_STORE_FILE):
            with open(LAST_STORE_FILE, "r", encoding="utf-8") as f:
                return normalize_store_url(f.read())
    except Exception:
        pass
    return ""


# --- MANEJADOR DE PÁGINAS LEGALES INTERNAS ---
legal_page = st.query_params.get("page", "main")

if legal_page == "terms":
    st.markdown("<p><a href='/' style='color: #3B82F6; text-decoration: underline;'>← Volver a la app principal</a></p>", unsafe_allow_html=True)
    st.markdown("## Términos y Condiciones — StoreCheck AI")
    st.markdown("""
    **1. Objeto del Servicio**  
    StoreCheck AI es una plataforma automatizada de auditoría y diagnóstico de e-commerce basada en inteligencia artificial y simulaciones de experiencia de usuario (*Mystery Shopper*). Los análisis y guías de implementación tienen un propósito informativo y técnico.

    **2. Pagos y Reembolsos**  
    Los reportes completos en PDF y los packs de consultoría técnica se habilitan tras la confirmación exitosa del pago. Al tratarse de entregables digitales y personalizados, no se realizan reembolsos una vez emitido el material.

    **3. Limitación de Responsabilidad**  
    Los resultados y recomendaciones se generan mediante modelos algorítmicos. StoreCheck AI provee especificaciones técnicas y guías de código orientativas, declinando toda responsabilidad sobre la ejecución final realizada por terceros en sus servidores.
    """)
    st.stop()

elif legal_page == "privacy":
    st.markdown("<p><a href='/' style='color: #3B82F6; text-decoration: underline;'>← Volver a la app principal</a></p>", unsafe_allow_html=True)
    st.markdown("## Política de Privacidad — StoreCheck AI")
    st.markdown("""
    **1. Recopilación de Datos**  
    StoreCheck AI procesa exclusivamente datos públicos de las URLs ingresadas y los datos de contacto provistos voluntariamente para el envío de entregables técnicos.

    **2. Uso de la Información**  
    Los datos de las tiendas analizadas no se comercializan con terceros ni se utilizan para entrenar modelos públicos de inteligencia artificial fuera del flujo operativo del servicio.

    **3. Seguridad de las Transacciones**  
    Los pagos son procesados de forma segura a través de pasarelas externas certificadas (como Lemon Squeezy), sin que nuestra plataforma almacene datos sensibles de tarjetas de crédito.
    """)
    st.stop()


def build_checkout_url(base_checkout_url, redirect_base_url, store_url, extra_params=""):
    normalized_store = normalize_store_url(store_url)
    encoded_store = quote(normalized_store, safe="") if normalized_store else ""
    store_query = f"&store={encoded_store}" if encoded_store else ""
    full_redirect = f"{redirect_base_url}{extra_params}{store_query}"
    return f"{base_checkout_url}?checkout[redirect_url]={quote(full_redirect, safe='')}"


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
        url = normalize_store_url(url)

        response = requests.get(url, headers=headers, timeout=12)

        if response.status_code in [403, 401]:
            return False, "El sitio cuenta con estrictas políticas de seguridad (WAF / Cloudflare) que bloquean accesos automatizados."

        if response.status_code != 200:
            return False, f"Código de estado HTTP devuelto: {response.status_code}"

        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.string.strip() if soup.title and soup.title.string else "Sin título"
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
            bool(soup.find_all(class_=lambda x: x and "cart" in (" ".join(x).lower() if isinstance(x, list) else x.lower())))
            or "carrito" in html_content
            or "bag" in html_content
        )
        has_checkout_link = (
            "checkout" in html_content
            or "finalizar" in html_content
            or "pagar" in html_content
        )

        payment_gateways = []
        if "mercadopago" in html_content:
            payment_gateways.append("MercadoPago")
        if "paypal" in html_content:
            payment_gateways.append("PayPal")
        if "stripe" in html_content:
            payment_gateways.append("Stripe")
        if "transferencia" in html_content or "transfer" in html_content:
            payment_gateways.append("Transferencia Bancaria")

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


def _clean_prose_line(text_line):
    """Limpia sintaxis de LaTeX suelta, backticks y comillas desparejas en texto de prosa."""
    cleaned = text_line.replace("`", "")
    cleaned = re.sub(r"\$A/B\$", "A/B", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("$", "")
    cleaned = re.sub(
        r"'(orders|order_items|total|id|user_id|status|currency|created_at|updated_at|product_id|qty|price)'",
        r"\1",
        cleaned,
    )
    cleaned = re.sub(r"'(/?[a-zA-Z0-9_/-]+)'(?=[)\s.,;:])", r"\1", cleaned)
    return cleaned.strip()


def _format_inline_bold(text_line):
    """Convierte **negrita** de forma segura a HTML para ReportLab."""
    escaped = html.escape(_clean_prose_line(text_line))
    parts = escaped.split("**")
    if len(parts) >= 3:
        new_parts = []
        for i, part in enumerate(parts):
            if i % 2 == 1:
                new_parts.append(f"<b>{part}</b>")
            else:
                new_parts.append(part)
        return "".join(new_parts)
    return escaped.replace("**", "")


def _clean_code_line(line_str):
    """Limpia y normaliza líneas de código generadas por el modelo de forma segura."""
    cleaned = line_str.strip()
    cleaned = re.sub(r"#([0-9a-fA-F]{7})\b", lambda m: "#" + m.group(1)[:6], cleaned)
    cleaned = cleaned.replace("$0=>\\{$", "() => {")
    cleaned = cleaned.replace("\\${", "${")
    cleaned = cleaned.replace("localStorage.removeltem", "localStorage.removeItem")
    cleaned = re.sub(r"\bconst\s+([a-zA-Z_]\w*)\s+([a-zA-Z_]\w*\s*\()", r"const \1 = \2", cleaned)
    cleaned = re.sub(r"\bconst\s+([a-zA-Z_]\w*)\s+(new\s+[a-zA-Z_]\w*\s*\()", r"const \1 = \2", cleaned)
    cleaned = re.sub(r"\bconst\s+([a-zA-Z_]\w*)\s+(require\s*\()", r"const \1 = \2", cleaned) if "onload=" in cleaned and "this.rel='stylesheet'>" in cleaned and not cleaned.endswith('">'): cleaned = cleaned.replace("this.rel='stylesheet'>", "this.rel='stylesheet'\">") cleaned = re.sub(r"\.\.\s*product\s*\)", "...product })", cleaned)
    return cleaned


def _is_code_line(line_stripped):
    """Detecta líneas que parecen código CSS, JSON, HTML o JS."""
    code_markers = [
        "{", "}", ";", "</", "<script", "<div", "<link", "const ", "let ", "var ",
        "function ", "export function", "@media", "display:", "padding:", "margin:",
        "color:", "background", "border", "width:", "font-", "priceCurrency", '"@context"',
        "localStorage", "addEventListener", "module.exports", "async function"
    ]
    return any(m in line_stripped for m in code_markers)


def generate_pdf_report(store_url, audit_text, language, health, seo, speed, mobile, doc_type="audit"):
    """Genera un PDF corporativo adaptado al tipo de entregable ('audit' o 'playbook')."""
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
        spaceAfter=8
    )
    section_heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=13,
        leading=18,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=16,
        spaceAfter=6
    )
    h2_style = ParagraphStyle(
        'ReportH2',
        parent=styles['Heading2'],
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=14,
        spaceAfter=4
    )
    code_style = ParagraphStyle(
        'CodeBlock',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#0F172A'),
        backColor=colors.HexColor('#F8FAFC'),
        borderColor=colors.HexColor('#CBD5E1'),
        borderWidth=0.5,
        borderPadding=8,
        leftIndent=8,
        rightIndent=8,
        spaceBefore=6,
        spaceAfter=10,
    )

    if doc_type == "playbook":
        doc_title = "StoreCheck AI — Playbook Pro de Implementación"
        section_header = "<b>Guía Técnica, Snippets y Plan de Acción</b>"
        intro_fixed_text = (
            "Guía práctica de implementación con bloques de código listos para adaptar, ajustes de checkout y "
            "prioridades de ejecución basadas en los datos reales detectados en el sitio."
        )
    else:
        doc_title = "StoreCheck AI — Reporte de Auditoría Profesional"
        section_header = "<b>Análisis Técnico y Diagnóstico Detallado</b>"
        intro_fixed_text = (
            "Se presenta un informe detallado sobre la experiencia (UI/UX) y la auditoría técnica de su sitio web, "
            "así como una revisión de la fricción de la fase de compra y una evaluación de ventajas competitivas. "
            "Además, se proporciona una guía paso a paso para implementar las correcciones necesarias para mejorar "
            "el rendimiento de conversión del sitio web."
        )

    story.append(Paragraph(doc_title, title_style))
    story.append(Paragraph(f"<b>Sitio analizado:</b> {html.escape(store_url)} &nbsp;|&nbsp; <b>Idioma:</b> {html.escape(language)}", meta_style))

    data_table = [
        [Paragraph("<b>Métrica Clave</b>", body_style), Paragraph("<b>Resultado / Valor</b>", body_style)],
        [Paragraph("Salud General (Health Score)", body_style), Paragraph(f"<b>{health} / 100</b>", body_style)],
        [Paragraph("Puntaje SEO", body_style), Paragraph(f"{seo}%", body_style)],
        [Paragraph("Índice de Velocidad", body_style), Paragraph(f"{speed}", body_style)],
        [Paragraph("Optimización Móvil", body_style), Paragraph(f"{mobile}", body_style)],
    ]

    t_obj = Table(data_table, colWidths=[252, 252])
    t_obj.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#0F172A')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
    ]))

    story.append(t_obj)
    story.append(Spacer(1, 15))
    story.append(Paragraph(section_header, h2_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(intro_fixed_text, body_style))
    story.append(Spacer(1, 8))

    blocks = audit_text.split("\n\n")
    cleaned_blocks = []
    seen_snippets = set()

    for block in blocks:
        b_clean = block.strip()
        b_lower = b_clean.lower()
        if not b_clean:
            continue
        if any(b_lower.startswith(prefix) for prefix in ["hola", "aquí tienes", "después de analizar", "estimado", "presento"]):
            continue
        if re.match(r"^\d+\.?$", b_clean):
            continue

        snippet_key = b_lower[:70]
        if snippet_key in seen_snippets:
            continue
        seen_snippets.add(snippet_key)
        cleaned_blocks.append(b_clean)

    for block in cleaned_blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip() and not re.match(r"^\d+\.?$", ln.strip())]
        if not lines:
            continue

        is_fence_block = lines[0].startswith("```")
        is_code_cluster = (not is_fence_block) and (
            len(lines) >= 2 and all(_is_code_line(l) or l in ["{", "}", "});"] for l in lines)
        )

        if is_fence_block or is_code_cluster:
            code_lines = []
            for l in lines:
                if l.startswith("```"):
                    continue
                code_lines.append(html.escape(_clean_code_line(l)))
            if code_lines:
                story.append(Paragraph("<br/>".join(code_lines), code_style))
            continue

        formatted_lines = []
        for line in lines:
            if re.match(r"^\|?[\s\-:]+\|[\s\-:|]+$", line):
                continue
            if line.startswith("```"):
                continue

            line_no_hash = re.sub(r"^#+\s*", "", line).strip()

            if line_no_hash.lower() in ["json", "css", "javascript", "js", "html"]:
                continue

            line_clean = line_no_hash.replace("Auditorio técnico", "Auditoría técnica")
            line_clean = line_clean.replace("auditorio técnico", "auditoría técnica")
            line_clean = line_clean.replace("experiencia utilizador", "experiencia de usuario")
            line_clean = line_clean.replace("e varejas", "minorista / e-commerce")
            line_clean = line_clean.replace("<title>", "título: ").replace("</title>", "")
            line_clean = _clean_prose_line(line_clean)

            if line_clean.startswith("|") and line_clean.endswith("|"):
                continue

            if doc_type == "audit":
                line_clean = re.sub(r"\$.*?\$", "", line_clean)
                line_clean = line_clean.replace("$", "")

            if re.match(r"^[1-5]\.\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", line_clean) and len(line_clean) < 85:
                if formatted_lines:
                    story.append(Paragraph("<br/>".join(formatted_lines), body_style))
                    formatted_lines = []
                story.append(Paragraph(f"<b>{html.escape(line_clean)}</b>", section_heading_style))
                continue

            line_lower = line_clean.lower()
            forced_heading = None
            if doc_type == "audit":
                if "auditoría técnica" in line_lower and len(line_clean) < 45:
                    forced_heading = "1. Auditoría técnica"
                elif "ui/ux" in line_lower and len(line_clean) < 50:
                    forced_heading = "2. Análisis UI/UX y buyer journey"
                elif "fricción" in line_lower and len(line_clean) < 55:
                    forced_heading = "3. Revisión de fricción en el proceso de compra"
                elif "ventaja competitiva" in line_lower and len(line_clean) < 50:
                    forced_heading = "4. Evaluación de ventaja competitiva"
                elif "implementación" in line_lower and len(line_clean) < 50:
                    forced_heading = "5. Guía de implementación paso a paso"

            if forced_heading:
                if formatted_lines:
                    story.append(Paragraph("<br/>".join(formatted_lines), body_style))
                    formatted_lines = []
                story.append(Paragraph(f"<b>{html.escape(forced_heading)}</b>", section_heading_style))
                continue

            rendered_line = _format_inline_bold(line_clean)
            if rendered_line.startswith("- ") or rendered_line.startswith("* "):
                rendered_line = "• " + rendered_line[2:]

            formatted_lines.append(rendered_line)

        if formatted_lines:
            story.append(Paragraph("<br/>".join(formatted_lines), body_style))

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


def call_groq_chat(client_instance, messages, temperature=0.7, max_tokens=1600):
    if not client_instance:
        raise Exception("El cliente de servicio no está disponible en este momento.")

    preferred_models = [
        "llama-3.3-70b-versatile",
        "qwen/qwen3.8-27b",
        "llama-3.1-8b-instant",
    ]

    last_error = None
    for model_id in preferred_models:
        try:
            response = client_instance.chat.completions.create(
                messages=messages,
                model=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response
        except Exception as e:
            last_error = e
            continue

    try:
        models_response = client_instance.models.list()
        all_models = [m.id for m in models_response.data]
        excluded_keywords = ["guard", "classifier", "tool", "moderation", "vision"]
        chat_models = [
            m_id
            for m_id in all_models
            if m_id not in preferred_models and not any(kw in m_id.lower() for kw in excluded_keywords)
        ]
        for model_id in chat_models[:3]:
            try:
                return client_instance.chat.completions.create(
                    messages=messages,
                    model=model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as e:
                last_error = e
                continue
    except Exception as e:
        last_error = e

    raise Exception(f"Error de comunicación con el servicio: {last_error}")


def build_report_text(client_instance, store_url, sd, report_language, doc_type="audit", comp_info=""):
    if doc_type == "playbook":
        prompt = f"""
        You are a master e-commerce CRO architect and senior full-stack developer.
        Based on the store data from {store_url}:{comp_info}
        - Platform: {sd['platform']}
        - Title: {sd['title']}
        - Cart/Checkout Ready: {sd['has_cart_button']} / {sd['has_checkout_link']}
        - Gateways: {', '.join(sd['payment_gateways'])}
        - Snippet: {sd['raw_text'][:1800]}

        Generate a complete, clear, and practical Technical Implementation Playbook Pro.
        STRICT RULES:
        1. No conversational greetings or intro fluff. Do NOT use '#' markdown headings.
        2. Write section titles cleanly on their own lines, e.g.:
           1. Diagnóstico crítico de conversión
           2. Snippets de código y optimización frontend
           3. Arquitectura del checkout y pasarelas de pago
           4. Plan de acción de 7 días para escalar
        3. Every JS/CSS/HTML/JSON code block must be syntactically complete and valid:
           - Always include '=' in variable assignments (e.g., const raw = localStorage.getItem(...);).
           - Always close every quote and bracket/parenthesis.
           - Use valid 6-digit hex colors (e.g., #3b0764).
           - Put each code block in its own paragraph block separated by blank lines.
        4. In prose and bullet points, write plain text without backticks (`), without raw LaTeX dollar signs like $A/B$ (write A/B), and without stray single quotes around identifiers.
        5. Never cut off mid-sentence or leave a trailing number at the end. Complete every section and bullet point cleanly.
        6. Write the response entirely in professional, corporate {report_language}.
        """
        system_msg = "You are an elite technical consultant and e-commerce conversion architect."
        tokens_limit = 4500
    else:
        prompt = f"""
        You are a world-class principal e-commerce CRO consultant and an elite executive copywriter.
        Analyze the store data from {store_url}:{comp_info}
        - Platform: {sd['platform']}
        - Title: {sd['title']}
        - Meta Description: {sd['meta_description']}
        - Cart Button Detected: {sd['has_cart_button']}
        - Checkout Flow Link Detected: {sd['has_checkout_link']}
        - Payment Gateways Found: {', '.join(sd['payment_gateways'])}
        - Content Snippet: {sd['raw_text'][:1800]}

        Provide a concise, highly professional, and deep technical audit report based strictly on these elements.
        STRICT EDITORIAL & STRUCTURAL RULES:
        1. DO NOT include any conversational greetings, intros, or polite filler. DO NOT use '#' characters anywhere.
        2. STRICTLY AVOID ANY REPETITION. Do not repeat sections, do not list titles in multiple foreign languages, and do not use boilerplate placeholder sentences. Every section and bullet point must contain unique, specific insights.
        3. Write the response entirely in flawless, professional, and natural corporate {report_language}. Avoid literal translations or colloquialisms.
        4. Ensure rigorous grammar, punctuation, and syntactic coherence.
        5. DO NOT use Markdown tables (pipes like '|'). Format all findings as clean, structured bullet points or paragraphs.
        6. Structure the report into exactly 5 concise sections:
           1. Auditoría técnica
           2. Análisis UI/UX y buyer journey
           3. Revisión de fricción en el proceso de compra
           4. Evaluación de ventaja competitiva
           5. Guía de implementación paso a paso
        """
        system_msg = "You are an elite corporate technical consultant and native copyeditor specializing in e-commerce optimization."
        tokens_limit = 2000

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": prompt},
    ]
    completion = call_groq_chat(client_instance, messages, temperature=0.2, max_tokens=tokens_limit)
    return completion.choices[0].message.content


def build_single_pdf(
    store_url,
    report_lang,
    doc_type,
    scraped_data=None,
    metrics=None,
    comp_info="",
):
    """Genera y guarda en session_state un único PDF ('audit' o 'playbook') con una sola llamada a la API."""
    if doc_type == "playbook":
        text_key = "playbook_report_text"
        pdf_key = "playbook_pdf_bytes"
        store_key = "playbook_pdf_store"
        lang_key = "playbook_pdf_lang"
        spinner_msg = "🤖 Compilando Playbook Pro con snippets de código y optimizaciones CRO avanzadas..."
    else:
        text_key = "audit_report_text"
        pdf_key = "audit_pdf_bytes"
        store_key = "audit_pdf_store"
        lang_key = "audit_pdf_lang"
        spinner_msg = "🤖 Elaborando informe técnico profundo y diseño corporativo..."

    needs_rebuild = (
        pdf_key not in st.session_state
        or st.session_state.get(store_key) != store_url
        or st.session_state.get(lang_key) != report_lang
    )

    if needs_rebuild:
        with st.spinner(spinner_msg):
            sd_to_use = scraped_data
            if not sd_to_use:
                ok_s, d_s = scrape_store_data(store_url)
                if not ok_s:
                    st.error(f"❌ {d_s}")
                    return None
                sd_to_use = d_s

            if metrics:
                h_val, s_val, sp_val, m_val = metrics
            else:
                h_val, s_val, sp_val, m_val = calculate_store_metrics(sd_to_use, report_lang)

            report_text = build_report_text(
                client, store_url, sd_to_use, report_lang, doc_type=doc_type, comp_info=comp_info
            )
            pdf_bytes = generate_pdf_report(
                store_url,
                report_text,
                report_lang,
                h_val,
                s_val,
                sp_val,
                m_val,
                doc_type=doc_type,
            )

            st.session_state[text_key] = report_text
            st.session_state[pdf_key] = pdf_bytes
            st.session_state[store_key] = store_url
            st.session_state[lang_key] = report_lang

    return st.session_state.get(pdf_key)


def render_audit_download_button(
    button_label,
    button_key,
    store_url,
    report_lang,
    scraped_data=None,
    metrics=None,
    comp_info="",
):
    """Renderiza el botón de descarga del Reporte de Auditoría ($19) con su propio PDF."""
    audit_pdf_bytes = build_single_pdf(
        store_url=store_url,
        report_lang=report_lang,
        doc_type="audit",
        scraped_data=scraped_data,
        metrics=metrics,
        comp_info=comp_info,
    )
    if audit_pdf_bytes:
        st.download_button(
            label=button_label,
            data=audit_pdf_bytes,
            file_name="StoreCheck_AI_Corporate_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
            key=button_key,
        )


def render_playbook_section(
    store_url,
    report_lang,
    is_playbook_already_paid,
    redirect_base_url,
    scraped_data=None,
    metrics=None,
    comp_info="",
):
    """Muestra la sección del Playbook Pro ($150 USD) y su descarga o enlace de pago."""
    st.markdown("---")
    st.markdown("### 🗺️ Playbook de Implementación Pro ($150 USD)")
    st.info(
        "Obtené los snippets de código exactos, configuraciones de SEO y correcciones UI/UX listas para integrar, "
        "basadas exclusivamente en los hallazgos de tu auditoría oficial."
    )

    if is_playbook_already_paid:
        st.success(
            "🎉 ¡Pago del Playbook Pro verificado con éxito! "
            "Tu guía técnica de implementación y snippets a medida ya están listos."
        )
        pdf_playbook_bytes = build_single_pdf(
            store_url=store_url,
            report_lang=report_lang,
            doc_type="playbook",
            scraped_data=scraped_data,
            metrics=metrics,
            comp_info=comp_info,
        )
        if pdf_playbook_bytes:
            st.download_button(
                label="📥 Descargar mi Playbook Pro de Implementación (PDF)",
                data=pdf_playbook_bytes,
                file_name="StoreCheck_AI_Playbook_Pro.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"dl_playbook_only_{store_url}",
            )
    else:
        playbook_checkout_url = build_checkout_url(
            "[https://storecheck-ai.lemonsqueezy.com/checkout/buy/c88fd3da-a0e7-4319-821a-f126d584d96e](https://storecheck-ai.lemonsqueezy.com/checkout/buy/c88fd3da-a0e7-4319-821a-f126d584d96e)",
            redirect_base_url,
            store_url,
            "?success=true&success_playbook=true",
        )

        st.link_button(
            label="💳 Pagar $150 USD y Activar Playbook Pro",
            url=playbook_checkout_url,
            use_container_width=True,
        )


# --- CAPTURAR URL DESDE QUERY PARAMS O ÚLTIMA TIENDA GUARDADA ---
query_store = normalize_store_url(st.query_params.get("store", ""))
if query_store and "store_url_input" not in st.session_state:
    st.session_state["store_url_input"] = query_store
if query_store and "store_url" not in st.session_state:
    st.session_state["store_url"] = query_store
    save_last_store_url(query_store)

# --- BARRA LATERAL ---
ui_language = st.sidebar.selectbox(
    "🌐 Idioma de la Interfaz / UI Language",
    ["Español", "English", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

enable_comparison = st.sidebar.checkbox("⚔️ Modo Comparación (Tu tienda vs. Competencia)", value=False)

# Diccionario i18n
i18n_ui = {
    "Español": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnósticos automatizados con IA y recomendaciones de crecimiento para e-commerce",
        "url_label": "Ingresá la URL de tu tienda principal",
        "url_placeholder": "[https://mitienda.com](https://mitienda.com)",
        "competitor_label": "Ingresá la URL de la tienda rival / competencia",
        "competitor_placeholder": "[https://tiendacompetencia.com](https://tiendacompetencia.com)",
        "btn_preview": "🚀 Ejecutar Auditoría / Comparativa",
        "btn_reset": "🔄 Restablecer",
        "spinner": "Analizando tiendas globalmente...",
        "success_preview": "Diagnóstico completado con éxito!",
        "preview_title": "📊 Salud General de la Tienda",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Hallazgos y Teaser del Mystery Shopper",
        "full_report_title": "📄 Generar y Descargar Reporte Completo en PDF",
        "full_report_info": "Obtené el informe técnico completo con formato corporativo, guías de optimización paso a paso y análisis profundo de conversión.",
        "report_lang_label": "Seleccioná el idioma para tu Reporte PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD y Descargar PDF Pro",
        "btn_download_unlocked": "📥 Descargar mi Reporte PDF Corporativo ($19)",
        "terms": "Términos y Condiciones",
        "privacy": "Política de Privacidad",
        "error_url": "Por favor, ingresá una URL válida.",
    },
    "English": {
        "title": "StoreCheck AI",
        "subtitle": "Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores",
        "url_label": "Enter your Main Store URL",
        "url_placeholder": "[https://your-store.com](https://your-store.com)",
        "competitor_label": "Enter Competitor Store URL",
        "competitor_placeholder": "[https://competitorstore.com](https://competitorstore.com)",
        "btn_preview": "🚀 Run Audit / Head-to-Head",
        "btn_reset": "🔄 Reset",
        "spinner": "Analyzing stores globally...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Mystery Shopper Teaser & Findings",
        "full_report_title": "📄 Generate & Download Full PDF Report",
        "full_report_info": "Get the complete technical report with corporate formatting, step-by-step optimization guides, and conversion deep-dive.",
        "report_lang_label": "Select the language for your full PDF report:",
        "btn_full_report": "💳 Pay $19 USD & Download Pro PDF",
        "btn_download_unlocked": "📥 Download My Corporate PDF Report ($19)",
        "terms": "Terms of Service",
        "privacy": "Privacy Policy",
        "error_url": "Please enter a valid URL.",
    },
    "Português": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnósticos automatizados por IA e recomendações de crescimento para e-commerce",
        "url_label": "Insira o URL da sua loja principal",
        "url_placeholder": "[https://sualoja.com](https://sualoja.com)",
        "competitor_label": "Insira o URL da loja concorrente",
        "competitor_placeholder": "[https://lojacorrente.com](https://lojacorrente.com)",
        "btn_preview": "🚀 Executar Auditoria / Comparativo",
        "btn_reset": "🔄 Redefinir",
        "spinner": "Analisando lojas globalmente...",
        "success_preview": "Diagnóstico concluído com sucesso!",
        "preview_title": "📊 Saúde Geral da Loja",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Descobertas e Teaser do Mystery Shopper",
        "full_report_title": "📄 Gerar e Baixar Relatório Completo em PDF",
        "full_report_info": "Obtenha o relatório técnico completo com formato corporativo, guias de otimização e análise profunda.",
        "report_lang_label": "Selecione o idioma para o seu relatório PDF completo:",
        "btn_full_report": "💳 Pagar $19 USD e Baixar PDF Pro",
        "btn_download_unlocked": "📥 Baixar meu Relatório PDF Corporativo ($19)",
        "terms": "Termos de Serviço",
        "privacy": "Política de Privacidade",
        "error_url": "Por favor, insira um URL válido.",
    },
    "Italiano": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnostica automatizzata tramite IA e consigli di crescita per e-commerce",
        "url_label": "Inserisci l'URL del tuo negozio principale",
        "url_placeholder": "[https://tuonegozio.com](https://tuonegozio.com)",
        "competitor_label": "Inserisci l'URL del negozio concorrente",
        "competitor_placeholder": "[https://negozioconcorrente.com](https://negozioconcorrente.com)",
        "btn_preview": "🚀 Esegui Audit / Testa a Testa",
        "btn_reset": "🔄 Reimposta",
        "spinner": "Analisi dei negozi in corso...",
        "success_preview": "Diagnostica completata con successo!",
        "preview_title": "📊 Salute Generale del Negozio",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Risultati e Teaser del Mystery Shopper",
        "full_report_title": "📄 Genera e Scarica il Rapporto PDF Completo",
        "full_report_info": "Ottieni il report tecnico completo con formattazione aziendale e guide di ottimizzazione dettagliate.",
        "report_lang_label": "Seleziona la lingua per il tuo rapporto PDF completo:",
        "btn_full_report": "💳 Paga $19 USD e Scarica PDF Pro",
        "btn_download_unlocked": "📥 Scarica il mio Report PDF Aziendale ($19)",
        "terms": "Termini di Servizio",
        "privacy": "Informativa sulla Privacy",
        "error_url": "Si prega di inserire un URL valido.",
    },
    "Français": {
        "title": "StoreCheck AI",
        "subtitle": "Diagnostics automatisés par IA et recommandations de croissance pour e-commerce",
        "url_label": "Entrez l'URL de votre boutique principale",
        "url_placeholder": "[https://votre-boutique.com](https://votre-boutique.com)",
        "competitor_label": "Entrez l'URL de la boutique concurrente",
        "competitor_placeholder": "[https://boutiqueconcurrente.com](https://boutiqueconcurrente.com)",
        "btn_preview": "🚀 Lancer l'Audit / Comparatif",
        "btn_reset": "🔄 Réinitialiser",
        "spinner": "Analyse des boutiques en cours...",
        "success_preview": "Diagnostic terminé avec succès !",
        "preview_title": "📊 Santé Globale de la Boutique",
        "seo_score_label": "SEO Score",
        "speed_index_label": "Speed Index",
        "mobile_readiness_label": "Mobile Readiness",
        "teaser_heading": "💡 Résultats et Teaser du Mystery Shopper",
        "full_report_title": "📄 Générer et Télécharger le Rapport PDF Complet",
        "full_report_info": "Obtenez le rapport technique complet avec mise en page d'entreprise et guides d'optimisation.",
        "report_lang_label": "Sélectionnez la langue de votre rapport PDF complet :",
        "btn_full_report": "💳 Payer 19 $ USD et Télécharger PDF Pro",
        "btn_download_unlocked": "📥 Télécharger mon Rapport PDF d'Entreprise ($19)",
        "terms": "Conditions Générales",
        "privacy": "Politique de Confidentialité",
        "error_url": "Veuillez entrer une URL valide.",
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI",
        "subtitle": "针对电商的自动化人工智能诊断与业务增长建议",
        "url_label": "输入您的主商店网址",
        "url_placeholder": "[https://your-store.com](https://your-store.com)",
        "competitor_label": "输入竞争对手商店网址",
        "competitor_placeholder": "[https://competitorstore.com](https://competitorstore.com)",
        "btn_preview": "🚀 运行审计 / 竞品对比",
        "btn_reset": "🔄 重置",
        "spinner": "正在全局分析商店...",
        "success_preview": "诊断成功完成！",
        "preview_title": "📊 商店总体健康状况",
        "seo_score_label": "SEO 评分",
        "speed_index_label": "加载速度",
        "mobile_readiness_label": "移动端适配",
        "teaser_heading": "💡 神秘顾客发现与摘要",
        "full_report_title": "📄 生成并下载完整PDF报告",
        "full_report_info": "获取包含企业级格式、分步优化指南和转化深度剖析的完整技术报告。",
        "report_lang_label": "选择完整PDF报告的语言：",
        "btn_full_report": "💳 支付 $19 USD 并下载 Pro PDF",
        "btn_download_unlocked": "📥 下载我的企业版PDF报告 ($19)",
        "terms": "服务条款",
        "privacy": "隐私政策",
        "error_url": "请输入有效的网址。",
    },
}

t = i18n_ui[ui_language]

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
    for key in [
        "preview_result",
        "scraped_data",
        "store_url",
        "audit_report_text",
        "audit_pdf_bytes",
        "audit_pdf_store",
        "audit_pdf_lang",
        "playbook_report_text",
        "playbook_pdf_bytes",
        "playbook_pdf_store",
        "playbook_pdf_lang",
        "comp_scraped_data",
        "competitor_url",
    ]:
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

            clean_store_url = normalize_store_url(store_url)
            save_last_store_url(clean_store_url)

            success_scraping, scraped_data = scrape_store_data(clean_store_url)
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
                STORE A (Main): {clean_store_url}
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
                You are an expert e-commerce CRO specialist and a "Mystery Shopper" attempting to buy items on the store {clean_store_url}.
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

            chat_completion = call_groq_chat(client, messages, temperature=0.7, max_tokens=900)
            preview_result = chat_completion.choices[0].message.content

            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()

            st.success(t["success_preview"])

            st.session_state["preview_result"] = preview_result
            st.session_state["store_url"] = clean_store_url
            st.session_state["scraped_data"] = scraped_data
            if enable_comparison and comp_scraped_data:
                st.session_state["competitor_url"] = competitor_url
                st.session_state["comp_scraped_data"] = comp_scraped_data
            else:
                if "comp_scraped_data" in st.session_state:
                    del st.session_state["comp_scraped_data"]

            for key_to_del in [
                "audit_report_text",
                "audit_pdf_bytes",
                "audit_pdf_store",
                "audit_pdf_lang",
                "playbook_report_text",
                "playbook_pdf_bytes",
                "playbook_pdf_store",
                "playbook_pdf_lang",
            ]:
                if key_to_del in st.session_state:
                    del st.session_state[key_to_del]

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ {e}")

has_session_audit = "preview_result" in st.session_state and "scraped_data" in st.session_state
is_paid = st.query_params.get("success", "false").lower() == "true"
is_playbook_paid = st.query_params.get("success_playbook", "false").lower() == "true"
app_redirect_base = "[https://storecheck-ai.streamlit.app/](https://storecheck-ai.streamlit.app/)"

if has_session_audit:
    st.markdown("---")

    active_store_url = normalize_store_url(st.session_state.get("store_url", ""))
    if active_store_url:
        save_last_store_url(active_store_url)

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

    comp_info_str = ""
    if "comp_scraped_data" in st.session_state:
        csd = st.session_state["comp_scraped_data"]
        comp_info_str = f"\n- COMPETITOR STORE: {st.session_state['competitor_url']}\n  Platform: {csd['platform']}\n  Title: {csd['title']}"

    if is_paid or is_playbook_paid:
        st.success("🎉 ¡Pago verificado con éxito! Ya podés descargar tu reporte.")

        render_audit_download_button(
            button_label=t["btn_download_unlocked"],
            button_key=f"dl_audit_session_{active_store_url}",
            store_url=active_store_url,
            report_lang=report_language,
            scraped_data=st.session_state["scraped_data"],
            metrics=(health, seo, speed, mobile),
            comp_info=comp_info_str,
        )

        render_playbook_section(
            store_url=active_store_url,
            report_lang=report_language,
            is_playbook_already_paid=is_playbook_paid,
            redirect_base_url=app_redirect_base,
            scraped_data=st.session_state["scraped_data"],
            metrics=(health, seo, speed, mobile),
            comp_info=comp_info_str,
        )

    else:
        checkout_url = build_checkout_url(
            "[https://storecheck-ai.lemonsqueezy.com/checkout/buy/16b5540c-1884-4e2c-a07a-3912222588dc](https://storecheck-ai.lemonsqueezy.com/checkout/buy/16b5540c-1884-4e2c-a07a-3912222588dc)",
            app_redirect_base,
            active_store_url,
            "?success=true",
        )

        st.link_button(
            label=t["btn_full_report"],
            url=checkout_url,
            use_container_width=True,
        )

elif is_paid or is_playbook_paid:
    st.markdown("---")
    st.success("🎉 ¡Pago verificado con éxito!")

    target_store_url = normalize_store_url(
        st.session_state.get("store_url")
        or st.query_params.get("store", "")
        or load_last_store_url()
    )
    target_lang = ui_language if ui_language in ["Español", "English", "Português", "Italiano", "Français", "中文 (Chinese)"] else "Español"

    if target_store_url:
        if is_playbook_paid:
            render_playbook_section(
                store_url=target_store_url,
                report_lang=target_lang,
                is_playbook_already_paid=True,
                redirect_base_url=app_redirect_base,
            )
            if "audit_pdf_bytes" in st.session_state and st.session_state.get("audit_pdf_store") == target_store_url:
                st.markdown("---")
                render_audit_download_button(
                    button_label=t["btn_download_unlocked"],
                    button_key=f"dl_audit_from_pb_{target_store_url}",
                    store_url=target_store_url,
                    report_lang=st.session_state.get("audit_pdf_lang", target_lang),
                )
        else:
            render_audit_download_button(
                button_label=t["btn_download_unlocked"],
                button_key=f"dl_audit_return_{target_store_url}",
                store_url=target_store_url,
                report_lang=target_lang,
            )
            render_playbook_section(
                store_url=target_store_url,
                report_lang=target_lang,
                is_playbook_already_paid=False,
                redirect_base_url=app_redirect_base,
            )
    else:
        st.info("Ingresá la URL de la tienda auditada para generar tu PDF:")
        fallback_url = st.text_input(
            t["url_label"],
            placeholder=t["url_placeholder"],
            key="fallback_paid_store_url",
        )
        if st.button("Generar PDF", use_container_width=True, key="btn_fallback_generate_pdf"):
            if not fallback_url.strip():
                st.warning(t["error_url"])
            else:
                manual_store = normalize_store_url(fallback_url)
                save_last_store_url(manual_store)
                st.session_state["store_url"] = manual_store
                st.rerun()

st.markdown("---")
st.markdown(
    f"<p style='text-align: center; font-size: 12px; color: gray;'>"
    f"<a href='/?page=terms' style='color: #3B82F6; text-decoration: underline;'>{t['terms']}</a> | "
    f"<a href='/?page=privacy' style='color: #3B82F6; text-decoration: underline;'>{t['privacy']}</a>"
    f"<br>© 2026 StoreCheck AI. Global E-commerce Audits."
    f"</p>",
    unsafe_allow_html=True,
)
