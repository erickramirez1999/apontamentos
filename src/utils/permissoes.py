"""
Helpers centralizados de permissões — LLE Protestos.

Regras:
- ADMIN (Gestão): pode TUDO (aprovar usuários, alterar permissões, excluir).
- OPERADOR: pode editar (uploads, geração de planilhas, alteração de status).
- DIRETORIA: só visualiza.
- FINANCEIRO: só visualiza.
"""
from __future__ import annotations
from src.modelos.tipos import PerfilUsuario


def eh_admin(usuario) -> bool:
    return usuario.perfil == PerfilUsuario.ADMIN


def eh_apenas_visualizacao(usuario) -> bool:
    return usuario.perfil in (PerfilUsuario.DIRETORIA, PerfilUsuario.FINANCEIRO)


def pode_editar(usuario) -> bool:
    """Pode alterar dados. DIRETORIA e FINANCEIRO não podem."""
    return usuario.perfil in (PerfilUsuario.ADMIN, PerfilUsuario.OPERADOR)


def pode_gerenciar_usuarios(usuario) -> bool:
    """Só ADMIN gerencia (cadastrar, aprovar, recusar, inativar, redefinir senha)."""
    return usuario.perfil == PerfilUsuario.ADMIN


def pode_visualizar_admin(usuario) -> bool:
    """Acesso à área administrativa de visualização (ver lista de usuários)."""
    return usuario.perfil in (PerfilUsuario.ADMIN, PerfilUsuario.DIRETORIA)


def pode_alterar_parametros(usuario) -> bool:
    return usuario.perfil == PerfilUsuario.ADMIN
