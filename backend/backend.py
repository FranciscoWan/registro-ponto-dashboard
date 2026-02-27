# backend.py
import requests
from datetime import datetime, timedelta
from collections import defaultdict


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
            raise Exception("Login inválido")

        self.token = resp.json().get("token")

        if not self.token:
            raise Exception("Token não encontrado")

        return self.token

    def buscar_marcas(self, ano: int, mes: int):
        if not self.token:
            raise Exception("Token inválido, faça login primeiro.")
        inicio = datetime(ano, mes, 1).strftime("%Y-%m-%d")
        fim = datetime(ano, mes + 1, 1) - timedelta(days=1) if mes < 12 else datetime(ano+1, 1, 1) - timedelta(days=1)
        fim = fim.strftime("%Y-%m-%d")
        url = f"https://apiweb.registroponto.com.br/api/v1/employee-day-events?DateGte={inicio}&DateLte={fim}"
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
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
                python_day = api_day - 1  # Python: 0=segunda
                carga_por_dia[python_day] = total_dia

        return carga_por_dia

class HorasTrabalhadas:
    carga_por_dia = {
        0: timedelta(hours=9),
        1: timedelta(hours=9),
        2: timedelta(hours=9),
        3: timedelta(hours=9),
        4: timedelta(hours=8),
    }

    carga_semanal = sum(carga_por_dia.values(), timedelta())
    carga_mensal = carga_semanal * 4

    def __init__(self, dados):
        self.dados = dados
        self.horas_por_semana = defaultdict(timedelta)
        self.calcular()

    @staticmethod
    def formatar_timedelta(td: timedelta):
        total_segundos = int(td.total_seconds())
        sinal = "-" if total_segundos < 0 else ""
        total_segundos = abs(total_segundos)
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        return f"{sinal}{horas:02d}:{minutos:02d}:{segundos:02d}"

    def calcular(self):
        for dia in self.dados:
            clockings = dia.get("clockings", [])
            requests_dia = dia.get("requests", [])
            data_obj = datetime.strptime(dia["date"], "%d/%m/%Y")
            dia_do_mes = data_obj.day
            semana = min(((dia_do_mes - 1) // 7) + 1, 4)
            total_dia = timedelta()
            weekday = data_obj.weekday()
            if weekday not in self.carga_por_dia:
                continue
            if clockings:
                horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
                horarios.sort()
                for i in range(0, len(horarios), 2):
                    if i+1 < len(horarios):
                        total_dia += horarios[i+1] - horarios[i]
                self.horas_por_semana[semana] += total_dia
            elif requests_dia:
                self.horas_por_semana[semana] += self.carga_por_dia[weekday]

    def resumo_semanal(self):
        resumo = {}

        horas_semana_atual = self.horas_por_semana.copy()
        resumo_dia = self.resumo_diario()

        if resumo_dia:
            hoje = datetime.now().date()

            for dia in self.dados:
                data_obj = datetime.strptime(dia["date"], "%d/%m/%Y").date()

                if data_obj == hoje:
                    dia_do_mes = data_obj.day
                    semana_atual = min(((dia_do_mes - 1) // 7) + 1, 4)

                    weekday = data_obj.weekday()

                    if weekday in self.carga_por_dia:
                        clockings = dia.get("clockings", [])
                        horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
                        horarios.sort()

                        total_dia_fechado = timedelta()

                        for i in range(0, len(horarios) - 1, 2):
                            total_dia_fechado += horarios[i + 1] - horarios[i]

                        horas_semana_atual[semana_atual] -= total_dia_fechado
                        horas_semana_atual[semana_atual] += resumo_dia["trabalhado"]
        for semana in range(1, 5):
            total = horas_semana_atual.get(semana, timedelta())
            saldo = total - self.carga_semanal

            status = (
                "🟢 Extra"
                if saldo > timedelta()
                else "🔴 Déficit"
                if saldo < timedelta()
                else "⚪ Exato"
            )

            resumo[semana] = {
                "total": total,
                "saldo": saldo,
                "status": status
            }

        return resumo

    def resumo_mensal(self):
        total_mensal = sum(self.horas_por_semana.values(), timedelta())

        resumo_dia = self.resumo_diario()

        if resumo_dia:
            hoje = datetime.now().date()

            for dia in self.dados:
                data_obj = datetime.strptime(dia["date"], "%d/%m/%Y").date()

                if data_obj == hoje:
                    weekday = data_obj.weekday()

                    if weekday in self.carga_por_dia:
                        carga_dia = self.carga_por_dia[weekday]

                        clockings = dia.get("clockings", [])
                        horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
                        horarios.sort()

                        total_dia_fechado = timedelta()

                        for i in range(0, len(horarios) - 1, 2):
                            total_dia_fechado += horarios[i + 1] - horarios[i]

                        total_mensal -= total_dia_fechado
                        total_mensal += resumo_dia["trabalhado"]

        saldo_mensal = total_mensal - self.carga_mensal

        status_mensal = (
            "🟢 Horas extras no mês"
            if saldo_mensal > timedelta()
            else "🔴 Horas faltantes"
            if saldo_mensal < timedelta()
            else "⚪ Mês fechado exato"
        )

        return {
            "total": total_mensal,
            "esperado": self.carga_mensal,
            "saldo": saldo_mensal,
            "status": status_mensal
        }
    
    def resumo_diario(self):
        hoje = datetime.now().date()
        total_dia = timedelta()
        carga_dia = timedelta()

        for dia in self.dados:
            data_obj = datetime.strptime(dia["date"], "%d/%m/%Y").date()

            if data_obj != hoje:
                continue

            weekday = data_obj.weekday()

            if weekday not in self.carga_por_dia:
                return None

            carga_dia = self.carga_por_dia[weekday]

            clockings = dia.get("clockings", [])
            horarios = [datetime.fromisoformat(c["date"]) for c in clockings]
            horarios.sort()

            # pares fechados
            for i in range(0, len(horarios) - 1, 2):
                total_dia += horarios[i + 1] - horarios[i]

            # ponto aberto (ímpar)
            if len(horarios) % 2 != 0:
                ultima_entrada = horarios[-1]
                total_dia += datetime.now() - ultima_entrada

            tempo_restante = carga_dia - total_dia

            return {
                "trabalhado": total_dia,
                "esperado": carga_dia,
                "restante": tempo_restante
            }

        return None