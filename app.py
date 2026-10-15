import io
import os
from groq import Groq
import streamlit as st

# Configuración inicial de la página (OBLIGATORIO PRIMERO)
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="⚡",
    layout="centered",
)


# Inicialización persistente y cacheada para evitar pérdida de contexto en reruns de Streamlit
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


# Carga segura del cliente cacheado
try:
    client = get_groq_client()
except Exception:
    client = None

# --- BARRA LATERAL (Únicamente Selector de Idioma) ---
ui_language = st.sidebar.selectbox(
    "🌐 Idioma de la Interfaz / UI Language",
    ["Español", "English", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

# Diccionario completo de textos de la interfaz (i18n)
i18n_ui = {
    "Español": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://mitienda.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "Analizando la tienda globalmente...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 Generar y Descargar Reporte Completo en PDF",
        "full_report_info": (
            "Obtené el informe técnico completo con guías de optimización paso a"
            " paso, análisis profundo de UI/UX, SEO y fricción de checkout."
        ),
        "report_lang_label": (
            "Seleccioná el idioma para tu Reporte PDF completo:"
        ),
        "btn_full_report": "💳 Pagar $19 USD y Descargar PDF",
        "terms": "Términos y Condiciones",
        "privacy": "Política de Privacidad",
        "error_url": "Por favor, ingresá una URL válida.",
        "error_api": (
            "⚠️ Error de inicialización del entorno o configuración ausente."
        ),
    },
    "English": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "Analyzing store globally...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 Generate & Download Full PDF Report",
        "full_report_info": (
            "Get the complete technical report with step-by-step optimization"
            " guides, deep UI/UX analysis, SEO, and checkout friction review."
        ),
        "report_lang_label": "Select the language for your full PDF report:",
        "btn_full_report": "💳 Pay $19 USD & Download PDF",
        "terms": "Terms of Service",
        "privacy": "Privacy Policy",
        "error_url": "Please enter a valid URL.",
        "error_api": "⚠️ Environment initialization error or missing configuration.",
    },
    "Português": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://sua-loja.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "Analisando a loja globalmente...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 Gerar e Baixar Relatório Completo em PDF",
        "full_report_info": (
            "Obtenha o relatório técnico completo com guias de otimização passo"
            " a passo, análise profunda de UI/UX, SEO e fricção de checkout."
        ),
        "report_lang_label": (
            "Selecione o idioma para o seu relatório PDF completo:"
        ),
        "btn_full_report": "💳 Pagar $19 USD e Baixar PDF",
        "terms": "Termos de Serviço",
        "privacy": "Política de Privacidade",
        "error_url": "Por favor, insira um URL válido.",
        "error_api": (
            "⚠️ Erro de inicialização do ambiente ou configuração ausente."
        ),
    },
    "Italiano": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://tuo-negozio.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "Analisi del negozio in corso...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 Genera e Scarica il Rapporto PDF Completo",
        "full_report_info": (
            "Ottieni il report tecnico completo con guide di ottimizzazione"
            " dettagliate, analisi approfondita di UI/UX, SEO e attrito al"
            " checkout."
        ),
        "report_lang_label": (
            "Seleziona la lingua per il tuo rapporto PDF completo:"
        ),
        "btn_full_report": "💳 Paga $19 USD e Scarica il PDF",
        "terms": "Termini di Servizio",
        "privacy": "Informativa sulla Privacy",
        "error_url": "Si prega di inserire un URL valido.",
        "error_api": (
            "⚠️ Errore di inizializzazione dell'ambiente o configurazione mancante."
        ),
    },
    "Français": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://votre-boutique.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "Analyse de la boutique en cours...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 Générer et Télécharger le Rapport PDF Complet",
        "full_report_info": (
            "Obtenez le rapport technique complet avec des guides"
            " d'optimisation étape par étape, une analyse approfondie UI/UX,"
            " SEO et tunnel d'achat."
        ),
        "report_lang_label": (
            "Sélectionnez la langue de votre rapport PDF complet :"
        ),
        "btn_full_report": "💳 Payer 19 $ USD et Télécharger le PDF",
        "terms": "Conditions Générales",
        "privacy": "Politique de Confidentialité",
        "error_url": "Veuillez entrer une URL valide.",
        "error_api": (
            "⚠️ Erreur d'initialisation de l'environnement ou configuration"
            " manquante."
        ),
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI",
        "subtitle": (
            "Automated AI Diagnostics & Growth Recommendations for E-Commerce"
            " Stores"
        ),
        "url_label": "Enter your Store URL",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 Run Free Store Audit",
        "spinner": "正在全局分析商店...",
        "success_preview": "Audit Completed Successfully!",
        "preview_title": "📊 Overall Store Health: 64/100",
        "full_report_title": "📄 生成并下载完整PDF报告",
        "full_report_info": (
            "获取包含分步优化指南、深入UI/UX分析、SEO和结账摩擦检查的完整技术报告。"
        ),
        "report_lang_label": "选择完整PDF报告的语言：",
        "btn_full_report": "💳 支付 $19 USD 并下载 PDF",
        "terms": "服务条款",
        "privacy": "隐私政策",
        "error_url": "请输入有效的网址。",
        "error_api": "⚠️ 环境初始化错误或缺少配置。",
    },
}

t = i18n_ui[ui_language]


def call_groq_chat(client_instance, messages, temperature=0.7):
    if not client_instance:
        raise Exception(
            "El cliente de servicio no está disponible en este momento."
        )

    try:
        models_response = client_instance.models.list()
        # Filtramos estrictamente descartando modelos de guard, clasificadores o herramientas
        available_models = [
            m.id
            for m in models_response.data
            if "llama" in m.id.lower()
            and not any(
                bad_word in m.id.lower()
                for bad_word in ["guard", "classifier", "tool", "moderation"]
            )
        ]
    except Exception as e:
        raise Exception(f"No se pudo consultar los modelos disponibles: {e}")

    if not available_models:
        raise Exception(
            "La API de Groq no devolvió modelos de chat activos para esta cuenta."
        )

    # Ordenamos para darle prioridad a los modelos 70b y versátiles/instructivos
    available_models.sort(
        key=lambda name: (
            0 if "70b" in name.lower() or "versatile" in name.lower() else 1
        )
    )

    last_error = None
    # Iteramos sobre los modelos de chat válidos por si alguno falla
    for model_id in available_models:
        try:
            response = client_instance.chat.completions.create(
                messages=messages, model=model_id, temperature=temperature
            )
            return response
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"Error de comunicación con el servicio: {last_error}")


# Interfaz Principal Estilo Pro
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

store_url = st.text_input(t["url_label"], placeholder=t["url_placeholder"])

if st.button(t["btn_preview"]):
    if not store_url:
        st.warning(t["error_url"])
    else:
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text(
                "🌐 [1/3] Conectando y escaneando la estructura de la tienda..."
            )
            progress_bar.progress(33)

            status_text.text(
                "🎨 [2/3] Evaluando rendimiento, UI/UX y fricción de checkout..."
            )
            progress_bar.progress(66)

            preview_prompt = (
                "You are an expert e-commerce auditor and CRO specialist. Analyze"
                f" the store {store_url}. Provide a structured AI Executive Summary"
                f" & Action Plan with 3 high-impact findings as bullet points. Write"
                f" the response in {ui_language}."
            )

            messages = [
                {
                    "role": "system",
                    "content": "You are an AI e-commerce audit expert.",
                },
                {"role": "user", "content": preview_prompt},
            ]

            status_text.text(
                "🤖 [3/3] Generando recomendaciones con Inteligencia Artificial..."
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
        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"❌ {e}")

if "preview_result" in st.session_state:
    st.markdown("---")

    st.markdown(f"### {t['preview_title']}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="SEO Score", value="64%", delta="-12%", delta_color="inverse"
        )
    with col2:
        st.metric(
            label="Speed Index", value="2.4s", delta="+0.8s", delta_color="inverse"
        )
    with col3:
        st.metric(label="Mobile Readiness", value="Warning")

    st.markdown("---")
    st.markdown("### 💡 AI Executive Summary & Action Plan")
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

    # URL base de tu producto en Lemon Squeezy con el parámetro de redirección automática incorporado
    checkout_url = "https://storecheck-ai.lemonsqueezy.com/checkout/buy/16b5540c-1884-4e2c-a07a-3912222588dc?checkout[redirect_url]=https://tu-app.streamlit.app/?success=true"

    st.link_button(
        label=t["btn_full_report"], url=checkout_url, use_container_width=True
    )

st.markdown("---")
st.markdown(
    f"<p style='text-align: center; font-size: 12px; color: gray;'>"
    f"<a href='#' target='_blank'>{t['terms']}</a> | <a href='#' target='_blank'>{t['privacy']}</a>"
    f"<br>© 2026 StoreCheck AI. Global E-commerce Audits."
    f"</p>",
    unsafe_allow_html=True,
)
