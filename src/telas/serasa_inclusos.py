"""Tela Serasa › Inclusos."""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, COR_AZUL
from src.utils.permissoes import pode_editar
from src.utils.exclusao_com_senha import confirmar_exclusao_com_senha
from src.servicos.serasa_eventos import excluir_evento_serasa


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📥 Serasa — Inclusos</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Arquivos de Inclusão enviados ao Serasa.")
    _renderizar_lista(tipo="INCLUSAO", usuario=usuario)


def _renderizar_lista(tipo: str, usuario):
    conn = obter_conexao()

    try:
        eventos = conn.execute(
            "SELECT id, data_arquivo, sequencial, nome_arquivo, total_clientes, criado_em "
            "FROM evento_serasa WHERE tipo = ? "
            "ORDER BY data_arquivo DESC, sequencial DESC;",
            (tipo,)
        ).fetchall()
    except Exception:
        eventos = []

    if not eventos:
        st.info(
            "📭 **Nenhum arquivo de inclusão carregado ainda.**\n\n"
            "Vá em **📤 Carregamento** para subir os arquivos do Serasa."
        )
        return

    total_arquivos = len(eventos)
    total_titulos = sum(e["total_clientes"] for e in eventos)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(card_kpi(
            "Arquivos", f"{total_arquivos:,}", "carregados", COR_AZUL, "📥"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Títulos", f"{total_titulos:,}", "registrados", COR_AZUL, "📋"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    by_day = {}
    for e in eventos:
        d = e["data_arquivo"]
        by_day.setdefault(d, []).append(e)

    permite_excluir = pode_editar(usuario)

    for dia in sorted(by_day.keys(), reverse=True):
        st.markdown(
            f"<h4 style='color:{AZUL_ESCURO}; margin-bottom:6px;'>📆 {dia}</h4>",
            unsafe_allow_html=True,
        )
        for e in by_day[dia]:
            with st.expander(f"#{e['sequencial']} · {e['total_clientes']} título(s)"):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.write(f"**Arquivo:** `{e['nome_arquivo']}`")
                    st.write(f"**Carregado em:** {e['criado_em']}")
                with col_btn:
                    if permite_excluir:
                        confirmar_exclusao_com_senha(
                            usuario_logado=usuario,
                            chave=f"del_serasa_inc_{e['id']}",
                            descricao_item=f"Inclusão #{e['sequencial']}",
                            on_confirmar=lambda eid=e['id']: excluir_evento_serasa(eid),
                        )

                try:
                    titulos = conn.execute(
                        "SELECT cnpj_cpf, nome FROM titulo_serasa "
                        "WHERE evento_id = ? ORDER BY nome;",
                        (e['id'],)
                    ).fetchall()
                except Exception:
                    titulos = []

                if titulos:
                    st.markdown("**Clientes:**")
                    for t in titulos:
                        cnpj = t["cnpj_cpf"] or "—"
                        st.caption(f"  • {t['nome']} (CNPJ/CPF: {cnpj})")
