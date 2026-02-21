import os
import io
import csv
import json
import random
import textwrap
import requests
import re
import time
from datetime import datetime, date
from typing import Optional, Tuple, List, Dict

import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go

from streamlit_autorefresh import st_autorefresh
from groq import Groq

# =========================
# 0) CONFIG / UI BASE
# =========================
from auth import check_password
from ui_components import inject_abraxa_design, render_sidebar, render_intraday_dashboard
from abraxa_tab import render_abraxa_hawkish_tab


# =========================
# LLM / TEXT SANITIZATION (NO HTML)
# =========================
_TAG_RE = re.compile(r"<[^>]+>")

def clean_llm_text(x) -> str:
    """
    Limpia cualquier salida del LLM para que:
    - Nunca aparezcan tags HTML (<div>, <style>, etc.)
    - Nunca aparezcan '<' o '>'
    - Nunca aparezcan ``` fences
    """
    s = "" if x is None else str(x)
    s = _TAG_RE.sub("", s)          # quita tags HTML
    s = s.replace("<", "").replace(">", "")
    s = s.replace("```", "")
    s = " ".join(s.split())
    return s.strip()


# =========================
# JSON SAFE PARSING (LLM OUTPUT)  ✅ (INTEGRADO SIN CAMBIAR LO FUNCIONAL)
# =========================
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)

def _extract_json_object(text: str) -> str:
    if not text:
        return ""
    m = _JSON_OBJ_RE.search(text)
    return m.group(0).strip() if m else text.strip()

def _repair_common_json_issues(s: str) -> str:
    if not s:
        return s

    # Quita fences si el modelo se las “olvida”
    s = s.replace("```json", "").replace("```", "").strip()

    # Reemplaza comillas tipográficas
    s = s.replace("“", '"').replace("”", '"').replace("’", "'")

    # Elimina trailing commas antes de } o ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    # Limpia caracteres de control
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)

    return s.strip()

def parse_llm_json(txt: str) -> dict:
    raw = _extract_json_object(txt)
    try:
        return json.loads(raw)
    except Exception:
        fixed = _repair_common_json_issues(raw)
        return json.loads(fixed)


st.set_page_config(
    page_title="ABRAXA MARKET INTELLIGENCE",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_abraxa_design()

# =========================
# CSS TOTAL BLACK (mantenido + upgrades)
# =========================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
    .stApp { background-color: #000000; }

    .ticker-wrap {
        background: #000000;
        border-bottom: 1px solid #1a1c22;
        padding: 12px 0;
        overflow: hidden;
        min-height: 48px;
    }
    .ticker-move {
        display: flex;
        animation: ticker 50s linear infinite;
        white-space: nowrap;
        align-items: center;
    }
    @keyframes ticker { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
    .ticker-item {
        display: flex;
        align-items: center;
        padding: 0 40px;
        border-right: 1px solid #1a1c22;
        gap: 10px;
        font-family: 'Inter', sans-serif;
        font-size: 13px;
    }
    .ticker-val { color: #ffffff; font-weight: 500; font-family: 'JetBrains Mono'; }

    .card-container {
        background: #0a0a0a;
        border: 1px solid #1a1c22;
        border-radius: 2px;
        padding: 22px;
        transition: all 0.2s ease;
        height: 100%;
        min-height: 170px;
    }
    .card-pair {
        font-size: 22px;
        font-weight: 600;
        color: #d1d4dc !important;
        text-transform: uppercase;
        margin: 0;
        letter-spacing: 0.5px;
    }
    .card-bias {
        font-size: 20px;
        font-weight: 500;
        margin: 8px 0;
        font-family: 'Inter', sans-serif;
    }

    .audit-toolbar {
        background:#0a0a0a;
        border: 1px solid #1a1c22;
        padding: 14px 16px;
        border-radius: 6px;
        margin: 8px 0 14px 0;
    }
    .muted { color:#787b86; font-size: 12px; }

    /* =======================
       DETAILS: MINI CARDS + PILLARS
       ======================= */
    .mini-cards{
        display:grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap:10px;
        margin-bottom:16px;
    }
    .mini-card{
        background:#0a0a0a;
        border:1px solid #1a1c22;
        border-radius:6px;
        padding:14px 14px;
        min-height:78px;
    }
    .mini-label{
        color:#787b86;
        font-size:10px;
        font-weight:800;
        letter-spacing:1.5px;
        text-transform:uppercase;
        margin-bottom:8px;
    }
    .mini-val{
        color:#ffffff;
        font-size:18px;
        font-weight:700;
        font-family:'JetBrains Mono';
    }
    .mini-sub{
        color:#787b86;
        font-size:11px;
        margin-top:6px;
        font-family:'Inter';
    }

    .pillars-wrap{
        background:#0a0a0a;
        border: 1px solid #1a1c22;
        padding: 18px 18px;
        border-radius: 6px;
        margin-bottom: 16px;
    }
    .pillars-title{
        color:#787b86;
        font-size:12px;
        font-weight:700;
        text-transform:uppercase;
        letter-spacing:2px;
        margin-bottom:12px;
    }
    .pillar-row{
        display:flex;
        justify-content:space-between;
        align-items:flex-start;
        gap:16px;
        padding:10px 0;
        border-bottom:1px solid #14161b;
    }
    .pillar-row:last-child{
        border-bottom:none;
    }
    .pillar-name{
        color:#d1d4dc;
        font-size:13px;
        font-weight:600;
    }
    .pillar-val{
        color:#787b86;
        font-size:12px;
        font-family:'JetBrains Mono';
        margin-top:4px;
        opacity:0.95;
        max-width: 760px;
        word-break: break-word;
    }

    /* =======================
       AI INTERPRETATION (NEW)
       ======================= */
    .ai-wrap{background:#0a0a0a;border:1px solid #1a1c22;border-radius:10px;padding:18px;margin:14px 0}
    .ai-top{display:flex;justify-content:space-between;align-items:flex-start;gap:14px}
    .ai-title{color:#fff;font-size:22px;font-weight:700}
    .ai-subtitle{color:#787b86;font-size:12px;line-height:1.55;margin-top:6px}
    .ai-chip{display:inline-block;padding:6px 10px;border-radius:999px;border:1px solid #1a1c22;color:#d1d4dc;font-size:11px;font-family:'JetBrains Mono';background:#070707}
    .ai-sec{color:#787b86;font-size:11px;font-weight:800;letter-spacing:1.6px;text-transform:uppercase;margin:6px 0 10px}
    .ai-col{background:#070707;border:1px solid #14161b;border-radius:10px;padding:14px;margin-bottom:10px}
    .ai-bullet{color:#fff;font-size:14px;font-weight:600;line-height:1.35}
    .ai-why{color:#787b86;font-size:12px;line-height:1.55;margin-top:6px}
    .ai-metrics{margin-top:8px;display:flex;flex-wrap:wrap;gap:8px}
    .ai-metric{border:1px solid #1a1c22;background:#0a0a0a;border-radius:8px;padding:6px 8px;font-size:11px;color:#d1d4dc;font-family:'JetBrains Mono'}
    .ai-tldr{margin-top:12px;padding-top:12px;border-top:1px solid #14161b;color:#d1d4dc;font-size:13px;line-height:1.6}
</style>
""", unsafe_allow_html=True)

# =========================
# 1) LOGIN
# =========================
if not check_password():
    st.stop()

# =========================
# 2) ROLES
# =========================
def is_admin() -> bool:
    return st.session_state.get("current_operator", "") == "sefonmar"

# =========================
# 3) GROQ
# =========================
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

def _groq_enabled() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip())

@st.cache_data(ttl=90, show_spinner=False)
def llama_interpret_bias(payload: dict, model: str = "llama-3.3-70b-versatile") -> dict:
    """
    Devuelve JSON con explicación CLARA + CONTEXTO:
      headline, drivers, risks, invalidation, tl_dr

    drivers/risks/invalidation ahora se devuelven como:
      [{"bullet": "...", "why": "...", "metrics": ["...", "..."]}, ...]
    """
    if not _groq_enabled():
        return {
            "headline": "AI Interpretation disabled (missing GROQ_API_KEY).",
            "drivers": [],
            "risks": [],
            "invalidation": [],
            "tl_dr": ""
        }

    system = (
        "Eres un estratega macro FX institucional (tono hedge fund / banco). "
        "Explicas decisiones de forma humana y didáctica, sin jerga técnica innecesaria. "
        "PROHIBIDO usar HTML o Markdown. Solo texto plano. "
        "Responde SOLO JSON válido."
    )

    user = f"""
Recibes un JSON con:
- pair, bias, conviction
- prob_context, delta_context, z_context (pueden ser null)
- macro_pillars: por pilar viene diff y detail (con números base vs quote).

Reglas DURAS:
- Prohibido incluir '<', '>', 'div', 'style', 'http', Markdown, o fences.
- No menciones "z-score", "modelo" ni "pilares". Habla como humano.
- Usa español simple + institucional.

Objetivo:
1) headline: 1 frase que explique el trade.
2) drivers: 3-5 items. Cada item como objeto:
   - bullet: idea corta (<= 16 palabras)
   - why: 1-2 frases explicando de dónde sale (ej: tasas, PMI, PIB, desempleo)
   - metrics: 1-3 strings con números o comparaciones (ej: "Tasas: 5.25% vs 0.10% (diff +5.15pp)")
3) risks: 2-4 items (mismo formato).
4) invalidation: 2-4 items (mismo formato). "Qué tendría que pasar para que el bias deje de tener sentido".
5) tl_dr: 1-2 líneas máximas.

TIP: Si hay diff grande en tasas o growth, explícame la causa: "Fed restrictiva vs BoJ acomodaticia", etc.
Si faltan datos, dilo sin inventar.

PAYLOAD:
{json.dumps(payload, ensure_ascii=False)}
"""

    def _call(prompt_user: str) -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.15,
            max_tokens=700,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt_user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    try:
        txt = _call(user)

        # 1) Parse robusto (extrae + repara comas/comillas)
        try:
            return parse_llm_json(txt)
        except Exception:
            # 2) Self-heal: pide al modelo arreglar SU salida a JSON válido
            fixer = f"""
Convierte esto en JSON VÁLIDO. Devuelve SOLO JSON. No agregues texto.
TEXTO:
{txt}
"""
            txt2 = _call(fixer)
            try:
                return parse_llm_json(txt2)
            except Exception as e2:
                return {
                    "headline": "AI Interpretation failed.",
                    "drivers": [],
                    "risks": [{"bullet": "Error al generar interpretación", "why": str(e2), "metrics": []}],
                    "invalidation": [],
                    "tl_dr": ""
                }

    except Exception as e:
        return {
            "headline": "AI Interpretation failed.",
            "drivers": [],
            "risks": [{"bullet": "Error al generar interpretación", "why": str(e), "metrics": []}],
            "invalidation": [],
            "tl_dr": ""
        }


# =========================
# 4) SESSION STATE
# =========================
if "page" not in st.session_state:
    st.session_state.page = "main"
if "selected_pair" not in st.session_state:
    st.session_state.selected_pair = None
if "ai_chat" not in st.session_state:
    st.session_state.ai_chat = ""

# Auditoría
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "LIVE"  # LIVE | SNAPSHOT
if "snapshot_id" not in st.session_state:
    st.session_state.snapshot_id = None
if "snapshot_df" not in st.session_state:
    st.session_state.snapshot_df = None

# UI Auditoría
if "audit_full" not in st.session_state:
    st.session_state.audit_full = False

# Prefills (no se pierden en rerun)
if "audit_name_prefill" not in st.session_state:
    st.session_state.audit_name_prefill = ""
if "audit_start_prefill" not in st.session_state:
    st.session_state.audit_start_prefill = ""
if "audit_end_prefill" not in st.session_state:
    st.session_state.audit_end_prefill = ""


# =========================
# 5) DATA LIVE (SHEET)
# =========================
URL_BASE = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRVMmdokdfLMYwT7fb7_LiEUqAZGco1-GOUYuvO_Vgiy0HusQtD2Hrjcy_a0SG9PUBamPfJHhSPGAaJ/pub?gid=1564576053&single=true&output=csv"

def _to_numeric_prob(x):
    try:
        return float(str(x).replace("%", "").replace(",", ".").strip())
    except:
        return 0.0

def get_data_no_cache():
    try:
        r = random.randint(1, 1000000)
        df = pd.read_csv(f"{URL_BASE}&refresh_id={r}")
        df.columns = [str(c).strip() for c in df.columns]
        if "Pair" not in df.columns:
            return pd.DataFrame()

        df = df.dropna(subset=["Pair"])
        df["Pair"] = df["Pair"].astype(str).str.strip().str.upper()

        if "Prob_Final" in df.columns:
            df["Prob_Num"] = df["Prob_Final"].apply(_to_numeric_prob)
        else:
            df["Prob_Final"] = ""
            df["Prob_Num"] = 0.0

        return df
    except:
        return pd.DataFrame()


# =========================
# 5.0) FIX YFINANCE: chart data estable + fallback
# =========================
def _safe_yf_download(symbol: str, period="1y", interval="1d") -> pd.DataFrame:
    """
    Descarga robusta:
    - intenta history() y luego download()
    - retry suave
    - normaliza columnas e índice
    """
    sym = (symbol or "").strip()
    if not sym:
        return pd.DataFrame()

    # 1) try: Ticker().history
    for attempt in range(2):
        try:
            t = yf.Ticker(sym)
            df = t.history(period=period, interval=interval, auto_adjust=False, actions=False)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except:
            pass
        time.sleep(0.4)

    # 2) fallback: yf.download
    for attempt in range(2):
        try:
            df = yf.download(sym, period=period, interval=interval, progress=False, auto_adjust=False, threads=False)
            if isinstance(df, pd.DataFrame) and not df.empty:
                return df
        except:
            pass
        time.sleep(0.4)

    return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_price_history_cached(pair_name: str) -> pd.DataFrame:
    """
    Cache 1h para que la gráfica:
    - no dependa de refresh cada 30s
    - salga "fija" (estable)
    """
    p = (pair_name or "").strip().upper()
    if len(p) < 6:
        return pd.DataFrame()
    sym = f"{p}=X"
    df = _safe_yf_download(sym, period="1y", interval="1d")

    # normaliza
    if df is None or df.empty:
        return pd.DataFrame()

    # algunos retornan columnas multiindex; lo forzamos a OHLC estándar si aplica
    cols = [c.lower() for c in df.columns.astype(str)]
    needed = ["open", "high", "low", "close"]
    if not all(any(n in c for c in cols) for n in needed):
        # a veces viene "Open" etc (ok). si no, devolvemos vacío.
        pass

    # índice datetime limpio
    try:
        df = df.copy()
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, errors="coerce")
        df = df[~df.index.isna()]
        # quitar tz para plotly (a veces molesta)
        if getattr(df.index, "tz", None) is not None:
            df.index = df.index.tz_convert(None)
        df = df.sort_index()
    except:
        return pd.DataFrame()

    return df

def get_ticker_prices(pairs_list):
    """
    Precios del ticker superior (1d/1m). Mantengo tu idea, pero lo hago
    más resiliente: cache corto + fallback a last close.
    """
    prices = {}
    for p in pairs_list:
        pp = (p or "").strip().upper()
        if not pp:
            continue
        sym = f"{pp}=X"
        try:
            d = yf.download(sym, period="1d", interval="1m", progress=False, auto_adjust=False, threads=False)
            if d is not None and not d.empty and "Close" in d.columns:
                prices[pp] = float(d["Close"].iloc[-1])
            else:
                h = _safe_yf_download(sym, period="5d", interval="1d")
                prices[pp] = float(h["Close"].iloc[-1]) if (h is not None and not h.empty and "Close" in h.columns) else 0.0
        except:
            prices[pp] = 0.0
    return prices


# =========================
# 5.1) MACRO DATA (PILLARS)
# =========================
DEFAULT_MACRODATA_URL = (
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vRVMmdokdfLMYwT7fb7_LiEUqAZGco1-GOUYuvO_Vgiy0HusQtD2Hrjcy_a0SG9PUBamPfJHhSPGAaJ/pub"
    "?gid=87716466&single=true&output=csv"
)

def get_macrodata_url() -> str:
    return (
        os.getenv("ABRAXA_MACRODATA_URL", "").strip()
        or os.getenv("ABRAXA_INPUT_URL", "").strip()
        or DEFAULT_MACRODATA_URL
    )

def _append_refresh(url: str) -> str:
    if not url:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}refresh_id={random.randint(1, 1000000)}"

def _gsheet_to_csv_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if "output=csv" in u or "tqx=out:csv" in u:
        return u
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", u)
    if not m:
        return u
    sheet_id = m.group(1)
    gid = "0"
    m_gid = re.search(r"[?#&]gid=(\d+)", u)
    if m_gid:
        gid = m_gid.group(1)
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&gid={gid}"

def _download_text(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,text/plain,*/*"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

def _sniff_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
        return dialect.delimiter
    except Exception:
        lines = [ln for ln in sample.splitlines() if ln.strip()]
        if not lines:
            return ","
        ln = lines[0]
        return ";" if ln.count(";") > ln.count(",") else ","

def _find_header_row(lines: List[str]) -> int:
    for i, ln in enumerate(lines[:25]):
        if "divisa" in ln.lower():
            return i
    return 0

@st.cache_data(ttl=30, show_spinner=False)
def fetch_macrodata_df(url: str) -> pd.DataFrame:
    u = (url or "").strip()
    if not u:
        return pd.DataFrame()

    csv_url = _append_refresh(_gsheet_to_csv_url(u))

    try:
        text = _download_text(csv_url)
        lines = text.splitlines()
        header_row = _find_header_row(lines)
        sample = "\n".join(lines[header_row:header_row + 10])
        sep = _sniff_delimiter(sample)

        df = pd.read_csv(
            io.StringIO(text),
            sep=sep,
            header=header_row,
            engine="python",
            decimal=",",
            thousands=None,
        )

        df.columns = [str(c).strip() for c in df.columns]
        df = df.loc[:, ~df.columns.str.contains("^Unnamed", case=False, regex=True)]
        return df

    except Exception as e:
        if st.session_state.get("current_operator", "") == "sefonmar":
            st.warning("MACRO DATA no cargó.")
            st.warning(f"URL original: {u}")
            st.warning(f"URL usada: {csv_url}")
            st.warning(f"Error: {e}")
        return pd.DataFrame()

def fetch_input_semanal_df() -> pd.DataFrame:
    return fetch_macrodata_df(get_macrodata_url())

def _safe_float(x, default=None):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace("%", "").replace(" ", "")
        if s.count(",") > 0 and s.count(".") == 0:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
        if s == "":
            return default
        return float(s)
    except:
        return default

def _strip_accents_lower(s: str) -> str:
    s = str(s or "").strip().lower()
    return (
        s.replace("á", "a").replace("é", "e").replace("í", "i")
         .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    )

def _col_lookup(df: pd.DataFrame, targets: List[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    norm = {_strip_accents_lower(c).replace(" ", "").replace("-", "_"): c for c in df.columns}
    for t in targets:
        key = _strip_accents_lower(t).replace(" ", "").replace("-", "_")
        if key in norm:
            return norm[key]
    return None

def _parse_pair(pair_name: str) -> Tuple[Optional[str], Optional[str]]:
    p = str(pair_name or "").strip().upper()
    if len(p) < 6:
        return None, None
    return p[:3], p[3:6]

def _sticky_score(sticky: str) -> float:
    s = _strip_accents_lower(sticky)
    if "stick" in s:
        return 1.0
    if "cedi" in s or "cool" in s or "baj" in s or "fall" in s:
        return -1.0
    if "neut" in s or "esta" in s:
        return 0.0
    return 0.0

def _score_0_5_abs(diff: float, bands: List[float]) -> int:
    if diff is None:
        return 0
    a = abs(float(diff))
    n = 0
    for b in bands:
        if a >= b:
            n += 1
    return max(0, min(5, n))

def _dots_html(score_0_5: int, accent="#ffffff", off="#2a2d35"):
    score_0_5 = max(0, min(5, int(score_0_5)))
    dots = []
    for i in range(5):
        color = accent if i < score_0_5 else off
        dots.append(
            f"<span style='display:inline-block;width:10px;height:10px;border-radius:99px;background:{color};margin-right:6px;'></span>"
        )
    return "".join(dots)

def build_currency_macro_table(df_input: pd.DataFrame) -> pd.DataFrame:
    if df_input is None or df_input.empty:
        return pd.DataFrame()

    col_ccy = _col_lookup(df_input, ["Divisa", "Currency", "CCY"])
    if not col_ccy:
        return pd.DataFrame()

    df = df_input.copy()
    df[col_ccy] = df[col_ccy].astype(str).str.strip().str.upper()
    df = df.dropna(subset=[col_ccy])

    c_rate_prev = _col_lookup(df, ["Tipos de Interes Anteriores", "Rate_prev"])
    c_rate_now  = _col_lookup(df, ["Tipos de Interes Actuales", "Rate_now", "Rate"])

    c_inf_prev  = _col_lookup(df, ["Inflacion Anterior", "CPI_prev"])
    c_inf_now   = _col_lookup(df, ["Inflacion Actual", "CPI_now", "CPI"])
    c_sticky    = _col_lookup(df, ["Sticky Inflation Actual", "Sticky", "Sticky Inflation"])

    c_pmi_prev  = _col_lookup(df, ["PMI Anterior", "PMI_prev"])
    c_pmi_now   = _col_lookup(df, ["PMI Actual", "PMI", "PMI_actual"])

    c_gdp       = _col_lookup(df, ["PIB QoQ Actual", "GDP", "GDP_actual", "GDP_QoQ"])

    c_u_prev    = _col_lookup(df, ["Tasa desempleo Anterior", "Unemployment_prev"])
    c_u_now     = _col_lookup(df, ["Tasa desempleo Actual", "Unemployment_now"])

    c_tone      = _col_lookup(df, ["Forward guidance", "Tono", "Guidance", "Policy tone"])

    rows = []
    for _, r in df.iterrows():
        ccy = str(r.get(col_ccy, "")).strip().upper()
        if not ccy:
            continue

        rate_now  = _safe_float(r.get(c_rate_now)) if c_rate_now else None
        rate_prev = _safe_float(r.get(c_rate_prev)) if c_rate_prev else None

        inf_now   = _safe_float(r.get(c_inf_now)) if c_inf_now else None
        inf_prev  = _safe_float(r.get(c_inf_prev)) if c_inf_prev else None
        sticky    = _sticky_score(r.get(c_sticky)) if c_sticky else 0.0

        pmi_now   = _safe_float(r.get(c_pmi_now)) if c_pmi_now else None
        pmi_prev  = _safe_float(r.get(c_pmi_prev)) if c_pmi_prev else None
        gdp       = _safe_float(r.get(c_gdp)) if c_gdp else None

        u_now     = _safe_float(r.get(c_u_now)) if c_u_now else None
        u_prev    = _safe_float(r.get(c_u_prev)) if c_u_prev else None

        rate_level = rate_now
        rate_delta = (rate_now - rate_prev) if (rate_now is not None and rate_prev is not None) else 0.0

        infl_level = inf_now
        infl_delta = (inf_now - inf_prev) if (inf_now is not None and inf_prev is not None) else 0.0
        infl_pressure = (infl_level or 0.0) + (sticky * 0.5) + (infl_delta * 0.5)

        pmi_mom = (pmi_now - pmi_prev) if (pmi_now is not None and pmi_prev is not None) else 0.0
        growth_mom = ((pmi_now - 50.0) if pmi_now is not None else 0.0) + ((gdp or 0.0) * 2.0) + (pmi_mom * 1.5)

        labor_mom = (u_prev - u_now) if (u_now is not None and u_prev is not None) else 0.0

        tone = 0.0
        if c_tone:
            t = _strip_accents_lower(r.get(c_tone))
            if "hawk" in t or "restrict" in t or "duro" in t or "agres" in t:
                tone = 1.0
            elif "dov" in t or "accommod" in t or "suave" in t or "flex" in t:
                tone = -1.0

        policy_bias = (tone * 1.0) + (rate_delta * 0.8) + ((rate_level or 0.0) * 0.05)
        macro_delta = (infl_delta * 1.0) + (pmi_mom * 1.0) + (labor_mom * 0.5)

        rows.append({
            "CCY": ccy,
            "RATE_LEVEL": rate_level,
            "INFL_PRESSURE": infl_pressure,
            "GROWTH_MOM": growth_mom,
            "POLICY_BIAS": policy_bias,
            "MACRO_DELTA": macro_delta,
        })

    return pd.DataFrame(rows).drop_duplicates(subset=["CCY"], keep="last")

def build_pair_pillars(pair_name: str, ccy_tbl: pd.DataFrame) -> Dict[str, Dict]:
    base, quote = _parse_pair(pair_name)
    if not base or not quote or ccy_tbl is None or ccy_tbl.empty:
        return {}

    b = ccy_tbl[ccy_tbl["CCY"] == base]
    q = ccy_tbl[ccy_tbl["CCY"] == quote]
    if b.empty or q.empty:
        return {}

    b = b.iloc[0]
    q = q.iloc[0]

    def _diff(a, b_):
        try:
            return float(a) - float(b_)
        except:
            return None

    rate_diff = _diff(b.get("RATE_LEVEL"), q.get("RATE_LEVEL"))
    infl_diff = _diff(b.get("INFL_PRESSURE"), q.get("INFL_PRESSURE"))
    grow_diff = _diff(b.get("GROWTH_MOM"), q.get("GROWTH_MOM"))
    pol_diff  = _diff(b.get("POLICY_BIAS"), q.get("POLICY_BIAS"))
    delt_diff = _diff(b.get("MACRO_DELTA"), q.get("MACRO_DELTA"))

    return {
        "Yield Divergence": {
            "value": rate_diff,
            "score": _score_0_5_abs(rate_diff, [0.10, 0.50, 1.00, 1.75, 2.50]),
            "detail": f"{base} {b.get('RATE_LEVEL','—')} vs {quote} {q.get('RATE_LEVEL','—')} | diff {rate_diff:+.2f}" if rate_diff is not None else "NO DATA"
        },
        "Inflation Relative Strength": {
            "value": infl_diff,
            "score": _score_0_5_abs(infl_diff, [0.10, 0.25, 0.50, 0.90, 1.40]),
            "detail": f"{base} {b.get('INFL_PRESSURE',0):.2f} vs {quote} {q.get('INFL_PRESSURE',0):.2f} | diff {infl_diff:+.2f}" if infl_diff is not None else "NO DATA"
        },
        "Growth Momentum": {
            "value": grow_diff,
            "score": _score_0_5_abs(grow_diff, [0.20, 0.60, 1.20, 2.00, 3.00]),
            "detail": f"{base} {b.get('GROWTH_MOM',0):.2f} vs {quote} {q.get('GROWTH_MOM',0):.2f} | diff {grow_diff:+.2f}" if grow_diff is not None else "NO DATA"
        },
        "Policy Bias": {
            "value": pol_diff,
            "score": _score_0_5_abs(pol_diff, [0.10, 0.30, 0.60, 1.00, 1.50]),
            "detail": f"{base} {b.get('POLICY_BIAS',0):.2f} vs {quote} {q.get('POLICY_BIAS',0):.2f} | diff {pol_diff:+.2f}" if pol_diff is not None else "NO DATA"
        },
        "Macro Delta": {
            "value": delt_diff,
            "score": _score_0_5_abs(delt_diff, [0.05, 0.15, 0.30, 0.60, 1.00]),
            "detail": f"{base} {b.get('MACRO_DELTA',0):.2f} vs {quote} {q.get('MACRO_DELTA',0):.2f} | diff {delt_diff:+.2f}" if delt_diff is not None else "NO DATA"
        },
    }


# =========================
# 6) SNAPSHOTS (AUDITORÍA)
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAP_DIR = os.path.join(BASE_DIR, "backtests", "abraxa_ny_bias", "outputs", "snapshots")
INDEX_PATH = os.path.join(SNAP_DIR, "index.json")
REQUIRED_COLS = ["Pair", "Bias", "Prob_Final"]

def _ensure_snap_dir():
    os.makedirs(SNAP_DIR, exist_ok=True)
    if not os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "w", encoding="utf-8") as f:
            json.dump({"snapshots": []}, f, ensure_ascii=False, indent=2)

def _load_index() -> Dict:
    _ensure_snap_dir()
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "snapshots" not in data or not isinstance(data["snapshots"], list):
            return {"snapshots": []}
        return data
    except:
        return {"snapshots": []}

def _save_index(idx: Dict):
    _ensure_snap_dir()
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def _normalize_date_key(s: str) -> str:
    return str(s or "").strip().replace("/", "-")

def _safe_filename(name: str) -> str:
    name = str(name or "").strip()
    name = name.replace("\\", "-").replace("/", "-")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. ")
    cleaned = "".join(ch for ch in name if ch in allowed).strip()
    cleaned = " ".join(cleaned.split()).replace(" ", "-")
    if not cleaned:
        cleaned = "snapshot.csv"
    if not cleaned.lower().endswith(".csv"):
        cleaned += ".csv"
    return cleaned

def _next_available_filename(base_name: str) -> str:
    name, ext = os.path.splitext(base_name)
    cand = base_name
    n = 2
    while os.path.exists(os.path.join(SNAP_DIR, cand)):
        cand = f"{name}_v{n}{ext}"
        n += 1
    return cand

def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    col_map = {}
    for c in df.columns:
        cc = c.strip().lower()
        if cc == "pair":
            col_map[c] = "Pair"
        elif cc == "bias":
            col_map[c] = "Bias"
        elif cc in ["prob_final", "prob final", "prob", "probfinal"]:
            col_map[c] = "Prob_Final"
    if col_map:
        df = df.rename(columns=col_map)

    for rc in REQUIRED_COLS:
        if rc not in df.columns:
            df[rc] = ""

    df["Pair"] = df["Pair"].astype(str).str.strip().str.upper()
    df["Prob_Num"] = df["Prob_Final"].apply(_to_numeric_prob) if "Prob_Final" in df.columns else 0.0
    return df

_MONTHS_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12
}

def _extract_week_from_filename(fname: str) -> Optional[Tuple[str, str]]:
    if not fname:
        return None
    s = fname.lower().replace("_", " ").replace(".", " ")
    s = " ".join(s.split())

    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2}).{0,10}(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y1, mo1, d1, y2, mo2, d2 = map(int, m.groups())
        try:
            a = date(y1, mo1, d1).isoformat()
            b = date(y2, mo2, d2).isoformat()
            return (a, b)
        except:
            pass

    m2 = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\s+([a-záéíóúñ]+)\s+(20\d{2})\b", s)
    if m2:
        d1 = int(m2.group(1))
        d2 = int(m2.group(2))
        mon = m2.group(3)
        y = int(m2.group(4))
        mon = mon.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        if mon in _MONTHS_ES:
            mo = _MONTHS_ES[mon]
            try:
                a = date(y, mo, d1).isoformat()
                b = date(y, mo, d2).isoformat()
                return (a, b)
            except:
                pass

    mon_map3 = {
        "jan": 1, "ene": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4, "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8, "ago": 8,
        "sep": 9, "set": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12, "dic": 12
    }
    m3 = re.search(r"\b(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*([a-z]{3})\s*-\s*(20\d{2})\b", s)
    if m3:
        d1 = int(m3.group(1))
        d2 = int(m3.group(2))
        mon3 = m3.group(3)
        y = int(m3.group(4))
        if mon3 in mon_map3:
            mo = mon_map3[mon3]
            try:
                a = date(y, mo, d1).isoformat()
                b = date(y, mo, d2).isoformat()
                return (a, b)
            except:
                pass

    return None

def save_snapshot_from_df(df: pd.DataFrame, start_date: str, end_date: str, source: str, custom_name: Optional[str] = None) -> str:
    _ensure_snap_dir()
    df = _normalize_df(df)

    start_key = _normalize_date_key(start_date)
    end_key = _normalize_date_key(end_date)

    default_base = f"{start_key}__{end_key}__{source}.csv"
    base_filename = _safe_filename(custom_name) if (custom_name and str(custom_name).strip()) else _safe_filename(default_base)
    snapshot_id = _next_available_filename(base_filename)

    fpath = os.path.join(SNAP_DIR, snapshot_id)
    df.to_csv(fpath, index=False, encoding="utf-8")

    idx = _load_index()
    created_utc = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    idx["snapshots"] = [x for x in idx.get("snapshots", []) if x.get("id") != snapshot_id]
    idx["snapshots"].append({
        "id": snapshot_id,
        "start": start_key,
        "end": end_key,
        "source": source,
        "created_utc": created_utc
    })
    idx["snapshots"] = sorted(idx["snapshots"], key=lambda x: x.get("created_utc", ""), reverse=True)
    _save_index(idx)
    return snapshot_id

def list_snapshots() -> List[Dict]:
    idx = _load_index()
    snaps = idx.get("snapshots", [])
    out = []
    for s in snaps:
        sid = s.get("id")
        if not sid:
            continue
        fpath = os.path.join(SNAP_DIR, sid)
        if os.path.exists(fpath):
            try:
                sz = os.path.getsize(fpath)
            except:
                sz = None
            out.append({**s, "size_bytes": sz})
    out = sorted(out, key=lambda x: (x.get("created_utc", ""), x.get("id", "")), reverse=True)
    return out

def load_snapshot_df(snapshot_id: str) -> pd.DataFrame:
    fpath = os.path.join(SNAP_DIR, snapshot_id)
    if not os.path.exists(fpath):
        return pd.DataFrame()
    try:
        df = pd.read_csv(fpath)
        return _normalize_df(df)
    except:
        try:
            df = pd.read_csv(fpath, sep=None, engine="python")
            return _normalize_df(df)
        except:
            return pd.DataFrame()

def delete_snapshot(snapshot_id: str) -> bool:
    try:
        fpath = os.path.join(SNAP_DIR, snapshot_id)
        if os.path.exists(fpath):
            os.remove(fpath)
        idx = _load_index()
        idx["snapshots"] = [x for x in idx.get("snapshots", []) if x.get("id") != snapshot_id]
        _save_index(idx)
        return True
    except:
        return False

def rename_snapshot(snapshot_id: str, new_name: str) -> Tuple[bool, str]:
    try:
        _ensure_snap_dir()
        new_base = _safe_filename(new_name)
        new_id = _next_available_filename(new_base)

        old_path = os.path.join(SNAP_DIR, snapshot_id)
        new_path = os.path.join(SNAP_DIR, new_id)
        if not os.path.exists(old_path):
            return (False, "Archivo original no existe.")

        os.rename(old_path, new_path)

        idx = _load_index()
        updated = False
        for s in idx.get("snapshots", []):
            if s.get("id") == snapshot_id:
                s["id"] = new_id
                updated = True
                break
        if not updated:
            idx.setdefault("snapshots", []).append({
                "id": new_id,
                "start": "",
                "end": "",
                "source": "csv",
                "created_utc": datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            })

        _save_index(idx)

        if st.session_state.get("snapshot_id") == snapshot_id:
            st.session_state.snapshot_id = new_id
        return (True, new_id)
    except Exception as e:
        return (False, str(e))

def update_snapshot_metadata(snapshot_id: str, start: str, end: str, source: Optional[str] = None) -> bool:
    try:
        idx = _load_index()
        ok = False
        for s in idx.get("snapshots", []):
            if s.get("id") == snapshot_id:
                s["start"] = _normalize_date_key(start)
                s["end"] = _normalize_date_key(end)
                if source is not None:
                    s["source"] = source
                ok = True
                break
        if ok:
            _save_index(idx)
        return ok
    except:
        return False

def _read_bytes(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def _snapshot_label(s: Dict) -> str:
    stt = s.get("start", "")
    end = s.get("end", "")
    sid = s.get("id", "")
    src = s.get("source", "")
    core = f"{stt} → {end}".strip()
    if core == "→":
        core = "(sin fechas)"
    return f"{core}   [{src}]   —   {sid}"

# =========================
# 6.9) AI CACHE (PRECOMPUTE / ONE-TIME)
# =========================
AI_CACHE_DIR = os.path.join(SNAP_DIR, "ai_cache")
MODEL_VERSION = "v1"  # súbelo a v2/v3 cuando cambies prompt o lógica

def _ensure_ai_cache_dir():
    os.makedirs(AI_CACHE_DIR, exist_ok=True)

def _safe_key(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", s)
    return s[:180] if len(s) > 180 else s

def _payload_fingerprint(payload: dict) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    except Exception:
        raw = str(payload)
    import hashlib
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()

def _ai_cache_path(pair: str, cache_key: str) -> str:
    _ensure_ai_cache_dir()
    pdir = os.path.join(AI_CACHE_DIR, _safe_key(pair))
    os.makedirs(pdir, exist_ok=True)
    return os.path.join(pdir, f"{_safe_key(cache_key)}.json")

def load_ai_cache(pair: str, cache_key: str) -> Optional[dict]:
    try:
        path = _ai_cache_path(pair, cache_key)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_ai_cache(pair: str, cache_key: str, data: dict):
    try:
        path = _ai_cache_path(pair, cache_key)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def build_ai_cache_key(pair: str, view_mode: str, snapshot_id: Optional[str], payload: dict) -> str:
    fp = _payload_fingerprint(payload)
    sid = snapshot_id or "LIVE"
    return f"{MODEL_VERSION}__{view_mode}__{sid}__{pair}__{fp}"

def get_or_build_ai_interpretation(pair: str, view_mode: str, snapshot_id: Optional[str], payload: dict) -> dict:
    ck = build_ai_cache_key(pair, view_mode, snapshot_id, payload)
    cached = load_ai_cache(pair, ck)
    if cached is not None:
        cached["_cache"] = {"hit": True, "key": ck}
        return cached

    llm = llama_interpret_bias(payload)
    llm["_cache"] = {"hit": False, "key": ck, "saved_utc": datetime.utcnow().isoformat()}
    save_ai_cache(pair, ck, llm)
    return llm

def clear_pair_ai_cache(pair: str):
    try:
        pdir = os.path.join(AI_CACHE_DIR, _safe_key(pair))
        if os.path.isdir(pdir):
            for fn in os.listdir(pdir):
                try:
                    os.remove(os.path.join(pdir, fn))
                except Exception:
                    pass
    except Exception:
        pass

# =========================
# 7) DETALLES POR PAR
# =========================
def _get_explanation_text(row: pd.Series) -> str:
    candidates = [
        "Explanation", "Explicacion", "Explicación", "Narrative",
        "Comentario", "Contexto", "Reason"
    ]
    for c in candidates:
        if c in row.index:
            txt = row.get(c)
            if txt is not None and str(txt).strip():
                return str(txt)

    try:
        if len(row.index) > 6:
            txt = row.iloc[6]
            if txt is not None and str(txt).strip():
                return str(txt)
    except:
        pass

    return "Contexto macro bajo procesamiento..."


def _as_items_list(x):
    """
    Normaliza drivers/risks/invalidation:
    - si viene lista de dicts: ok
    - si viene lista de strings: lo convierte
    """
    out = []
    for it in (x or []):
        if isinstance(it, dict):
            out.append({
                "bullet": clean_llm_text(it.get("bullet", "")),
                "why": clean_llm_text(it.get("why", "")),
                "metrics": [clean_llm_text(m) for m in (it.get("metrics", []) or [])][:3],
            })
        else:
            out.append({"bullet": clean_llm_text(it), "why": "", "metrics": []})
    return out


def render_pair_details(pair_name, df_full):
    row = df_full[df_full["Pair"] == pair_name].iloc[0]

    if st.button("← VOLVER AL MONITOR G8"):
        st.session_state.page = "main"
        st.rerun()

    st.markdown(f"## {pair_name} // INSTITUTIONAL DEEP ANALYSIS")

        # 1) Chart (LINE by default + cached)
    try:
        hist = get_price_history_cached(pair_name)

        if hist is None or hist.empty:
            st.warning("No pude cargar la gráfica (YFinance). Probablemente rate-limit o símbolo sin data.")
        else:
            if "Close" not in hist.columns and "close" in hist.columns:
                hist["Close"] = hist["close"]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=hist.index,
                y=hist["Close"],
                mode="lines",
                name="Close"
            ))

            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="black",
                plot_bgcolor="black",
                height=520,
                margin=dict(l=0, r=0, t=10, b=0),
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#14161b"),
                showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)

            c_ref1, c_ref2 = st.columns([1.2, 4])
            with c_ref1:
                if st.button("↻ Refresh chart", use_container_width=True):
                    get_price_history_cached.clear()
                    st.rerun()
            with c_ref2:
                st.caption("Gráfica LINE (Close) cacheada 1h para que sea estable (no se rompe con autorefresh).")

    except Exception as e:
        st.error(f"Error cargando gráfica de {pair_name}: {e}")

    st.markdown("---")

    # 2) Base (NO CAMBIAMOS NADA DEL SHEET G8)
    bias_txt = str(row.get("Bias", "")).upper()
    clr_main = "#f23645" if "SHORT" in bias_txt else "#089981"
    prob_final = str(row.get("Prob_Final", "—"))

    prob_contexto = _safe_float(row.get("Prob_Contexto")) if "Prob_Contexto" in row.index else None
    delta_contexto = _safe_float(row.get("Delta_Contexto")) if "Delta_Contexto" in row.index else None
    z_contexto = _safe_float(row.get("Z_Contexto")) if "Z_Contexto" in row.index else None

    pc = "—" if prob_contexto is None else f"{prob_contexto:.3f}"
    dc = "—" if delta_contexto is None else f"{delta_contexto:.3f}"
    zc = "—" if z_contexto is None else f"{z_contexto:.3f}"

    # 3) Mini Cards
    mini_html = f"""
<div class="mini-cards">
  <div class="mini-card">
    <div class="mini-label">Directional Bias</div>
    <div class="mini-val" style="color:{clr_main};">{bias_txt}</div>
    <div class="mini-sub">From Sheet</div>
  </div>
  <div class="mini-card">
    <div class="mini-label">Conviction</div>
    <div class="mini-val">{prob_final}</div>
    <div class="mini-sub">From Sheet</div>
  </div>
  <div class="mini-card">
    <div class="mini-label">Prob Context</div>
    <div class="mini-val">{pc}</div>
    <div class="mini-sub">Sheet (optional)</div>
  </div>
  <div class="mini-card">
    <div class="mini-label">Delta Context</div>
    <div class="mini-val">{dc}</div>
    <div class="mini-sub">Sheet (optional)</div>
  </div>
  <div class="mini-card">
    <div class="mini-label">Z Context</div>
    <div class="mini-val">{zc}</div>
    <div class="mini-sub">Sheet (optional)</div>
  </div>
</div>
"""
    st.markdown(textwrap.dedent(mini_html).strip(), unsafe_allow_html=True)

    # 4) Macro Pillars
    df_input = fetch_input_semanal_df()
    ccy_tbl = build_currency_macro_table(df_input) if not df_input.empty else pd.DataFrame()
    pillars = build_pair_pillars(pair_name, ccy_tbl) if not ccy_tbl.empty else {}

    pillar_rows_html = []
    if pillars:
        order = [
            "Yield Divergence",
            "Inflation Relative Strength",
            "Growth Momentum",
            "Policy Bias",
            "Macro Delta"
        ]
        for pname in order:
            p = pillars.get(pname, {})
            score = int(p.get("score", 0) or 0)
            detail = str(p.get("detail", "NO DATA"))
            dots = _dots_html(score, accent="#ffffff", off="#2a2d35")
            pillar_rows_html.append(
                f"""
<div class="pillar-row">
  <div>
    <div class="pillar-name">{pname}</div>
    <div class="pillar-val">{detail}</div>
  </div>
  <div style="margin-top:2px;">{dots}</div>
</div>
""".strip()
            )
    else:
        pillar_rows_html.append(
            f"""
<div class="pillar-row">
  <div>
    <div class="pillar-name">Macro Pillars</div>
    <div class="pillar-val">NO DATA — No pude leer MACRO DATA (CSV)</div>
  </div>
  <div style="margin-top:2px;">{_dots_html(0, accent="#ffffff", off="#2a2d35")}</div>
</div>
""".strip()
        )

    cot_status = "PENDING"
    cot_color = "#787b86"

    pillars_html = f"""
<div class="pillars-wrap">
  <div class="pillars-title">Macro Pillars (Why this bias)</div>
  {''.join(pillar_rows_html)}
  <div style="margin-top:14px; padding-top:14px; border-top:1px solid #14161b; display:flex; justify-content:space-between; align-items:center;">
    <div style="color:#787b86; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:2px;">Institutional Validator (COT)</div>
    <div style="color:{cot_color}; font-family:JetBrains Mono; font-size:12px;">{cot_status}</div>
  </div>
</div>
"""
    st.markdown(textwrap.dedent(pillars_html).strip(), unsafe_allow_html=True)

    # 4.5) AI Interpretation (NEW - explicativa)
    try:
        payload = {
            "pair": pair_name,
            "bias": bias_txt,
            "conviction": prob_final,
            "prob_context": prob_contexto,
            "delta_context": delta_contexto,
            "z_context": z_contexto,
            "macro_pillars": {
                k: {
                    "diff": v.get("value"),
                    "score_0_5": v.get("score"),
                    "detail": v.get("detail"),
                }
                for k, v in (pillars or {}).items()
            }
        }

        with st.spinner("Interpretando drivers macro..."):
            llm = get_or_build_ai_interpretation(
                pair=pair_name,
                view_mode=st.session_state.get("view_mode", "LIVE"),
                snapshot_id=st.session_state.get("snapshot_id", None),
                payload=payload
            )

        headline = clean_llm_text(llm.get("headline", ""))
        tldr = clean_llm_text(llm.get("tl_dr", ""))

        drivers = _as_items_list(llm.get("drivers", []))[:5]
        risks = _as_items_list(llm.get("risks", []))[:4]
        invalidation = _as_items_list(llm.get("invalidation", []))[:4]

        chip = f"{pair_name} | {bias_txt} | {prob_final}"

        st.markdown(
            f"""
<div class="ai-wrap">
  <div class="ai-top">
    <div>
      <div class="ai-title">AI Interpretation</div>
      <div class="ai-subtitle">{headline}</div>
    </div>
    <div class="ai-chip">{chip}</div>
  </div>
</div>
            """.strip(),
            unsafe_allow_html=True
        )

        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("<div class='ai-sec'>Drivers</div>", unsafe_allow_html=True)
            for d in drivers:
                metrics_html = ""
                if d["metrics"]:
                    metrics_html = (
                        "<div class='ai-metrics'>"
                        + "".join([f"<span class='ai-metric'>{m}</span>" for m in d["metrics"]])
                        + "</div>"
                    )
                why_html = f"<div class='ai-why'>{d['why']}</div>" if d["why"] else ""
                st.markdown(
                    f"""
<div class="ai-col">
  <div class="ai-bullet">• {d['bullet']}</div>
  {why_html}
  {metrics_html}
</div>
                    """.strip(),
                    unsafe_allow_html=True
                )

        with col2:
            if risks:
                st.markdown("<div class='ai-sec'>Key Risks</div>", unsafe_allow_html=True)
                for r in risks:
                    metrics_html = ""
                    if r["metrics"]:
                        metrics_html = (
                            "<div class='ai-metrics'>"
                            + "".join([f"<span class='ai-metric'>{m}</span>" for m in r["metrics"]])
                            + "</div>"
                        )
                    why_html = f"<div class='ai-why'>{r['why']}</div>" if r["why"] else ""
                    st.markdown(
                        f"""
<div class="ai-col">
  <div class="ai-bullet">• {r['bullet']}</div>
  {why_html}
  {metrics_html}
</div>
                        """.strip(),
                        unsafe_allow_html=True
                    )

            if invalidation:
                st.markdown("<div class='ai-sec' style='margin-top:10px;'>Invalidation</div>", unsafe_allow_html=True)
                for i in invalidation:
                    metrics_html = ""
                    if i["metrics"]:
                        metrics_html = (
                            "<div class='ai-metrics'>"
                            + "".join([f"<span class='ai-metric'>{m}</span>" for m in i["metrics"]])
                            + "</div>"
                        )
                    why_html = f"<div class='ai-why'>{i['why']}</div>" if i["why"] else ""
                    st.markdown(
                        f"""
<div class="ai-col">
  <div class="ai-bullet">• {i['bullet']}</div>
  {why_html}
  {metrics_html}
</div>
                        """.strip(),
                        unsafe_allow_html=True
                    )

        if tldr:
            st.markdown(
                f"<div class='ai-tldr'><b>TL;DR:</b> {tldr}</div>",
                unsafe_allow_html=True
            )

        with st.expander("Cómo se calcula (transparencia)", expanded=False):
            st.write("Yield Divergence: diferencia de RATE_LEVEL (tasa actual) entre base y quote.")
            st.write("Growth Momentum: PMI vs 50 + PIB QoQ ponderado + momentum del PMI.")
            st.write("Policy Bias: tono (hawk/dove) + cambios de tasa + nivel de tasa suavizado.")
            st.write("Inflation Relative Strength: CPI + sticky + cambio CPI (ponderado).")
            st.write("Macro Delta: cambios recientes (inflación, PMI, desempleo) como impulso de corto plazo.")

    except Exception as e:
        st.warning(f"No pude generar AI Interpretation: {e}")

    # 5) Mantener tu explicación (SÍ O SÍ)
    st.markdown("---")
    clr_report = "#f23645" if "SHORT" in bias_txt else "#089981"
    explicacion_ia = _get_explanation_text(row)

    report_html = f"""
<div style="background:#0a0a0a; border: 1px solid #1a1c22; padding: 40px; border-radius: 6px; border-left: 6px solid {clr_report};">
  <p style="color:#787b86; font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:2px; margin-bottom:20px;">Abraxa Strategic Intelligence Report</p>
  <div style="color:#ffffff; font-size:16px; line-height:1.8; font-family:'Inter'; white-space: pre-wrap;">{explicacion_ia}</div>
  <div style="margin-top:40px; padding-top:25px; border-top:1px solid #1a1c22; display: flex; justify-content: space-between; align-items: baseline;">
    <div>
      <p style="color:#787b86; font-size:10px; font-weight:700; text-transform:uppercase;">Signal</p>
      <h3 style="color:{clr_report}; margin:0; font-family:'Inter';">{pair_name}</h3>
    </div>
    <div style="text-align: right;">
      <p style="color:#787b86; font-size:10px; font-weight:700; text-transform:uppercase;">Confidence Score</p>
      <h2 style="color:#ffffff; margin:0; font-family:'JetBrains Mono'; font-size:36px;">{row.get("Prob_Final","")}</h2>
    </div>
  </div>
</div>
"""
    st.markdown(textwrap.dedent(report_html).strip(), unsafe_allow_html=True)


# =========================
# 8) SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### ABRAXA AI")
    user_input = st.text_area("Analyze macro flow...", height=120)
    if st.button("Analizar") and user_input:
        df_live = get_data_no_cache()
        contexto = df_live[["Pair", "Bias", "Prob_Final"]].to_string(index=False) if not df_live.empty else ""
        prompt = f"Eres Horus, analista institucional. Datos:\n{contexto}\nPregunta: {user_input}"
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        st.session_state.ai_chat = completion.choices[0].message.content

    if st.session_state.ai_chat:
        st.markdown(
            f'<div style="background:#0a0a0a; padding:15px; border:1px solid #1a1c22; font-size:12px; color:#ccc;">{st.session_state.ai_chat}</div>',
            unsafe_allow_html=True
        )
    st.markdown("---")
    render_sidebar()


# =========================
# 9) AUDITORÍA PANEL + LISTADO COMPLETO
# =========================
def render_auditoria_panel(df_live: pd.DataFrame):
    _ensure_snap_dir()
    snaps = list_snapshots()

    st.markdown("### AUDITORÍA")
    st.caption("Selecciona una semana guardada y la app carga esa versión auditada.")

    options_labels = ["SEMANA ACTUAL (LIVE)"]
    options_ids = [None]
    for s in snaps:
        options_labels.append(_snapshot_label(s))
        options_ids.append(s["id"])

    default_idx = 0
    if st.session_state.view_mode == "SNAPSHOT" and st.session_state.snapshot_id in options_ids:
        default_idx = options_ids.index(st.session_state.snapshot_id)

    sel_label = st.selectbox("Ver semana:", options_labels, index=default_idx, key="audit_week_select")
    sel_id = options_ids[options_labels.index(sel_label)]

    colA, colB, colC = st.columns([2, 2, 1])
    with colA:
        if st.button("Cargar semana", use_container_width=True):
            if sel_id is None:
                st.session_state.view_mode = "LIVE"
                st.session_state.snapshot_id = None
                st.session_state.snapshot_df = None
            else:
                df_snap = load_snapshot_df(sel_id)
                if df_snap.empty:
                    st.error("No pude cargar ese snapshot (archivo vacío/corrupto).")
                else:
                    st.session_state.view_mode = "SNAPSHOT"
                    st.session_state.snapshot_id = sel_id
                    st.session_state.snapshot_df = df_snap
            st.rerun()

    with colB:
        if st.button("Volver a LIVE", use_container_width=True):
            st.session_state.view_mode = "LIVE"
            st.session_state.snapshot_id = None
            st.session_state.snapshot_df = None
            st.rerun()

    with colC:
        if st.button("Auditoría completa", use_container_width=True):
            st.session_state.audit_full = not st.session_state.audit_full
            st.rerun()

    st.markdown("<div class='audit-toolbar'>", unsafe_allow_html=True)
    if st.session_state.view_mode == "SNAPSHOT" and st.session_state.snapshot_id:
        meta = None
        for s in snaps:
            if s.get("id") == st.session_state.snapshot_id:
                meta = s
                break
        if meta:
            st.markdown(
                f"<div class='muted'>VIEW MODE: SNAPSHOT</div>"
                f"<div style='color:#d1d4dc;font-family:JetBrains Mono;font-size:12px;'>"
                f"{meta.get('start','')} → {meta.get('end','')}  [{meta.get('source','')}]<br>"
                f"{meta.get('id','')}"
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"<div class='muted'>VIEW MODE: SNAPSHOT</div>"
                f"<div style='color:#d1d4dc;font-family:JetBrains Mono;font-size:12px;'>{st.session_state.snapshot_id}</div>",
                unsafe_allow_html=True
            )
    else:
        st.markdown("<div class='muted'>VIEW MODE: LIVE</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # ADMIN ONLY
    if is_admin():
        st.markdown("---")
        st.markdown("## ADMIN (solo sefonmar)")
        st.caption("Backfill / correcciones para auditoría.")

        default_start = st.session_state.audit_start_prefill or "2026-02-16"
        default_end = st.session_state.audit_end_prefill or "2026-02-20"

        c1, c2 = st.columns(2)
        with c1:
            start_date = st.text_input("Inicio (YYYY-MM-DD)", value=default_start, key="snap_start")
        with c2:
            end_date = st.text_input("Fin (YYYY-MM-DD)", value=default_end, key="snap_end")

        snapshot_name = st.text_input(
            "Guardar snapshot como (opcional)",
            value=st.session_state.audit_name_prefill,
            placeholder="Ej: 9-13-Feb-2026_TRADES.csv",
            key="snap_custom_name"
        )

        if st.button("Guardar semana (Sheet actual)", use_container_width=True):
            try:
                sid = save_snapshot_from_df(df_live, start_date, end_date, source="sheet", custom_name=snapshot_name)
                st.success(f"✅ Guardado: {sid}")
                st.session_state.view_mode = "SNAPSHOT"
                st.session_state.snapshot_id = sid
                st.session_state.snapshot_df = load_snapshot_df(sid)
                st.rerun()
            except Exception as e:
                st.error(f"No pude guardar snapshot del Sheet: {e}")

        st.markdown("### Backfill CSV (solo admin)")
        st.caption("Sube CSV export directo de tu tabla.")

        up = st.file_uploader(" ", type=["csv"], accept_multiple_files=False, key="csv_uploader_backfill")

        if up is not None:
            st.markdown(f"<div class='muted'>Archivo subido: <b>{up.name}</b></div>", unsafe_allow_html=True)

            if not st.session_state.get("snap_custom_name", "").strip():
                st.session_state.audit_name_prefill = up.name

            guess = _extract_week_from_filename(up.name)
            if guess:
                g_start, g_end = guess
                if not st.session_state.get("snap_start", "").strip() or st.session_state.get("snap_start") == default_start:
                    st.session_state.audit_start_prefill = g_start
                if not st.session_state.get("snap_end", "").strip() or st.session_state.get("snap_end") == default_end:
                    st.session_state.audit_end_prefill = g_end

                st.info(f"Detecté fechas en el nombre: {g_start} → {g_end}. (Puedes cambiarlas si quieres.)")

        if st.button("Guardar snapshot desde CSV", use_container_width=True):
            if up is None:
                st.error("Sube un CSV primero.")
            else:
                try:
                    try:
                        df_csv = pd.read_csv(up)
                    except:
                        up.seek(0)
                        df_csv = pd.read_csv(up, sep=None, engine="python")

                    df_csv = _normalize_df(df_csv)
                    if df_csv.empty or df_csv["Pair"].dropna().shape[0] == 0:
                        st.error("CSV leído pero parece vacío o sin columna Pair válida.")
                    else:
                        final_name = snapshot_name.strip() if snapshot_name and snapshot_name.strip() else up.name
                        sid = save_snapshot_from_df(
                            df_csv,
                            start_date,
                            end_date,
                            source="csv",
                            custom_name=final_name
                        )
                        st.success(f"✅ Backfill guardado: {sid}")
                        st.session_state.view_mode = "SNAPSHOT"
                        st.session_state.snapshot_id = sid
                        st.session_state.snapshot_df = load_snapshot_df(sid)
                        st.rerun()
                except Exception as e:
                    st.error(f"No pude guardar snapshot desde CSV: {e}")

        st.markdown("---")
        st.markdown("### Renombrar snapshot (ya guardado)")
        snaps_now = list_snapshots()
        if snaps_now:
            pick_rename = st.selectbox(
                "Selecciona snapshot a renombrar:",
                options=[s["id"] for s in snaps_now],
                key="rename_pick"
            )

            new_name = st.text_input(
                "Nuevo nombre (termina en .csv opcional):",
                value=pick_rename,
                key="rename_newname"
            )

            rr1, rr2 = st.columns(2)
            with rr1:
                if st.button("Renombrar archivo", use_container_width=True):
                    ok, msg = rename_snapshot(pick_rename, new_name)
                    if ok:
                        st.success(f"✅ Renombrado a: {msg}")
                        if st.session_state.view_mode == "SNAPSHOT" and st.session_state.snapshot_id == msg:
                            st.session_state.snapshot_df = load_snapshot_df(msg)
                        st.rerun()
                    else:
                        st.error(f"No pude renombrar: {msg}")

            with rr2:
                st.caption("Tip: si el nombre ya existe, se crea automáticamente _v2, _v3...")

            st.markdown("#### (Opcional) Corregir fechas del snapshot en el índice")
            m = None
            for s in snaps_now:
                if s["id"] == pick_rename:
                    m = s
                    break
            m_start = (m.get("start") if m else "") or ""
            m_end = (m.get("end") if m else "") or ""
            mm1, mm2 = st.columns(2)
            with mm1:
                meta_start = st.text_input("Start (index)", value=m_start, key="meta_start")
            with mm2:
                meta_end = st.text_input("End (index)", value=m_end, key="meta_end")
            if st.button("Guardar metadata (start/end)", use_container_width=True):
                ok = update_snapshot_metadata(pick_rename, meta_start, meta_end)
                if ok:
                    st.success("✅ Metadata actualizada.")
                    st.rerun()
                else:
                    st.error("No pude actualizar metadata.")
        else:
            st.info("Aún no hay snapshots guardados.")

        st.markdown("---")
        st.markdown("### Borrar snapshot (si subiste mal)")
        snaps_now = list_snapshots()
        if snaps_now:
            del_opts = [s["id"] for s in snaps_now]
            del_choice = st.selectbox("Selecciona snapshot a borrar:", del_opts, key="del_choice")

            confirm = st.checkbox("Confirmo que quiero borrarlo", key="del_confirm")
            if st.button("🗑️ Borrar snapshot", use_container_width=True, disabled=not confirm):
                ok = delete_snapshot(del_choice)
                if ok:
                    if st.session_state.snapshot_id == del_choice:
                        st.session_state.view_mode = "LIVE"
                        st.session_state.snapshot_id = None
                        st.session_state.snapshot_df = None
                    st.success("✅ Snapshot borrado.")
                    st.rerun()
                else:
                    st.error("No pude borrar el snapshot.")
        else:
            st.info("Aún no hay snapshots guardados.")
    else:
        st.markdown("<div class='muted'>Modo auditoría (solo lectura). Backfill y borrado: solo admin.</div>", unsafe_allow_html=True)

    # AUDITORÍA COMPLETA (LISTADO PARA TODOS)
    if st.session_state.audit_full:
        st.markdown("---")
        st.markdown("## AUDITORÍA COMPLETA")
        st.caption("Listado de todos los snapshots guardados. Puedes buscarlos, ver metadata y descargarlos.")

        snaps_all = list_snapshots()
        if not snaps_all:
            st.info("No hay snapshots guardados todavía.")
            return

        q = st.text_input("Buscar (por fecha, id, source)", value="", key="audit_search")
        sources = sorted(list(set([s.get("source", "") for s in snaps_all if s.get("source", "")])))
        src_filter = st.multiselect("Filtrar por source", options=sources, default=[], key="audit_src_filter")

        def _match(s):
            blob = f"{s.get('id','')} {s.get('start','')} {s.get('end','')} {s.get('source','')}".lower()
            if q.strip() and q.strip().lower() not in blob:
                return False
            if src_filter and s.get("source", "") not in src_filter:
                return False
            return True

        snaps_f = [s for s in snaps_all if _match(s)]
        if not snaps_f:
            st.warning("No hay resultados con esos filtros.")
            return

        rows = []
        for s in snaps_f:
            rows.append({
                "id": s.get("id"),
                "start": s.get("start"),
                "end": s.get("end"),
                "source": s.get("source"),
                "created_utc": s.get("created_utc"),
                "size_kb": round((s.get("size_bytes") or 0) / 1024, 2)
            })
        df_table = pd.DataFrame(rows)
        st.dataframe(df_table, use_container_width=True, hide_index=True)

        st.markdown("### Acciones")
        pick_opts = [r["id"] for r in rows]
        pick = st.selectbox("Selecciona snapshot del listado:", options=pick_opts, key="audit_pick")

        a1, a2, a3 = st.columns([1.2, 1.2, 1.2])

        with a1:
            if st.button("Cargar este snapshot", use_container_width=True):
                df_snap = load_snapshot_df(pick)
                if df_snap.empty:
                    st.error("No pude cargar ese snapshot (vacío/corrupto).")
                else:
                    st.session_state.view_mode = "SNAPSHOT"
                    st.session_state.snapshot_id = pick
                    st.session_state.snapshot_df = df_snap
                    st.rerun()

        with a2:
            fpath = os.path.join(SNAP_DIR, pick)
            if os.path.exists(fpath):
                st.download_button(
                    "Descargar CSV",
                    data=_read_bytes(fpath),
                    file_name=pick,
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.button("Descargar CSV", disabled=True, use_container_width=True)

        with a3:
            if is_admin():
                del_ok = st.checkbox("Confirmo borrado", key="audit_del_ok_2")
                if st.button("Borrar (admin)", use_container_width=True, disabled=not del_ok):
                    ok = delete_snapshot(pick)
                    if ok:
                        if st.session_state.snapshot_id == pick:
                            st.session_state.view_mode = "LIVE"
                            st.session_state.snapshot_id = None
                            st.session_state.snapshot_df = None
                        st.success("✅ Borrado.")
                        st.rerun()
                    else:
                        st.error("No pude borrar.")
            else:
                st.button("Borrar (admin)", disabled=True, use_container_width=True)


# =========================
# 10) MAIN RENDER
# =========================
try:
    df_live = get_data_no_cache()

    df_sheet = df_live
    if st.session_state.view_mode == "SNAPSHOT" and isinstance(st.session_state.snapshot_df, pd.DataFrame):
        if not st.session_state.snapshot_df.empty:
            df_sheet = st.session_state.snapshot_df

    if not df_sheet.empty:
        if st.session_state.page == "main":
            prices_dict = get_ticker_prices(df_sheet["Pair"].tolist())
            ticker_html = "".join([
                f'<div class="ticker-item"><span style="color:#787b86; font-weight:500;">{k}</span> <span class="ticker-val">{v:.4f}</span></div>'
                for k, v in prices_dict.items() if v is not None
            ])
            st.markdown(
                f'<div class="ticker-wrap"><div class="ticker-move">{ticker_html + ticker_html}</div></div>',
                unsafe_allow_html=True
            )

            top_p = df_sheet.sort_values(by="Prob_Num", ascending=False).iloc[0]
            clr_edge = "#089981" if "LONG" in str(top_p["Bias"]).upper() else "#f23645"

            st.markdown(
                f'''<div style="background: #0a0a0a; border: 1px solid #1a1c22; padding: 35px; border-radius: 6px; border-left: 6px solid {clr_edge}; margin: 25px 0;">
                <h2 style="margin:0; font-size:48px; color:#ffffff;">{top_p["Pair"]} <span style="font-size:34px; color:{clr_edge};">| {top_p["Bias"]} | {top_p["Prob_Final"]}</span></h2>
                </div>''',
                unsafe_allow_html=True
            )

            tab_bias, tab_intraday, tab_vault = st.tabs([
                "MONITOR SWING SEMANAL G8",
                "MONITOR INTRADAY",
                "HAWKISH CAPITAL LIVE TRADES"
            ])

            with tab_bias:
                sub_monitor, sub_audit = st.tabs(["MONITOR", "AUDITORÍA"])

                with sub_monitor:
                    if st.session_state.view_mode == "SNAPSHOT" and st.session_state.snapshot_id:
                        st.caption("VIEW MODE: SNAPSHOT")
                    else:
                        st.caption("VIEW MODE: SEMANA ACTUAL (LIVE)")

                    cols = st.columns(4)
                    for i, r in df_sheet.iterrows():
                        with cols[i % 4]:
                            clr = "#f23645" if "SHORT" in str(r["Bias"]).upper() else "#089981"
                            st.markdown(
                                f'<div class="card-container" style="border-top: 2px solid {clr};">'
                                f'<p class="card-pair">{r["Pair"]}</p>'
                                f'<div class="card-bias" style="color:{clr};">{r["Bias"]}</div>'
                                f'<p class="card-conv">CONVICTION: <b>{r["Prob_Final"]}</b></p>'
                                f"</div>",
                                unsafe_allow_html=True
                            )
                            if st.button("Details", key=f"det_{r['Pair']}", use_container_width=True):
                                st.session_state.selected_pair = r["Pair"]
                                st.session_state.page = "details"
                                st.rerun()

                with sub_audit:
                    render_auditoria_panel(df_live)

            with tab_intraday:
                render_intraday_dashboard()

            with tab_vault:
                render_abraxa_hawkish_tab()

        else:
            render_pair_details(st.session_state.selected_pair, df_sheet)

    else:
        st.warning("No pude cargar data LIVE del Sheet (vacío o error).")

except Exception as e:
    st.error(f"Sync error: {e}")

# Global refresh: mantén, pero ya NO rompe la gráfica porque la cacheamos 1h
st_autorefresh(interval=30000, key="global_refresh")
