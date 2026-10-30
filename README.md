# Balcão MEI

Sistema web para registrar e conduzir atendimentos presenciais a microempreendedores: cadastro de pessoas e empresas, atendimento guiado por serviço, solicitações com fluxo de status, requerimentos em PDF, relatórios e painéis de análise.

> **Demonstração.** A organização ("Central do Empreendedor"), a cidade padrão e todos os dados são fictícios. Nome, organização, cidade e área do mapa são configuráveis por variável de ambiente (veja abaixo).

---

## Funcionalidades

- **Cadastro de pessoas** — pessoa física, jurídica e MEI, com validação de CPF/CNPJ, detecção de duplicatas e mesclagem de cadastros
- **Atendimento guiado** — o atendente seleciona o cliente e marca os serviços prestados (emissão de DAS, abertura de MEI, consulta cadastral etc.), filtrados pelo perfil (MEI / não MEI), com atalho para o portal oficial de cada serviço
- **Solicitações** — credenciamentos e requerimentos com fluxo de status e alerta de solicitações paradas
- **Requerimento em PDF** — documento gerado com os dados do cadastro já preenchidos
- **Relatórios** — atendimentos por período, desempenho por atendente e painel executivo, exportáveis em PDF e Excel
- **Análise** — jornada do empreendedor, mapa de calor da demanda por bairro, perfil dos atendidos e potencial de reativação
- **Integrações** — preenchimento de endereço pelo CEP (Correios) e de dados de empresa pelo CNPJ (Receita Federal)
- **Controle de acesso** — perfis administrador, supervisor e atendente, com escopo por equipe e log de auditoria
- **Privacidade** — página de política de privacidade (LGPD) e exclusão de cadastros sob aprovação

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | Python + Flask |
| Banco de dados | PostgreSQL + SQLAlchemy |
| Autenticação | Flask-Login, Flask-WTF (CSRF), Flask-Limiter |
| Templates | Jinja2 |
| PDF / Excel | ReportLab / openpyxl |
| Frontend | CSS próprio + Chart.js + Leaflet |
| Testes | pytest (SQLite em memória) |

---

## Como rodar

Pré-requisitos: Python 3.10+ e PostgreSQL 14+.

```bash
git clone <url-do-repositorio>
cd balcao-mei

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # preencha SECRET_KEY e as credenciais do banco
psql -U postgres -c "CREATE DATABASE sistema_solicitacoes;"
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

python -X utf8 scripts/gerar_dados_ficticios.py   # popula o banco com dados de demonstração
python run.py
```

Acesse `http://localhost:5000`.

### Testes

```bash
pytest
```

---

## Personalização

| Variável | Padrão | Uso |
|---|---|---|
| `APP_NOME` | `Balcão MEI` | Nome exibido na interface e nos documentos |
| `ORG_NOME` | `Central do Empreendedor` | Organização (substantivo feminino: os textos usam "a") |
| `MUNICIPIO` / `UF` | `Curitiba` / `PR` | Endereços, requerimentos e geocodificação dos bairros |
| `BAIRROS` | lista de bairros de Curitiba | Bairros do cadastro, separados por `;` |
| `SEDE_LAT` / `SEDE_LNG` | centro de Curitiba | Marcador da sede no mapa de demanda |
| `MAPA_BBOX` | área de Curitiba | `sul,oeste,norte,leste` para buscar os polígonos dos bairros |

A logo fica em `app/static/img/logo.png` e a paleta em `app/static/css/base.css`.

---

## Estrutura

```
app/
├── __init__.py        # application factory
├── marca.py           # identidade da instância (nome, cidade, mapa)
├── models.py          # modelos SQLAlchemy
├── escopo.py          # regras de visibilidade por equipe
├── routes/            # blueprints: atendimentos, pessoas, solicitações, fichas, relatórios, análise…
├── static/            # CSS, logo, manifest
└── templates/         # Jinja2
migrations/            # scripts SQL incrementais
scripts/               # geração de dados fictícios
tests/                 # suíte pytest
```
