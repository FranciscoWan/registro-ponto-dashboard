# backend.py
import requests
from datetime import datetime, timedelta
from collections import defaultdict
import config

class PontoAPI:
    def __init__(self):
        self.token = None

    def login(self):
        url = "https://apiweb.registroponto.com.br/api/v1/auth/login"
        payload = {"login": config.LOGIN, "password": config.PASSWORD}
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"Erro ao logar: {resp.text}")
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
        for semana in range(1, 5):
            total = self.horas_por_semana.get(semana, timedelta())
            saldo = total - self.carga_semanal
            status = "🟢 Extra" if saldo > timedelta() else "🔴 Déficit" if saldo < timedelta() else "⚪ Exato"
            resumo[semana] = {
                "total": total,
                "saldo": saldo,
                "status": status
            }
        return resumo

    def resumo_mensal(self):
        total_mensal = sum(self.horas_por_semana.values(), timedelta())
        saldo_mensal = total_mensal - self.carga_mensal
        status_mensal = "🟢 Horas extras no mês" if saldo_mensal > timedelta() else "🔴 Horas faltantes" if saldo_mensal < timedelta() else "⚪ Mês fechado exato"
        return {
            "total": total_mensal,
            "esperado": self.carga_mensal,
            "saldo": saldo_mensal,
            "status": status_mensal
        }