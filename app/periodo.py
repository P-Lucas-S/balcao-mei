"""Período padrão dos relatórios e análises."""
from datetime import date, timedelta

from flask import current_app


def inicio_padrao(hoje=None):
    """Primeiro dia do mês atual; na demonstração, os últimos 6 meses.

    Na demo pública os dados são fictícios e o mês corrente pode ter poucos
    dias, então um período mais longo mostra os painéis preenchidos.
    """
    hoje = hoje or date.today()
    if current_app.config.get('DEMO_MODE'):
        return (hoje - timedelta(days=182)).replace(day=1)
    return hoje.replace(day=1)
