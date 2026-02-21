import pandas as pd
import requests
import streamlit as st
import yfinance as yf

def get_real_vix():
    """Bypass total: Extrae el VIX en tiempo real absoluto"""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1m&range=1d"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        return float(data['chart']['result'][0]['meta']['regularMarketPrice'])
    except:
        try:
            return float(yf.Ticker("^VIX").fast_info['last_price'])
        except: return 20.40

@st.cache_data(ttl=2) # Bajamos a 2 segundos para máxima precisión
def get_market_drivers():
    # Diccionario de tickers institucionales
    tickers = {
        'DXY': 'DX-Y.NYB', 
        'GOLD': 'GC=F', 
        'SILVER': 'SI=F', 
        'US10Y': '^TNX', 
        'ZQ': 'ZQ=F'
    }
    
    market_dict = {}
    
    try:
        # Usamos el objeto Ticker individual con fast_info (Latencia < 1s)
        for key, symbol in tickers.items():
            t = yf.Ticker(symbol)
            # Acceso directo al precio de red sin procesar tablas
            market_dict[key] = float(t.fast_info['last_price'])
        
        # VIX Directo
        market_dict['VIX'] = get_real_vix()
        
        # Delta ZQ (Necesario para sentimiento de tasas)
        t_zq = yf.Ticker(tickers['ZQ'])
        history = t_zq.history(period="1d", interval="1m")
        if len(history) > 1:
            market_dict['DELTA_ZQ'] = float(history['Close'].iloc[-1] - history['Close'].iloc[-2])
        else:
            market_dict['DELTA_ZQ'] = 0.0
            
        return market_dict
    except:
        # Failsafe con valores neutros para no romper la UI
        return {'DXY': 104.20, 'GOLD': 2030.50, 'SILVER': 22.80, 'US10Y': 4.25, 'VIX': 18.50, 'DELTA_ZQ': 0.0}