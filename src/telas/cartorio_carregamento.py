"""Tela Cartório › Carregamento (upload do relatório do cartório)."""
from __future__ import annotations

from time import time

import streamlit as st

from src.banco.conexao import obter_conexao
from src.servicos.parser_cartorio import ler_relatorio_cartorio
from src.servicos.carregamento_cartorio import (
    processar_relatorio_cartorio,
    excluir_upload_cartorio,
)
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, COR_AZUL, COR_VERDE, COR_VERMELHO, COR_LARANJA
from src.utils.permissoes import pode_editar
from src.utils.exclusao_com_senha import confirmar_exclusao_com_senha


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>"
        f"⚖️ Cartório — Carregamento</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Carregue o relatório XLSX do cartório com a relação de títulos "
        "protestados. O sistema atualiza o status dos clientes automaticamente."
    )

    if not pode_editar(usuario):
        st.error("🔒 Seu perfil não permite carregar relatórios. "
                 "Você pode visualizar nas próximas seções.")
    else:
        _renderizar_uploader(usuario)

    st.markdown("---")
    _renderizar_uploads_anteriores(usuario)


def _renderizar_uploader(usuario):
    arquivo = st.file_uploader(
        "Selecione o arquivo do cartório (.xlsx)",
        type=["xlsx"],
        key=st.session_state.get("cartorio_uploader_key", "cart_uploader_v1"),
    )

    # Mensagem persistente do último processamento
    msg = st.session_state.pop("cartorio_msg_resultado", None)
    if msg:
        if msg["tipo"] == "sucesso":
            st.success(msg["texto"])
        elif msg["tipo"] == "aviso":
            st.warning(msg["texto"])
        else:
            st.error(msg["texto"])

    if arquivo is None:
        return

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button(
        "▶️ Processar arquivo do cartório",
        type="primary",
        use_container_width=False,
        key="btn_proc_cart",
    ):
        try:
            relatorio = ler_relatorio_cartorio(arquivo.read())
            resultado = processar_relatorio_cartorio(
                relatorio=relatorio,
                nome_arquivo=arquivo.name,
                usuario_id=usuario.id,
            )
            st.session_state["cartorio_msg_resultado"] = {
                "tipo": "sucesso",
                "texto": (
                    f"✅ Relatório processado!\n\n"
                    f"- Linhas no arquivo: **{relatorio.total_linhas}**\n"
                    f"- Clientes novos: **{resultado['clientes_criados']}**\n"
                    f"- Clientes atualizados: **{resultado['clientes_atualizados']}**\n"
                    f"- Clientes em PROTESTADO: **{resultado['clientes_protestados']}**\n"
                    f"- Clientes que PAGARAM (cancelamento): **{resultado['clientes_pagos']}**\n\n"
                    f"Veja em **👥 Clientes** e **📁 Arquivados**."
                ),
            }
            # Limpar uploader
            st.session_state["cartorio_uploader_key"] = f"cart_uploader_{int(time())}"
            st.rerun()
        except Exception as e:
            st.error(f"❌ Erro ao processar: {e}")
            st.exception(e)


def _renderizar_uploads_anteriores(usuario):
    conn = obter_conexao()
    try:
        uploads = conn.execute(
            "SELECT id, nome_arquivo, total_linhas, total_clientes, "
            "total_cancelados, criado_em "
            "FROM upload_cartorio ORDER BY criado_em DESC;"
        ).fetchall()
    except Exception:
        uploads = []

    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>"
        f"📂 Carregamentos anteriores</h3>",
        unsafe_allow_html=True,
    )

    if not uploads:
        st.info("📭 Nenhum carregamento de cartório registrado ainda.")
        return

    permite_excluir = pode_editar(usuario)

    for u in uploads:
        with st.expander(
            f"📄 {u['nome_arquivo']} · "
            f"{u['total_linhas']} título(s) · "
            f"{u['total_cancelados']} cancelado(s) · "
            f"{u['criado_em'][:16]}"
        ):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.write(f"**Arquivo:** `{u['nome_arquivo']}`")
                st.write(f"**Carregado em:** {u['criado_em']}")
                st.write(f"**Total de títulos:** {u['total_linhas']}")
                st.write(f"**Clientes únicos:** {u['total_clientes']}")
                st.write(f"**Cancelados:** {u['total_cancelados']}")
            with col_btn:
                if permite_excluir:
                    confirmar_exclusao_com_senha(
                        usuario_logado=usuario,
                        chave=f"del_cart_{u['id']}",
                        descricao_item=f"Carregamento {u['nome_arquivo']}",
                        on_confirmar=lambda uid=u['id']: excluir_upload_cartorio(uid),
                    )
