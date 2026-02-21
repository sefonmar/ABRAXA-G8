import streamlit as st
import pandas as pd
import yfinance as yf
import random
from auth import check_password
from ui_components import inject_abraxa_design, render_sidebar
from gold_tab import render_gold_tab

# 1. CONFIGURACIÓN
st.set_page_config(page_title="ABRAXA G8 ELITE", layout="wide", initial_sidebar_state="collapsed")

# 2. SEGURIDAD
if not check_password():
    st.stop()

# 3. IDIOMAS
LANGUAGES = {
    "Español": {"monitor_title": "MONITOR G8", "visual_tab": "ANÁLISIS ELITE", "macro_tab": "MACRO UPDATE LIVE"},
    "English": {"monitor_title": "G8 MONITOR", "visual_tab": "ELITE ANALYSIS", "macro_tab": "MACRO UPDATE LIVE"}
}
T = LANGUAGES[st.session_state.get('lang_choice', 'Español')]

# 4. INTERFAZ (Solo una vez)
inject_abraxa_design()
render_sidebar()

# ESTO MATA EL DUPLICADO: Usamos un contenedor vacío para limpiar la pantalla
placeholder = st.empty()

with st.container():
    st.markdown("# ABRAXA")
    st.markdown("### SISTEMA DE INTELIGENCIA ESTRATÉGICA")

    # NAVEGACIÓN ÚNICA
    # Ponemos nombres fijos para evitar el error de 'T' si algo falla
    tab_monitor, tab_visual, tab_macro, tab_gold, tab_hawkish = st.tabs([
        "MONITOR G8", "ANÁLISIS ELITE", "MACRO UPDATE LIVE", "COMMODITIES", "ABRAXA CON HAWKISH CAPITAL"
    ])

    # BUSCA DONDE DEFINES LAS PESTAÑAS Y DÉJALO ASÍ:
# Esto elimina la barra de arriba y deja solo la de abajo
tab_monitor, tab_visual, tab_macro, tab_gold, tab_hawkish = st.tabs([
    T["monitor_title"], 
    T["visual_tab"], 
    T["macro_tab"], 
    "COMMODITIES", 
    "ABRAXA CON HAWKISH CAPITAL"
])

with tab_monitor:
    # Aquí es donde viven tus cuadros verdes/rojos
    st.write("### Panel de Control Principal")
    # Tu lógica de render_monitor() va aquí

with tab_hawkish:
    # Solo aquí se cargará el contenido de Hawkish
    from abraxa_tab import render_abraxa_hawkish_tab
    render_abraxa_hawkish_tab()

    with tab_gold:
        render_gold_tab(None)

# 2. ESTILO OSCURO PERMANENTE (CSS)
st.markdown("""
    <style>
    /* Fondo principal negro profundo */
    .stApp {
        background-color: #0E1117 !important;
        color: #FFFFFF !important;
    }
    
    /* Sidebar oscuro */
    [data-testid="stSidebar"] {
        background-color: #161B22 !important;
    }

    /* Forzar que todos los textos sean blancos o grises claros */
    .stMarkdown, p, span, label, h1, h2, h3 {
        color: #FFFFFF !important;
    }

    /* Estilo para tus tarjetas de pares (las cajas negras) */
    div[style*="background-color: black"] {
        background-color: #1A1C24 !important;
        border: 1px solid #30363D !important;
        border-radius: 10px !important;
        padding: 15px !important;
    }

    /* Hacer que los botones resalten */
    .stButton>button {
        background-color: #21262D !important;
        color: white !important;
        border: 1px solid #30363D !important;
        border-radius: 8px !important;
    }
    
    /* Color de las métricas (DXY, VIX, etc.) */
    [data-testid="stMetricValue"] {
        color: #58A6FF !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- A PARTIR DE AQUÍ SIGUE TU LÓGICA (Análisis, etc.) ---

# --- A PARTIR DE AQUÍ SIGUE EL RESTO DE TU CÓDIGO (Lógica de análisis, etc.) ---
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from streamlit_autorefresh import st_autorefresh
from groq import Groq
import asyncio
import os
import time
import random
from gold_tab import render_gold_tab

# --- 1. CONFIGURACIÓN E IDIOMAS (10 Idiomas Principales) ---
st.set_page_config(page_title="Abraxa G8 ELITE", layout="wide", page_icon="")

API_ID = 20879464
API_HASH = '9f7455ec162aa0a39af1f7e97b9e7d9d'
CHANNEL_USERNAME = 'otc_financial_markets'

# Intentar importar Telethon
try:
    from telethon import TelegramClient
except ImportError:
    st.error("Error: Librería 'telethon' not found. Run 'python3 -m pip install telethon'")

if 'telegram_history' not in st.session_state:
    st.session_state.telegram_history = []

LANGUAGES = {
    "Español": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Nuevo Escaneo", "chat_placeholder": "Analicemos el flujo institucional...",
        "analyze_btn": "Analizar", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "MONITOR G8",
        "details_btn": "DETALLES", "back_btn": "VOLVER AL MONITOR", "scanning": "ESCANEANDO", "diagnostics": "Diagnósticos",
        "prob_score": "Puntuación Prob", "ai_prompt": "Responde de forma técnica en ESPAÑOL.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ANÁLISIS ELITE", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Sin actualizaciones.", "horizon": "Horizonte:"
    },
    "English": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ New Scan", "chat_placeholder": "Analyze institutional flow...",
        "analyze_btn": "Analyze", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "G8 MONITOR",
        "details_btn": "DETAILS", "back_btn": "BACK TO MONITOR", "scanning": "SCANNING", "diagnostics": "Diagnostics",
        "prob_score": "Prob Score", "ai_prompt": "Respond technically in ENGLISH.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ELITE ANALYSIS", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "No updates.", "horizon": "Horizon:"
    },
    "Português": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Novo Scan", "chat_placeholder": "Analisar fluxo institucional...",
        "analyze_btn": "Analisar", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "MONITOR G8",
        "details_btn": "DETALHES", "back_btn": "VOLTAR AO MONITOR", "scanning": "ESCANER", "diagnostics": "Diagnósticos",
        "prob_score": "Pontuação Prob", "ai_prompt": "Responda tecnicamente em PORTUGUÊS.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ANÁLISE ELITE", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Sem atualizações.", "horizon": "Horizonte:"
    },
    "Français": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Nouveau Scan", "chat_placeholder": "Analyser le flux institutionnel...",
        "analyze_btn": "Analyser", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "MONITEUR G8",
        "details_btn": "DÉTAILS", "back_btn": "RETOUR AU MONITEUR", "scanning": "SCAN EN COURS", "diagnostics": "Diagnostics",
        "prob_score": "Score de Prob", "ai_prompt": "Répondez techniquement en FRANÇAIS.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ANALYSE ELITE", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Pas de mises à jour.", "horizon": "Horizon:"
    },
    "Deutsch": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Neuer Scan", "chat_placeholder": "Institutionellen Fluss analysieren...",
        "analyze_btn": "Analysieren", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "G8 MONITOR",
        "details_btn": "DETAILS", "back_btn": "ZURÜCK ZUM MONITOR", "scanning": "SCANNT", "diagnostics": "Diagnose",
        "prob_score": "Prob-Score", "ai_prompt": "Antworten Sie technisch auf DEUTSCH.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ELITE ANALYSE", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Keine Updates.", "horizon": "Zeithorizont:"
    },
    "Italiano": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Nuova Scansione", "chat_placeholder": "Analizza il flujo istituzionale...",
        "analyze_btn": "Analizza", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "MONITOR G8",
        "details_btn": "DETTAGLI", "back_btn": "TORNA AL MONITOR", "scanning": "SCANSIONE", "diagnostics": "Diagnostica",
        "prob_score": "Punteggio Prob", "ai_prompt": "Rispondi tecnicamente in ITALIANO.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ANALISI ELITE", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Nessun aggiornamento.", "horizon": "Orizzonte:"
    },
    "Русский": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ Новый скан", "chat_placeholder": "Анализ потоков...",
        "analyze_btn": "Анализ", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "МОНИТОР G8",
        "details_btn": "ДЕТАЛИ", "back_btn": "НАЗАД К МОНИТОРУ", "scanning": "СКАНИРОВАНИЕ", "diagnostics": "Диагностика",
        "prob_score": "Вероятность", "ai_prompt": "Отвечайте технически на РУССКОМ языке.", "macro_tab": "MACRO UPDATE LIVE",
        "visual_tab": "ЭЛИТНЫЙ АНАЛИЗ", "sync_btn": "SYNC LIVE FOREX FEED", "no_news": "Нет обновлений.", "horizon": "Горизонт:"
    },
    "中文": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ 新扫描", "chat_placeholder": "分析机构流向...",
        "analyze_btn": "分析", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "G8 监控",
        "details_btn": "详情", "back_btn": "返回监控", "scanning": "扫描中", "diagnostics": "诊断",
        "prob_score": "概率评分", "ai_prompt": "用中文进行技术性回答。", "macro_tab": "宏观更新",
        "visual_tab": "精英分析", "sync_btn": "同步电报馈送", "no_news": "无更新。", "horizon": "周期:"
    },
    "日本語": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ 新規スキャン", "chat_placeholder": "機関投資家のフローを分析...",
        "analyze_btn": "分析", "insight_title": "AI ABRAXA MASTER INSIGHT:", "monitor_title": "G8 モニター",
        "details_btn": "詳細", "back_btn": "モニターに戻る", "scanning": "スキャン中", "diagnostics": "診断",
        "prob_score": "確率スコア", "ai_prompt": "日本語で専門的に回答してください。", "macro_tab": "マクロ更新",
        "visual_tab": "エリート分析", "sync_btn": "テレグラム同期", "no_news": "更新なし。", "horizon": "期間:"
    },
    "العربية": {
        "sidebar_title": "Abraxa AI", "refresh_btn": "+ مسح جديد", "chat_placeholder": "تحليل التدفق المؤسسي...",
        "analyze_btn": "تحليل", "insight_title": "رؤية حورس الرئيسية:", "monitor_title": "مراقب G8",
        "details_btn": "تفاصيل", "back_btn": "العودة للمراقب", "scanning": "جاري المسح", "diagnostics": "التشخيص",
        "prob_score": "درجة الاحتمال", "ai_prompt": "أجب بشكل تقني باللغة العربية.", "macro_tab": "تحديث الماكرو",
        "visual_tab": "تحليل النخبة", "sync_btn": "مزامنة تلغرام", "no_news": "لا تحديثات.", "horizon": "الأفق:"
    }
}

# Selector de Idioma en el Sidebar
if 'lang_choice' not in st.session_state: 
    st.session_state.lang_choice = "Español"

with st.sidebar:
    st.session_state.lang_choice = st.selectbox("Language / Idioma", list(LANGUAGES.keys()), index=list(LANGUAGES.keys()).index(st.session_state.lang_choice))
    T = LANGUAGES[st.session_state.lang_choice]

URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRVMmdokdfLMYwT7fb7_LiEUqAZGco1-GOUYuvO_Vgiy0HusQtD2Hrjcy_a0SG9PUBamPfJHhSPGAaJ/pub?gid=1564576053&single=true&output=csv"
# Este es el link que me pasaste de USD DATA
URL_USD = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRVMmdokdfLMYwT7fb7_LiEUqAZGco1-GOUYuvO_Vgiy0HusQtD2Hrjcy_a0SG9PUBamPfJHhSPGAaJ/pub?gid=87716466&single=true&output=csv"

# --- 2. ESTILOS CSS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&display=swap');
.stApp { background-color: #000000; color: #ffffff; font-family: 'JetBrains Mono', monospace; }
.pair-card { background: #0a0a0a; border: 1px solid #1e2229; border-radius: 4px; padding: 15px; border-left: 4px solid #333; margin-bottom: 10px; }
.ticker-wrap { background: #050505; border-bottom: 1px solid #333; padding: 6px 0; overflow: hidden; margin-bottom: 15px; }
.ticker-move { display: flex; width: fit-content; animation: ticker 60s linear infinite; }
@keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
.ticker-item { padding: 0 25px; border-right: 1px solid #222; font-size: 0.8rem; }
.ticker-val { color: #ffffff; font-weight: bold; }
.ai-summary { background: #0a0a0a; border: 1px solid #1e2229; padding: 15px; border-radius: 4px; margin-bottom: 20px; border-left: 4px solid #ffffff; }
.ai-response { background: #0a0a0a; border: 1px solid #333; padding: 15px; border-radius: 4px; font-size: 0.85rem; color: #ffffff; margin-top: 10px; line-height: 1.5; }
.msg-box { border-bottom: 1px solid #222; padding: 10px 0; font-size: 0.85rem; color: #00ff00; }
.bb-tools { background: #1a1a1a; padding: 5px 15px; border: 1px solid #333; display: flex; gap: 15px; font-size: 11px; color: #ffffff; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# --- 3. MOTOR DE IA Y TELEGRAM ---
client = Groq(api_key="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")

async def fetch_telegram_news():
    client_tg = TelegramClient('horus_terminal_session', API_ID, API_HASH)
    try:
        await client_tg.connect()
        if not await client_tg.is_user_authorized(): return T["no_news"]
        messages = []
        async for message in client_tg.iter_messages(CHANNEL_USERNAME, limit=10):
            if message.text:
                messages.append({"text": message.text, "date": message.date.strftime("%Y-%m-%d %H:%M")})
        await client_tg.disconnect()
        return messages
    except Exception as e: return []

def horus_ai_logic(query, data):
    try:
        contexto_data = data[['Pair', 'Bias', 'Prob_Final']].to_string(index=False)
        prompt = f"Eres Horus, analista institucional. Datos:\n{contexto_data}\nInstrucción: {T['ai_prompt']}\nPregunta: {query}"
        completion = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role": "user", "content": prompt}], temperature=0.6)
        return completion.choices[0].message.content
    except Exception as e: return f"Error AI: {str(e)}"

# --- 4. FUNCIONES DE DATOS ---
def get_data_no_cache():
    r = random.randint(1, 1000000)
    df = pd.read_csv(f"{URL_BASE}&refresh_id={r}")
    df.columns = df.columns.str.strip()
    df['Pair'] = df['Pair'].str.strip()
    def to_numeric(x):
        try: return float(str(x).replace('%', '').replace(',', '.').strip())
        except: return 0.0
    df['Prob_Num'] = df['Prob_Final'].apply(to_numeric)
    return df

def get_market_data(symbol, tf_label):
    clean_symbol = symbol.strip().upper()
    if not clean_symbol.endswith("=X"): clean_symbol = f"{clean_symbol}=X"
    tf_map = {"1H": {"period": "7d", "interval": "15m"}, "4H": {"period": "30d", "interval": "1h"}, "DIARIO": {"period": "2y", "interval": "1d"}, "SEMANAL": {"period": "5y", "interval": "1wk"}}
    config = tf_map.get(tf_label, {"period": "1mo", "interval": "1h"})
    try:
        df = yf.download(clean_symbol, period=config["period"], interval=config["interval"], progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        df = df.sort_values(by=df.columns[0], ascending=True)
        if tf_label == "4H":
            df.set_index(df.columns[0], inplace=True)
            df = df.resample('4H').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}).dropna()
            df = df.reset_index()
        return df
    except: return pd.DataFrame()

def get_ticker_prices(pairs_list):
    prices = {}
    for p in pairs_list:
        clean_p = p.strip().upper()
        if not clean_p.endswith("=X"): clean_p = f"{clean_p}=X"
        try:
            d = yf.download(clean_p, period="1d", interval="1m", progress=False)
            prices[p] = float(d['Close'].iloc[-1]) if not d.empty else 0.0
        except: prices[p] = 0.0
    return prices

# --- 5. RENDERIZADO ---
if 'page' not in st.session_state: st.session_state.page = 'main'
if 'selected_pair' not in st.session_state: st.session_state.selected_pair = None
if 'ai_chat' not in st.session_state: st.session_state.ai_chat = ""

with st.sidebar:
    st.markdown(f'### {T["sidebar_title"]}')
    if st.button(T["refresh_btn"]): st.rerun()
    user_input = st.text_area(T["chat_placeholder"], height=150)
    if st.button(T["analyze_btn"]) and user_input:
        df_live = get_data_no_cache()
        st.session_state.ai_chat = horus_ai_logic(user_input, df_live)
    if st.session_state.ai_chat:
        st.markdown(f'<div class="ai-response">{st.session_state.ai_chat}</div>', unsafe_allow_html=True)

if st.session_state.page == 'details':
    pair = st.session_state.selected_pair
    df_live = get_data_no_cache()
    row = df_live[df_live['Pair'] == pair].iloc[0]
    bias_raw = str(row['Bias']).upper()
    bias_clean = "SHORT" if "SHORT" in bias_raw else "LONG"
    color_main = "#ff3333" if bias_clean == "SHORT" else "#00FF00"
    if st.button(T["back_btn"]): 
        st.session_state.page = 'main'
        st.rerun()
    st.markdown(f"### DEEP ANALYSIS: {pair}")
    col_m, col_s = st.columns([3, 1])
    with col_m:
        st.markdown(f'<div class="bb-tools">GO | {pair} Equity | <span style="color:#ffffff;">{bias_clean}</span></div>', unsafe_allow_html=True)
        selected_tf = st.radio(T["horizon"], ["1H", "4H", "DIARIO", "SEMANAL"], index=2, horizontal=True)
        df_h = get_market_data(pair, selected_tf)
        if not df_h.empty:
            df_h = df_h.sort_values(by=df_h.columns[0], ascending=True)
            y_min, y_max = df_h['Close'].min(), df_h['Close'].max()
            margin = (y_max - y_min) * 0.1
            # --- MOTOR GRÁFICO INMOVILIZADO ---
            fig = go.Figure(go.Scatter(x=df_h.iloc[:, 0], y=df_h['Close'], mode='lines', line=dict(color=color_main, width=2), fill='tozeroy', fillcolor=f'rgba({255 if bias_clean == "SHORT" else 0}, {51 if bias_clean == "SHORT" else 255}, 0, 0.10)'))
            fig.update_layout(
                template="plotly_dark", paper_bgcolor='black', plot_bgcolor='black', height=500, margin=dict(l=0, r=0, t=10, b=0),
                hovermode=False, # Bloquea info al pasar mouse
                xaxis=dict(showgrid=False, fixedrange=True), # Bloquea zoom/movimiento X
                yaxis=dict(side='right', gridcolor='#1a1a1a', tickformat=".4f", range=[y_min - margin, y_max + margin], fixedrange=True) # Bloquea zoom/movimiento Y
            )
            # Desactiva barra de herramientas y scroll
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})
    with col_s:
        st.subheader(T["diagnostics"])
        st.code(f"[{T['scanning']}]: {pair}\n[Z_CONTEXT]: {row['Z_Contexto']}")
        st.metric(T["prob_score"], str(row['Prob_Final']))
else: # Línea 244
        try:
            # 1. CARGA DE DATOS SEGUROS
            df_sheet = get_data_no_cache()
            
            # Carga de la hoja USD DATA
            try:
                df_usd_data = pd.read_csv(URL_USD)
                df_usd_data.columns = df_usd_data.columns.str.strip()
            except:
                df_usd_data = pd.DataFrame(columns=['Tono_actual'])
            
            # 2. TICKER Y RESUMEN AI
            prices = get_ticker_prices(df_sheet['Pair'].tolist())
            ticker_html = "".join([f'<div class="ticker-item"><span style="color:#666">{k}</span> <span class="ticker-val">{v:.4f}</span></div>' for k, v in prices.items()])
            st.markdown(f'<div class="ticker-wrap"><div class="ticker-move">{ticker_html + ticker_html}</div></div>', unsafe_allow_html=True)
            
            top_p = df_sheet.sort_values(by='Prob_Num', ascending=False).iloc[0]
            st.markdown(f'<div class="ai-summary"><b style="color:#ffffff;">{T["insight_title"]}</b><br>{top_p["Pair"]} | {top_p["Prob_Final"]}</div>', unsafe_allow_html=True)

            # 3. DEFINICIÓN DE PESTAÑAS (Línea 272 corregida)
            tab_monitor, tab_visual, tab_macro, tab_gold = st.tabs([T["monitor_title"], T["visual_tab"], T["macro_tab"], "COMMODITIES"])

            with tab_monitor:
                cols = st.columns(4)
                for i, row in df_sheet.iterrows():
                    with cols[i % 4]:
                        clr = "#ff3333" if "SHORT" in str(row['Bias']).upper() else "#00ff00"
                        st.markdown(f'<div class="pair-card" style="border-left-color: {clr}"><b>{row["Pair"]}</b><br>{row["Bias"]} // {row["Prob_Final"]}</div>', unsafe_allow_html=True)
                        if st.button(f"{T['details_btn']}", key=f"btn_{row['Pair']}"):
                            st.session_state.selected_pair = row['Pair']
                            st.session_state.page = 'details'
                            st.rerun()

            with tab_visual:
                st.plotly_chart(px.treemap(df_sheet, path=['Pair'], values='Prob_Num', color='Prob_Num', color_continuous_scale='RdYlGn', template="plotly_dark"), use_container_width=True)

            with tab_macro:
                if st.button("SYNC LIVE FEED"):
                    import asyncio
                    from messenger import fetch_latest_news
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    st.session_state.telegram_history = loop.run_until_complete(fetch_latest_news())
                
                if "telegram_history" in st.session_state:
                    for msg in st.session_state.telegram_history:
                        if isinstance(msg, dict) and 'text' in msg:
                            border_clr = "#1d82f5" if msg.get('impact') == "HIGH" else "#333"
                            st.markdown(f'<div style="background:#0a0a0a; padding:15px; border-left: 4px solid {border_clr}; margin-bottom:8px; border-radius:4px;"><small style="color:#888;">{msg.get("date", "")}</small><p style="margin-top:5px; font-size:0.9rem; font-family:\'JetBrains Mono\'; color:#eee;">{msg.get("text", "")}</p></div>', unsafe_allow_html=True)

            # --- PESTAÑAS FINALES (CORREGIDO CON MEMORIA DE SESIÓN) ---
            with tab_gold:
                try:
                    # 1. Renderizado del Monitor Principal (XAUUSD)
                    render_gold_tab(df_usd_data)
                    
                    # 2. Integración del Módulo de Backtesting
                    st.markdown("---")
                    with st.expander("MODULO AUDITORIA + BACKTESTING(5 AÑOS)", expanded=True):
                        st.markdown("### PANEL DE CONTROL XAUUSD BIAS")
                        
                        # INICIALIZACIÓN DE MEMORIA (Para que no se borre al refrescar)
                        if 'bt_results' not in st.session_state:
                            st.session_state.bt_results = None
                        if 'bt_stats' not in st.session_state:
                            st.session_state.bt_stats = None

                        # BOTÓN DE EJECUCIÓN
                        if st.button("INICIAR AI + SIMULACIÓN HISTÓRICA"):
                            with st.spinner("Generando auditoría de 5 años..."):
                                results, stats = run_horus_backtest()
                                # Guardamos en la memoria de la sesión
                                st.session_state.bt_results = results
                                st.session_state.bt_stats = stats

                        # RENDERIZADO PERSISTENTE (Muestra los datos incluso tras el refresco)
                        if st.session_state.bt_results is not None:
                            results = st.session_state.bt_results
                            stats = st.session_state.bt_stats
                            
                            # Métricas Corregidas (Sin weekly_winrate para evitar errores)
                            c1, c2 = st.columns(2)
                            c1.metric("WINRATE DE DIRECCIÓN", f"{stats['daily_winrate']:.2f}%")
                            c2.metric("ACIERTO TOTAL", f"{stats['correct_days']} / {stats['total_days']} días")

                            # Gráfica de Equidad
                            st.line_chart(results['Equity_Curve'])

                            # TABLA DE AUDITORÍA DIARIA
                            st.markdown("### TABLA DE AUDITORÍA: DIRECCIÓN DÍA A DÍA")
                            st.write("Comprueba si el radar acertó comparando el Sesgo con el Movimiento real:")
                            
                            audit_df = results[['Sesgo_Visual', 'Movimiento', 'Precisión', 'GOLD']].sort_index(ascending=False)
                            
                            st.dataframe(
                                audit_df,
                                use_container_width=True,
                                height=400,
                                column_config={
                                    "Sesgo_Visual": "Sesgo Abraxa",
                                    "Movimiento": "Resultado Mercado",
                                    "Precisión": "¿Dirección Correcta?",
                                    "GOLD": st.column_config.NumberColumn("Precio Oro", format="$%.2f")
                                }
                            )

                except Exception as e:
                    st.error(f"Error en pestaña Oro: {e}")

        except Exception as e:
            st.error(f"Error general en el monitor: {e}")

# Autorefresh (Fuera de los bloques principales)
st_autorefresh(interval=30000, key="refresh")