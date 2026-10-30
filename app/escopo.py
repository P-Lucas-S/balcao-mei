"""
Escopo de visibilidade por perfil — uma regra só, num lugar só.

Antes deste módulo havia **duas regras diferentes com o mesmo nome**:

  - `atendimentos.py` e `solicitacoes.py`: equipe = quem tem `supervisor_id`
    apontando para o supervisor (`current_user.atendentes`)
  - `relatorios/routes.py` (4 cópias) e `main.py`: equipe = **todos** os
    usuários de perfil atendente, vinculados ou não

O resultado era um supervisor vendo no relatório gente que não via na lista
de atendimentos. Consolidado em 2026-08-29: **equipe é exclusivamente
`supervisor_id`**, em toda tela.

O **fallback legado** — supervisor sem equipe vinculada via TUDO — foi
removido no mesmo ciclo. Ele existia para não deixar um supervisor com a
tela vazia, mas transformava "ainda não configurei a equipe" em "vejo o
sistema inteiro", que é o oposto do que a regra pretende.

Um supervisor sem equipe continua vendo **os próprios registros**. Isso não
é resquício do fallback: é o invariante de que ninguém deixa de enxergar o
próprio trabalho. Na prática, para quem não atende no balcão, a tela fica
vazia — que era o efeito pretendido.
"""
from flask_login import current_user


def ids_da_equipe(usuario=None):
    """Ids de usuário que `usuario` enxerga.

    Devolve `None` para administrador — `None` significa **sem filtro**, e
    não "lista vazia". Quem chama precisa distinguir os dois casos.

        administrador  ->  None            (tudo)
        supervisor     ->  [equipe] + [ele]
        atendente      ->  [ele]
    """
    u = usuario or current_user
    perfil = u.perfil.nome

    if perfil == 'administrador':
        return None
    if perfil == 'supervisor':
        return [a.id for a in u.atendentes] + [u.id]
    return [u.id]


def no_escopo(registro, usuario=None):
    """Se `registro` está no escopo de `usuario` — registro a registro.

    Espelha `filtrar_por_escopo` exatamente. Vale para qualquer registro com
    `id_usuario`; `exclusao_pendente`, quando existe, some para não-admin na
    listagem e portanto também não é acessível por eles.
    """
    u = usuario or current_user

    if u.perfil.nome == 'administrador':
        return True
    if getattr(registro, 'exclusao_pendente', False):
        return False

    return registro.id_usuario in ids_da_equipe(u)


def filtrar_por_escopo(query, coluna_usuario, usuario=None):
    """Aplica o escopo a uma query. Administrador passa sem filtro."""
    ids = ids_da_equipe(usuario)
    if ids is None:
        return query
    return query.filter(coluna_usuario.in_(ids))
