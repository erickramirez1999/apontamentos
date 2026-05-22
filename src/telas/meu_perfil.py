"""
Tela Meu Perfil — usuário pode trocar a própria senha e o próprio nome.
"""
from __future__ import annotations

import streamlit as st

from src.banco import repo_usuario


def renderizar_meu_perfil(usuario):
    st.title("👤 Meu Perfil")
    st.caption("Suas informações e configurações de conta.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Nome**")
        st.write(usuario.nome)
    with col2:
        st.markdown("**E-mail**")
        st.write(usuario.email)

    from src.utils.traducoes import traduzir_perfil
    st.markdown(f"**Perfil:** {traduzir_perfil(usuario.perfil.value)}")
    if usuario.ultimo_login:
        st.markdown(f"**Último login:** {usuario.ultimo_login}")

    st.markdown("---")

    # ============================================================
    # ALTERAR NOME
    # ============================================================
    with st.expander("✏️ Alterar nome"):
        with st.form("alterar_nome"):
            novo_nome = st.text_input("Novo nome", value=usuario.nome)
            salvar = st.form_submit_button("Salvar", type="primary")
            if salvar:
                try:
                    repo_usuario.alterar_nome(usuario.id, novo_nome)
                    atualizado = repo_usuario.buscar_por_id(usuario.id)
                    st.session_state["usuario_atual"] = atualizado
                    st.success("✓ Nome alterado.")
                    st.rerun()
                except ValueError as e:
                    st.error(f"❌ {e}")

    # ============================================================
    # ALTERAR SENHA
    # ============================================================
    with st.expander("🔐 Alterar senha"):
        with st.form("alterar_senha"):
            senha_atual = st.text_input("Senha atual", type="password")
            nova = st.text_input("Nova senha (mín. 8)", type="password")
            confirma = st.text_input("Confirme a nova senha", type="password")
            salvar = st.form_submit_button("Trocar senha", type="primary")
            if salvar:
                if not repo_usuario.verificar_senha(
                    senha_atual,
                    _hash_atual(usuario.id),
                ):
                    st.error("❌ Senha atual incorreta.")
                elif nova != confirma:
                    st.error("❌ As senhas não conferem.")
                else:
                    try:
                        repo_usuario.alterar_senha(usuario.id, nova,
                                                   deve_trocar_no_proximo_login=False)
                        st.success("✓ Senha alterada com sucesso.")
                    except ValueError as e:
                        st.error(f"❌ {e}")


def _hash_atual(usuario_id: int) -> str:
    """Lê o hash atual da senha (pra confirmar a senha antes da troca)."""
    from src.banco.conexao import obter_conexao
    cur = obter_conexao().execute(
        "SELECT senha_hash FROM usuario WHERE id = ?;", (usuario_id,)
    )
    row = cur.fetchone()
    return row["senha_hash"] if row else ""
