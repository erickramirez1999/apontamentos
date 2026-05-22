"""
Componente reutilizável: confirmação de exclusão com senha.

Uso:
    confirmar_exclusao_com_senha(
        usuario_logado=usuario,
        chave="del_serasa_4547",
        descricao_item="Inclusão #4547",
        on_confirmar=lambda: excluir_evento_serasa(4547),
    )
"""
from __future__ import annotations
from typing import Callable

import streamlit as st


def confirmar_exclusao_com_senha(
    usuario_logado,
    chave: str,
    descricao_item: str,
    on_confirmar: Callable[[], None],
    label_botao: str = "🗑 Excluir",
):
    """
    Renderiza botão "Excluir" e, ao clicar, abre modal exigindo senha.
    
    Args:
        usuario_logado: objeto Usuario com .id e .email
        chave: string única no st.session_state pra identificar esse fluxo
        descricao_item: texto que vai aparecer no modal (ex: "Inclusão #4547")
        on_confirmar: callback chamada quando a senha for validada
        label_botao: texto do botão (default: "🗑 Excluir")
    
    Retorna True se a exclusão foi confirmada e executada nessa run.
    """
    from src.banco import repo_usuario

    if st.button(label_botao, key=f"btn_{chave}", use_container_width=True):
        st.session_state[chave] = True
        st.rerun()

    if not st.session_state.get(chave):
        return False

    st.markdown(
        f"<div style='background:#FFF0F0; border:1px solid #DC3545; "
        f"padding:14px; border-radius:8px; margin:8px 0;'>"
        f"<b>Confirmar exclusão de {descricao_item}?</b><br>"
        f"<small>Esta ação não pode ser desfeita. Digite sua senha para confirmar.</small>"
        f"</div>",
        unsafe_allow_html=True,
    )

    with st.form(key=f"form_{chave}"):
        senha = st.text_input("Sua senha", type="password", key=f"senha_{chave}")
        col_ok, col_cancel = st.columns(2)
        with col_ok:
            confirmar = st.form_submit_button(
                "Sim, excluir", type="primary", use_container_width=True
            )
        with col_cancel:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if confirmar:
            u_valid = repo_usuario.autenticar(usuario_logado.email, senha)
            if u_valid is None:
                st.error("❌ Senha incorreta.")
                return False
            try:
                on_confirmar()
                del st.session_state[chave]
                st.success(f"✓ {descricao_item} excluído com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Erro ao excluir: {e}")
                return False

        if cancelar:
            del st.session_state[chave]
            st.rerun()

    return False
