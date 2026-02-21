import streamlit as st
import asyncio
from telethon import TelegramClient
import os
import json # Importamos para leer los accesos específicos

# Credenciales G8 ELITE
API_ID = 20879464
API_HASH = '9f7455ec162aa0a39af1f7e97b9e7d9d'

async def get_live_telegram_feed():
    client = TelegramClient('horus_final_auth', API_ID, API_HASH)
    trades = []
    try:
        await client.connect()
        entity = None
        async for dialog in client.iter_dialogs():
            if 'Abraxa Trades' in dialog.name:
                entity = dialog.entity
                break
        
        if entity:
            async for message in client.iter_messages(entity, limit=15):
                trade_data = {
                    "text": message.text if message.text else "",
                    "date": message.date.strftime("%H:%M | %d %b"),
                    "photo": None
                }
                if message.photo:
                    if not os.path.exists("temp_media"): os.makedirs("temp_media")
                    path = await message.download_media(file=f"temp_media/live_{message.id}.jpg")
                    trade_data["photo"] = path
                trades.append(trade_data)
        await client.disconnect()
    except Exception as e:
        return [{"text": f"Error de conexión: {str(e)}", "date": "", "photo": None}]
    return trades

def render_abraxa_hawkish_tab():
    # --- CARGAR ACCESOS EXCLUSIVOS DESDE JSON ---
    try:
        with open('trades_access.json', 'r') as f:
            trade_users = json.load(f)
    except FileNotFoundError:
        st.error("⚠️ Error Crítico: No se encuentra 'trades_access.json'.")
        return

    # --- CAPA DE SEGURIDAD G8 (VAULT) ---
    if "abraxa_vault_auth" not in st.session_state:
        st.session_state.abraxa_vault_auth = False

    if not st.session_state.abraxa_vault_auth:
        st.markdown("### 🔒 VAULT: OPERATIVA HAWKISH FUND")
        with st.form("vault_login"):
            # Ahora el sistema valida contra los PINs del JSON
            pin = st.text_input("PIN DE ACCESO OPERATIVO:", type="password")
            submit = st.form_submit_button("DESBLOQUEAR TERMINAL", use_container_width=True)
            
            if submit:
                # Comprobamos si el PIN existe en los valores del archivo
                if pin in trade_users.values(): 
                    st.session_state.abraxa_vault_auth = True
                    st.rerun()
                else:
                    st.error("PIN INVÁLIDO. Acceso denegado.")
        return 

    # --- CONTENIDO PROTEGIDO (MODO ESPEJO) ---
    st.markdown("### Abraxa Ai - Hawkish Capital")
    
    # Navegación interna
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("TELEGRAM FEED", use_container_width=True):
            st.session_state.abraxa_sub = "telegram"
    with col2:
        if st.button("JOURNAL G8", use_container_width=True):
            st.session_state.abraxa_sub = "journal"
    with col3:
        if st.button("🔒 CERRAR VAULT", use_container_width=True):
            st.session_state.abraxa_vault_auth = False
            st.rerun()

    if "abraxa_sub" not in st.session_state: st.session_state.abraxa_sub = "telegram"

    st.markdown("---")

    if st.session_state.abraxa_sub == "telegram":
        with st.spinner("Sincronizando espejo con Abraxa Trades..."):
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            feed = loop.run_until_complete(get_live_telegram_feed())

        if feed:
            for post in feed:
                with st.container(border=True):
                    st.caption(f"{post['date']}")
                    if post["photo"]:
                        st.image(post["photo"], width=300)
                    if post["text"]:
                        st.write(post["text"])
        else:
            st.warning("No se detectaron mensajes en el canal.")
    
    elif st.session_state.abraxa_sub == "journal":
        st.subheader("Performance Journal")
        st.info("Modo espejo activo: Los datos son volátiles.")