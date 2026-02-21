import streamlit as st

def apply_custom_theme():
    # 1. Selector en el sidebar sin estorbar
    if 'theme_mode' not in st.session_state:
        st.session_state.theme_mode = "Dark"
    
    st.sidebar.markdown("---")
    st.session_state.theme_mode = st.sidebar.radio("MODO", ["Dark", "Light"], horizontal=True)

    # 2. Definición de colores
    if st.session_state.theme_mode == "Dark":
        bg, txt, card, border = "#000000", "#ffffff", "#0a0a0a", "#1e2229"
        ticker_bg = "#050505"
    else:
        bg, txt, card, border = "#ffffff", "#000000", "#f8f9fa", "#dee2e6"
        ticker_bg = "#f0f2f6"

    # 3. Inyección de CSS
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {bg}; color: {txt}; }}
        .pair-card {{ background: {card} !important; border: 1px solid {border} !important; color: {txt} !important; }}
        .ticker-wrap {{ background: {ticker_bg} !important; border-bottom: 1px solid {border} !important; }}
        .ticker-val {{ color: {txt} !important; }}
        .stTabs [data-baseweb="tab-list"] {{ background-color: {bg}; }}
        .stTabs [data-baseweb="tab"] {{ color: {txt} !important; }}
        /* Estilos para el historial de noticias */
        div[style*="background:#0a0a0a"] {{
            background: {card} !important;
            color: {txt} !important;
            border: 1px solid {border} !important;
        }}
        </style>
    """, unsafe_allow_html=True)
    
    return bg, txt, card, border