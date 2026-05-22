"""Tela 'Arquivados' — clientes que já pagaram."""
from __future__ import annotations

import streamlit as st

from src.banco.conexao import obter_conexao


def renderizar(usuario):
    st.title("📁 Arquivados")
    st.caption("Clientes que já pagaram. Indicador BAIXADO mostra se foi dado baixa no cartório.")
    st.markdown("---")

    conn = obter_conexao()

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
            "Os clientes que tiverem status alterado para 'PAGO' aparecem aqui automaticamente."
        )
        return

    st.markdown(f"**{len(clientes)} cliente(s) arquivado(s).**")

    for c in clientes:
        baixado_emoji = "✅" if c['baixado'] else "⚠️"
        baixado_text = "BAIXADO" if c['baixado'] else "NÃO BAIXADO"

        with st.expander(f"{baixado_emoji} {c['nome']} — {baixado_text}"):
            st.write(f"**Parceiro:** {c['cod_parceiro']}")
            if c['cnpj_cpf']:
                st.write(f"**CNPJ/CPF:** {c['cnpj_cpf']}")
            st.write(f"**Arquivado em:** {c['atualizado_em']}")
