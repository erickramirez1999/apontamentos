"""
Tela administrativa de Usuários.

Permite ao ADMIN e DIRETORIA:
  - Aprovar / recusar usuários pendentes
  - Alterar perfil (cargo) de usuários
  - Inativar / reativar usuários
  - Revogar aprovação
  - Redefinir senha (gera senha temporária)
"""
from __future__ import annotations

import secrets
import string

import streamlit as st

from src.banco import repo_usuario
from src.modelos.tipos import PerfilUsuario
from src.utils.traducoes import traduzir_perfil


def renderizar_usuarios(usuario_logado):
    st.title("👥 Usuários")
    st.caption("Gestão de cadastros, aprovações e perfis.")

    tab_aprov, tab_ativos, tab_inativos = st.tabs([
        "⏳ Pendentes", "✅ Ativos", "🚫 Inativos"
    ])

    # ============================================================
    # PENDENTES
    # ============================================================
    with tab_aprov:
        pendentes = [u for u in repo_usuario.listar_todos() if not u.aprovado and u.ativo]
        if not pendentes:
            st.success("✓ Nenhum usuário pendente de aprovação.")
        else:
            for u in pendentes:
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 2, 2])
                    with col1:
                        st.markdown(f"**{u.nome}**")
                        st.caption(u.email)
                        st.caption(f"Chave: `{u.chave_aprovacao}`")
                    with col2:
                        st.caption(f"Cadastrado em: {u.criado_em}")
                    with col3:
                        if st.button("✓ Aprovar", key=f"apr_{u.id}", type="primary"):
                            repo_usuario.aprovar_usuario(u.id)
                            st.success(f"✓ {u.nome} aprovado.")
                            st.rerun()
                        if st.button("✕ Recusar", key=f"rec_{u.id}"):
                            repo_usuario.recusar_usuario(u.id)
                            st.warning(f"Usuário {u.nome} recusado.")
                            st.rerun()

    # ============================================================
    # ATIVOS
    # ============================================================
    with tab_ativos:
        ativos = [u for u in repo_usuario.listar_todos(apenas_ativos=True) if u.aprovado]
        if not ativos:
            st.info("Nenhum usuário ativo cadastrado ainda.")
        else:
            for u in ativos:
                _render_card_usuario(u, usuario_logado)

    # ============================================================
    # INATIVOS
    # ============================================================
    with tab_inativos:
        inativos = [u for u in repo_usuario.listar_todos() if not u.ativo]
        if not inativos:
            st.info("Nenhum usuário inativo.")
        else:
            for u in inativos:
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{u.nome}** — _{traduzir_perfil(u.perfil.value)}_")
                        st.caption(u.email)
                    with col2:
                        if st.button("Reativar", key=f"reat_{u.id}"):
                            repo_usuario.reativar_usuario(u.id)
                            st.success(f"✓ {u.nome} reativado.")
                            st.rerun()


def _render_card_usuario(u, usuario_logado):
    """Card de um usuário ativo com ações: alterar perfil, redefinir senha, inativar."""
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 2, 2])
        with col1:
            st.markdown(f"**{u.nome}**")
            st.caption(u.email)
        with col2:
            st.markdown(f"_{traduzir_perfil(u.perfil.value)}_")
            if u.ultimo_login:
                st.caption(f"Último login: {u.ultimo_login}")

        with col3:
            with st.popover("Ações", use_container_width=True):
                # Alterar perfil
                opcoes = [p for p in PerfilUsuario]
                idx_atual = opcoes.index(u.perfil)
                novo_perfil = st.selectbox(
                    "Perfil",
                    opcoes,
                    index=idx_atual,
                    format_func=lambda p: traduzir_perfil(p.value),
                    key=f"perfil_{u.id}",
                )
                if novo_perfil != u.perfil:
                    if st.button("Salvar perfil", key=f"save_perfil_{u.id}",
                                 type="primary"):
                        try:
                            repo_usuario.alterar_perfil(u.id, novo_perfil)
                            st.success("✓ Perfil alterado.")
                            st.rerun()
                        except ValueError as e:
                            st.error(f"❌ {e}")

                st.markdown("---")
                # Redefinir senha
                if st.button("🔐 Redefinir senha", key=f"reset_{u.id}"):
                    nova_temp = _gerar_senha_temporaria()
                    repo_usuario.alterar_senha(u.id, nova_temp,
                                               deve_trocar_no_proximo_login=True)
                    st.success(f"Senha temporária: **{nova_temp}**")
                    st.caption("Avise o usuário. Ele será forçado a trocar no próximo login.")

                st.markdown("---")
                # Revogar aprovação
                if st.button("⏳ Revogar aprovação", key=f"revog_{u.id}"):
                    repo_usuario.revogar_aprovacao(u.id)
                    st.warning(f"Aprovação de {u.nome} revogada.")
                    st.rerun()
                # Inativar
                if u.id != usuario_logado.id:
                    if st.button("🚫 Inativar", key=f"inat_{u.id}"):
                        repo_usuario.inativar_usuario(u.id)
                        st.warning(f"{u.nome} inativado.")
                        st.rerun()


def _gerar_senha_temporaria(tamanho: int = 10) -> str:
    """Gera senha temporária legível (sem ambiguidades)."""
    alfabeto = string.ascii_uppercase.replace("O", "").replace("I", "") + "23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(tamanho))
