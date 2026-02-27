import json
import os

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".controle_horas", "config.json")


class AuthService:

    @staticmethod
    def salvar_config(login, password):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump({
                "login": login,
                "password": password
            }, f)

    @staticmethod
    def carregar_config():
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        return None

    @staticmethod
    def limpar_config():
        if os.path.exists(CONFIG_PATH):
            os.remove(CONFIG_PATH)