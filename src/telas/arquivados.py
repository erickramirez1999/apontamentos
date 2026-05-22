"""Tela 'Arquivados' — clientes que já pagaram. Permite marcar baixa."""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, COR_VERDE, COR_LARANJA
from src.utils.permissoes import pode_editar


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📁 Arquivados</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Clientes que já pagaram. Marque como BAIXADO depois de dar baixa no cartório."
    )

    conn = obter_conexao()

    # Processar ação de baixar/desbaixar (vem do botão)
    acao = st.session_state.pop("arq_acao", None)
    if acao:
        cliente_id, novo_baixado = acao
        try:
            conn.execute(
                "UPDATE cliente_protesto SET baixado = ?, "
                "atualizado_em = datetime('now') WHERE id = ?;",
                (novo_baixado, cliente_id)
            )
            st.session_state["arq_msg"] = (
                "sucesso",
                "✅ Marcado como BAIXADO." if novo_baixado else "↩️ Baixa removida."
            )
            st.rerun()
        except Exception as e:
            st.session_state["arq_msg"] = ("erro", f"❌ Erro: {e}")
            st.rerun()

    # Mensagem persistente
    msg = st.session_state.pop("arq_msg", None)
    if msg:
        tipo, texto = msg
        (st.success if tipo == "sucesso" else st.error)(texto)

    cur = conn.execute(
        "SELECT id, cod_parceiro, nome, cnpj_cpf, baixado, atualizado_em "
        "FROM cliente_protesto "
        "WHERE arquivado = 1 "
        "ORDER BY atualizado_em DESC;"
    )
    clientes = cur.fetchall()

    if not clientes:
        st.info(
            "📭 **Nenhum cliente arquivado ainda.**\n\n"
            "Os clientes que tiverem status alterado para 'PAGO' "
            "(via carregamento do cartório, por exemplo) aparecem aqui automaticamente."
        )
        return

    # KPIs
    total = len(clientes)
    baixados = sum(1 for c in clientes if c['baixado'])
    nao_baixados = total - baixados

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Total arquivados", f"{total:,}", "clientes pagos", AZUL_ESCURO, "📁"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Baixados", f"{baixados:,}", "baixa confirmada", COR_VERDE, "✅"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Pendentes de baixa", f"{nao_baixados:,}",
            "aguardando baixa no cartório", COR_LARANJA, "⚠️"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Filtro
    filtro = st.selectbox(
        "Mostrar:",
        ["Todos", "Apenas pendentes de baixa", "Apenas baixados"],
        index=0,
    )
    if filtro == "Apenas pendentes de baixa":
        clientes = [c for c in clientes if not c['baixado']]
    elif filtro == "Apenas baixados":
        clientes = [c for c in clientes if c['baixado']]

    if not clientes:
        st.caption("Nenhum cliente nessa categoria.")
        return

    permite_editar = pode_editar(usuario)

    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO}; margin-bottom:8px;'>"
        f"📋 {len(clientes)} cliente(s)</h3>",
        unsafe_allow_html=True,
    )

    for c in clientes:
        baixado_emoji = "✅" if c['baixado'] else "⚠️"
        baixado_text = "BAIXADO" if c['baixado'] else "NÃO BAIXADO"
        cor = COR_VERDE if c['baixado'] else COR_LARANJA

        # Card do cliente
        with st.container():
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(
                    f"<div style='background:#FFF; padding:12px 16px; border-radius:8px; "
                    f"box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:4px; "
                    f"border-left:4px solid {cor};'>"
                    f"<span style='font-size:15px; font-weight:600; color:{AZUL_ESCURO};'>"
                    f"{c['nome']}</span>"
                    f"<span style='background:{cor}; color:white; padding:2px 10px; "
                    f"border-radius:10px; font-size:11px; font-weight:600; margin-left:10px;'>"
                    f"{baixado_emoji} {baixado_text}</span><br>"
                    f"<span style='font-size:12px; color:#666;'>"
                    f"Parceiro <strong>{c['cod_parceiro'] or '—'}</strong> · "
                    f"{c['cnpj_cpf'] or '—'}"
                    f"</span></div>",
                    unsafe_allow_html=True,
                )

            with col_btn:
                if permite_editar:
                    if c['baixado']:
                        if st.button(
                            "↩️ Desfazer baixa",
                            key=f"undo_baix_{c['id']}",
                            use_container_width=True,
                        ):
                            st.session_state["arq_acao"] = (c['id'], 0)
                            st.rerun()
                    else:
                        if st.button(
                            "✅ Marcar como baixado",
                            key=f"baix_{c['id']}",
                            type="primary",
                            use_container_width=True,
                        ):
                            st.session_state["arq_acao"] = (c['id'], 1)
                            st.rerun()
