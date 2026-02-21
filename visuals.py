import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

def render_chart(df_h, color_main):
    # Limpieza absoluta de datos
    df_h = df_h.sort_values(by=df_h.columns[0], ascending=True).dropna()
    y_min, y_max = df_h['Close'].min(), df_h['Close'].max()
    margin = (y_max - y_min) * 0.1
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_h.iloc[:, 0], y=df_h['Close'], 
        mode='lines', line=dict(color=color_main, width=2),
        fill='tozeroy', fillcolor=f'rgba(0, 255, 0, 0.10)' if color_main == "#00FF00" else f'rgba(255, 51, 51, 0.10)'
    ))
    fig.update_layout(
        template="plotly_dark", paper_bgcolor='black', plot_bgcolor='black', height=500, margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(showgrid=False, fixedrange=True),
        yaxis=dict(side='right', gridcolor='#1a1a1a', tickformat=".4f", range=[y_min - margin, y_max + margin], fixedrange=True),
        showlegend=False
    )
    return st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})

def render_heatmap(df):
    # Versión corregida sin el error de 'aspect'
    fig = px.density_heatmap(
        df, x="Bias", y="Pair", z="Prob_Num",
        color_continuous_scale='RdYlGn', text_auto=".1f", template="plotly_dark"
    )
    fig.update_layout(
        paper_bgcolor='black', plot_bgcolor='black', margin=dict(t=30, l=10, r=10, b=10),
        xaxis=dict(side="top", title=None), yaxis=dict(title=None), coloraxis_showscale=False
    )
    return st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True})