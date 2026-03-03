# backend.py
import requests
from datetime import datetime, timedelta
from collections import defaultdict

from .calendar_function import info_mes


class PontoAPI:
    def __init__(self, login, password):
        self.login_user = login
        self.password_user = password
        self.token = None

    def login(self):
        url = "https://apiweb.registroponto.com.br/api/v1/auth/login"

        payload = {
            "login": self.login_user,
            "password": self.password_user
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        resp = requests.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            raise Exception(f"Erro API: {resp.status_code} - {resp.text}")

        if not self.token:
            raise Exception("Token não encontrado")

        return self.token

    def buscar_marcas(self, ano: int, mes: int):
        if not self.token:
            raise Exception("Token inválido, faça login primeiro.")

        inicio = datetime(ano, mes, 1).strftime("%Y-%m-%d")

        if mes < 12:
            fim = datetime(ano, mes + 1, 1) - timedelta(days=1)
        else:
            fim = datetime(ano + 1, 1, 1) - timedelta(days=1)

        fim = fim.strftime("%Y-%m-%d")

        url = f"https://apiweb.registroponto.com.br/api/v1/employee-day-events?DateGte={inicio}&DateLte={fim}"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            raise Exception(f"Erro ao buscar dados: {resp.text}")

        return resp.json()

    def buscar_carga_horaria(self):
        if not self.token:
            raise Exception("Token inválido, faça login primeiro.")

        url = "https://apiweb.registroponto.com.br/api/v1/workday"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json"
        }

        resp = requests.get(url, headers=headers)

        if resp.status_code != 200:
            raise Exception("Erro ao buscar carga horária")

        dados = resp.json()
        carga_por_dia = {}

        for periodo in dados.get("workedPeriods", []):
            start_day = periodo["startWeekDay"]
            end_day = periodo["endWeekDay"]

            total_dia = timedelta()

            for turno in periodo.get("times", []):
                inicio = datetime.strptime(turno["startTime"], "%H:%M:%S")
                fim = datetime.strptime(turno["endTime"], "%H:%M:%S")
                total_dia += (fim - inicio)

            for api_day in range(start_day, end_day + 1):
                python_day = api_day - 2  # ajuste API → Python (0=segunda)
                if 0 <= python_day <= 6:
                    carga_por_dia[python_day] = total_dia

        return carga_por_dia


class HorasTrabalhadas:
    def __init__(self, dados, carga_por_dia, ano, mes):
        self.dados = dados
        self.carga_por_dia = carga_por_dia
        self.ano = ano
        self.mes = mes

        self.horas_por_semana = defaultdict(timedelta)

        self.calendario_mes = info_mes(ano, mes)
        self.mapa_dia_semana = self._mapear_dias_para_semana()
        self.carga_semanal_real = self._calcular_carga_semanal_real()
        self.carga_mensal_real = sum(self.carga_semanal_real.values(), timedelta())

        self.calcular()

    # =============================
    # MAPEAMENTO DE DIAS
    # =============================
    def _mapear_dias_para_semana(self):
        mapa = {}

        for indice_semana, semana in enumerate(self.calendario_mes, start=1):
            for posicao_dia, dia in enumerate(semana):
                if dia == 0:
                    continue

                if posicao_dia in (5, 6):  # ignora sábado/domingo
                    continue

                mapa[dia] = indice_semana

        return mapa

    # =============================
    # CARGA ESPERADA REAL
    # =============================
    def _calcular_carga_semanal_real(self):
        carga_semanal = defaultdict(timedelta)

        for indice_semana, semana in enumerate(self.calendario_mes, start=1):
            for posicao_dia, dia in enumerate(semana):
                if dia == 0:
                    continue

                if posicao_dia in (5, 6):
                    continue

                if posicao_dia in self.carga_por_dia:
                    carga_semanal[indice_semana] += self.carga_por_dia[posicao_dia]

        return carga_semanal

    # =============================
    # CÁLCULO DAS HORAS
    # =============================
    def calcular(self):
        for dia in self.dados:
            clockings = dia.get("clockings", [])
            requests_dia = dia.get("requests", [])

            data_obj = datetime.strptime(dia["date"], "%d/%m/%Y")
            dia_do_mes = data_obj.day
            weekday = data_obj.weekday()

            # só considera dias úteis do mês
            if dia_do_mes not in self.mapa_dia_semana:
                continue

            if weekday not in self.carga_por_dia:
                continue

            semana = self.mapa_dia_semana[dia_do_mes]
            total_dia = timedelta()

            # ✔ CASO 1 — TEM MARCAÇÃO
            if clockings:
                horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
                horarios.sort()

                for i in range(0, len(horarios) - 1, 2):
                    total_dia += horarios[i + 1] - horarios[i]

                # ponto aberto
                if len(horarios) % 2 != 0:
                    total_dia += datetime.now() - horarios[-1]

                self.horas_por_semana[semana] += total_dia

            # ✔ CASO 2 — TEM REQUEST (atestado, abono etc.)
            elif requests_dia:
                self.horas_por_semana[semana] += self.carga_por_dia[weekday]

            # ✔ CASO 3 — DIA ÚTIL SEM CLOCKING E SEM REQUEST
            # NÃO SOMA NADA
            # (dispensa não deve gerar débito automático)

    # =============================
    # RESUMO SEMANAL
    # =============================
    def resumo_semanal(self):
        resumo = {}

        for semana in self.carga_semanal_real:
            total = self.horas_por_semana.get(semana, timedelta())
            esperado = self.carga_semanal_real[semana]
            saldo = total - esperado

            resumo[semana] = {
                "total": total,
                "esperado": esperado,
                "saldo": saldo
            }

        return resumo

    # =============================
    # RESUMO MENSAL
    # =============================
    def resumo_mensal(self):
        total_mensal = sum(self.horas_por_semana.values(), timedelta())
        saldo_mensal = total_mensal - self.carga_mensal_real

        return {
            "total": total_mensal,
            "esperado": self.carga_mensal_real,
            "saldo": saldo_mensal
        }

    # =============================
    # RESUMO DIÁRIO (CORRIGIDO)
    # =============================
    def resumo_diario(self):
        hoje = datetime.now().date()

        for dia in self.dados:
            data_obj = datetime.strptime(dia["date"], "%d/%m/%Y").date()

            if data_obj != hoje:
                continue

            weekday = data_obj.weekday()

            if weekday not in self.carga_por_dia:
                return None

            clockings = dia.get("clockings", [])
            total_dia = timedelta()

            if clockings:
                horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
                horarios.sort()

                for i in range(0, len(horarios) - 1, 2):
                    total_dia += horarios[i + 1] - horarios[i]

                # ponto aberto
                if len(horarios) % 2 != 0:
                    total_dia += datetime.now() - horarios[-1]

            esperado = self.carga_por_dia[weekday]
            restante = esperado - total_dia

            return {
                "trabalhado": total_dia,
                "esperado": esperado,
                "restante": restante
            }

        return None

    # =============================
    # FORMATADOR
    # =============================
    @staticmethod
    def formatar_timedelta(td):
        total_segundos = int(td.total_seconds())
        sinal = "-" if total_segundos < 0 else ""
        total_segundos = abs(total_segundos)

        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60

        return f"{sinal}{horas:02d}:{minutos:02d}"