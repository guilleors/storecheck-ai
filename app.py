import os
from groq import Groq
import streamlit as st

# Configuración inicial de la página
st.set_page_config(
    page_title="StoreCheck AI - Global E-commerce Audit",
    page_icon="🚀",
    layout="centered",
)

# --- BARRA LATERAL (Solo Configuración de API Key) ---
st.sidebar.header("⚙️ Configuración")

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
      help="Ingresá tu clave de Groq si no está configurada en los Secrets.",
  )

# --- INTERFAZ PRINCIPAL (Flujo limpio y directo) ---
st.title("StoreCheck AI 🛒🤖")
st.markdown(
    "Auditoría instantánea de tiendas online potenciada por Inteligencia"
    " Artificial para mercados globales."
)

if not api_key:
  st.warning(
      "⚠️ Por favor, ingresá tu **Groq API Key** en la barra lateral izquierda"
      " para comenzar."
  )
  st.stop()

client = Groq(api_key=api_key)

# Paso 1: Ingreso de URL limpio y sin fricción inicial
store_url = st.text_input(
    "Ingresá la URL de la tienda a auditar:",
    placeholder="https://tu-tienda.com",
)

if st.button("🚀 Analizar Tienda (Vista Previa Gratis)"):
  if not store_url:
    st.warning("Por favor, ingresá una URL válida.")
  else:
    with st.spinner("Analizando la tienda globalmente..."):
      try:
        # Prompt rápido para la vista previa
        preview_prompt = (
            "You are an expert e-commerce auditor and CRO specialist."
            f" Analyze the store {store_url}. Provide exactly 3 quick,"
            " high-impact findings or issues as a free preview. Write the"
            " output in a professional tone."
        )

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI e-commerce audit expert.",
                },
                {"role": "user", "content": preview_prompt},
            ],
            model="llama3-8b-8192",
            temperature=0.7,
        )

        preview_result = chat_completion.choices[0].message.content

        st.success("¡Vista previa generada con éxito!")

        # Guardamos en el estado de la sesión para que no se borre al interactuar
        st.session_state["preview_result"] = preview_result
        st.session_state["store_url"] = store_url

      except Exception as e:
        st.error(f"Error: {e}")

# Paso 2: Si ya se generó la vista previa, mostramos el resultado y el selector de idioma para el pago
if "preview_result" in st.session_state:
  st.markdown("---")
  st.markdown("### 🔍 Vista Previa del Análisis")
  st.write(st.session_state["preview_result"])

  st.markdown("---")
  st.markdown("### 📄 Desbloquear Reporte Completo en PDF")
  st.info(
      "Obtené el informe técnico completo con guías de optimización paso a"
      " paso, análisis profundo de UI/UX, SEO y fricción de checkout."
  )

  # Selector de idioma estratégico ubicado justo antes del botón de pago
  report_language = st.selectbox(
      "Seleccioná el idioma para tu Reporte PDF completo:",
      [
          "English",
          "Español",
          "Português",
          "Italiano",
          "Français",
          "中文 (Chinese)",
      ],
  )

  st.markdown(
      f"*(El reporte completo se generará en: **{report_language}**)*"
  )

  # Botón de pago (Lemon Squeezy)
  st.markdown(
      "[🔒 Desbloquear Reporte Completo por $19"
      " USD](https://tu-enlace-de-pago-aqui.lemonsqueezy.com)"
  )
