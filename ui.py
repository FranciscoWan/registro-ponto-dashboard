import streamlit as st
from backend import PontoAPI, HorasTrabalhadas
from datetime import datetime
import plotly.graph_objects as go

class AppUI:

    def run(self):
        st.set_page_config(page_title="Controle de Horas", layout="wide")
        st.title("Controle de Horas Trabalhadas")

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

        self.render_dashboard(ano, mes)

    def render_dashboard(self, ano, mes):
        try:
            api = PontoAPI()
            api.login()
            dados = api.buscar_marcas(ano, mes)

            horas = HorasTrabalhadas(dados)

            self.render_metricas(horas)
            self.render_grafico(horas)
            self.render_fechamento(horas)

        except Exception as e:
            st.error(str(e))

    def render_metricas(self, horas):
        st.subheader("Resumo Semanal")

        for semana, info in horas.resumo_semanal().items():
            st.metric(
                label=f"Semana {semana}",
                value=HorasTrabalhadas.formatar_timedelta(info["total"]),
                delta=HorasTrabalhadas.formatar_timedelta(info["saldo"])
            )

    def render_grafico(self, horas):
        semanas = list(range(1, 5))

        total_semana = [
            horas.horas_por_semana.get(s, 0).total_seconds() / 3600
            for s in semanas
        ]

        carga_semanal = [
            HorasTrabalhadas.carga_semanal.total_seconds() / 3600
            for _ in semanas
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=semanas,
            y=total_semana,
            mode='lines+markers',
            name='Horas Trabalhadas'
        ))

        fig.add_trace(go.Scatter(
            x=semanas,
            y=carga_semanal,
            mode='lines+markers',
            name='Carga Esperada',
            line=dict(dash='dash')
        ))

        fig.update_layout(
            title='Horas Trabalhadas vs Carga Esperada',
            xaxis_title='Semana',
            yaxis_title='Horas'
        )

        st.plotly_chart(fig, use_container_width=True)

    def render_fechamento(self, horas):
        st.markdown("### Fechamento Mensal")

        resumo = horas.resumo_mensal()

        st.write(f"**Total Trabalhado:** {HorasTrabalhadas.formatar_timedelta(resumo['total'])}")
        st.write(f"**Total Esperado:** {HorasTrabalhadas.formatar_timedelta(resumo['esperado'])}")
        st.write(f"**Saldo Mensal:** {HorasTrabalhadas.formatar_timedelta(resumo['saldo'])}")