"""Tela 'Lista de Protesto' — visualização das remessas geradas."""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao
from src.utils.marca import AZUL_ESCURO
from src.utils.estilo import card_kpi, COR_AZUL, COR_VERDE, COR_LARANJA
from src.utils.permissoes import pode_editar
from src.utils.exclusao_com_senha import confirmar_exclusao_com_senha
from src.servicos.protesto_remessas import excluir_remessa_protesto


def renderizar(usuario):
    st.markdown(
        f"<h1 style='color:{AZUL_ESCURO};margin-bottom:4px;'>📋 Lista de Protesto</h1>",
        unsafe_allow_html=True,
    )
    st.caption("Remessas geradas (Passo 3) e clientes em protesto.")
    st.markdown("---")

    conn = obter_conexao()

    try:
        remessas = conn.execute(
            "SELECT id, mes_referencia, nome_arquivo_gerado, total_clientes, "
            "total_titulos, valor_total, criado_em "
            "FROM remessa_protesto "
            "ORDER BY criado_em DESC;"
        ).fetchall()
    except Exception:
        remessas = []

    # Cards de resumo
    n_remessas = len(remessas)
    n_clientes = sum(r["total_clientes"] for r in remessas)
    valor_total = sum(r["valor_total"] for r in remessas)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(card_kpi(
            "Remessas", f"{n_remessas:,}", "geradas", COR_AZUL, "📦"
        ), unsafe_allow_html=True)
    with c2:
        st.markdown(card_kpi(
            "Clientes", f"{n_clientes:,}", "em protesto", COR_LARANJA, "👥"
        ), unsafe_allow_html=True)
    with c3:
        st.markdown(card_kpi(
            "Valor total", f"R$ {valor_total:,.2f}", "em protesto", COR_VERDE, "💰"
        ), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    if not remessas:
        st.info(
            "📭 **Ainda não há remessas registradas.**\n\n"
            "Para criar a primeira, vá em **📤 Protestar** → Passo 3, e clique em "
            "**💾 Salvar remessa no sistema**."
        )
        return

    permite_excluir = pode_editar(usuario)

    st.markdown(
        f"<h3 style='color:{AZUL_ESCURO};margin-bottom:8px;'>📦 Remessas</h3>",
        unsafe_allow_html=True,
    )

    for r in remessas:
        with st.expander(
            f"📦 {r['mes_referencia']} — "
            f"{r['total_clientes']} clientes · "
            f"R$ {r['valor_total']:,.2f}"
        ):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.write(f"**Arquivo:** `{r['nome_arquivo_gerado']}`")
                st.write(f"**Criado em:** {r['criado_em']}")
                st.write(f"**Total de títulos:** {r['total_titulos']}")
            with col_btn:
                if permite_excluir:
                    confirmar_exclusao_com_senha(
                        usuario_logado=usuario,
                        chave=f"del_remessa_{r['id']}",
                        descricao_item=f"Remessa {r['mes_referencia']}",
                        on_confirmar=lambda rid=r['id']: excluir_remessa_protesto(rid),
                    )

            # Listar clientes da remessa
            try:
                titulos = conn.execute(
                    """
                    SELECT c.nome, c.cod_parceiro, t.nro_unico, t.empresa, t.valor
                    FROM titulo_protesto t
                    JOIN cliente_protesto c ON c.id = t.cliente_id
                    WHERE t.remessa_id = ?
                    ORDER BY c.nome, t.empresa;
                    """,
                    (r['id'],)
                ).fetchall()
            except Exception:
                titulos = []

            if titulos:
                st.markdown("**Títulos da remessa:**")
                ultimo_cliente = None
                for t in titulos:
                    if t['nome'] != ultimo_cliente:
                        st.markdown(
                            f"&nbsp;&nbsp;**{t['nome']}** "
                            f"<span style='color:#999;font-size:11px;'>"
                            f"Parc {t['cod_parceiro']}</span>",
                            unsafe_allow_html=True,
                        )
                        ultimo_cliente = t['nome']
                    st.caption(
                        f"  &nbsp;&nbsp;&nbsp;&nbsp;• {t['empresa']} · "
                        f"{t['nro_unico']} · R$ {t['valor']:,.2f}"
                    )
