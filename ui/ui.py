import streamlit as st
from backend.backend import PontoAPI, HorasTrabalhadas
from datetime import datetime
from auth.auth_service import AuthService


class AppUI:

    def run(self):
        st.set_page_config(page_title="Controle de Horas", layout="wide")
        self.apply_responsive_styles()

        config = AuthService.carregar_config()

        if "auth" not in st.session_state:
            st.session_state["auth"] = config

        if st.session_state["auth"]:
            self.render_app()
        else:
            self.render_login()

    # ==============================
    # APP PRINCIPAL (após login)
    # ==============================
    def render_app(self):

        st.title("Controle de Horas Trabalhadas")

        # Sidebar somente logado
        ano = st.sidebar.number_input(
            "Ano",
            min_value=2000,
            max_value=2100,
            value=datetime.now().year
        )

        mes = st.sidebar.selectbox(
            "Mês",
            list(range(1, 13)),
            index=datetime.now().month - 1
        )

        if st.sidebar.button("Sair"):
            AuthService.limpar_config()
            st.session_state["auth"] = None
            st.rerun()

        self.render_dashboard(ano, mes)

    # ==============================
    # RESPONSIVIDADE
    # ==============================
    def apply_responsive_styles(self):
        st.markdown("""
        <style>

        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        
        h1 {
            font-size: 30px !important;
            text-align: center;
        }

        h2 {
            font-size: 24px !important;
        }

        h3 {
            font-size: 22px !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 32px !important;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 18px !important;
        }

        @media (max-width: 768px) {

            html, body {
                font-size: 14px !important;
            }

            h1 {
                font-size: 22px !important;
                text-align: center;
            }

            h2 {
                font-size: 18px !important;
                text-align: center;
            }

            h3 {
                font-size: 16px !important;
                text-align: center;
            }

            div[data-testid="stMetricValue"] {
                font-size: 18px !important;
            }

            div[data-testid="stMetricLabel"] {
                font-size: 13px !important;
            }

            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

        }

        </style>
        """, unsafe_allow_html=True)

    # ==============================
    # LOGIN
    # ==============================
    def render_login(self):

        st.title("Login")

        col1, col2, col3 = st.columns([1,2,1])

        with col2:
            with st.form("login_form"):
                login = st.text_input("Login")
                password = st.text_input("Senha", type="password")
                submit = st.form_submit_button("Entrar")

                if submit:
                    try:
                        api = PontoAPI(login, password)
                        api.login()

                        AuthService.salvar_config(login, password)
                        st.session_state["auth"] = {
                            "login": login,
                            "password": password
                        }

                        st.rerun()

                    except Exception:
                        st.error("Login inválido")

    # ==============================
    # DASHBOARD
    # ==============================
    def render_dashboard(self, ano, mes):

        try:
            auth = st.session_state["auth"]

            api = PontoAPI(auth["login"], auth["password"])
            api.login()

            dados = api.buscar_marcas(ano, mes)
            carga_por_dia = api.buscar_carga_horaria()

            
            horas = HorasTrabalhadas(dados, carga_por_dia, ano, mes)

            self.render_resumo_diario(horas)
            self.render_metricas(horas)
            self.render_fechamento(horas)

        except Exception as e:
            st.error(str(e))

    # ==============================
    # RESUMO SEMANAL
    # ==============================
    def render_metricas(self, horas):

        st.subheader("Resumo Semanal")

        resumo = horas.resumo_semanal()
        cols = st.columns(len(resumo))

        for i, (semana, info) in enumerate(resumo.items()):
            cols[i].metric(
                label=f"Semana {semana-1}",
                value=HorasTrabalhadas.formatar_timedelta(info["total"]),
                delta=HorasTrabalhadas.formatar_timedelta(info["saldo"])
            )

    # ==============================
    # FECHAMENTO MENSAL
    # ==============================
    def render_fechamento(self, horas):

        st.markdown("### Fechamento Mensal")

        resumo = horas.resumo_mensal()
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Total Trabalhado",
            HorasTrabalhadas.formatar_timedelta(resumo["total"])
        )

        col2.metric(
            "Total Esperado",
            HorasTrabalhadas.formatar_timedelta(resumo["esperado"])
        )

        col3.metric(
            "Saldo Mensal",
            HorasTrabalhadas.formatar_timedelta(resumo["saldo"])
        )

    # ==============================
    # RESUMO DIÁRIO
    # ==============================
    def render_resumo_diario(self, horas):

        resumo = horas.resumo_diario()

        if not resumo:
            return

        st.markdown("## Resumo do Dia")

        trabalhado = resumo["trabalhado"]
        esperado = resumo["esperado"]
        restante = resumo["restante"]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Trabalhado Hoje",
            HorasTrabalhadas.formatar_timedelta(trabalhado)
        )

        col2.metric(
            "Carga de Hoje",
            HorasTrabalhadas.formatar_timedelta(esperado)
        )

        col3.metric(
            "Tempo Restante",
            HorasTrabalhadas.formatar_timedelta(restante)
        )

        progresso = 0.0
        if esperado.total_seconds() > 0:
            progresso = trabalhado.total_seconds() / esperado.total_seconds()

        progresso_visual = min(max(progresso, 0), 1)

        st.markdown("### Progresso Diário")
        st.progress(progresso_visual)
        st.caption(f"{round(progresso * 100, 1)}% da carga diária cumprida")