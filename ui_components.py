import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import pytz
from textwrap import dedent

# =============================================================================
# OBJETIVO DEL PANEL
# =============================================================================
"""
ABRAXA — INTRADAY EXECUTION (FILTER MODE)

Este panel NO te dice "compra/vende".
Este panel SOLO filtra si el entorno intradía está limpio (ejecutable) o sucio (fakeouts).

Añadido (V3 - Beginner Layer):
- Beginner Mode: convierte el panel en una guía accionable para traders novatos (técnicos)
- Action Box: "qué hago ahora" según el veredicto
- Time Windows: guía de cuándo operar / cuándo no
- Glosario simple: para que macro no sea requisito

V2 ya incluido:
1) EVENT RISK REAL:
   - Calendario USD por CSV o entrada manual
   - HIGH/MODERATE/NONE según cercanía e impacto

2) AUDITORÍA (SNAPSHOT LOG):
   - Guarda snapshots del panel en memoria
   - Descarga CSV

Añadido (V4):
- NY Direction (09:30–11:30 NY): sesgo LONG/SHORT/NEUTRAL para EURUSD/XAUUSD
  (con confianza + playbook) SIN dañar el filtro existente.

Nota:
- Si NO cargas calendario, Event Risk usa un fallback proxy (menos institucional).
"""

# =============================================================================
# 0) HTML SAFE RENDER (FIX CRÍTICO)
# =============================================================================
def md(html: str):
    """Render HTML sin que Streamlit lo convierta en bloque de código por indentación."""
    st.markdown(dedent(html).strip(), unsafe_allow_html=True)

# =============================================================================
# 0) INIT STATE (CRÍTICO)
# =============================================================================
def _init_calendar_state():
    if "usd_calendar_df" not in st.session_state:
        st.session_state.usd_calendar_df = pd.DataFrame(columns=["dt_ny", "title", "impact"])
    if "usd_calendar_manual" not in st.session_state:
        st.session_state.usd_calendar_manual = ""

def _init_audit_state():
    if "audit_log" not in st.session_state:
        st.session_state.audit_log = pd.DataFrame(columns=[
            "ts_ny", "session_phase",
            "verdict", "fakeout", "event_risk",
            "next_event", "instrument",
            "exec_score", "clarity", "whipsaw", "breakout",
            "data_quality",
            "dxy", "dxy_state", "us10y", "us10y_state", "vix", "vix_state"
        ])

# =============================================================================
# 0-A) INSTRUMENT STATE (CRÍTICO)
# =============================================================================
def _init_instrument_state():
    if "instrument" not in st.session_state:
        st.session_state.instrument = "EURUSD"

# =============================================================================
# 0-B) MICRO UX: ICONO "?" (TOOLTIP) — NO ES BOTÓN
# =============================================================================
def info_icon(text: str) -> str:
    """Círculo '?' con tooltip al pasar el mouse. No ejecuta nada."""
    safe = (text or "").replace('"', "&quot;")
    return f'<span class="info-tip" title="{safe}">?</span>'

def label_with_help(label: str, help_text: str) -> str:
    return f'<span class="lbl-help">{label} {info_icon(help_text)}</span>'

# =============================================================================
# 1) DISEÑO (UI) — ESTÉTICA / LEGIBILIDAD
# =============================================================================
def inject_abraxa_design():
    md("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp {
    background-color: #000000;
    color: #ffffff;
    font-family: 'Inter', sans-serif;
}

:root{
    --fs-xs:  12px;
    --fs-sm:  13px;
    --fs-md:  15px;
    --fs-lg:  17px;
    --fs-xl:  20px;
    --fs-xxl: 26px;
}

/* Tooltip "?" */
.info-tip{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    width:16px;
    height:16px;
    border-radius:999px;
    border:1px solid #2b2f39;
    background:#0f1116;
    color:#b9bcc7;
    font-size:11px;
    font-weight:900;
    margin-left:6px;
    line-height:1;
    cursor: help;
    user-select:none;
    transform: translateY(-1px);
}
.lbl-help{
    display:inline-flex;
    align-items:center;
    gap:4px;
}

.b-label {
    background: #101217;
    color: #b9bcc7;
    padding: 5px 10px;
    border-radius: 6px;
    font-size: var(--fs-xs);
    font-weight: 700;
    text-transform: uppercase;
    border: 1px solid #22252d;
    letter-spacing: .7px;
    display: inline-block;
}

.card-exec {
    background: #0a0a0a;
    border: 1px solid #1a1c22;
    padding: 18px;
    border-radius: 12px;
    height: 100%;
}

.muted  { color:#8b8f9b; font-size: var(--fs-sm); margin:0; line-height:1.35; }
.muted2 { color:#a7aab6; font-size: var(--fs-xs); margin:0; letter-spacing:.9px; text-transform:uppercase; font-weight:700; }

.divider { border-top: 1px solid #1a1c22; margin: 18px 0; }

.hdr-title { margin:0; font-size: var(--fs-xl); letter-spacing:1px; font-weight: 900; }
.hdr-sub   { margin:0; font-size: var(--fs-md); color:#8b8f9b; }

.verdict {
    background:#060606;
    border:1px solid #1a1c22;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 10px 0 16px 0;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap: 12px;
}
.verdict-title{
    font-size: var(--fs-xs);
    color:#a7aab6;
    letter-spacing:.9px;
    text-transform:uppercase;
    margin:0;
    font-weight: 800;
}
.verdict-main{
    font-size: var(--fs-xxl);
    font-weight: 900;
    margin:0;
    letter-spacing: .3px;
}
.verdict-sub{
    font-size: var(--fs-md);
    color:#8b8f9b;
    margin:0;
    max-width: 820px;
    line-height: 1.35;
}

.feed-box {
    background:#070707;
    border:1px solid #1a1c22;
    border-radius:10px;
    padding:14px 16px;
    max-height:210px;
    overflow-y:auto;
}
.feed-item {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12.5px;
    color:#d7d9df;
    padding:10px 0;
    border-bottom:1px solid #121418;
    line-height: 1.35;
}
.feed-item:last-child { border-bottom:none; }

.playbook-line {
    background: #0b2018;
    border: 1px solid #1f5b47;
    color: #56d1a8;
    padding: 14px;
    border-radius: 10px;
    font-weight: 900;
    text-align: center;
    margin-top: 16px;
    font-size: var(--fs-md);
}

/* Pills / badges */
.active-pill {
    display:inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    border: 1px solid #2b2f39;
    background: #0f1116;
    color: #b9bcc7;
    font-size: var(--fs-xs);
    font-weight: 800;
    letter-spacing: .6px;
    text-transform: uppercase;
}

/* Fila de flags */
.flag-row{
    display:flex;
    flex-wrap:wrap;
    gap:10px;
    margin: 10px 0 18px 0;
}
.flag-pill{
    display:inline-flex;
    gap:8px;
    align-items:center;
    padding: 8px 10px;
    border-radius: 999px;
    border: 1px solid #22252d;
    background: #0b0b0b;
    color: #d7d9df;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: .35px;
}
.flag-key{
    color:#a7aab6;
    font-weight:900;
    text-transform:uppercase;
    font-size: 11px;
    letter-spacing:.8px;
}

/* Sugerencia de ejecución (por instrumento) */
.exec-suggest{
    background:#070707;
    border:1px solid #1a1c22;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 10px 0 14px 0;
}
.exec-suggest h4{
    margin:0 0 10px 0;
    font-size: 14px;
    letter-spacing:.6px;
    text-transform:uppercase;
    color:#a7aab6;
}
.exec-suggest .line{
    margin:0;
    font-size: 14px;
    line-height:1.35;
    color:#d7d9df;
}
.exec-suggest .ok{ color:#56d1a8; font-weight:900; }
.exec-suggest .no{ color:#f23645; font-weight:900; }

div[data-testid="stMetricValue"] { font-size: 20px !important; }
div[data-testid="stMetricLabel"] { font-size: 12px !important; color:#a7aab6 !important; }

/* Beginner box */
.beginner-box{
    background:#060606;
    border:1px solid #1a1c22;
    border-radius: 12px;
    padding: 14px 16px;
    margin: 10px 0 16px 0;
}
.beginner-title{
    margin:0 0 8px 0;
    font-size: 13px;
    letter-spacing:.9px;
    text-transform:uppercase;
    color:#a7aab6;
    font-weight: 900;
}
.beginner-step{
    margin:0;
    font-size: 14px;
    line-height:1.45;
    color:#d7d9df;
}
.kpi-pill{
    display:inline-flex;
    gap:8px;
    align-items:center;
    padding: 8px 10px;
    border-radius: 10px;
    border: 1px solid #22252d;
    background: #0b0b0b;
    color: #d7d9df;
    font-size: 12.5px;
    font-weight: 900;
    letter-spacing: .25px;
}
.kpi-grid{
    display:flex;
    flex-wrap:wrap;
    gap:10px;
    margin-top:10px;
}

/* === INSTRUMENT PICKER (TOP) — RADIO HORIZONTAL “SEGMENTED” === */
.instrument-wrap{
    display:flex;
    align-items:center;
    justify-content:space-between;
    gap:12px;
    background:#060606;
    border:1px solid #1a1c22;
    border-radius: 14px;
    padding: 12px 14px;
    margin: 12px 0 10px 0;
}
.instrument-title{
    margin:0;
    font-size: 12px;
    letter-spacing: .9px;
    text-transform: uppercase;
    color:#a7aab6;
    font-weight: 900;
}
.instrument-sub{
    margin:4px 0 0 0;
    color:#8b8f9b;
    font-size: 13px;
}

/* Hack radio -> segmented look */
div[data-testid="stRadio"] > label { display:none !important; }
div[data-testid="stRadio"] div[role="radiogroup"]{
    display:flex !important;
    gap:10px !important;
    align-items:center !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label{
    background:#0b0b0b !important;
    border:1px solid #22252d !important;
    border-radius: 999px !important;
    padding: 8px 12px !important;
    color:#d7d9df !important;
    font-weight: 900 !important;
    letter-spacing: .35px !important;
    cursor:pointer !important;
}
div[data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked){
    border-color:#1f5b47 !important;
    background:#0b2018 !important;
    color:#56d1a8 !important;
}

/* Make radio bullets invisible */
div[data-testid="stRadio"] input[type="radio"]{
    opacity:0 !important;
    width:0 !important;
    height:0 !important;
    position:absolute !important;
}
</style>
""")

# =============================================================================
# 2) SIDEBAR
# =============================================================================
def render_sidebar():
    with st.sidebar:
        st.markdown("### ABRAXA G8 ELITE")
        st.markdown("**Operador:** SEFONMAR")

        if "beginner_mode" not in st.session_state:
            st.session_state.beginner_mode = True

        st.session_state.beginner_mode = st.toggle(
            "Beginner Mode (recomendado)",
            value=st.session_state.beginner_mode,
            help="ON = instrucciones simples para operar (sin macro). OFF = vista más 'desk'."
        )

        md(f"<p><b>Modo:</b> Intraday Execution Filter {info_icon('Modo de filtro: evalúa si el entorno intradía está ejecutable (limpio) o con alto riesgo de fakeouts (sucio).')}</p>")
        st.markdown("---")
        md(f"<p>{label_with_help('Reiniciar panel', 'Borra la memoria de sesión (calendario cargado, auditoría, instrumento seleccionado) y recarga el panel.')}</p>")
        if st.button("Reiniciar panel"):
            st.session_state.clear()
            st.rerun()

# =============================================================================
# 3) TIEMPO NY + FASE DE SESIÓN
# =============================================================================
def ny_now():
    return datetime.now(pytz.timezone("America/New_York"))

def get_session_phase(now_ny: datetime) -> str:
    total_minutes = now_ny.hour * 60 + now_ny.minute

    def between(start_h, start_m, end_h, end_m):
        s = start_h * 60 + start_m
        e = end_h * 60 + end_m
        return s <= total_minutes <= e

    if between(0, 0, 6, 59):    return "Asia"
    if between(7, 0, 9, 29):    return "London"
    if between(9, 30, 11, 30):  return "NY AM"
    if between(11, 31, 13, 30): return "NY Lunch"
    if between(13, 31, 16, 0):  return "NY PM"
    return "Off-hours"

# =============================================================================
# 4) GUÍA DE OPERACIÓN
# =============================================================================
def render_operator_guide(beginner: bool):
    if beginner:
        with st.expander("Cómo usar este panel (modo principiante)", expanded=True):
            st.markdown("""
### Lo único que necesitas (si solo sabes técnico)

**Este panel NO te dice compra/vende.**  
Te dice si **HOY** el mercado está **limpio** o **sucio** para ejecutar intradía.

#### Tu workflow (3 pasos)
1) Mira **EXECUTION VERDICT** → EVITAR / PRECAUCIÓN / OPERAR  
2) Si dice **OPERAR**, mira **EVENT WINDOW** y **FIRST IMPULSE**  
3) Si EVENT WINDOW = YES o FIRST IMPULSE = ON → **solo retest** (no chase)

#### Regla #1 de supervivencia
Si no entiendes un módulo, **igual puedes operar**: solo respeta el veredicto + las flags.
            """)
    else:
        with st.expander("Cómo usar este panel (guía simple)", expanded=False):
            st.markdown("""
**Qué es:** filtro de ejecución, no señales.

**Decisión:**
- EVITAR: no ejecutar primer impulso
- PRECAUCIÓN: reducir size y esperar confirmación
- OPERAR: ejecutar A+ setups (ideal retest)

**Orden de lectura:**
1) Veredicto de ejecución  
2) Execution Score + Flags (contexto rápido)  
3) Fakeout Risk + Event Risk (USD)  
4) Drivers (DXY / US10Y / VIX)  
5) Módulo del instrumento y playbook  
6) Auditoría para revisión histórica
            """)

# =============================================================================
# 4-B) Time Windows + Glosario (para novatos)
# =============================================================================
def render_time_windows(now_ny: datetime):
    phase = get_session_phase(now_ny)
    md("<div class='divider'></div>")
    md(f"<h3>Cuándo operar (guía rápida) {info_icon('Esto NO es macro. Es una guía de “calidad de mercado” por sesión.')}</h3>")

    st.markdown("""
- **London (07:00–09:30 NY):** buen momentum para FX. Evita el **primer rompimiento** sin retest.
- **NY AM (09:30–11:30 NY):** la mejor ventana intradía. Aquí nacen los movimientos “reales”.
- **NY Lunch (11:31–13:30 NY):** baja liquidez → más chop/fakeouts.
- **NY PM (13:31–16:00 NY):** puede haber segunda ola, pero ojo a reversals.
- **Off-hours:** más spreads/ruido → si operas aquí, solo A+ con retest sí o sí.
""")
    md(f"<div class='beginner-box'><p class='beginner-title'>Tu sesión actual</p><p class='beginner-step'><b>{phase}</b> — usa esta info para decidir si vale la pena “forzar” trades hoy.</p></div>")

def render_glossary(beginner: bool):
    if not beginner:
        return
    with st.expander("Glosario (para no-macro)", expanded=False):
        st.markdown("""
**DXY (Dollar Index):** mide fuerza del USD.  
- Si está raro/“comprimido”, el mercado tiende a “amagar” (más trampas).

**US10Y:** proxy de yields (tasas).  
- Subidas rápidas suelen “ensuciar” ejecución (más volatilidad).

**VIX:** estrés del mercado.  
- Alto o subiendo rápido = más whipsaw/fakeouts.

**Event Risk (USD):** si hay noticia importante cerca (NFP, CPI, FOMC, etc.)  
- En ventana de evento: **NO primer impulso**. Espera retest o que pase el shock.

**Fakeout:** rompimiento falso (te saca y vuelve).  
- Lo evita: no perseguir velas, confirmar con retest, operar en ventanas buenas.
        """)

# =============================================================================
# 5) VEREDICTO
# =============================================================================
def compute_verdict(fakeout_risk: str, event_level: str, vix_state: str) -> tuple[str, str, str]:
    if event_level == "HIGH" or vix_state == "Dirty":
        return ("EVITAR", "#f23645", "Distorsión alta: evita primer impulso. Espera confirmación / retest.")
    if fakeout_risk == "High" or event_level == "MODERATE":
        return ("PRECAUCIÓN", "#ff9800", "Probabilidad de fakeout: reduce size y no persigas rupturas.")
    return ("OPERAR", "#089981", "Condiciones limpias: ejecuta solo A+ setups con retest.")

# =============================================================================
# 5-B) EXECUTION SCORE MASTER (0–100) + CLARITY / WHIPSAW / BREAKOUT
# =============================================================================
def compute_execution_score(fakeout_risk: str, event_level: str, vix_state: str, dxy_state: str, session_phase: str, data_quality: str):
    score = 100

    if vix_state == "Dirty":
        score -= 25
    elif vix_state == "Caution":
        score -= 12

    if event_level == "HIGH":
        score -= 25
    elif event_level == "MODERATE":
        score -= 12

    if fakeout_risk == "High":
        score -= 18
    elif fakeout_risk == "Moderate":
        score -= 8

    if dxy_state == "Compression":
        score -= 10

    if session_phase == "Off-hours":
        score -= 12

    if data_quality == "STALE":
        score -= 18

    score = max(0, min(100, score))

    if score >= 80:
        clarity, whipsaw, breakout = "Alta", "Baja", "Buena"
    elif score >= 60:
        clarity, whipsaw, breakout = "Media", "Media", "Aceptable"
    else:
        clarity, whipsaw, breakout = "Baja", "Alta", "Pobre"

    return score, clarity, whipsaw, breakout

# =============================================================================
# 5-C) NY DIRECTION ENGINE (09:30–11:30 NY)
# =============================================================================
def _clamp(x: float, lo: float, hi: float) -> float:
    try:
        return float(max(lo, min(hi, x)))
    except Exception:
        return float(lo)

def compute_ny_direction(
    instrument: str,
    session_phase: str,
    drivers: dict,
    event_level: str,
    within_window: bool,
    fakeout_risk: str,
    data_quality: str
):
    """
    Devuelve (direction, confidence_0_100, playbook, reasons[])
    - direction: LONG / SHORT / NEUTRAL / WAIT
    - Solo se activa en NY AM. Fuera => WAIT (no inventa)
    - Gating fuerte si: evento HIGH, VIX Dirty, data STALE
    """
    if session_phase != "NY AM":
        return ("WAIT", 0, "Fuera de NY AM (09:30–11:30 NY). No forzar dirección.", ["Session != NY AM"])

    if data_quality == "STALE":
        return ("NEUTRAL", 20, "Datos STALE: confirma en broker/TV. Si operas, solo retest A+.", ["DATA STALE"])
    if drivers.get("VIX_STATE") == "Dirty":
        return ("NEUTRAL", 25, "VIX Dirty: whipsaw alto. Evita dirección; solo observa o retest muy selectivo.", ["VIX Dirty"])
    if event_level == "HIGH" or within_window:
        return ("NEUTRAL", 30, "Evento en ventana: NO primer impulso. Espera 15–30m y opera solo retest.", ["Event window"])

    dxy_imp = float(drivers.get("DXY_IMPULSE_60M", 0.0))
    tnx_imp = float(drivers.get("US10Y_IMPULSE_60M", 0.0))
    vix_imp = float(drivers.get("VIX_IMPULSE_60M", 0.0))

    dxy_state = drivers.get("DXY_STATE", "Balanced")
    tnx_state = drivers.get("US10Y_STATE", "Stable")
    vix_state = drivers.get("VIX_STATE", "Clean")

    conf = 55.0
    if vix_state == "Caution":
        conf -= 8
    if dxy_state == "Compression":
        conf -= 8
    if fakeout_risk == "High":
        conf -= 10
    elif fakeout_risk == "Moderate":
        conf -= 5

    conf += min(18.0, abs(dxy_imp) * 80.0)
    conf += min(12.0, abs(tnx_imp) * 60.0)
    conf -= min(10.0, max(0.0, vix_imp) * 30.0)

    instrument = (instrument or "").upper().strip()
    reasons = []

    dxy_up = dxy_imp > 0.05
    dxy_dn = dxy_imp < -0.05
    tnx_up = (tnx_state == "Rising") or (tnx_imp > 0.10)
    tnx_dn = (tnx_state == "Reversing") or (tnx_imp < -0.10)

    direction = "NEUTRAL"

    if instrument == "EURUSD":
        if dxy_up and tnx_up:
            direction = "SHORT"
            reasons += ["DXY up", "US10Y rising"]
        elif dxy_dn and tnx_dn:
            direction = "LONG"
            reasons += ["DXY down", "US10Y reversing"]
        elif dxy_up and not tnx_dn:
            direction = "SHORT"
            conf -= 5
            reasons += ["DXY up (solo)"]
        elif dxy_dn and not tnx_up:
            direction = "LONG"
            conf -= 5
            reasons += ["DXY down (solo)"]
        else:
            direction = "NEUTRAL"
            conf -= 10
            reasons += ["No clear USD impulse"]
    else:
        if dxy_up and tnx_up:
            direction = "SHORT"
            reasons += ["DXY up", "US10Y rising"]
        elif dxy_dn and tnx_dn:
            direction = "LONG"
            reasons += ["DXY down", "US10Y reversing"]
        elif tnx_up and not dxy_dn:
            direction = "SHORT"
            conf -= 6
            reasons += ["US10Y rising (solo)"]
        elif tnx_dn and not dxy_up:
            direction = "LONG"
            conf -= 6
            reasons += ["US10Y reversing (solo)"]
        else:
            direction = "NEUTRAL"
            conf -= 10
            reasons += ["No clear rate/USD impulse"]

    conf = _clamp(conf, 0, 95)

    if direction in ["LONG", "SHORT"]:
        if fakeout_risk in ["High", "Moderate"] or dxy_state == "Compression":
            pb = "Dirección OK pero riesgo de fakeout: NO chase. Espera retest + confirmación (M15/H1)."
        else:
            pb = "Dirección OK: ejecuta pullback/retest. Evita entrar tarde en vela grande."
    else:
        pb = "NEUTRAL: hoy manda el filtro. Opera solo si tu técnico da A+ con retest y sin evento cerca."

    if direction == "NEUTRAL":
        conf = min(conf, 55)

    if direction in ["LONG", "SHORT"] and conf < 55:
        direction = "NEUTRAL"
        pb = "Sesgo débil: NEUTRAL. Evita forzar. Si operas: solo A+ retest."
        reasons = (reasons[:2] + ["Confidence low"]) if reasons else ["Confidence low"]

    return (direction, int(round(conf)), pb, reasons[:5])

# =============================================================================
# 6) DATA HELPERS
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def _safe_download(ticker: str, period="60d", interval="1h") -> pd.DataFrame:
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        return df.dropna().copy()
    except Exception:
        return pd.DataFrame()

def atr(series_high, series_low, series_close, length=14) -> pd.Series:
    prev_close = series_close.shift(1)
    tr = pd.concat([
        (series_high - series_low),
        (series_high - prev_close).abs(),
        (series_low - prev_close).abs()
    ], axis=1).max(axis=1)
    return tr.rolling(length).mean()

def atr_ratio_from_df(df: pd.DataFrame, length=14) -> float:
    if df.empty or not all(col in df.columns for col in ["High", "Low", "Close"]):
        return 1.0
    a = atr(df["High"], df["Low"], df["Close"], length=length).dropna()
    if a.empty:
        return 1.0
    a_now = float(a.iloc[-1])
    a_base = float(a.tail(100).mean()) if len(a) >= 100 else float(a.mean())
    return (a_now / a_base) if a_base else 1.0

def impulse_60m_from_df(df: pd.DataFrame) -> float:
    if df.empty or "Close" not in df.columns:
        return 0.0
    closes = df["Close"].dropna()
    if len(closes) < 2:
        return 0.0
    last = float(closes.iloc[-1])
    prev = float(closes.iloc[-2])
    return ((last - prev) / prev) * 100.0 if prev else 0.0

def _last_price_fast(tkr: str, df: pd.DataFrame, fallback: float) -> float:
    try:
        return float(yf.Ticker(tkr).fast_info["last_price"])
    except Exception:
        try:
            if not df.empty and "Close" in df.columns:
                return float(df["Close"].dropna().iloc[-1])
        except Exception:
            pass
    return float(fallback)

def _last_bar_age_minutes(df: pd.DataFrame, now_ny: datetime):
    if df is None or df.empty:
        return None
    try:
        ts = df.index[-1]
        tz_ny = pytz.timezone("America/New_York")

        if getattr(ts, "tzinfo", None) is None:
            ts_utc = pytz.UTC.localize(pd.Timestamp(ts).to_pydatetime())
            ts_ny = ts_utc.astimezone(tz_ny)
        else:
            ts_ny = pd.Timestamp(ts).to_pydatetime().astimezone(tz_ny)

        delta = (now_ny - ts_ny).total_seconds() / 60.0
        return float(delta)
    except Exception:
        return None

def _data_quality_label(ages, stale_threshold_min: float = 120.0):
    valid = [a for a in ages if isinstance(a, (int, float))]
    if not valid:
        return "UNKNOWN", "No se pudo verificar la frescura de datos (fallback)."
    worst = max(valid)
    if worst > stale_threshold_min:
        return "STALE", f"Datos potencialmente desactualizados: última vela hace ~{int(worst)}m."
    return "LIVE", f"Datos recientes: última vela hace ~{int(worst)}m."

# =============================================================================
# 7) INSTRUMENT DATA
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def get_instrument_data(now_ny: datetime):
    df_xau = _safe_download("XAUUSD=X")
    xau_ticker_used = "XAUUSD=X"
    if df_xau.empty:
        df_xau = _safe_download("GC=F")
        xau_ticker_used = "GC=F"

    df_eur = _safe_download("EURUSD=X")

    xau_last = _last_price_fast(xau_ticker_used, df_xau, 2000.0)
    eur_last = _last_price_fast("EURUSD=X", df_eur, 1.08)

    xau_age = _last_bar_age_minutes(df_xau, now_ny)
    eur_age = _last_bar_age_minutes(df_eur, now_ny)

    return {
        "XAU_TKR": xau_ticker_used,
        "XAU_LAST": xau_last,
        "XAU_ATR_RATIO": atr_ratio_from_df(df_xau),
        "XAU_IMPULSE_60M": impulse_60m_from_df(df_xau),
        "XAU_LAST_BAR_AGE_MIN": xau_age,

        "EUR_LAST": eur_last,
        "EUR_ATR_RATIO": atr_ratio_from_df(df_eur),
        "EUR_IMPULSE_60M": impulse_60m_from_df(df_eur),
        "EUR_LAST_BAR_AGE_MIN": eur_age,
    }

# =============================================================================
# 8) DRIVERS MACRO (DXY / US10Y / VIX)
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def get_tactical_data(now_ny: datetime):
    fallback_prices = {"DXY": 104.20, "US10Y": 4.25, "VIX": 14.50}

    df_dxy = _safe_download("DX-Y.NYB")
    df_tnx = _safe_download("^TNX")
    df_vix = _safe_download("^VIX")

    dxy   = _last_price_fast("DX-Y.NYB", df_dxy, fallback_prices["DXY"])
    us10y = _last_price_fast("^TNX", df_tnx, fallback_prices["US10Y"])
    vix   = _last_price_fast("^VIX", df_vix, fallback_prices["VIX"])

    dxy_atr_ratio = atr_ratio_from_df(df_dxy)
    dxy_impulse   = impulse_60m_from_df(df_dxy)
    us10y_impulse = impulse_60m_from_df(df_tnx)
    vix_impulse   = impulse_60m_from_df(df_vix)

    if dxy_atr_ratio < 0.85:
        dxy_state = "Compression"
    elif dxy_atr_ratio > 1.15:
        dxy_state = "Expansion"
    else:
        dxy_state = "Balanced"

    if us10y_impulse > 0.10:
        us10y_state = "Rising"
    elif us10y_impulse < -0.10:
        us10y_state = "Reversing"
    else:
        us10y_state = "Stable"

    if vix >= 22 or vix_impulse > 0.35:
        vix_state = "Dirty"
    elif vix >= 18 or vix_impulse > 0.15:
        vix_state = "Caution"
    else:
        vix_state = "Clean"

    dxy_age = _last_bar_age_minutes(df_dxy, now_ny)
    tnx_age = _last_bar_age_minutes(df_tnx, now_ny)
    vix_age = _last_bar_age_minutes(df_vix, now_ny)

    return {
        "DXY": dxy,
        "US10Y": us10y,
        "VIX": vix,
        "DXY_ATR_RATIO": dxy_atr_ratio,
        "DXY_IMPULSE_60M": dxy_impulse,
        "US10Y_IMPULSE_60M": us10y_impulse,
        "VIX_IMPULSE_60M": vix_impulse,
        "DXY_STATE": dxy_state,
        "US10Y_STATE": us10y_state,
        "VIX_STATE": vix_state,
        "DXY_LAST_BAR_AGE_MIN": dxy_age,
        "US10Y_LAST_BAR_AGE_MIN": tnx_age,
        "VIX_LAST_BAR_AGE_MIN": vix_age,
    }

# =============================================================================
# 9) NARRATIVA (MVP placeholder)
# =============================================================================
def narrative_snapshot():
    pressure = "Low"
    frequency = "Normal"
    tone = "Neutral"
    feed = [
        "USD yields stabilizing — liquidity returning to bids.",
        "Macro calendar proxy: no major USD shock detected.",
        "Orderflow: bids near key zone (watch retest).",
        "DXY balanced regime — avoid chasing first break.",
        "VIX steady — execution quality improving into session.",
    ]
    return pressure, frequency, tone, feed

def headline_spike_proxy(frequency: str, pressure: str) -> str:
    if frequency == "Elevated" or pressure in ["Moderate", "High"]:
        return "ON"
    return "OFF"

# =============================================================================
# 10) EVENT RISK REAL (V2): calendario USD + ventanas
# =============================================================================
def _parse_calendar_csv_to_events(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["dt_ny", "title", "impact"])

    cols = {c.lower().strip(): c for c in df.columns}
    title_col = cols.get("title") or cols.get("event") or cols.get("name")
    impact_col = cols.get("impact") or cols.get("importance")
    dt_ny_col = cols.get("datetime_ny")
    dt_utc_col = cols.get("datetime_utc")

    if not title_col:
        return pd.DataFrame(columns=["dt_ny", "title", "impact"])

    out = pd.DataFrame()
    out["title"] = df[title_col].astype(str)

    if impact_col:
        out["impact"] = df[impact_col].astype(str).str.lower().str.strip()
    else:
        out["impact"] = "medium"

    tz_ny = pytz.timezone("America/New_York")

    if dt_ny_col:
        parsed = pd.to_datetime(df[dt_ny_col], errors="coerce")

        def _to_ny(x):
            if pd.isna(x):
                return pd.NaT
            if getattr(x, "tzinfo", None) is None:
                try:
                    return tz_ny.localize(x)
                except Exception:
                    return pd.NaT
            try:
                return x.astimezone(tz_ny)
            except Exception:
                return pd.NaT

        out["dt_ny"] = parsed.apply(_to_ny)
    elif dt_utc_col:
        parsed = pd.to_datetime(df[dt_utc_col], errors="coerce", utc=True)
        out["dt_ny"] = parsed.dt.tz_convert("America/New_York")
    else:
        return pd.DataFrame(columns=["dt_ny", "title", "impact"])

    out = out.dropna(subset=["dt_ny"]).copy()

    def norm_imp(x: str) -> str:
        x = (x or "").lower()
        if "high" in x or x.strip() == "3":
            return "high"
        if "med" in x or x.strip() == "2":
            return "medium"
        if "low" in x or x.strip() == "1":
            return "low"
        return "medium"

    out["impact"] = out["impact"].apply(norm_imp)
    out = out.sort_values("dt_ny").reset_index(drop=True)
    return out[["dt_ny", "title", "impact"]]

def _parse_manual_events(text: str, now_ny: datetime) -> pd.DataFrame:
    if not text or not text.strip():
        return pd.DataFrame(columns=["dt_ny", "title", "impact"])

    tz_ny = pytz.timezone("America/New_York")
    today = now_ny.date()

    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue

        hhmm = parts[0]
        if len(parts) == 2:
            impact = "medium"
            title = parts[1]
        else:
            impact = parts[1].lower()
            title = ",".join(parts[2:]).strip()

        try:
            hh, mm = hhmm.split(":")
            dt_naive = datetime(today.year, today.month, today.day, int(hh), int(mm), 0)
            dt_ny = tz_ny.localize(dt_naive)
            rows.append({"dt_ny": dt_ny, "title": title, "impact": impact})
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["dt_ny", "title", "impact"])

    def norm_imp(x: str) -> str:
        x = (x or "").lower()
        if "high" in x:
            return "high"
        if "med" in x:
            return "medium"
        if "low" in x:
            return "low"
        return "medium"

    df["impact"] = df["impact"].apply(norm_imp)
    df = df.sort_values("dt_ny").reset_index(drop=True)
    return df

def compute_event_risk_real(now_ny: datetime, events: pd.DataFrame):
    if events is None or events.empty:
        return ("NONE", "—", "No calendar loaded.", pd.DataFrame(columns=["dt_ny", "title", "impact", "mins_to"]), "—", False)

    start = now_ny.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    day_events = events[(events["dt_ny"] >= start) & (events["dt_ny"] < end)].copy()

    if day_events.empty:
        return ("NONE", "—", "Calendario cargado (0 eventos hoy).", pd.DataFrame(columns=["dt_ny", "title", "impact", "mins_to"]), "—", False)

    day_events["mins_to"] = (day_events["dt_ny"] - now_ny).dt.total_seconds() / 60.0
    day_events["abs_mins"] = day_events["mins_to"].abs()

    high_now = day_events[(day_events["impact"] == "high") & (day_events["abs_mins"] <= 30)]
    med_now  = day_events[(day_events["impact"] == "medium") & (day_events["abs_mins"] <= 15)]

    within_window = False

    if not high_now.empty or not med_now.empty:
        level = "HIGH"
        within_window = True
    else:
        high_near = day_events[(day_events["impact"] == "high") & (day_events["abs_mins"] <= 90)]
        med_near  = day_events[(day_events["impact"] == "medium") & (day_events["abs_mins"] <= 45)]
        level = "MODERATE" if (not high_near.empty or not med_near.empty) else "NONE"
        within_window = (level != "NONE")

    future = day_events[day_events["mins_to"] >= 0].sort_values("mins_to")
    next_window_hhmm = future.iloc[0]["dt_ny"].strftime("%H:%M") if not future.empty else "—"
    next_in = f"{int(future.iloc[0]['mins_to'])}m" if not future.empty else "—"

    near = day_events.sort_values("abs_mins").head(5)[["dt_ny", "title", "impact", "mins_to"]].copy()
    drivers_text = "Calendario: ventanas por impacto (hora NY). HIGH=±30m (high) / ±15m (medium). MODERATE=±90m (high) / ±45m (medium)."
    return (level, next_window_hhmm, drivers_text, near, next_in, within_window)

def compute_event_risk_proxy(drivers, narrative_pressure: str, spike: str):
    score = 0
    if narrative_pressure == "High":
        score += 2
    elif narrative_pressure == "Moderate":
        score += 1

    if drivers["VIX_STATE"] == "Dirty":
        score += 2
    elif drivers["VIX_STATE"] == "Caution":
        score += 1

    if spike == "ON":
        score += 1

    if score >= 4:
        level = "HIGH"; next_window = "—"; next_in = "20m"; within_window = True
    elif score >= 2:
        level = "MODERATE"; next_window = "—"; next_in = "45m"; within_window = True
    else:
        level = "NONE"; next_window = "—"; next_in = "—"; within_window = False

    drivers_text = "Proxy: VIX + narrativa + spike (sin calendario)."
    return level, next_window, next_in, within_window, drivers_text

# =============================================================================
# 10-C) FAKEOUT / DISTORTION
# =============================================================================
def compute_fakeout_risk(drivers, narrative_pressure: str):
    dxy_comp = (drivers["DXY_STATE"] == "Compression")
    dxy_exp  = (drivers["DXY_STATE"] == "Expansion")
    vix_clean = (drivers["VIX_STATE"] == "Clean")
    vix_risky = (drivers["VIX_STATE"] in ["Caution", "Dirty"])
    nar_risky = (narrative_pressure in ["Moderate", "High"])
    nar_low   = (narrative_pressure == "Low")

    if dxy_comp and vix_risky and nar_risky:
        return "High"
    if dxy_exp and vix_clean and nar_low:
        return "Low"
    return "Moderate"

def compute_distortion_overlay(event_level: str, narrative_pressure: str, vix_state: str) -> str:
    if vix_state == "Dirty" or event_level == "HIGH":
        return "HIGH"
    if event_level == "MODERATE" and narrative_pressure in ["Moderate", "High"]:
        return "HIGH"
    if event_level == "MODERATE" or narrative_pressure == "Moderate" or vix_state == "Caution":
        return "MODERATE"
    return "LOW"

# =============================================================================
# 11) INDICADOR SIMPLE DXY (EUR)
# =============================================================================
def dollar_pressure_index(drivers):
    imp = drivers["DXY_IMPULSE_60M"]
    stt = drivers["DXY_STATE"]

    if stt == "Expansion" and imp > 0.05:
        return "ACTIVE", "Impulse +"
    if stt == "Compression" and abs(imp) < 0.05:
        return "NEUTRAL", "Impulse flat"
    if imp < -0.05:
        return "SOFT", "Impulse -"
    return "ACTIVE", "Impulse mixed"

def _vol_state_from_atr_ratio(r: float) -> str:
    if r < 0.85:
        return "Compression"
    if r > 1.15:
        return "Expansion"
    return "Balanced"

# =============================================================================
# 11-B) Beginner Action Box (qué hago ahora)
# =============================================================================
def render_beginner_action_box(
    verdict_label: str,
    event_level: str,
    within_window: bool,
    first_impulse_risk: str,
    data_quality: str,
    session_phase: str,
    exec_score: int,
    instrument: str
):
    md("<div class='divider'></div>")
    md(f"<h3>Qué hago ahora (modo principiante) {info_icon('Esto es la traducción del panel a acciones concretas para un trader técnico.')}</h3>")

    rules = []
    if data_quality == "STALE":
        rules.append("⚠️ Data STALE → confirma en TradingView/broker antes de ejecutar.")
    if session_phase in ["NY Lunch", "Off-hours"]:
        rules.append("⚠️ Sesión mala (Lunch/Off-hours) → si operas, solo A+ con retest.")
    if event_level in ["HIGH", "MODERATE"] or within_window:
        rules.append("⏱️ Evento cerca → NO primer impulso. Espera retest o que pase la ventana.")
    if first_impulse_risk == "ON":
        rules.append("🚫 FIRST IMPULSE = ON → prohibido chase. Solo retest/confirmación.")
    if not rules:
        rules.append("✅ Nada crítico activado. Aún así: A+ setups y no sobretrades.")

    if verdict_label == "EVITAR":
        action = "Hoy el mercado está SUCIO para intradía. No operes o haz solo paper / observa."
        plan = [
            "No tomes rompimientos.",
            "Si igual operas: 1 trade máximo, size mínimo, solo retest + confirmación extra."
        ]
        color = "#f23645"
        tag = "NO TRADE / OBSERVAR"
    elif verdict_label == "PRECAUCIÓN":
        action = "Puedes operar, pero como francotirador: pocas entradas, size reducido, retest obligatorio."
        plan = [
            "Reduce size (ej: 0.25–0.5x).",
            "Solo setups A+ (tu patrón favorito) y preferir retest.",
            "Máx 2 intentos si te sacan (sin revenge)."
        ]
        color = "#ff9800"
        tag = "TRADE CON REGLAS"
    else:
        action = "Condiciones limpias. Puedes ejecutar tu técnico normal, pero sin perseguir velas."
        plan = [
            "Prioriza retest/confirmación (mejor fill, menos fakeouts).",
            "Evita entrar tarde en vela grande.",
            "Si pierdes 1 trade: pausa y re-evalúa (no encadenar)."
        ]
        color = "#56d1a8"
        tag = "OK PARA OPERAR"

    md(f"""
<div class="beginner-box">
  <p class="beginner-title">Semáforo de hoy (para {instrument})</p>
  <div class="kpi-grid">
    <div class="kpi-pill" style="border-color:{color}; color:{color};">VEREDICTO: {verdict_label}</div>
    <div class="kpi-pill">SCORE: {exec_score}</div>
    <div class="kpi-pill">EVENT: {event_level}</div>
    <div class="kpi-pill">FIRST IMPULSE: {first_impulse_risk}</div>
    <div class="kpi-pill">SESIÓN: {session_phase}</div>
  </div>

  <div style="margin-top:12px;">
    <p class="beginner-step"><b style="color:{color};">{tag}:</b> {action}</p>
  </div>

  <div style="margin-top:10px;">
    <p class="beginner-step"><b>Plan (simple):</b></p>
    <ul style="margin:6px 0 0 18px; color:#d7d9df; font-size:14px; line-height:1.45;">
      {''.join([f"<li>{x}</li>" for x in plan])}
    </ul>
  </div>

  <div style="margin-top:10px;">
    <p class="beginner-step"><b>Reglas activas:</b></p>
    <ul style="margin:6px 0 0 18px; color:#d7d9df; font-size:14px; line-height:1.45;">
      {''.join([f"<li>{x}</li>" for x in rules])}
    </ul>
  </div>
</div>
""")

# =============================================================================
# 12) AUDITORÍA
# =============================================================================
def audit_append_snapshot(
    now_ny: datetime,
    session_phase: str,
    verdict_label: str,
    fakeout_risk: str,
    event_level: str,
    next_window: str,
    instrument: str,
    exec_score: int,
    clarity: str,
    whipsaw: str,
    breakout: str,
    data_quality: str,
    drivers: dict
):
    _init_audit_state()

    row = {
        "ts_ny": now_ny.strftime("%Y-%m-%d %H:%M:%S"),
        "session_phase": session_phase,
        "verdict": verdict_label,
        "fakeout": fakeout_risk,
        "event_risk": event_level,
        "next_event": next_window,
        "instrument": instrument,
        "exec_score": exec_score,
        "clarity": clarity,
        "whipsaw": whipsaw,
        "breakout": breakout,
        "data_quality": data_quality,
        "dxy": round(float(drivers["DXY"]), 4),
        "dxy_state": drivers["DXY_STATE"],
        "us10y": round(float(drivers["US10Y"]), 4),
        "us10y_state": drivers["US10Y_STATE"],
        "vix": round(float(drivers["VIX"]), 4),
        "vix_state": drivers["VIX_STATE"],
    }

    st.session_state.audit_log = pd.concat([st.session_state.audit_log, pd.DataFrame([row])], ignore_index=True)

    if len(st.session_state.audit_log) > 2000:
        st.session_state.audit_log = st.session_state.audit_log.tail(2000).reset_index(drop=True)

def render_audit_panel():
    _init_audit_state()
    with st.expander("Auditoría (snapshots)", expanded=False):
        md(f"<p>Registro del estado del panel {info_icon('Guarda snapshots con veredicto, riesgos, score y estados de drivers. Sirve para validar si el filtro te evitó días sucios y para post-mortem.')}</p>")

        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("Guardar snapshot ahora", use_container_width=True):
                st.session_state.force_snapshot = True
        with c2:
            if st.button("Limpiar auditoría", use_container_width=True):
                st.session_state.audit_log = st.session_state.audit_log.iloc[0:0].copy()
        with c3:
            csv = st.session_state.audit_log.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Descargar auditoría CSV",
                data=csv,
                file_name="abraxa_auditoria.csv",
                mime="text/csv",
                use_container_width=True
            )

        md("<div class='divider'></div>")
        st.caption("Últimos 50 registros:")
        st.dataframe(st.session_state.audit_log.tail(50), use_container_width=True, height=240)

# =============================================================================
# 13) DASHBOARD PRINCIPAL
# =============================================================================
def render_intraday_dashboard():
    _init_calendar_state()
    _init_instrument_state()

    now = ny_now()
    ny_time = now.strftime("%H:%M")
    session_phase = get_session_phase(now)
    beginner = bool(st.session_state.get("beginner_mode", True))

    # HEADER (ahora resalta instrumento escogido)
    md(f"""
<div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1a1c22; padding-bottom:14px; margin-bottom:10px;">
  <div>
    <h2 class="hdr-title">
      INTRADAY EXECUTION — FILTER MODE {info_icon('Panel de filtro: NO da señales. Evalúa calidad de ejecución intradía (fakeouts, eventos, régimen de DXY, estrés via VIX).')}
    </h2>
    <p class="hdr-sub">
      Session phase: <b>{session_phase}</b> {info_icon('Fase horaria aproximada: Asia/London/NY. Off-hours suele tener menor liquidez y más spreads.')}
      | Last update: {ny_time} NY {info_icon('Hora actual en Nueva York. El panel refresca por interacción y cache TTL (60s).')}
    </p>
  </div>
  <div style="text-align:right;">
    <span class="b-label" style="color:#56d1a8; border-color:#1f5b47;">
      Filter: ACTIVE {info_icon('El filtro está activo: calcula riesgos, score y módulos por instrumento.')}
    </span><br><br>
    <span class="active-pill">Selected: {st.session_state.instrument}</span>
  </div>
</div>
""")

    # =========================
    # INSTRUMENT PICKER (AL INICIO INICIO)
    # =========================
    md(f"""
<div class="instrument-wrap">
  <div>
    <p class="instrument-title">Instrument Selector {info_icon('Escoge el instrumento arriba del todo. Afecta el módulo y el NY Direction (cuando aplica).')}</p>
    <p class="instrument-sub">El filtro y drivers siguen iguales; el módulo y lectura se adaptan al instrumento.</p>
  </div>
  <div style="min-width:260px;">
</div>
</div>
""")
    # Radio horizontal estilo “segmented”
    selected = st.radio(
        "Instrument",
        ["EURUSD", "XAUUSD"],
        index=0 if st.session_state.instrument == "EURUSD" else 1,
        horizontal=True,
        key="instrument_selector",
        help="Cambia el instrumento del módulo. No es señal."
    )
    st.session_state.instrument = selected
    md(f"<div style='margin-top:8px;'><span class='active-pill'>ACTIVE INSTRUMENT: {st.session_state.instrument}</span></div>")

    # Guías (después de escoger instrumento)
    render_operator_guide(beginner=beginner)
    if beginner:
        render_time_windows(now)
        render_glossary(beginner=True)

    # =========================
    # EVENT RISK INPUT (REAL) - con BOTÓN (st.form)
    # =========================
    md("<div class='divider'></div>")
    md(f"<h3>Event Risk (USD) — Calendar Input {info_icon('Carga eventos USD para medir distorsión real por calendario. Si no hay calendario, se usa proxy menos institucional.')}</h3>")

    with st.expander("Cargar calendario USD (recomendado) / entrada manual", expanded=False):
        st.caption("CSV recomendado: columnas datetime_ny, title, impact (high/medium/low). Ej: 2026-02-19 08:30, Initial Jobless Claims, high")
        st.caption("Manual: una línea por evento -> HH:MM,impact,title. Se asume HOY (NY).")

        with st.form("usd_calendar_form", clear_on_submit=False):
            upl = st.file_uploader("Sube CSV de calendario USD", type=["csv"])
            manual = st.text_area(
                "O pega eventos manuales (HH:MM,impact,title)",
                height=110,
                value=st.session_state.usd_calendar_manual,
                placeholder="08:30,high,Initial Jobless Claims\n10:00,medium,ISM Services PMI\n14:00,high,FOMC Minutes"
            )

            cA, cB = st.columns(2)
            with cA:
                apply_btn = st.form_submit_button("Aplicar calendario", use_container_width=True)
            with cB:
                clear_btn = st.form_submit_button("Limpiar calendario", use_container_width=True)

        if clear_btn:
            st.session_state.usd_calendar_df = pd.DataFrame(columns=["dt_ny", "title", "impact"])
            st.session_state.usd_calendar_manual = ""
            st.success("Calendario limpiado.")
            st.rerun()

        if apply_btn:
            merged = pd.DataFrame(columns=["dt_ny", "title", "impact"])

            if upl is not None:
                try:
                    raw = pd.read_csv(upl)
                    merged = pd.concat([merged, _parse_calendar_csv_to_events(raw)], ignore_index=True)
                except Exception as e:
                    st.error(f"Error leyendo CSV: {e}")

            st.session_state.usd_calendar_manual = manual
            manual_df = _parse_manual_events(manual, now)
            if not manual_df.empty:
                merged = pd.concat([merged, manual_df], ignore_index=True)

            merged = merged.dropna(subset=["dt_ny"]).sort_values("dt_ny").reset_index(drop=True)
            st.session_state.usd_calendar_df = merged

            st.success(f"Calendario aplicado: {len(merged)} eventos.")
            st.rerun()

        st.caption("Si no cargas nada, el panel usa un fallback proxy (menos institucional).")

    # =========================
    # Datos del panel
    # =========================
    drivers = get_tactical_data(now)
    inst = get_instrument_data(now)

    data_quality, data_quality_note = _data_quality_label([
        drivers.get("DXY_LAST_BAR_AGE_MIN"),
        drivers.get("US10Y_LAST_BAR_AGE_MIN"),
        drivers.get("VIX_LAST_BAR_AGE_MIN"),
        inst.get("EUR_LAST_BAR_AGE_MIN"),
        inst.get("XAU_LAST_BAR_AGE_MIN"),
    ])

    pressure, frequency, tone, feed = narrative_snapshot()
    spike = headline_spike_proxy(frequency, pressure)

    # =========================
    # EVENT RISK (REAL si hay calendario)
    # =========================
    cal_events = st.session_state.usd_calendar_df.copy() if isinstance(st.session_state.usd_calendar_df, pd.DataFrame) else pd.DataFrame()

    if cal_events is None or cal_events.empty:
        event_level, next_window, next_in, within_window, event_drivers_text = compute_event_risk_proxy(drivers, pressure, spike)
        near_events = pd.DataFrame(columns=["dt_ny", "title", "impact", "mins_to"])
        event_mode = "PROXY"
    else:
        event_level, next_window, event_drivers_text, near_events, next_in, within_window = compute_event_risk_real(now, cal_events)
        event_mode = "CALENDAR"

    fakeout_risk = compute_fakeout_risk(drivers, pressure)
    verdict_label, verdict_color, verdict_text = compute_verdict(fakeout_risk, event_level, drivers["VIX_STATE"])

    gating_notes = []
    if session_phase == "Off-hours" and verdict_label == "OPERAR":
        verdict_label = "PRECAUCIÓN"
        verdict_color = "#ff9800"
        verdict_text = "Off-hours: liquidez menor y spreads peores. Evita primer impulso y ejecuta solo si hay confirmación."
        gating_notes.append("Off-hours gating: OPERAR → PRECAUCIÓN")

    if data_quality == "STALE" and verdict_label == "OPERAR":
        verdict_label = "PRECAUCIÓN"
        verdict_color = "#ff9800"
        verdict_text = "Datos STALE: puede haber retraso de velas. Reduce exposición y confirma con tu broker/TV antes de ejecutar."
        gating_notes.append("Data gating: OPERAR → PRECAUCIÓN")

    exec_score, clarity, whipsaw, breakout = compute_execution_score(
        fakeout_risk=fakeout_risk,
        event_level=event_level,
        vix_state=drivers["VIX_STATE"],
        dxy_state=drivers["DXY_STATE"],
        session_phase=session_phase,
        data_quality=data_quality if data_quality in ["LIVE", "STALE"] else "UNKNOWN"
    )

    first_impulse_risk = "ON" if (fakeout_risk in ["High", "Moderate"] or within_window or drivers["DXY_STATE"] == "Compression") else "OFF"
    chop_risk = "High" if (drivers["DXY_STATE"] == "Compression" and drivers["VIX_STATE"] in ["Caution", "Dirty"]) else "Moderate" if drivers["DXY_STATE"] == "Compression" else "Low"
    event_window_flag = "YES" if within_window else "NO"

    gating_hint = info_icon("Notas de gating: Off-hours o datos STALE pueden degradar OPERAR a PRECAUCIÓN.") if gating_notes else ""

    md(f"""
<div class="verdict">
  <div>
    <p class="verdict-title">
        Execution Verdict {info_icon('Veredicto de ejecución: indica si conviene operar el entorno intradía. NO es dirección.')}
    </p>
    <p class="verdict-main" style="color:{verdict_color};">{verdict_label}</p>
    <p class="verdict-sub">
        {verdict_text}<br>
        <span style="color:#8b8f9b; font-size:12px;">{gating_hint}</span>
    </p>
  </div>
  <div style="text-align:right;">
    <span class="b-label" style="border-color:{verdict_color}; color:{verdict_color};">
        Fakeout: {fakeout_risk} {info_icon('Riesgo de fakeout: alto cuando hay compresión en DXY + VIX riesgoso + presión narrativa.')}
    </span><br><br>
    <span class="b-label">
        Event Risk (USD): {event_level} {info_icon('Riesgo por eventos USD: CALENDAR usa eventos reales; PROXY usa VIX+narrativa+spike.')}
    </span><br><br>
    <span class="b-label" style="border-color:#2b2f39;">
        Data: {data_quality} {info_icon(data_quality_note)}
    </span>
  </div>
</div>
""")

    md(f"<p class='muted2'>EXECUTION SCORE (MASTER) {info_icon('Score 0–100 de “ejecutabilidad”: resume VIX, eventos, fakeout, régimen DXY, off-hours y calidad de data. No es señal.')}</p>")

    score_color = "#56d1a8" if exec_score >= 80 else "#ff9800" if exec_score >= 60 else "#f23645"
    md(f"""
<div class="card-exec" style="margin-top:8px;">
  <p class="muted2">
    SCORE 0–100 {info_icon('80+ = entorno limpio. 60–79 = ejecutable con cautela. <60 = alta probabilidad de ruido/fakeouts.')}
  </p>
  <h3 style="margin:8px 0; font-size:26px; color:{score_color};">{exec_score}</h3>
  <p class="muted" style="margin-top:6px;">
    Clarity: <b>{clarity}</b> {info_icon('Claridad del entorno.')}
    &nbsp;|&nbsp; Whipsaw: <b>{whipsaw}</b> {info_icon('Riesgo de latigazos.')}
    &nbsp;|&nbsp; Breakout Quality: <b>{breakout}</b> {info_icon('Calidad esperada de rupturas.')}
  </p>
</div>
""")

    md(
        f"<div class='flag-row'>"
        f"<div class='flag-pill'><span class='flag-key'>INSTRUMENT</span> {st.session_state.instrument} {info_icon('Instrumento activo para módulo y NY Direction.')}</div>"
        f"<div class='flag-pill'><span class='flag-key'>FIRST IMPULSE</span> {first_impulse_risk} {info_icon('ON = alto riesgo de que el primer impulso sea trampa. Evita chase; prioriza retest/confirmación.')}</div>"
        f"<div class='flag-pill'><span class='flag-key'>CHOP RISK</span> {chop_risk} {info_icon('Riesgo de rango/serrucho: típico en compresión DXY y VIX no limpio.')}</div>"
        f"<div class='flag-pill'><span class='flag-key'>EVENT WINDOW</span> {event_window_flag} {info_icon('YES = hay evento cerca (o proxy alto) en ventana relevante; la ejecución suele distorsionarse.')}</div>"
        f"<div class='flag-pill'><span class='flag-key'>LIQUIDITY</span> {session_phase} {info_icon('Fase de liquidez: Asia/London/NY. Off-hours = menos liquidez, spreads peores.')}</div>"
        f"</div>"
    )

    # =========================
    # NY DIRECTION CARD — NO TOCA VEREDICTO
    # =========================
    ny_dir, ny_conf, ny_playbook, ny_reasons = compute_ny_direction(
        instrument=st.session_state.instrument,
        session_phase=session_phase,
        drivers=drivers,
        event_level=event_level,
        within_window=within_window,
        fakeout_risk=fakeout_risk,
        data_quality=data_quality
    )

    ny_color = "#56d1a8" if ny_dir == "LONG" else "#f23645" if ny_dir == "SHORT" else "#ff9800" if ny_dir == "NEUTRAL" else "#b9bcc7"
    reasons_txt = " | ".join(ny_reasons) if ny_reasons else "—"

    md(f"""
<div class="card-exec" style="margin-top:12px;">
  <p class="muted2">
    NY DIRECTION (09:30–11:30 NY) {info_icon('Sesgo rápido solo para NY AM. NO reemplaza el filtro. Si hay distorsión/evento/VIX sucio, fuerza NEUTRAL.')}
  </p>
  <div style="display:flex; align-items:flex-end; justify-content:space-between; gap:12px;">
    <div>
      <h3 style="margin:8px 0; font-size:28px; color:{ny_color};">{ny_dir}</h3>
      <p class="muted" style="margin:0;">Confidence: <b>{ny_conf}</b>/100</p>
    </div>
    <div style="text-align:right;">
      <span class="b-label" style="border-color:{ny_color}; color:{ny_color};">Bias: {ny_dir}</span>
    </div>
  </div>
  <p class="muted" style="margin-top:10px;"><b>Why:</b> {reasons_txt}</p>
  <p class="muted" style="margin-top:8px;"><b>Playbook:</b> {ny_playbook}</p>
</div>
""")

    if beginner:
        render_beginner_action_box(
            verdict_label=verdict_label,
            event_level=event_level,
            within_window=within_window,
            first_impulse_risk=first_impulse_risk,
            data_quality=data_quality,
            session_phase=session_phase,
            exec_score=int(exec_score),
            instrument=st.session_state.instrument
        )

    # Drivers grid
    c1, c2, c3, c4 = st.columns(4)

    with c1:
        md(f"""
<div class="card-exec">
  <p class="muted2">{label_with_help('DXY STATE', 'DXY mide fuerza del dólar. Estado por ATR ratio: Compression=vol bajo (más trampas), Expansion=vol alto, Balanced=normal.')}</p>
  <h3 style="margin:8px 0; font-size:22px;">{drivers["DXY"]:.2f}</h3>
  <span class="b-label">{drivers["DXY_STATE"]}</span>
  <p class="muted" style="margin-top:10px;">
    Impulse 60m: {drivers["DXY_IMPULSE_60M"]:+.2f}% {info_icon('Cambio porcentual aprox en 60m (1 vela 1H). Driver micro, no señal final.')}
  </p>
</div>
""")

    with c2:
        md(f"""
<div class="card-exec">
  <p class="muted2">{label_with_help('US10Y STATE', 'US10Y (^TNX) es proxy de yields nominales. Rising presiona risk assets y suele pesar sobre oro; Reversing alivia; Stable neutral.')}</p>
  <h3 style="margin:8px 0; font-size:22px;">{drivers["US10Y"]:.2f}%</h3>
  <span class="b-label">{drivers["US10Y_STATE"]}</span>
  <p class="muted" style="margin-top:10px;">
    Impulse 60m: {drivers["US10Y_IMPULSE_60M"]:+.2f}% {info_icon('Movimientos rápidos suelen aumentar volatilidad y distorsión.')}
  </p>
</div>
""")

    with c3:
        md(f"""
<div class="card-exec">
  <p class="muted2">{label_with_help('VIX CONTEXT', 'VIX mide estrés/vol. Clean = mejor ejecución. Caution/Dirty = más whipsaws/fakeouts.')}</p>
  <h3 style="margin:8px 0; font-size:22px;">{drivers["VIX"]:.2f}</h3>
  <span class="b-label">{drivers["VIX_STATE"]}</span>
  <p class="muted" style="margin-top:10px;">
    Trend 60m: {drivers["VIX_IMPULSE_60M"]:+.2f}% {info_icon('Subidas rápidas del VIX suelen ensuciar ejecución.')}
  </p>
</div>
""")

    with c4:
        level_color = "#f23645" if event_level == "HIGH" else "#ff9800" if event_level == "MODERATE" else "#56d1a8"
        md(f"""
<div class="card-exec">
  <p class="muted2">{label_with_help('EVENT RISK (USD)', 'Distorsión por eventos USD: en ventana crítica se evita primer impulso. CALENDAR usa eventos reales; PROXY estima por condiciones.')}</p>
  <h3 style="margin:8px 0; font-size:22px; color:{level_color};">{event_level}</h3>
  <p class="muted" style="margin-top:8px;">Next event: {next_window} {info_icon('Hora NY del siguiente evento (si hay calendario). En proxy puede ser “—”.')}</p>
  <p class="muted" style="margin-top:8px;">Next in: {next_in} {info_icon('Minutos aprox hasta el siguiente evento. En proxy es heurística.')}</p>
  <p class="muted" style="margin-top:8px;">Within window: {"YES" if within_window else "NO"} {info_icon('YES = estás dentro de ventana donde la ejecución suele distorsionarse.')}</p>
  <p class="muted" style="margin-top:8px;">Mode: {event_mode} {info_icon('CALENDAR = evento real. PROXY = estimación.')}</p>
  <p class="muted" style="margin-top:8px;">{event_drivers_text}</p>
</div>
""")

    if event_mode == "CALENDAR" and near_events is not None and not near_events.empty:
        with st.expander("Eventos cercanos (NY)", expanded=False):
            md(f"<p>{info_icon('Lista de eventos más cercanos por distancia temporal (minutos).')}</p>")
            show = near_events.copy()
            show["time_ny"] = show["dt_ny"].dt.strftime("%H:%M")
            show["in"] = show["mins_to"].apply(lambda m: f"{int(m)}m")
            show = show[["time_ny", "impact", "title", "in"]]
            st.dataframe(show, use_container_width=True, height=180)

    md("<div class='divider'></div>")

    md(f"<h3>Narrative Engine (MVP) {info_icon('Motor placeholder: luego reemplázalo por data real (news/flow).')}</h3>")
    n1, n2, n3 = st.columns(3)
    n1.metric("Pressure", pressure)
    n2.metric("Frequency", frequency)
    n3.metric("Tone", tone)

    md(f"<p class='muted2'>LIVE FEED {info_icon('Feed simulado: idealmente aquí van headlines/flow con clasificador de presión.')}</p>")
    md("<div class='feed-box'>" + "".join([f"<div class='feed-item'>• {x}</div>" for x in feed[:12]]) + "</div>")

    # =========================
    # AUDITORÍA: snapshot automático + manual
    # =========================
    _init_audit_state()
    if "force_snapshot" not in st.session_state:
        st.session_state.force_snapshot = False

    minute_key = now.strftime("%Y-%m-%d %H:%M")
    last_minute = st.session_state.get("last_audit_minute", None)
    should_auto = (last_minute != minute_key)

    if should_auto or st.session_state.force_snapshot:
        audit_append_snapshot(
            now_ny=now,
            session_phase=session_phase,
            verdict_label=verdict_label,
            fakeout_risk=fakeout_risk,
            event_level=event_level,
            next_window=next_window,
            instrument=st.session_state.instrument,
            exec_score=int(exec_score),
            clarity=clarity,
            whipsaw=whipsaw,
            breakout=breakout,
            data_quality=data_quality,
            drivers=drivers,
        )
        st.session_state.last_audit_minute = minute_key
        st.session_state.force_snapshot = False

    render_audit_panel()

    # Instrument modules
    if st.session_state.instrument == "XAUUSD":
        render_gold_tactical(drivers, inst, pressure, event_level, within_window)
    else:
        render_eurusd_tactical(drivers, inst, pressure, event_level, within_window)

# =============================================================================
# 14) XAUUSD MODULE
# =============================================================================
def render_gold_tactical(drivers, inst, narrative_pressure: str, event_level: str, within_window: bool):
    st.markdown("---")
    md(f"<h2>XAUUSD — Execution Module {info_icon('Módulo para oro: alineación con DXY, proxy yields y timing de volatilidad. NO da dirección.')}</h2>")
    st.caption("No direction. Execution guidance only.")

    xau_atr = float(inst["XAU_ATR_RATIO"])
    xau_vol_state = _vol_state_from_atr_ratio(xau_atr)

    xau_imp = float(inst["XAU_IMPULSE_60M"])
    low_signal = abs(xau_imp) < 0.05

    if event_level == "HIGH" or drivers["VIX_STATE"] == "Dirty" or within_window:
        action = "Esperar: solo ejecutar tras confirmación y preferir retest."
        avoid = "No ejecutar el primer break; no perseguir velas grandes."
    else:
        if xau_vol_state == "Compression":
            action = "Breakout permitido SOLO con retest (setups A+)."
            avoid = "No chase del primer impulso; cuidado con fakeouts en compresión."
        elif xau_vol_state == "Expansion":
            action = "Ejecutar pullback/retest; evitar entradas tardías."
            avoid = "No perseguir rupturas extendidas (riesgo de reversión)."
        else:
            action = "Ejecutar A+ setups con confirmación (ideal retest)."
            avoid = "Evitar entradas impulsivas sin estructura."

    if low_signal:
        action += " (Low signal: impulso 60m muy pequeño)"
        avoid += " (Impulso débil: sube el ruido relativo)"

    md(f"""
<div class="exec-suggest">
  <h4>
    EXECUTION SUGGESTION {info_icon('Sugerencia de ejecución (no dirección): una línea de acción y una línea de “qué evitar” para operar tipo desk.')}
  </h4>
  <p class="line"><span class="ok">✅ Acción:</span> {action} {info_icon('Cómo ejecutar: retest/confirmación/pullback según entorno.')}</p>
  <p class="line" style="margin-top:8px;"><span class="no">🚫 Evitar:</span> {avoid} {info_icon('No-go: chase/primer break/velas extendidas en días sucios.')}</p>
</div>
""")

    c1, c2, c3 = st.columns(3)

    dxy_imp = drivers["DXY_IMPULSE_60M"]

    if (dxy_imp > 0 and xau_imp < 0) or (dxy_imp < 0 and xau_imp > 0):
        align = "ALIGNED"
        align_note = "Inverse link stable"
        align_color = "#56d1a8"
    elif (dxy_imp > 0 and xau_imp > 0) or (dxy_imp < 0 and xau_imp < 0):
        align = "DIVERGENT"
        align_note = "Inverse link unstable (fakeouts)"
        align_color = "#ff9800"
    else:
        align = "NEUTRAL"
        align_note = "No clear impulse relationship"
        align_color = "#b9bcc7"

    c1.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("GOLD ALIGNMENT", "ALIGNED cuando oro se mueve inverso al DXY (más normal). DIVERGENT cuando se mueve igual (más fakeouts).")}</p>
              <h3 style="margin:8px 0; font-size:22px;">{align}</h3>
              <p style="font-size:13px; color:{align_color}; margin:0;">{align_note}</p>
              <p class="muted" style="margin-top:10px;">Gold 60m: {xau_imp:+.2f}% | DXY 60m: {dxy_imp:+.2f}%</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    if drivers["US10Y_STATE"] == "Rising":
        y_proxy = "PRESSURE"
        y_note = "Yields rising"
        y_color = "#f23645"
    elif drivers["US10Y_STATE"] == "Reversing":
        y_proxy = "RELIEF"
        y_note = "Yields falling"
        y_color = "#56d1a8"
    else:
        y_proxy = "NEUTRAL"
        y_note = "Yields stable"
        y_color = "#b9bcc7"

    c2.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("REAL YIELD PROXY", "Proxy simple: usamos dirección/estado de US10Y como aproximación. Rising suele presionar oro; Reversing suele aliviar.")}</p>
              <h3 style="margin:8px 0; font-size:22px;">{y_proxy}</h3>
              <p style="font-size:13px; color:{y_color}; margin:0;">{y_note}</p>
              <p class="muted" style="margin-top:10px;">US10Y 60m: {drivers["US10Y_IMPULSE_60M"]:+.2f}%</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    c3.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("VOLATILITY TIMING", "ATR ratio: Compression (<0.85) = poca vol (más trampas); Expansion (>1.15) = vol alta (slippage); Balanced = normal.")}</p>
              <h3 style="margin:8px 0; font-size:22px;">{xau_atr:.2f}</h3>
              <p class="muted" style="margin-top:8px;">State: {xau_vol_state}</p>
              <p class="muted" style="margin-top:8px;">Ticker: {inst["XAU_TKR"]}</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    if event_level == "HIGH" or drivers["VIX_STATE"] == "Dirty":
        play = "High distortion — avoid first impulse, wait retest/confirmation"
    else:
        if xau_vol_state == "Compression":
            play = "Compression — breakout ok but only with retest"
        elif xau_vol_state == "Expansion":
            play = "Expansion — avoid chasing, wait pullback"
        else:
            play = "Balanced — execute A+ setups with confirmation"

    md(f"<div class='playbook-line'>Playbook: {play} {info_icon('Playbook: instrucción breve por distorsión (eventos/VIX) y estado de vol.')}</div>")

# =============================================================================
# 15) EURUSD MODULE
# =============================================================================
def render_eurusd_tactical(drivers, inst, narrative_pressure: str, event_level: str, within_window: bool):
    st.markdown("---")
    md(f"<h2>EURUSD — Execution Module {info_icon('Módulo EURUSD: presión del dólar, vol del euro, distorsión por eventos/VIX. NO da dirección.')}</h2>")
    st.caption("No direction. Execution guidance only.")

    eur_atr = float(inst["EUR_ATR_RATIO"])
    eur_vol_state = _vol_state_from_atr_ratio(eur_atr)
    eur_imp = float(inst["EUR_IMPULSE_60M"])
    low_signal = abs(eur_imp) < 0.05

    distortion = compute_distortion_overlay(event_level, narrative_pressure, drivers["VIX_STATE"])

    if distortion == "HIGH" or within_window:
        action = "Esperar confirmación; ejecutar solo tras retest/estructura."
        avoid = "No chase; evitar entradas cerca de evento/ventana."
    else:
        if eur_vol_state == "Compression":
            action = "Preferir rango/mean-reversion salvo ruptura confirmada con retest."
            avoid = "No ejecutar rupturas sin retest (alto fakeout en compresión)."
        elif eur_vol_state == "Expansion":
            action = "Trend ok: ejecutar pullbacks/retests, no entradas tardías."
            avoid = "No perseguir impulsos extendidos (riesgo de whipsaw)."
        else:
            action = "A+ setups únicamente; confirmación + retest preferido."
            avoid = "Evitar decisiones por una sola vela."

    if low_signal:
        action += " (Low signal: impulso 60m muy pequeño)"
        avoid += " (Impulso débil: más ruido relativo)"

    md(f"""
<div class="exec-suggest">
  <h4>EXECUTION SUGGESTION {info_icon('Sugerencia de ejecución (no dirección): acción + evitar para operar tipo desk.')}</h4>
  <p class="line"><span class="ok">✅ Acción:</span> {action}</p>
  <p class="line" style="margin-top:8px;"><span class="no">🚫 Evitar:</span> {avoid}</p>
</div>
""")

    c1, c2, c3 = st.columns(3)

    dp_state, dp_note = dollar_pressure_index(drivers)
    dp_color = "#56d1a8" if dp_state == "ACTIVE" else "#ff9800" if dp_state == "NEUTRAL" else "#b9bcc7"

    c1.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("DOLLAR PRESSURE", "Presión del dólar sobre EUR: ACTIVE=presión presente; NEUTRAL=plano; SOFT=debilidad USD.")}</p>
              <h3 style="margin:8px 0; font-size:22px;">{dp_state}</h3>
              <p style="font-size:13px; color:{dp_color}; margin:0;">{dp_note}</p>
              <p class="muted" style="margin-top:10px;">DXY: {drivers["DXY_STATE"]} | 60m: {drivers["DXY_IMPULSE_60M"]:+.2f}%</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    c2.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("EUR VOLATILITY", "ATR ratio: Compression=rango/trampas; Expansion=tendencia con slippage; Balanced=normal.")}</p>
              <h3 style="margin:8px 0; font-size:22px;">{eur_atr:.2f}</h3>
              <p class="muted" style="margin-top:8px;">State: {eur_vol_state}</p>
              <p class="muted" style="margin-top:8px;">EUR 60m: {eur_imp:+.2f}%</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    dist_color = "#f23645" if distortion == "HIGH" else "#ff9800" if distortion == "MODERATE" else "#56d1a8"

    c3.markdown(
        dedent(
            f"""
            <div class="card-exec">
              <p class="muted2">{label_with_help("EVENT DISTORTION", "Overlay: Event Risk + presión narrativa + VIX. HIGH = evitar primer impulso. MODERATE = cautela. LOW = más limpio.")}</p>
              <h3 style="margin:8px 0; font-size:22px; color:{dist_color};">{distortion}</h3>
              <p class="muted" style="margin-top:8px;">Events: {event_level} | VIX: {drivers["VIX_STATE"]}</p>
            </div>
            """
        ),
        unsafe_allow_html=True
    )

    if distortion == "HIGH":
        play = "High distortion — avoid first impulse, wait confirmation"
    else:
        if eur_vol_state == "Compression":
            play = "Compression — range/mean-reversion unless DXY breaks"
        elif eur_vol_state == "Expansion":
            play = "Expansion — trend ok, wait retest"
        else:
            play = "Balanced — A+ setups only, no chasing"

    md(f"<div class='playbook-line'>Playbook: {play} {info_icon('Playbook por distorsión y estado de volatilidad del EURUSD.')}</div>")

# =============================================================================
# RUNNER
# =============================================================================
def main():
    inject_abraxa_design()
    render_sidebar()
    render_intraday_dashboard()

if __name__ == "__main__":
    main()