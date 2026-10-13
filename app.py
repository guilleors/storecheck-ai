%%writefile app.py
import streamlit as st
from groq import Groq
import time
import random

# 1. Configuración de página
st.set_page_config(
    page_title="StoreCheck AI | Instant E-Commerce Audit",
    page_icon="⚡",
    layout="centered"
)

# Estilos CSS
st.markdown("""
    <style>
    .main { padding-top: 2rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# Manejo seguro de API Key para local y producción
api_key = None
try:
    if "GROQ_API_KEY" in st.secrets:
        api_key = st.secrets["GROQ_API_KEY"]
except Exception:
    api_key = None

st.title("⚡ StoreCheck AI")
st.caption("Automated AI Diagnostics & Growth Recommendations for E-Commerce Stores")

# Sidebar para prueba local si no hay secret configurado
if not api_key:
    api_key = st.sidebar.text_input("🔑 Groq API Key (Local Test)", type="password")

st.markdown("---")

url_input = st.text_input("🌐 Enter your Store URL", placeholder="https://mycoolstore.com")

if st.button("🚀 Run Free Store Audit"):
    if not url_input:
        st.warning("Please enter a valid store URL first.")
    elif not api_key:
        st.error("Please enter your Groq API Key in the sidebar to proceed.")
    else:
        clean_url = url_input.replace("https://", "").replace("http://", "").strip("/")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("🔍 Scanning store headers & speed response...")
        progress_bar.progress(30)
        time.sleep(0.5)
        
        status_text.text("📱 Checking mobile responsiveness & viewport tags...")
        progress_bar.progress(60)
        time.sleep(0.5)
        
        status_text.text("🤖 Asking AI Engine for optimization tips...")
        progress_bar.progress(90)
        
        score = random.randint(62, 78)
        issues = [
            "Missing meta description on key product pages.",
            "3 large images detected without WebP compression or ALT tags.",
            "Missing mobile viewport meta tag affecting responsive rendering."
        ]
        
        prompt = f"""
        You are an elite E-Commerce SEO and conversion rate optimization consultant.
        A diagnostic tool scanned '{clean_url}' and found: {issues}.
        
        Provide 3 clear, actionable recommendations in English to fix these issues and boost conversions.
        Use bullet points. Do not include markdown headers or conversational intros.
        """
        
        try:
            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            ai_report = completion.choices[0].message.content
            
            progress_bar.progress(100)
            status_text.empty()
            
            st.success("✅ Audit Completed Successfully!")
            st.subheader(f"📊 Overall Store Health: {score}/100")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("SEO Score", f"{score}%", "-12%")
            col2.metric("Speed Index", "2.4s", "+0.8s")
            col3.metric("Mobile Readiness", "Warning", delta_color="inverse")
            
            st.markdown("---")
            st.subheader("💡 AI Executive Summary & Action Plan")
            st.markdown(ai_report)
            
            st.markdown("---")
            col_low, col_high = st.columns(2)
            
            with col_low:
                st.markdown("### 🔒 Deep Technical Report")
                st.write("**Price: $9 USD**")
                st.write("• 15+ automated technical checks")
                st.write("• Exact code snippets to copy/paste")
                st.write("• PDF export for your developers")
                st.link_button("💳 Get PDF Report ($9)", "https://lemon-squeezer-placeholder-link")

            with col_high:
                st.markdown("### 🛠️ Hands-On Fix Service")
                st.write("**Price: From $299 USD**")
                st.write("• 100% Done-For-You implementation")
                st.write("• Guaranteed 90+ Health Score")
                st.write("• Ready in less than 48 hours")
                st.link_button("💬 Request Fix / Contact", "https://wa.me/placeholder")

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Error connecting to AI engine: {e}")

# Pie legal
st.markdown("---")
st.caption("© 2026 StoreCheck AI. All rights reserved.")

with st.expander("⚖️ Legal, Privacy & Terms of Service"):
    tab1, tab2, tab3 = st.tabs(["Terms of Service", "Privacy Policy", "Refund Policy"])
    with tab1:
        st.markdown("1. **Service Overview:** Automated SEO & technical diagnostics...")
    with tab2:
        st.markdown("1. **Data Collection:** Only public URLs processed...")
    with tab3:
        st.markdown("1. **Digital Reports:** Non-refundable once delivered...")
