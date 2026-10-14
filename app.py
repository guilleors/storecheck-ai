import io
import os
from groq import Groq
import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="🚀",
    layout="centered",
)

# --- BARRA LATERAL (Selector de Idioma de la Interfaz) ---
ui_language = st.sidebar.selectbox(
    "🌐 Idioma de la Interfaz / UI Language",
    ["Español", "English", "Português", "Italiano", "Français", "中文 (Chinese)"],
)

# Ingreso directo de la API Key en la barra lateral
api_key = st.sidebar.text_input(
    "🔑 Groq API Key:",
    type="password",
    help="Pegá aquí tu clave de Groq.",
)

# Diccionario completo de textos de la interfaz (i18n)
i18n_ui = {
    "Español": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Auditoría instantánea de tiendas online potenciada por Inteligencia"
            " Artificial para mercados globales."
        ),
        "url_label": "Ingresá la URL de la tienda a auditar:",
        "url_placeholder": "https://tu-tienda.com",
        "btn_preview": "🚀 Analizar Tienda (Vista Previa Gratis)",
        "spinner": "Analizando la tienda globalmente...",
        "success_preview": "¡Vista previa generada con éxito!",
        "preview_title": "🔍 Vista Previa del Análisis",
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
            "⚠️ Por favor, ingresá tu **Groq API Key** en la barra lateral"
            " izquierda para comenzar."
        ),
    },
    "English": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": (
            "Instant AI-powered e-commerce store audit for global markets."
        ),
        "url_label": "Enter the store URL to audit:",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 Analyze Store (Free Preview)",
        "spinner": "Analyzing store globally...",
        "success_preview": "Preview generated successfully!",
        "preview_title": "🔍 Analysis Preview",
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
        "error_api": (
            "⚠️ Please enter your **Groq API Key** in the left sidebar to"
            " begin."
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
        "btn_preview": "🚀 Analisar Loja (Pré-visualização Gratuita)",
        "spinner": "Analisando a loja globalmente...",
        "success_preview": "Pré-visualização gerada com sucesso!",
        "preview_title": "🔍 Visualização da Análise",
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
            "⚠️ Insira sua **Groq API Key** na barra lateral esquerda para"
            " começar."
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
        "btn_preview": "🚀 Analizza Negozio (Anteprima Gratuita)",
        "spinner": "Analisi del negozio in corso...",
        "success_preview": "Anteprima generata con successo!",
        "preview_title": "🔍 Anteprima dell'Analisi",
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
            "⚠️ Inserisci la tua **Groq API Key** nella barra laterale sinistra"
            " per iniziare."
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
        "btn_preview": "🚀 Analyser la Boutique (Aperçu Gratuit)",
        "spinner": "Analyse de la boutique en cours...",
        "success_preview": "Aperçu généré avec succès !",
        "preview_title": "🔍 Aperçu de l'Analyse",
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
            "⚠️ Veuillez entrer votre **Groq API Key** dans la barre latérale"
            " gauche pour commencer."
        ),
    },
    "中文 (Chinese)": {
        "title": "StoreCheck AI 🛒🤖",
        "subtitle": "面向全球市场的AI驱动型在线商店即时审计工具。",
        "url_label": "输入要审计的商店网址：",
        "url_placeholder": "https://your-store.com",
        "btn_preview": "🚀 分析商店 (免费预览)",
        "spinner": "正在全局分析商店...",
        "success_preview": "预览生成成功！",
        "preview_title": "🔍 分析预览",
        "full_report_title": "📄 生成并下载完整PDF报告",
        "full_report_info": (
            "获取包含分步优化指南、深入UI/UX分析、SEO和结账摩擦检查的完整技术报告。"
        ),
        "report_lang_label": "选择完整PDF报告的语言：",
        "btn_full_report": "💳 支付 $19 USD 并下载 PDF",
        "terms": "服务条款",
        "privacy": "隐私政策",
        "error_url": "请输入有效的网址。",
        "error_api": "⚠️ 请在左侧边栏中输入您的 **Groq API Key** 以开始。",
    },
}

t = i18n_ui[ui_language]


# Función de llamada con respaldo de modelos de chat
def call_groq_chat(client, messages, temperature=0.7):
  chat_models = [
      "openai/gpt-oss-120b",
      "openai/gpt-oss-20b",
      "llama-3.3-70b-versatile",
      "llama-3.1-8b-instant",
  ]
  last_error = None
  for model_name in chat_models:
    try:
      response = client.chat.completions.create(
          messages=messages, model=model_name, temperature=temperature
      )
      return response
    except Exception as e:
      last_error = e
      continue

  try:
    models_resp = client.models.list()
    available_ids = [m.id for m in models_resp.data]
    raise Exception(
        f"Ningún modelo estándar funcionó. Modelos habilitados en tu cuenta de"
        f" Groq: {available_ids}. Último error: {last_error}"
    )
  except Exception as inner_e:
    raise Exception(
        f"Error de conexión con Groq. Detalle: {last_error} | Listado:"
        f" {inner_e}"
    )


# Interfaz Principal
st.title(t["title"])
st.markdown(t["subtitle"])

if not api_key:
  st.warning(t["error_api"])
  st.stop()

client = Groq(api_key=api_key)

store_url = st.text_input(t["url_label"], placeholder=t["url_placeholder"])

if st.button(t["btn_preview"]):
  if not store_url:
    st.warning(t["error_url"])
  else:
    # Barra de progreso y textos dinámicos con "dibujitos" (emojis)
    progress_bar = st.progress(0)
    status_text = st.empty()

    try:
      status_text.text(
          "🌐 [1/3] Conectando y escaneando la estructura de la tienda..."
      )
      progress_bar.progress(33)

      status_text.text(
          "🎨 [2/3] Evaluando UI/UX, diseño y fricción de checkout..."
      )
      progress_bar.progress(66)

      preview_prompt = (
          "You are an expert e-commerce auditor and CRO specialist. Analyze"
          f" the store {store_url}. Provide exactly 3 quick, high-impact"
          f" findings or issues as a free preview. Write the response in"
          f" {ui_language}."
      )

      messages = [
          {"role": "system", "content": "You are an AI e-commerce audit expert."},
          {"role": "user", "content": preview_prompt},
      ]

      status_text.text(
          "🤖 [3/3] Procesando auditoría con Inteligencia Artificial..."
      )
      progress_bar.progress(90)

      chat_completion = call_groq_chat(client, messages, temperature=0.7)

      preview_result = chat_completion.choices[0].message.content

      # Completar la barra al 100%
      progress_bar.progress(100)
      status_text.text("¡Análisis completado con éxito! 🎉")

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

  # =========================================================
  # CONFIGURACIÓN DEL BOTÓN DE PAGO CON LEMON SQUEEZY
  # =========================================================
  # Reemplazá 'TU_SUBDOMINIO' por el nombre corto de tu tienda en Lemon Squeezy (ej: storecheck-ai)
  # Reemplazá 'TU_VARIANT_ID' por tu número de 7 cifras de Lemon Squeezy (ej: 1234567)
  checkout_url = (
      "https://storecheck-ai.lemonsqueezy.com/checkout/buy/16b5540c-1884-4e2c-a07a-3912222588dc"  # <- EDITAR ACÁ
  )

  st.link_button(
      label=t["btn_full_report"], url=checkout_url, use_container_width=True
  )

# --- PIE DE PÁGINA ---
st.markdown("---")
st.markdown(
    f"<p style='text-align: center; font-size: 12px; color: gray;'>"
    f"<a href='#' target='_blank'>{t['terms']}</a> | <a href='#' target='_blank'>{t['privacy']}</a>"
    f"<br>© 2026 StoreCheck AI. Global E-commerce Audits."
    f"</p>",
    unsafe_allow_html=True,
)
