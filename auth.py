import streamlit as st
import json

def load_users():
    """Carga usuarios desde users.json."""
    try:
        with open("users.json", "r") as f:
            data = json.load(f)
            # Soporta formato viejo: {"user":"pwd"} y nuevo: {"user":{"password":"pwd","role":"x"}}
            normalized = {}
            for u, v in (data or {}).items():
                if isinstance(v, dict):
                    normalized[u] = {
                        "password": str(v.get("password", "")),
                        "role": str(v.get("role", "user"))
                    }
                else:
                    normalized[u] = {"password": str(v), "role": "user"}
            return normalized
    except FileNotFoundError:
        st.error("Error crítico: Archivo de usuarios no encontrado.")
        return {}
    except Exception as e:
        st.error(f"Error crítico cargando usuarios: {e}")
        return {}

def check_password():
    """Retorna True si el usuario ingresó credenciales válidas."""

    def password_entered():
        authorized_users = load_users()
        user = st.session_state.get("username", "")
        pwd = st.session_state.get("password", "")

        if user in authorized_users and authorized_users[user]["password"] == pwd:
            st.session_state["password_correct"] = True
            st.session_state["current_operator"] = user
            st.session_state["current_role"] = authorized_users[user].get("role", "user")

            # limpiamos inputs, pero dejamos operador/rol
            if "password" in st.session_state: del st.session_state["password"]
            if "username" in st.session_state: del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct"):
        return True

    # Login UI
    st.markdown("<h1 style='text-align: center;'>ABRAXA</h1>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input("ID de Operador", on_change=password_entered, key="username")
        st.text_input("Código de Acceso", type="password", on_change=password_entered, key="password")
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("Acceso denegado: Credenciales inválidas")

    return False