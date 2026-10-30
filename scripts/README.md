# Scripts

## gerar_dados_ficticios.py

Popula o banco com dados de demonstração: cerca de 400 pessoas, 800 atendimentos, 250 solicitações, requerimentos e logs, distribuídos ao longo de 17 meses com sazonalidade. É idempotente: apaga os dados fictícios anteriores antes de gerar novos.

```bash
python -X utf8 scripts/gerar_dados_ficticios.py
```

## popular_bairros.py

Atribui bairros (da lista em `app/marca.py`) aos cadastros fictícios que estão sem bairro.

```bash
python scripts/popular_bairros.py
```
