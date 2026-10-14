import os
from groq import Groq
import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="🚀",
    layout="centered",
)

# Inicializar cliente de Groq con los Secrets de Streamlit
try:
  api_key = st.secrets["GROQ_API_KEY"]
  client = Groq(api_key=api_key)
except Exception:
  st.error(
      "⚠️ No se encontró la GROQ_API_KEY en los Secrets de Streamlit."
      " Configurala en el panel de control."
  )
  st.stop()

# Interfaz Principal
st.title("StoreCheck AI 🛒🤖")
st.markdown(
    "Auditoría instantánea de tiendas online potenciada por Inteligencia"
    " Artificial para mercados globales."
)

# Barra lateral para configuración de idioma
st.sidebar.header("⚙️ Configuración")
language = st.sidebar.selectbox(
    "Seleccioná el Idioma / Language",
    ["English", "Español", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

# Campo para ingresar la URL de la tienda
store_url = st.text_input(
    "Ingresá la URL de la tienda a auditar:",
    placeholder="https://tu-tienda.com",
)

# Diccionario de prompts por idioma
prompts_dict = {
    "English": (
        "You are an expert e-commerce auditor and conversion rate optimization"
        f" (CRO) specialist. Analyze the store {store_url} based on general"
        " best practices for online shops. Provide your response divided into"
        " two clear sections:\n1. FREE PREVIEW: Give 3 quick, high-impact"
        " findings/issues.\n2. FULL REPORT: Give a detailed, comprehensive"
        " audit including UI/UX, checkout friction, SEO, and specific"
        " actionable steps for improvement. Write the output in English."
    ),
    "Español": (
        "Sos un experto auditor de e-commerce y especialista en optimización de"
        f" tasas de conversión (CRO). Analiza la tienda {store_url} basándote"
        " en buenas prácticas de tiendas online. Proporciona tu respuesta"
        " dividida en dos secciones claras:\n1. VISTA PREVIA GRATUITA: Da 3"
        " hallazgos o problemas rápidos de alto impacto.\n2. REPORTE COMPLETO: Da"
        " una auditoría detallada y completa que incluya UI/UX, fricción en el"
        " checkout, SEO y pasos accionables específicos. Escribí la salida en"
        " español."
    ),
    "Português": (
        "Você é um auditor especialista em e-commerce e especialista em"
        f" otimização de taxa de conversão (CRO). Analise a loja {store_url}"
        " com base nas melhores práticas para lojas virtuais. Forneça sua"
        " resposta dividida em duas seções claras:\n1. VISUALIZAÇÃO GRATUITA:"
        " Dê 3 descobertas ou problemas rápidos de alto impacto.\n2. RELATÓRIO"
        " COMPLETO: Dê uma auditoria detalhada e abrangente, incluindo UI/UX,"
        " fricción no checkout, SEO e etapas acionáveis específicas. Escreva"
        " em português."
    ),
    "Italiano": (
        "Sei un revisore esperto di e-commerce e uno specialista in"
        " ottimizzazione del tasso di conversione (CRO). Analizza il negozio"
        f" {store_url} in base alle migliori pratiche per i negozi online."
        " Fornisci la tua risposta divisa in due sezioni chiare:\n1. ANTEPRIMA"
        " GRATUITA: Dai 3 risultati o problemi rapidi ad alto impatto.\n2."
        " RAPPORTO COMPLETO: Fornisci un audit dettagliato e completo che"
        " includa UI/UX, attrito al checkout, SEO e passaggi specifici"
        " azionabili. Scrivi in italiano."
    ),
    "Français": (
        "Vous êtes un auditeur expert en e-commerce et un spécialiste de"
        " l'optimisation du taux de conversion (CRO). Analysez la boutique"
        f" {store_url} en vous basant sur les meilleures pratiques pour les"
        " boutiques en ligne. Fournissez votre réponse divisée en deux sections"
        " claires :\n1. APERÇU GRATUIT : Donnez 3 constatations ou problèmes"
        " rapides à fort impact.\n2. RAPPORT COMPLET : Fournissez un audit"
        " détaillé et complet comprenant l'UI/UX, la friction du tunnel d'achat,"
        " le SEO et des étapes exploitables. Écrivez en français."
    ),
    "中文 (Chinese)": (
        "您是一位专业的电商审计师和转化率优化（CRO）专家。请根据网店的最佳实践分析店铺"
        f" {store_url}。请将您的回答分为两部分：\n1.免费预览：提供3个快速、高影响力的发现或问题。\n2.完整报告：提供详细且全面的审计，包括UI/UX、结账摩擦、SEO和具体的优化步骤。请用中文回答。"
    ),
}

if st.button("🚀 Analizar Tienda / Analyze Store"):
  if not store_url:
    st.warning(
        "Por favor, ingresá una URL válida. / Please enter a valid URL."
    )
  else:
    with st.spinner(
        "Analizando la tienda globalmente... / Analyzing store globally..."
    ):
      try:
        selected_prompt = prompts_dict[language]

        # Llamada a la API de Groq
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

        # Mostrar resultados en pantalla
        st.success("¡Análisis completado con éxito! / Analysis completed!")

        st.markdown("### 🔍 Vista Previa del Análisis / Preview")
        st.write(analysis_result)

        # Sección de monetización simulada (Próximo paso: conectar botón de pago)
        st.markdown("---")
        st.markdown("### 📄 Descargar Reporte Completo en PDF / Full PDF Report")
        st.info(
            "Obtené el informe técnico completo con guías de optimización paso"
            " a paso en PDF."
        )
        st.markdown(
            "[🔒 Desbloquear Reporte Completo por $19 USD / Unlock Full Report]"
            "(https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
        )

      except Exception as e:
        st.error(f"Error al procesar la solicitud / Error processing: {e}")
