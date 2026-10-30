"""
popular_bairros.py
Atribui bairros aleatórios aos cadastros fictícios que não têm bairro.
Usa apenas registros com origem='dados_ficticios' ou sem bairro.

Uso:
    python scripts/popular_bairros.py
"""
import sys
import os
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db, marca
from app.models import Pessoa

BAIRROS = list(marca.BAIRROS)

# Pesos para simular distribuição desigual entre bairros
PESOS = [(i % 5) + 1 for i in range(len(BAIRROS))]

random.seed(42)

app = create_app()
with app.app_context():
    pessoas = Pessoa.query.filter(
        db.or_(Pessoa.bairro == None, Pessoa.bairro == '')
    ).all()

    print(f"Atualizando {len(pessoas)} cadastros sem bairro...")

    for p in pessoas:
        p.bairro = random.choices(BAIRROS, weights=PESOS)[0]

    db.session.commit()
    print(f"OK: {len(pessoas)} cadastros atualizados com bairros.")

    # Resumo por bairro
    from sqlalchemy import func
    rows = (
        db.session.query(Pessoa.bairro, func.count(Pessoa.id).label('total'))
        .filter(Pessoa.bairro != None)
        .group_by(Pessoa.bairro)
        .order_by(func.count(Pessoa.id).desc())
        .all()
    )
    print("\nDistribuição por bairro:")
    for r in rows:
        print(f"  {r.bairro}: {r.total}")
