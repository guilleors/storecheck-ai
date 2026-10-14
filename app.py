import os
from groq import Groq
import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="🚀",
    layout="centered",
)

# --- BARRA LATERAL (Configuración y Idioma) ---
st.sidebar.header("⚙️ Configuración / Settings")

# Intentar cargar la key de los secrets de Streamlit
api_key = None
try:
  if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
except Exception:
  pass

if not api_key:
  api_key = st.sidebar.text_input(
      "🔑 Groq API Key:",
      type="password",
      help=(
          "Pegá tu clave de Groq acá si no la configuraste en los Secrets de"
          " Streamlit."
      ),
  )

# Selector de 6 idiomas en la barra lateral
language = st.sidebar.selectbox(
    "Seleccioná el Idioma / Select Language",
    ["English", "Español", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

# Diccionario completo de textos de la interfaz y prompts por idioma
i18n = {
    "English": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Instant AI-powered e-commerce store audit for global markets."
        ),
        "url_label": "Enter the store URL to audit:",
        "url_placeholder": "https://your-store.com",
        "btn_text": "🚀 Analyze Store",
        "spinner": "Analyzing store globally...",
        "success": "Analysis completed successfully!",
        "preview_title": "🔍 Analysis Preview",
        "full_report_title": "📄 Full PDF Report",
        "full_report_info": (
            "Get the complete technical report with step-by-step optimization"
            " guides."
        ),
        "payment_link": (
            "[🔒 Unlock Full Report for $19 USD]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "Please enter a valid URL.",
        "error_api": (
            "⚠️ Please enter your **Groq API Key** in the left sidebar to use"
            " artificial intelligence."
        ),
        "prompt": lambda url: (
            "You are an expert e-commerce auditor and conversion rate"
            f" optimization (CRO) specialist. Analyze the store {url} based on"
            " general best practices for online shops. Provide your response"
            " divided into two clear sections:\n1. FREE PREVIEW: Give 3 quick,"
            " high-impact findings/issues.\n2. FULL REPORT: Give a detailed,"
            " comprehensive audit including UI/UX, checkout friction, SEO, and"
            " specific actionable steps for improvement. Write the output in"
            " English."
        ),
    },
    "Español": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Auditoría instantánea de tiendas online potenciada por Inteligencia"
            " Artificial para mercados globales."
        ),
        "url_label": "Ingresá la URL de la tienda a auditar:",
        "url_placeholder": "https://tu-tienda.com",
        "btn_text": "🚀 Analizar Tienda",
        "spinner": "Analizando la tienda globalmente...",
        "success": "¡Análisis completado con éxito!",
        "preview_title": "🔍 Vista Previa del Análisis",
        "full_report_title": "📄 Reporte Completo en PDF",
        "full_report_info": (
            "Obtené el informe técnico completo con guías de optimización paso a"
            " paso en PDF."
        ),
        "payment_link": (
            "[🔒 Desbloquear Reporte Completo por $19 USD]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "Por favor, ingresá una URL válida.",
        "error_api": (
            "⚠️ Por favor, ingresá tu **Groq API Key** en la barra lateral"
            " izquierda para poder usar la inteligencia artificial."
        ),
        "prompt": lambda url: (
            "Sos un experto auditor de e-commerce y especialista en"
            f" optimización de tasas de conversión (CRO). Analiza la tienda"
            f" {url} basándote en buenas prácticas de tiendas online."
            " Proporciona tu respuesta dividida en dos secciones claras:\n1."
            " VISTA PREVIA GRATUITA: Da 3 hallazgos o problemas rápidos de alto"
            " impacto.\n2. REPORTE COMPLETO: Da una auditoría detallada y"
            " completa que incluya UI/UX, fricción en el checkout, SEO y pasos"
            " accionables específicos. Escribí la salida en español."
        ),
    },
    "Português": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Auditoria instantânea de lojas online impulsionada por"
            " Inteligência Artificial para mercados globais."
        ),
        "url_label": "Digite o URL da loja para auditar:",
        "url_placeholder": "https://sua-loja.com",
        "btn_text": "🚀 Analisar Loja",
        "spinner": "Analisando a loja globalmente...",
        "success": "Análise concluída com sucesso!",
        "preview_title": "🔍 Visualização da Análise",
        "full_report_title": "📄 Relatório Completo em PDF",
        "full_report_info": (
            "Obtenha o relatório técnico completo com guias de otimização passo"
            " a passo."
        ),
        "payment_link": (
            "[🔒 Desbloquear Relatório Completo por $19 USD]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "Por favor, insira um URL válido.",
        "error_api": (
            "⚠️ Insira sua **Groq API Key** na barra lateral esquerda para usar"
            " a inteligência artificial."
        ),
        "prompt": lambda url: (
            "Você é um auditor especialista em e-commerce e especialista em"
            f" otimização de taxa de conversão (CRO). Analise a loja {url} com"
            " base nas melhores práticas para lojas virtuais. Forneça sua"
            " resposta dividida em duas seções claras:\n1. VISUALIZAÇÃO"
            " GRATUITA: Dê 3 descobertas ou problemas rápidos de alto impacto.\n2."
            " RELATÓRIO COMPLETO: Dê uma auditoria detalhada e abrangente,"
            " incluindo UI/UX, fricção no checkout, SEO e etapas acionáveis"
            " específicas. Escreva em português."
        ),
    },
    "Italiano": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Audit istantaneo di negozi online basato su intelligenza"
            " artificiale per mercati globali."
        ),
        "url_label": "Inserisci l'URL del negozio da analizzare:",
        "url_placeholder": "https://tuo-negozio.com",
        "btn_text": "🚀 Analizza Negozio",
        "spinner": "Analisi del negozio in corso...",
        "success": "Analisi completata con successo!",
        "preview_title": "🔍 Anteprima dell'Analisi",
        "full_report_title": "📄 Rapporto PDF Completo",
        "full_report_info": (
            "Ottieni il report tecnico completo con guide di ottimizzazione"
            " dettagliate."
        ),
        "payment_link": (
            "[🔒 Sblocca il Rapporto Completo per $19 USD]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "Si prega di inserire un URL valido.",
        "error_api": (
            "⚠️ Inserisci la tua **Groq API Key** nella barra laterale sinistra"
            " per utilizzare l'intelligenza artificiale."
        ),
        "prompt": lambda url: (
            "Sei un revisore esperto di e-commerce e uno specialista in"
            " ottimizzazione del tasso di conversione (CRO). Analiza il negozio"
            f" {url} in base alle migliori pratiche per i negozi online."
            " Fornisci la tua risposta divisa in due sezioni chiare:\n1."
            " ANTEPRIMA GRATUITA: Dai 3 risultati o problemi rapidi ad alto"
            " impatto.\n2. RAPPORTO COMPLETO: Fornisci un audit dettagliato e"
            " completo che includa UI/UX, attrito al checkout, SEO e passaggi"
            " specifici azionabili. Scrivi in italiano."
        ),
    },
    "Français": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Audit instantané de boutiques en ligne propulsé par l'intelligence"
            " artificielle pour les marchés mondiaux."
        ),
        "url_label": "Entrez l'URL de la boutique à auditer :",
        "url_placeholder": "https://votre-boutique.com",
        "btn_text": "🚀 Analyser la Boutique",
        "spinner": "Analyse de la boutique en cours...",
        "success": "Analyse terminée avec succès !",
        "preview_title": "🔍 Aperçu de l'Analyse",
        "full_report_title": "📄 Rapport PDF Complet",
        "full_report_info": (
            "Obtenez le rapport technique complet avec des guides"
            " d'optimisation étape par étape."
        ),
        "payment_link": (
            "[🔒 Déverrouiller le Rapport Complet pour $19 USD]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "Veuillez entrer une URL valide.",
        "error_api": (
            "⚠️ Veuillez entrer votre **Groq API Key** dans la barre latérale"
            " gauche pour utiliser l'IA."
        ),
        "prompt": lambda url: (
            "Vous êtes un auditeur expert en e-commerce et un spécialiste de"
            " l'optimisation du taux de conversion (CRO). Analysez la boutique"
            f" {url} en vous basant sur les meilleures pratiques pour les"
            " boutiques en ligne. Fournissez votre réponse divisée en deux"
            " sections claires :\n1. APERÇU GRATUIT : Donnez 3 constatations ou"
            " problèmes rapides à fort impact.\n2. RAPPORT COMPLET : Fournissez"
            " un audit détaillé et complet comprenant l'UI/UX, le tunnel d'achat,"
            " le SEO et des étapes exploitables. Écrivez en français."
        ),
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": "面向全球市场的AI驱动型在线商店即时审计工具。",
        "url_label": "输入要审计的商店网址：",
        "url_placeholder": "https://your-store.com",
        "btn_text": "🚀 分析商店",
        "spinner": "正在全局分析商店...",
        "success": "分析成功完成！",
        "preview_title": "🔍 分析预览",
        "full_report_title": "📄 完整PDF报告",
        "full_report_info": "获取包含分步优化指南的完整技术报告。",
        "payment_link": (
            "[🔒 解锁完整报告 ($19 USD)]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        ),
        "error_url": "请输入有效的网址。",
        "error_api": "⚠️ 请在左侧边栏中输入您的 **Groq API Key** 以使用人工智能。",
        "prompt": lambda url: (
            "您是一位专业的电商审计师和转化率优化（CRO）专家。请根据网店的最佳实践分析店铺"
            f" {url}。请将您的回答分为两部分：\n1.免费预览：提供3个快速、高影响力的发现或问题。\n2.完整报告：提供详细且全面的审计，包括UI/UX、结账摩擦、SEO和具体的优化步骤。请用中文回答。"
        ),
    },
}

# Obtener textos según el idioma elegido
t = i18n[language]

# Interfaz Principal traducida dinámicamente
st.title(t["title"])
st.markdown(t["subtitle"])

if not api_key:
  st.warning(t["error_api"])
  st.stop()

# Inicializar cliente de Groq
client = Groq(api_key=api_key)

# Campo de URL traducido
store_url = st.text_input(t["url_label"], placeholder=t["url_placeholder"])

if st.button(t["btn_text"]):
  if not store_url:
    st.warning(t["error_url"])
  else:
    with st.spinner(t["spinner"]):
      try:
        selected_prompt = t["prompt"](store_url)

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI e-commerce audit expert. Always provide"
                        " structured, highly professional analysis."
                    ),
                },
                {"role": "user", "content": selected_prompt},
            ],
            model="llama3-8b-8192",
            temperature=0.7,
        )

        analysis_result = chat_completion.choices[0].message.content

        st.success(t["success"])

        st.markdown(f"### {t['preview_title']}")
        st.write(analysis_result)

        st.markdown("---")
        st.markdown(f"### {t['full_report_title']}")
        st.info(t["full_report_info"])
        st.markdown(t["payment_link"])

      except Exception as e:
        st.error(f"Error: {e}")

      except Exception as e:
        st.error(f"Error al procesar la solicitud / Error processing: {e}")
