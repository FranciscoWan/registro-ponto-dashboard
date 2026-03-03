import streamlit as st
import extra_streamlit_components as stx


class AuthService:

    @staticmethod
    def init_cookie_manager():
        if "cookie_manager" not in st.session_state:
            st.session_state["cookie_manager"] = stx.CookieManager(
                key="global_cookie_manager"
            )
        return st.session_state["cookie_manager"]

    @classmethod
    def salvar_token(cls, token):
        cm = cls.init_cookie_manager()
        cm.set("auth_token", token)

    @classmethod
    def carregar_token(cls):
        cm = cls.init_cookie_manager()
        return cm.get("auth_token")

    @classmethod
    def limpar_token(cls):
        cm = cls.init_cookie_manager()
        cm.delete("auth_token")