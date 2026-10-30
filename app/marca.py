"""
Identidade da instância (nome, organização, cidade e mapa).

Tudo é configurável por variável de ambiente, para que o mesmo código
sirva a qualquer balcão de atendimento. Os valores padrão descrevem uma
instância de DEMONSTRAÇÃO, com organização e dados fictícios.

ORG_NOME deve ser um substantivo feminino ("a Central...") porque os
textos da interface usam o artigo "a".
"""
import os

APP_NOME  = os.environ.get('APP_NOME',  'Balcão MEI')
ORG_NOME  = os.environ.get('ORG_NOME',  'Central do Empreendedor')
MUNICIPIO = os.environ.get('MUNICIPIO', 'Curitiba')
UF        = os.environ.get('UF',        'PR')

CIDADE_UF        = f'{MUNICIPIO} - {UF}'
ORG_COMPLETO     = f'{ORG_NOME} de {MUNICIPIO}'
APP_NOME_UP      = APP_NOME.upper()
ORG_COMPLETO_UP  = ORG_COMPLETO.upper()

# Mapa de demanda: marcador da sede e área de busca dos polígonos de bairros
SEDE_LAT = float(os.environ.get('SEDE_LAT', '-25.4284'))
SEDE_LNG = float(os.environ.get('SEDE_LNG', '-49.2733'))
# (sul, oeste, norte, leste) — formato da Overpass API
MAPA_BBOX = os.environ.get('MAPA_BBOX', '-25.65,-49.39,-25.34,-49.18')

_BAIRROS_PADRAO = [
    'Água Verde', 'Alto da XV', 'Bacacheri', 'Bairro Alto', 'Batel',
    'Bigorrilho', 'Boa Vista', 'Boqueirão', 'Cabral', 'Cajuru',
    'Campo Comprido', 'Capão Raso', 'Centro', 'Cidade Industrial',
    'Fazendinha', 'Hauer', 'Jardim Botânico', 'Juvevê', 'Mercês',
    'Novo Mundo', 'Pinheirinho', 'Portão', 'Rebouças', 'Santa Felicidade',
    'Sítio Cercado', 'Tatuquara', 'Uberaba', 'Xaxim',
]
_bairros_env = os.environ.get('BAIRROS')
BAIRROS = ([b.strip() for b in _bairros_env.split(';') if b.strip()]
           if _bairros_env else _BAIRROS_PADRAO)
