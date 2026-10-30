"""Migration: adiciona campos da ficha física de cadastro."""
from app import create_app, db
import sqlalchemy as sa

def upgrade():
    with db.engine.connect() as conn:
        conn.execute(sa.text("""
            ALTER TABLE pessoa
            ADD COLUMN IF NOT EXISTS rg VARCHAR(20),
            ADD COLUMN IF NOT EXISTS nivel_escolar VARCHAR(50),
            ADD COLUMN IF NOT EXISTS num_membros_familia INTEGER,
            ADD COLUMN IF NOT EXISTS renda_familiar VARCHAR(50),
            ADD COLUMN IF NOT EXISTS instagram VARCHAR(100),
            ADD COLUMN IF NOT EXISTS endereco_comercial TEXT,
            ADD COLUMN IF NOT EXISTS principais_produtos TEXT,
            ADD COLUMN IF NOT EXISTS faturamento_mensal VARCHAR(30),
            ADD COLUMN IF NOT EXISTS num_funcionarios INTEGER,
            ADD COLUMN IF NOT EXISTS observacoes_cadastro TEXT
        """))
        conn.commit()
    print("Migration concluída: campos da ficha física adicionados.")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        upgrade()
