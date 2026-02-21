# horus_brain.py
def get_execution_scores(df_1h, news_data):
    # 🔹 1. Environment Status (0-100)
    # Si el precio tiene muchas mechas y poco cuerpo = DIRTY
    env_score = 75  # Ejemplo: Cálculo basado en volatilidad actual
    status = "Clean" if env_score > 60 else "Dirty"

    # 🔹 2. Volatility State (ATR Ratio)
    # Detecta si el mercado está comprimido (listo para estallar)
    vol_state = "Compression" # o "Expansion"

    # 🔹 3. Narrative Pressure (Live Feed reestructurado)
    # En lugar de texto, devolvemos un nivel de presión
    narrative_pressure = "High" if len(news_data) > 5 else "Low"

    return {
        "env_status": status,
        "env_score": env_score,
        "vol_state": vol_state,
        "narrative_pressure": narrative_pressure,
        "alignment": "Aligned" # Oro vs USD Alignment
    }